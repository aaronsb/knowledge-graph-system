"""
Rate limiting and retry logic for AI provider API calls.

Implements exponential backoff with jitter for handling 429 rate limit errors
across multiple providers (OpenAI, Anthropic, Ollama).

Thread-safe implementation suitable for parallel ingestion workers.

**Per-Provider Concurrency Limits:**
- Ollama: 1 concurrent request (single GPU/CPU bottleneck)
- Anthropic: 4 concurrent requests (moderate API rate limits)
- OpenAI: 8 concurrent requests (higher API rate limits)
"""

import time
import random
import logging
import os
import threading
from typing import Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Per-provider concurrency semaphores (thread-safe)
_provider_semaphores = {}
_semaphore_lock = threading.Lock()


def get_provider_concurrency_limit(provider_name: str) -> int:
    """
    Get the concurrency limit for a specific provider.

    Configuration precedence (ADR-041):
    1. Database (ai_extraction_config.max_concurrent_requests)
    2. Environment variable ({PROVIDER}_MAX_CONCURRENT)
    3. Hardcoded defaults per provider

    Defaults based on provider characteristics:
    - ollama: 1 (single GPU/CPU bottleneck)
    - anthropic: 4 (moderate API rate limits)
    - openai: 8 (higher API rate limits)
    - mock: 100 (no real limits for testing)

    Args:
        provider_name: Provider name ('openai', 'anthropic', 'ollama', 'mock')

    Returns:
        Maximum concurrent requests allowed for this provider
    """
    provider = provider_name.lower()

    # Default concurrency limits per provider
    defaults = {
        'ollama': 1,      # Local GPU/CPU - serialize to avoid thrashing
        'anthropic': 4,   # Moderate API rate limits
        'openai': 8,      # Higher API rate limits
        'mock': 100,      # Testing - no real limits
    }

    default_limit = defaults.get(provider, 4)

    # Try to load from database first (ADR-041 pattern)
    try:
        from .age_client import AGEClient

        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT max_concurrent_requests
                    FROM kg_api.ai_extraction_config
                    WHERE provider = %s AND active = TRUE
                    LIMIT 1
                """, (provider,))

                row = cur.fetchone()
                if row and row[0] is not None:
                    limit = row[0]
                    logger.debug(
                        f"Provider '{provider}' concurrency limit: {limit} (from database)"
                    )
                    return limit
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.debug(f"Could not load concurrency limit from database for '{provider}': {e}")

    # Fall back to environment variable
    env_var = f"{provider.upper()}_MAX_CONCURRENT"
    env_value = os.getenv(env_var)

    if env_value is not None:
        limit = int(env_value)
        logger.debug(f"Provider '{provider}' concurrency limit: {limit} (from {env_var})")
    else:
        limit = default_limit
        logger.debug(f"Provider '{provider}' concurrency limit: {limit} (default)")

    # Safety checks: Enforce reasonable bounds (1-MAX_THREADS)
    # Configurable maximum to prevent resource exhaustion
    MAX_THREADS = int(os.getenv("MAX_CONCURRENT_THREADS", "32"))

    if limit is None or limit < 1:
        logger.warning(
            f"Provider '{provider}' concurrency limit not configured or invalid ({limit}). "
            f"Defaulting to 1 (serial processing) for safety. "
            f"Configure via database or {env_var} environment variable."
        )
        return 1

    if limit > MAX_THREADS:
        logger.warning(
            f"Provider '{provider}' concurrency limit ({limit}) exceeds maximum ({MAX_THREADS}). "
            f"Capping at {MAX_THREADS} to prevent resource exhaustion. "
            f"Configure MAX_CONCURRENT_THREADS to adjust this limit."
        )
        return MAX_THREADS

    return limit


def get_provider_max_retries(provider_name: str) -> int:
    """
    Get the max retry count for a specific provider.

    Configuration precedence (ADR-041):
    1. Database (ai_extraction_config.max_retries)
    2. Environment variable ({PROVIDER}_MAX_RETRIES)
    3. Hardcoded defaults per provider

    Defaults based on provider characteristics:
    - ollama: 3 (local, fewer retries needed)
    - anthropic: 8 (cloud API, more resilience)
    - openai: 8 (cloud API, more resilience)
    - mock: 0 (testing, no retries)

    Args:
        provider_name: Provider name ('openai', 'anthropic', 'ollama', 'mock')

    Returns:
        Maximum retry attempts for rate-limited requests
    """
    provider = provider_name.lower()

    # Default retry counts per provider
    defaults = {
        'ollama': 3,      # Local - fewer retries needed
        'anthropic': 8,   # Cloud API - more resilience
        'openai': 8,      # Cloud API - more resilience
        'mock': 0,        # Testing - no retries
    }

    default_retries = defaults.get(provider, 8)

    # Try to load from database first (ADR-041 pattern)
    try:
        from .age_client import AGEClient

        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT max_retries
                    FROM kg_api.ai_extraction_config
                    WHERE provider = %s AND active = TRUE
                    LIMIT 1
                """, (provider,))

                row = cur.fetchone()
                if row and row[0] is not None:
                    retries = row[0]
                    logger.debug(
                        f"Provider '{provider}' max_retries: {retries} (from database)"
                    )
                    return retries
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.debug(f"Could not load max_retries from database for '{provider}': {e}")

    # Fall back to environment variable
    env_var = f"{provider.upper()}_MAX_RETRIES"
    retries = int(os.getenv(env_var, default_retries))

    logger.debug(f"Provider '{provider}' max_retries: {retries} (env or default)")
    return retries


