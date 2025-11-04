"""
Vision Provider abstraction layer for image-to-prose conversion.

Supports multiple providers (OpenAI GPT-4o, Anthropic Claude, Ollama) with
configurable models for converting images to literal text descriptions.

Research Findings (ADR-057, Nov 2025):
- Primary: GPT-4o Vision (100% reliable, excellent literal descriptions)
- Alternate: Claude 3.5 Sonnet Vision (similar quality to GPT-4o)
- Optional: Ollama (Granite, LLaVA) - inconsistent quality, use only when cloud unavailable

See docs/research/vision-testing/ for comprehensive findings.

API Key Loading (ADR-031):
- First tries encrypted key store (system_api_keys table)
- Falls back to environment variables (.env or direct)
- Maintains backward compatibility
"""

import os
import logging
import base64
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from io import BytesIO

logger = logging.getLogger(__name__)


# Literal description prompt (validated in research, Nov 2025)
# See docs/research/vision-testing/FINDINGS.md
LITERAL_DESCRIPTION_PROMPT = """
Describe everything visible in this image literally and exhaustively.

Do NOT summarize or interpret. Do NOT provide analysis or conclusions.

Instead, describe:
- Every piece of text you see, word for word
- Every visual element (boxes, arrows, shapes, colors)
- The exact layout and positioning of elements
- Any diagrams, charts, or graphics in detail
- Relationships between elements (what connects to what, what's above/below)
- Any logos, branding, or page numbers

Be thorough and literal. If you see text, transcribe it exactly. If you see a box with an arrow pointing to another box, describe that precisely.
""".strip()


def _load_api_key(provider: str, explicit_key: Optional[str] = None, env_var: Optional[str] = None, service_token: Optional[str] = None) -> Optional[str]:
    """
    Load API key with fallback chain (ADR-031).

    Priority order:
    1. Explicit key provided as parameter
    2. Encrypted key from database (system_api_keys table) - requires service token
    3. Environment variable
    4. None (will raise error in provider __init__)

    Args:
        provider: Provider name ('openai', 'anthropic', etc.)
        explicit_key: API key passed explicitly to constructor
        env_var: Environment variable name (e.g., 'OPENAI_API_KEY')
        service_token: Internal service authorization token (for encrypted key access)

    Returns:
        API key if found, None otherwise
    """
    # 1. Explicit key takes precedence
    if explicit_key:
        logger.debug(f"Using explicit API key for {provider}")
        return explicit_key

    # 2. Try encrypted key store (requires service token)
    try:
        from .encrypted_keys import get_system_api_key
        from .age_client import AGEClient
        from .secrets import get_internal_key_service_secret

        try:
            client = AGEClient()
            conn = client.pool.getconn()
            try:
                # Load service token if not provided
                if service_token is None:
                    service_token = get_internal_key_service_secret()

                key = get_system_api_key(conn, provider, service_token)
                if key:
                    logger.debug(f"Loaded encrypted API key for {provider} from database")
                    return key
            finally:
                client.pool.putconn(conn)
        except ValueError as e:
            # ValueError is raised for missing/invalid token or missing key
            logger.debug(f"Could not load encrypted key for {provider}: {e}")
        except Exception as e:
            logger.debug(f"Could not load encrypted key for {provider}: {e}")
    except ImportError:
        logger.debug("Encrypted key store not available")

    # 3. Fall back to environment variable
    if env_var:
        key = os.getenv(env_var)
        if key:
            logger.debug(f"Loaded API key for {provider} from environment variable: {env_var}")
            return key

    logger.debug(f"No API key found for {provider}")
    return None


class VisionProvider(ABC):
    """Abstract base class for vision providers (image → text)"""

    @abstractmethod
    def describe_image(self, image_bytes: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert image to prose description.

        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            prompt: Description prompt (defaults to LITERAL_DESCRIPTION_PROMPT)

        Returns:
            Dict with:
            - 'text': The prose description
            - 'tokens': Token usage info (input_tokens, output_tokens, total_tokens)
            - 'model': Model name used
            - 'provider': Provider name
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name used for vision"""
        pass

    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate that the API key works"""
        pass

    @abstractmethod
    def list_available_models(self) -> list[str]:
        """List available vision models for this provider"""
        pass


class OpenAIVisionProvider(VisionProvider):
    """
    OpenAI GPT-4o Vision provider (PRIMARY - validated in research).

    Research shows:
    - 100% reliable (no random refusals)
    - Excellent literal descriptions (3,017 chars avg)
    - Fast (~5s per image)
    - Cost: ~$0.01/image

    See docs/research/vision-testing/FINDINGS.md
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        from openai import OpenAI

        # Load API key with fallback chain (ADR-031)
        self.api_key = _load_api_key("openai", api_key, "OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Either:\n"
                "  1. Configure via admin API: POST /admin/keys/openai\n"
                "  2. Set OPENAI_API_KEY environment variable\n"
                "  3. Add to .env file (development only)"
            )

        # Configure retry behavior
        from .rate_limiter import get_provider_max_retries
        max_retries = get_provider_max_retries("openai")

        self.client = OpenAI(
            api_key=self.api_key,
            max_retries=max_retries,
            timeout=120.0  # 2 minute timeout for vision requests
        )
        logger.info(f"OpenAI Vision client configured with max_retries={max_retries}")

        # Configurable model with default
        self.model = model or os.getenv("VISION_MODEL", "gpt-4o")

    def describe_image(self, image_bytes: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Describe image using GPT-4o Vision.

        Args:
            image_bytes: Raw image bytes
            prompt: Description prompt (defaults to LITERAL_DESCRIPTION_PROMPT)

        Returns:
            Dict with 'text', 'tokens', 'model', 'provider'
        """
        # Use literal prompt by default
        if prompt is None:
            prompt = LITERAL_DESCRIPTION_PROMPT

        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # Detect mime type (simplified - assumes JPEG if not PNG)
        if image_bytes.startswith(b'\x89PNG'):
            mime_type = 'image/png'
        else:
            mime_type = 'image/jpeg'

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1  # Low temperature for consistent literal descriptions
            )

            description = response.choices[0].message.content

            # Extract token usage
            usage = response.usage
            tokens = {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }

            logger.info(
                f"OpenAI Vision described image: {len(description)} chars, "
                f"{tokens['total_tokens']} tokens"
            )

            return {
                "text": description,
                "tokens": tokens,
                "model": self.model,
                "provider": "openai"
            }

        except Exception as e:
            logger.error(f"OpenAI Vision error: {e}")
            raise

    def get_provider_name(self) -> str:
        return "openai"

    def get_model_name(self) -> str:
        return self.model

    def validate_api_key(self) -> bool:
        """Validate API key by making a minimal API call"""
        try:
            # Simple test: describe a tiny 1x1 black pixel PNG
            test_image = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
            result = self.describe_image(test_image, "What color is this pixel?")
            return bool(result.get("text"))
        except Exception as e:
            logger.error(f"OpenAI Vision API key validation failed: {e}")
            return False

    def list_available_models(self) -> list[str]:
        """List available vision models"""
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]


class AnthropicVisionProvider(VisionProvider):
    """
    Anthropic Claude 3.5 Sonnet Vision provider (ALTERNATE).

    Similar quality to GPT-4o, slightly higher cost.
    Cost: ~$0.015/image, Speed: ~5s/image

    See docs/research/vision-testing/ (not tested yet, but expected similar quality).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        from anthropic import Anthropic

        # Load API key with fallback chain (ADR-031)
        self.api_key = _load_api_key("anthropic", api_key, "ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Either:\n"
                "  1. Configure via admin API: POST /admin/keys/anthropic\n"
                "  2. Set ANTHROPIC_API_KEY environment variable\n"
                "  3. Add to .env file (development only)"
            )

        # Configure retry behavior
        from .rate_limiter import get_provider_max_retries
        max_retries = get_provider_max_retries("anthropic")

        self.client = Anthropic(
            api_key=self.api_key,
            max_retries=max_retries,
            timeout=120.0
        )
        logger.info(f"Anthropic Vision client configured with max_retries={max_retries}")

        # Configurable model with default
        self.model = model or os.getenv("VISION_MODEL", "claude-3-5-sonnet-20241022")

    def describe_image(self, image_bytes: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Describe image using Claude Vision.

        Args:
            image_bytes: Raw image bytes
            prompt: Description prompt (defaults to LITERAL_DESCRIPTION_PROMPT)

        Returns:
            Dict with 'text', 'tokens', 'model', 'provider'
        """
        # Use literal prompt by default
        if prompt is None:
            prompt = LITERAL_DESCRIPTION_PROMPT

        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # Detect mime type
        if image_bytes.startswith(b'\x89PNG'):
            mime_type = 'image/png'
        else:
            mime_type = 'image/jpeg'

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.1,  # Low temperature for consistent literal descriptions
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": image_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            description = response.content[0].text

            # Extract token usage
            tokens = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }

            logger.info(
                f"Anthropic Vision described image: {len(description)} chars, "
                f"{tokens['total_tokens']} tokens"
            )

            return {
                "text": description,
                "tokens": tokens,
                "model": self.model,
                "provider": "anthropic"
            }

        except Exception as e:
            logger.error(f"Anthropic Vision error: {e}")
            raise

    def get_provider_name(self) -> str:
        return "anthropic"

    def get_model_name(self) -> str:
        return self.model

    def validate_api_key(self) -> bool:
        """Validate API key by making a minimal API call"""
        try:
            # Simple test: describe a tiny 1x1 black pixel PNG
            test_image = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
            result = self.describe_image(test_image, "What color is this pixel?")
            return bool(result.get("text"))
        except Exception as e:
            logger.error(f"Anthropic Vision API key validation failed: {e}")
            return False

    def list_available_models(self) -> list[str]:
        """List available vision models"""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]