def get_provider_semaphore(provider_name: str) -> threading.Semaphore:
    """
    Get or create a semaphore for the given provider.

    Thread-safe singleton pattern - one semaphore per provider.

    Args:
        provider_name: Provider name ('openai', 'anthropic', 'ollama')

    Returns:
        Semaphore limiting concurrent requests for this provider
    """
    provider = provider_name.lower()

    with _semaphore_lock:
        if provider not in _provider_semaphores:
            limit = get_provider_concurrency_limit(provider)
            _provider_semaphores[provider] = threading.Semaphore(limit)
            logger.info(
                f"Created concurrency semaphore for provider '{provider}' "
                f"with limit={limit}"
            )

        return _provider_semaphores[provider]


class RateLimitError(Exception):
    """Raised when rate limit is exceeded and retries exhausted"""
    pass


def exponential_backoff_retry(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    catch_exceptions: tuple = None
):
    """
    Decorator that retries a function with exponential backoff on rate limit errors.

    Implements the industry-standard exponential backoff with jitter pattern:
    - Attempt 1: immediate
    - Attempt 2: ~1s delay
    - Attempt 3: ~2s delay
    - Attempt 4: ~4s delay
    - Attempt 5: ~8s delay
    - Attempt 6: ~16s delay

    Jitter (random ±20%) prevents "thundering herd" when multiple workers
    retry simultaneously.

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        jitter: Add random ±20% jitter to delays (default: True)
        catch_exceptions: Tuple of exception types to catch (auto-detects if None)

    Returns:
        Decorated function that retries on rate limit errors

    Example:
        @exponential_backoff_retry(max_retries=5)
        def call_api():
            return client.chat.completions.create(...)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Log recovery if we had previous failures
                    if attempt > 0:
                        logger.info(
                            f"Rate limit recovered after {attempt} retries "
                            f"(function: {func.__name__})"
                        )

                    return result

                except Exception as e:
                    last_exception = e

                    # Check if this is a rate limit error
                    is_rate_limit = _is_rate_limit_error(e, catch_exceptions)

                    if not is_rate_limit:
                        # Not a rate limit error, don't retry
                        raise

                    if attempt == max_retries:
                        # Final attempt failed
                        logger.error(
                            f"Rate limit retry exhausted after {max_retries} attempts "
                            f"(function: {func.__name__}): {e}"
                        )
                        raise RateLimitError(
                            f"Rate limit exceeded after {max_retries} retries: {e}"
                        ) from e

                    # Calculate backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)

                    # Add jitter (±20% randomization)
                    if jitter:
                        delay = delay * random.uniform(0.8, 1.2)

                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), "
                        f"backing off for {delay:.2f}s (function: {func.__name__}): {e}"
                    )

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise RateLimitError(
                f"Rate limit retry logic error (last exception: {last_exception})"
            )

        return wrapper
    return decorator


def _is_rate_limit_error(exception: Exception, catch_exceptions: Optional[tuple] = None) -> bool:
    """
    Detect if an exception is a rate limit error.

    Checks for:
    - HTTP 429 status code
    - Rate limit keywords in error message
    - Provider-specific rate limit exceptions

    Args:
        exception: The exception to check
        catch_exceptions: Optional tuple of exception types to catch

    Returns:
        True if this is a rate limit error that should trigger retry
    """
    # If explicit exception types provided, check those first
    if catch_exceptions and isinstance(exception, catch_exceptions):
        return True

    # Convert to string for message checking
    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()

    # Check for 429 status code (HTTP Too Many Requests)
    if '429' in error_str or '429' in error_type:
        return True

    # Check for rate limit keywords
    rate_limit_keywords = [
        'rate limit',
        'ratelimit',
        'too many requests',
        'quota exceeded',
        'requests per',
        'tokens per minute',
        'rpm exceeded',
        'tpm exceeded'
    ]

    for keyword in rate_limit_keywords:
        if keyword in error_str or keyword in error_type:
            return True

    # Check for provider-specific exception types
    # OpenAI SDK >= 1.0.0
    if 'ratelimiterror' in error_type:
        return True

    # Anthropic SDK
    if 'ratelimit' in error_type:
        return True

    # Ollama / HTTP requests
    if hasattr(exception, 'response'):
        status_code = getattr(exception.response, 'status_code', None)
        if status_code == 429:
            return True

    return False


def configure_provider_retries(provider_name: str, max_retries: int = 5):
    """
    Get retry configuration for a specific provider.

    Different providers may need different retry settings based on their
    rate limits and typical usage patterns.

    Args:
        provider_name: Name of the provider ('openai', 'anthropic', 'ollama')
        max_retries: Override max retries (default: 5)

    Returns:
        Dict with retry configuration parameters
    """
    configs = {
        'openai': {
            'max_retries': max_retries,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'jitter': True
        },
        'anthropic': {
            'max_retries': max_retries,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'jitter': True
        },
        'ollama': {
            # Local provider, unlikely to have rate limits
            # but might have resource constraints
            'max_retries': 3,
            'base_delay': 0.5,
            'max_delay': 10.0,
            'jitter': False
        }
    }

    return configs.get(provider_name.lower(), configs['openai'])