class OllamaVisionProvider(VisionProvider):
    """
    Ollama Vision provider (OPTIONAL - pattern in place, not recommended).

    Research shows:
    - Inconsistent quality (works on some images, refuses on others)
    - Random refusals with "text is not fully visible" errors
    - Slower than cloud (~15s per image)
    - Cost: $0 (local)

    Use only when cloud APIs unavailable.

    See docs/research/vision-testing/FINDINGS.md for details.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize Ollama Vision provider.

        Args:
            base_url: Ollama API base URL (defaults to OLLAMA_BASE_URL env or http://localhost:11434)
            model: Vision model name (defaults to VISION_MODEL env or granite-vision-3.3:2b)
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("VISION_MODEL", "granite-vision-3.3:2b")

        logger.warning(
            f"Using Ollama Vision ({self.model}). Research shows inconsistent quality. "
            "See docs/research/vision-testing/FINDINGS.md"
        )

    def describe_image(self, image_bytes: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Describe image using Ollama vision model.

        Args:
            image_bytes: Raw image bytes
            prompt: Description prompt (defaults to LITERAL_DESCRIPTION_PROMPT)

        Returns:
            Dict with 'text', 'tokens', 'model', 'provider'

        Note: May fail with random refusals on some images.
        """
        import requests

        # Use literal prompt by default
        if prompt is None:
            prompt = LITERAL_DESCRIPTION_PROMPT

        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False
                },
                timeout=120.0
            )
            response.raise_for_status()

            result = response.json()
            description = result.get("response", "")

            # Ollama doesn't provide detailed token counts
            tokens = {
                "input_tokens": 0,  # Not available
                "output_tokens": 0,  # Not available
                "total_tokens": 0
            }

            logger.info(
                f"Ollama Vision described image: {len(description)} chars "
                f"(model: {self.model})"
            )

            return {
                "text": description,
                "tokens": tokens,
                "model": self.model,
                "provider": "ollama"
            }

        except Exception as e:
            logger.error(f"Ollama Vision error: {e}")
            raise

    def get_provider_name(self) -> str:
        return "ollama"

    def get_model_name(self) -> str:
        return self.model

    def validate_api_key(self) -> bool:
        """Validate Ollama connection (no API key needed)"""
        import requests
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Ollama connection validation failed: {e}")
            return False

    def list_available_models(self) -> list[str]:
        """List available vision models from Ollama"""
        import requests
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()

            models = response.json().get("models", [])
            # Filter for vision models (contains "vision" or "llava" in name)
            vision_models = [
                m["name"] for m in models
                if "vision" in m["name"].lower() or "llava" in m["name"].lower()
            ]
            return vision_models if vision_models else ["No vision models found"]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []


def get_vision_provider(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> VisionProvider:
    """
    Factory function to get vision provider instance.

    Args:
        provider: Provider name ('openai', 'anthropic', 'ollama')
                 Defaults to VISION_PROVIDER env var or 'openai'
        api_key: API key (optional, will use env vars if not provided)
        model: Model name (optional, will use env vars or provider defaults)

    Returns:
        VisionProvider instance

    Raises:
        ValueError: If provider not recognized or configuration invalid

    Examples:
        # Use default provider (OpenAI GPT-4o)
        provider = get_vision_provider()

        # Use specific provider
        provider = get_vision_provider(provider="anthropic")

        # Override model
        provider = get_vision_provider(provider="openai", model="gpt-4o-mini")
    """
    provider = provider or os.getenv("VISION_PROVIDER", "openai")
    provider = provider.lower()

    logger.info(f"Initializing vision provider: {provider}")

    if provider == "openai":
        return OpenAIVisionProvider(api_key=api_key, model=model)
    elif provider == "anthropic":
        return AnthropicVisionProvider(api_key=api_key, model=model)
    elif provider == "ollama":
        # Ollama doesn't use API keys
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaVisionProvider(base_url=base_url, model=model)
    else:
        raise ValueError(
            f"Unknown vision provider: {provider}. "
            f"Supported: openai (recommended), anthropic, ollama"
        )
