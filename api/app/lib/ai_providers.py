"""
AI Provider abstraction layer for concept extraction and embeddings.

Supports multiple providers (OpenAI, Anthropic) with configurable models.

API Key Loading (ADR-031):
- First tries encrypted key store (system_api_keys table)
- Falls back to environment variables (.env or direct)
- Maintains backward compatibility
"""

import os
import logging
from typing import List, Dict, Any, Literal, Optional
from abc import ABC, abstractmethod
import json
from .rate_limiter import exponential_backoff_retry

logger = logging.getLogger(__name__)


# Default prompt for image description (ADR-033 Phase 1)
IMAGE_DESCRIPTION_PROMPT = """Analyze this image for knowledge extraction. Provide a detailed description:

**Text Content:** Transcribe ALL visible text exactly as written (titles, headings, bullets, labels, annotations).

**Visual Structure:** Describe diagrams, charts, tables, hierarchies, and layout organization.

**Relationships:** Explain connections shown via arrows, lines, groupings, proximity, or color coding.

**Key Concepts:** Identify main ideas, frameworks, terminology, principles, or models presented.

**Context:** Note the content type (e.g., presentation slide, flowchart, system diagram).

Be thorough - capture information density over brevity. Focus on facts and structure, not interpretation."""


def _load_api_key(provider: str, explicit_key: Optional[str] = None, env_var: Optional[str] = None, service_token: Optional[str] = None) -> Optional[str]:
    """
    Load API key with fallback chain (ADR-031).

    Priority order:
    1. Explicit key provided as parameter
    2. Encrypted key from database (system_api_keys table) - requires service token
    3. Environment variable
    4. None (will raise error in provider __init__)

    Args:
        provider: Provider name ('openai' or 'anthropic')
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


def _list_models_from_catalog(provider: str) -> Optional[Dict[str, List[str]]]:
    """
    Query the provider_model_catalog for enabled models (ADR-800).

    Returns dict of category -> model_id list, or None if catalog unavailable.
    """
    try:
        from .model_catalog import list_catalog
        from .age_client import AGEClient

        client = AGEClient()
        conn = client.pool.getconn()
        try:
            rows = list_catalog(conn, provider=provider, enabled_only=True)
            if not rows:
                return None

            result: Dict[str, List[str]] = {}
            for row in rows:
                cat = row["category"]
                result.setdefault(cat, []).append(row["model_id"])
            return result
        finally:
            client.pool.putconn(conn)
    except Exception:
        return None


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    @abstractmethod
    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Extract concepts from text using the provider's LLM"""
        pass

    @abstractmethod
    def generate_embedding(self, text: str, purpose: Literal["query", "document"] = "document") -> List[float]:
        """Generate vector embedding for text. Purpose: 'query' or 'document'."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider"""
        pass

    @abstractmethod
    def get_extraction_model(self) -> str:
        """Get the model used for concept extraction"""
        pass

    @abstractmethod
    def get_embedding_model(self) -> str:
        """Get the model used for embeddings"""
        pass

    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate that the API key works"""
        pass

    @abstractmethod
    def list_available_models(self) -> Dict[str, List[str]]:
        """List available models for this provider"""
        pass

    @abstractmethod
    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """
        Translate code/diagram to plain prose for concept extraction.

        Used by markdown preprocessor to convert code blocks, mermaid diagrams,
        and other structured content into descriptive prose.

        Args:
            prompt: Translation prompt (specific to content type)
            code: Code/diagram content to translate

        Returns:
            Dict with 'text' (prose translation) and 'tokens' (usage info)
        """
        pass

    @abstractmethod
    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Generate detailed description of an image using multimodal AI.

        Used for ingesting visual content (slides, diagrams, charts) into the
        knowledge graph by converting them to text descriptions that can be
        processed by the normal concept extraction pipeline.

        Args:
            image_data: Raw image bytes (PNG, JPEG, etc.)
            prompt: Description prompt (e.g., "Describe this slide in detail")

        Returns:
            Dict with 'text' (description) and 'tokens' (usage info)
        """
        pass

    def fetch_model_catalog(self) -> List[Dict[str, Any]]:
        """
        Fetch available models from the provider API for catalog storage (ADR-800).

        Returns a list of dicts with keys matching provider_model_catalog columns:
            provider, model_id, display_name, category, context_length,
            max_completion_tokens, supports_vision, supports_json_mode,
            supports_tool_use, supports_streaming, price_prompt_per_m,
            price_completion_per_m, upstream_provider, raw_metadata

        Default implementation returns an empty list. Providers override
        this to query their model listing APIs.
        """
        return []


class OpenAIProvider(AIProvider):
    """OpenAI provider for GPT models and embeddings"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_provider: Optional[AIProvider] = None
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

        # Configure retry behavior (exponential backoff built into SDK)
        # Load from database (ADR-041) or fall back to env/defaults
        from .rate_limiter import get_provider_max_retries
        max_retries = get_provider_max_retries("openai")

        self.client = OpenAI(
            api_key=self.api_key,
            max_retries=max_retries,
            timeout=120.0  # 2 minute timeout for long operations
        )
        logger.info(f"OpenAI client configured with max_retries={max_retries}")

        # Configurable models with defaults
        self.extraction_model = extraction_model or os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o")
        self.embedding_model = embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        # Optional separate embedding provider (e.g., LocalEmbeddingProvider)
        self.embedding_provider = embedding_provider

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Extract concepts using OpenAI GPT models

        Returns dict with 'result' (extracted data) and 'tokens' (usage info)

        Note: system_prompt is already formatted by llm_extractor.py
        """

        try:
            response = self.client.chat.completions.create(
                model=self.extraction_model,
                messages=[
                    {"role": "system", "content": system_prompt},  # Already formatted
                    {"role": "user", "content": f"Text to analyze:\n\n{text}"}
                ],
                max_tokens=4096,
                temperature=0.3,  # Lower for consistency
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content

            # Parse JSON with better error handling
            try:
                result = self._extract_json(response_text)
            except json.JSONDecodeError as json_err:
                raise Exception(
                    f"Failed to parse JSON from OpenAI response.\n"
                    f"Error: {json_err}\n"
                    f"Response text (first 500 chars): {response_text[:500]}"
                )

            # Validate structure
            result.setdefault("concepts", [])
            result.setdefault("instances", [])
            result.setdefault("relationships", [])

            # Extract token usage
            tokens = 0
            if hasattr(response, 'usage') and response.usage:
                tokens = response.usage.total_tokens

            return {
                "result": result,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"OpenAI concept extraction failed: {e}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response text (handles markdown code blocks and whitespace)"""
        # Remove markdown code blocks if present (some models add them despite json_object format)
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Provide detailed error for debugging
            raise json.JSONDecodeError(
                f"JSON parsing failed: {e.msg}. Response snippet: {cleaned[:100]}...",
                e.doc,
                e.pos
            )

    def generate_embedding(self, text: str, purpose: Literal["query", "document"] = "document") -> Dict[str, Any]:
        """Generate embedding using the system embedding provider.

        All embedding generation goes through the configured embedding provider
        (e.g., local nomic-embed-text). The reasoning provider never generates
        its own embeddings — this prevents dimension mismatches between the
        embedding model (768-dim nomic) and OpenAI's text-embedding-3-small
        (1536-dim).

        Returns dict with 'embedding' (vector) and 'tokens' (usage info)
        """
        if self.embedding_provider:
            return self.embedding_provider.generate_embedding(text, purpose=purpose)

        raise RuntimeError(
            "No embedding provider configured. OpenAI reasoning provider cannot "
            "generate embeddings without a system embedding config. Configure via "
            "POST /admin/embedding/config or ensure local embedding model is loaded."
        )

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """
        Translate code/diagram to prose using gpt-4o-mini (cheap and fast).

        Returns dict with 'text' (prose) and 'tokens' (usage info)
        """
        try:
            # Use mini model for cost-effective translation
            translation_model = "gpt-4o-mini"

            response = self.client.chat.completions.create(
                model=translation_model,
                messages=[
                    {"role": "system", "content": "You are a technical writer who explains code and diagrams in clear, simple prose."},
                    {"role": "user", "content": f"{prompt}\n\n{code}"}
                ],
                max_tokens=1000,  # Prose translations are typically shorter than code
                temperature=0.5   # Balanced: clear but not robotic
            )

            prose = response.choices[0].message.content.strip()

            # Extract token usage
            tokens = 0
            if hasattr(response, 'usage') and response.usage:
                tokens = response.usage.total_tokens

            return {
                "text": prose,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"OpenAI code translation failed: {e}")

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Describe an image using GPT-4o vision capabilities.

        Returns dict with 'text' (description) and 'tokens' (usage info)
        """
        import base64

        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Use gpt-4o which has vision capabilities
            vision_model = "gpt-4o"

            response = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"  # High detail for better extraction
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,  # Allow detailed descriptions
                temperature=0.3   # Lower for consistency
            )

            description = response.choices[0].message.content.strip()

            # Extract token usage
            tokens = 0
            if hasattr(response, 'usage') and response.usage:
                tokens = response.usage.total_tokens

            return {
                "text": description,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"OpenAI image description failed: {e}")

    def get_provider_name(self) -> str:
        return "OpenAI"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        """Get embedding model name (may be from separate provider)"""
        if self.embedding_provider:
            return self.embedding_provider.get_embedding_model()
        return self.embedding_model

    @property
    def model_name(self) -> str:
        """Embedding model name, delegating to embedding_provider if set."""
        if self.embedding_provider and hasattr(self.embedding_provider, 'model_name'):
            return self.embedding_provider.model_name
        return self.embedding_model

    def validate_api_key(self) -> bool:
        """Validate OpenAI API key by making a simple API call"""
        try:
            # Try to list models (lightweight check)
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI API key validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available OpenAI models. Prefers catalog (ADR-800), falls back to API then hardcoded."""
        catalog = _list_models_from_catalog("openai")
        if catalog:
            return catalog

        try:
            models_response = self.client.models.list()
            all_models = [model.id for model in models_response.data]
            extraction_models = [m for m in all_models if any(x in m for x in ["gpt-4", "gpt-3.5", "o1"])]
            embedding_models = [m for m in all_models if "embedding" in m]

            return {
                "extraction": extraction_models or AVAILABLE_MODELS["openai"]["extraction"],
                "embedding": embedding_models or AVAILABLE_MODELS["openai"]["embedding"]
            }
        except Exception:
            return AVAILABLE_MODELS["openai"]

    def fetch_model_catalog(self) -> List[Dict[str, Any]]:
        """Fetch models from OpenAI API and return catalog entries (ADR-800)."""
        # Known pricing (USD per 1M tokens) — OpenAI doesn't expose pricing via API
        known_pricing = {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "o1-preview": (15.00, 60.00),
            "o1-mini": (3.00, 12.00),
            "text-embedding-3-small": (0.02, None),
            "text-embedding-3-large": (0.13, None),
            "text-embedding-ada-002": (0.10, None),
        }

        entries = []
        try:
            models_response = self.client.models.list()
            for model in models_response.data:
                mid = model.id
                # Filter to models we care about
                is_extraction = any(x in mid for x in ["gpt-4", "gpt-3.5", "o1"])
                is_embedding = "embedding" in mid

                if not is_extraction and not is_embedding:
                    continue

                category = "embedding" if is_embedding else "extraction"
                pricing = known_pricing.get(mid, (None, None))

                entries.append({
                    "provider": "openai",
                    "model_id": mid,
                    "display_name": mid,
                    "category": category,
                    "context_length": None,
                    "supports_vision": "4o" in mid or "gpt-4-turbo" in mid,
                    "supports_json_mode": not is_embedding and "o1" not in mid,
                    "supports_tool_use": not is_embedding and "o1" not in mid,
                    "supports_streaming": True,
                    "price_prompt_per_m": pricing[0],
                    "price_completion_per_m": pricing[1],
                    "upstream_provider": None,
                    "raw_metadata": {"id": mid, "created": getattr(model, "created", None)},
                })
        except Exception as e:
            logger.warning(f"Failed to fetch OpenAI model catalog: {e}")

        return entries


class LocalEmbeddingProvider(AIProvider):
    """
    Local embedding provider using sentence-transformers models.

    This provider runs embeddings locally (no API calls) using models like
    nomic-embed-text or BGE. It uses the EmbeddingModelManager singleton
    which loads models once at startup.

    Note: This provider is ONLY for embeddings. Concept extraction still
    requires an LLM provider (OpenAI or Anthropic).
    """

    def __init__(self):
        """
        Initialize local embedding provider.

        Relies on EmbeddingModelManager being initialized at startup.
        """
        from .embedding_model_manager import get_embedding_model_manager

        try:
            self.model_manager = get_embedding_model_manager()
        except RuntimeError as e:
            raise ValueError(
                f"Local embedding model not initialized: {e}\n"
                "Ensure init_embedding_model_manager() was called at startup."
            )

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        LocalEmbeddingProvider does not support concept extraction.

        Use OpenAI or Anthropic providers for LLM-based extraction.
        """
        raise NotImplementedError(
            "LocalEmbeddingProvider only supports embeddings, not concept extraction. "
            "Use OpenAI or Anthropic for extraction."
        )

    def generate_embedding(self, text: str, purpose: Literal["query", "document"] = "document") -> Dict[str, Any]:
        """
        Generate embedding using local model with purpose-aware task prefix.

        Returns dict with 'embedding' (vector), 'model', and 'tokens' (0 for local).
        This matches the interface expected by the rest of the system.
        """
        try:
            embedding = self.model_manager.generate_embedding(text, purpose=purpose)

            return {
                "embedding": embedding,
                "model": self.model_manager.get_model_name(),
                "tokens": 0  # Local embeddings have no token cost
            }
        except Exception as e:
            raise Exception(f"Local embedding generation failed: {e}")

    def get_provider_name(self) -> str:
        return "Local (sentence-transformers)"

    @property
    def model_name(self) -> str:
        """Get the local embedding model name (for compatibility with other providers)"""
        return self.model_manager.get_model_name()

    def get_extraction_model(self) -> str:
        """LocalEmbeddingProvider doesn't support extraction"""
        return "N/A (local embeddings only)"

    def get_embedding_model(self) -> str:
        """Get the local embedding model name"""
        return self.model_manager.get_model_name()

    def validate_api_key(self) -> bool:
        """
        Validate that local model is loaded and working.

        For local provider, this checks model availability rather than API key.
        """
        try:
            # Test embedding generation
            test_embedding = self.model_manager.generate_embedding("test")

            # Verify dimensions match expected
            expected_dims = self.model_manager.get_dimensions()
            if len(test_embedding) != expected_dims:
                logger.error(f"Embedding dimension mismatch: got {len(test_embedding)}, expected {expected_dims}")
                return False

            logger.info(f"✅ Local embedding model validated ({expected_dims} dims)")
            return True

        except Exception as e:
            logger.error(f"Local embedding model validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List recommended local embedding models"""
        return {
            "extraction": [],  # Local provider doesn't do extraction
            "embedding": [
                "nomic-ai/nomic-embed-text-v1.5",    # 768 dims, 8K context (recommended)
                "BAAI/bge-small-en-v1.5",            # 384 dims, lightweight
                "BAAI/bge-base-en-v1.5",             # 768 dims, balanced
                "BAAI/bge-large-en-v1.5",            # 1024 dims, high quality
                "sentence-transformers/all-MiniLM-L6-v2",  # 384 dims, fast
            ]
        }

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """LocalEmbeddingProvider doesn't support prose translation (requires LLM)"""
        raise NotImplementedError(
            "LocalEmbeddingProvider only supports embeddings, not prose translation. "
            "Use OpenAI or Anthropic for translation."
        )

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """LocalEmbeddingProvider doesn't support image description (requires multimodal LLM)"""
        raise NotImplementedError(
            "LocalEmbeddingProvider only supports embeddings, not image description. "
            "Use OpenAI or Anthropic for image description."
        )


class AnthropicProvider(AIProvider):
    """Anthropic provider for Claude models"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_provider: Optional[AIProvider] = None
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

        # Configure retry behavior (exponential backoff built into SDK)
        # Load from database (ADR-041) or fall back to env/defaults
        from .rate_limiter import get_provider_max_retries
        max_retries = get_provider_max_retries("anthropic")

        self.client = Anthropic(
            api_key=self.api_key,
            max_retries=max_retries,
            timeout=120.0  # 2 minute timeout for long operations
        )
        logger.info(f"Anthropic client configured with max_retries={max_retries}")

        # Configurable extraction model
        self.extraction_model = extraction_model or os.getenv("ANTHROPIC_EXTRACTION_MODEL", "claude-sonnet-4-20250514")

        # Anthropic doesn't provide embeddings, delegate to another provider (OpenAI by default)
        self.embedding_provider = embedding_provider
        if not self.embedding_provider:
            # Default to OpenAI for embeddings
            try:
                self.embedding_provider = OpenAIProvider(
                    embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                )
            except ValueError:
                raise ValueError("Anthropic requires an embedding provider. Set OPENAI_API_KEY or provide embedding_provider.")

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Extract concepts using Anthropic Claude models

        Returns dict with 'result' (extracted data) and 'tokens' (usage info)

        Note: system_prompt is already formatted by llm_extractor.py
        """

        try:
            message = self.client.messages.create(
                model=self.extraction_model,
                max_tokens=4096,
                temperature=0.3,  # Lower for consistency
                system=system_prompt,  # Already formatted
                messages=[
                    {"role": "user", "content": f"Text to analyze:\n\n{text}"}
                ]
            )

            response_text = message.content[0].text

            # Try to extract JSON from response
            result = self._extract_json(response_text)

            # Validate structure
            result.setdefault("concepts", [])
            result.setdefault("instances", [])
            result.setdefault("relationships", [])

            # Extract token usage from Anthropic response
            tokens = 0
            if hasattr(message, 'usage') and message.usage:
                tokens = message.usage.input_tokens + message.usage.output_tokens

            return {
                "result": result,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"Anthropic concept extraction failed: {e}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response text (handles markdown code blocks)"""
        # Remove markdown code blocks if present
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON from Claude response: {e}\nResponse: {text}")

    def generate_embedding(self, text: str, purpose: Literal["query", "document"] = "document") -> List[float]:
        """Generate embedding using the configured embedding provider"""
        return self.embedding_provider.generate_embedding(text, purpose=purpose)

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """
        Translate code/diagram to prose using Claude Haiku (fast and cheap).

        Returns dict with 'text' (prose) and 'tokens' (usage info)
        """
        try:
            # Use Haiku for cost-effective translation
            translation_model = "claude-3-haiku-20240307"

            message = self.client.messages.create(
                model=translation_model,
                max_tokens=1000,
                temperature=0.5,  # Balanced: clear but not robotic
                system="You are a technical writer who explains code and diagrams in clear, simple prose.",
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n{code}"}
                ]
            )

            prose = message.content[0].text.strip()

            # Extract token usage
            tokens = 0
            if hasattr(message, 'usage') and message.usage:
                tokens = message.usage.input_tokens + message.usage.output_tokens

            return {
                "text": prose,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"Anthropic code translation failed: {e}")

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Describe an image using Claude 3.5 Sonnet vision capabilities.

        Returns dict with 'text' (description) and 'tokens' (usage info)
        """
        import base64

        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Detect image type from magic bytes
            image_type = "image/png"  # Default
            if image_data[:2] == b'\xff\xd8':
                image_type = "image/jpeg"
            elif image_data[:4] == b'GIF8':
                image_type = "image/gif"
            elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
                image_type = "image/webp"

            # Use latest Claude 3.5 Sonnet with vision
            vision_model = "claude-3-5-sonnet-20241022"

            message = self.client.messages.create(
                model=vision_model,
                max_tokens=2000,  # Allow detailed descriptions
                temperature=0.3,  # Lower for consistency
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            description = message.content[0].text.strip()

            # Extract token usage
            tokens = 0
            if hasattr(message, 'usage') and message.usage:
                tokens = message.usage.input_tokens + message.usage.output_tokens

            return {
                "text": description,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"Anthropic image description failed: {e}")

    def get_provider_name(self) -> str:
        return "Anthropic"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        return self.embedding_provider.get_embedding_model()

    @property
    def model_name(self) -> str:
        """Embedding model name, delegating to embedding_provider."""
        if self.embedding_provider and hasattr(self.embedding_provider, 'model_name'):
            return self.embedding_provider.model_name
        return self.extraction_model

    def validate_api_key(self) -> bool:
        """Validate Anthropic API key by making a simple API call"""
        try:
            # Try to create a minimal message (lightweight check)
            self.client.messages.create(
                model=self.extraction_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic API key validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available Anthropic models. Prefers catalog (ADR-800), falls back to hardcoded."""
        catalog = _list_models_from_catalog("anthropic")
        if catalog:
            return catalog
        return AVAILABLE_MODELS["anthropic"]

    def fetch_model_catalog(self) -> List[Dict[str, Any]]:
        """Return hardcoded Anthropic model catalog with known pricing (ADR-800)."""
        models = [
            ("claude-sonnet-4-20250514", "Claude Sonnet 4", 200000, True, 3.00, 15.00),
            ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", 200000, True, 3.00, 15.00),
            ("claude-3-opus-20240229", "Claude 3 Opus", 200000, True, 15.00, 75.00),
            ("claude-3-sonnet-20240229", "Claude 3 Sonnet", 200000, True, 3.00, 15.00),
            ("claude-3-haiku-20240307", "Claude 3 Haiku", 200000, True, 0.25, 1.25),
        ]
        return [
            {
                "provider": "anthropic",
                "model_id": mid,
                "display_name": name,
                "category": "extraction",
                "context_length": ctx,
                "supports_vision": vision,
                "supports_json_mode": True,
                "supports_tool_use": True,
                "supports_streaming": True,
                "price_prompt_per_m": prompt_cost,
                "price_completion_per_m": comp_cost,
                "upstream_provider": None,
                "raw_metadata": None,
            }
            for mid, name, ctx, vision, prompt_cost, comp_cost in models
        ]


class OpenRouterProvider(AIProvider):
    """
    OpenRouter provider for accessing 200+ models via a unified API (ADR-800).

    OpenRouter provides an OpenAI-compatible API that routes to multiple upstream
    providers (OpenAI, Anthropic, Google, Meta, Mistral, etc.). Model IDs are
    namespaced (e.g., 'openai/gpt-4o', 'anthropic/claude-sonnet-4').

    Key differences from direct provider access:
    - Single API key for all upstream models
    - Automatic provider routing and fallback
    - Per-model pricing available via catalog API
    - No direct embedding support (delegate to embedding_provider)
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_provider: Optional[AIProvider] = None,
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key (falls back to OPENROUTER_API_KEY env var)
            extraction_model: Model ID (e.g., 'openai/gpt-4o', 'anthropic/claude-sonnet-4')
            embedding_provider: Separate provider for embeddings (required — OpenRouter
                               doesn't serve embeddings)
        """
        from openai import OpenAI

        self.api_key = _load_api_key("openrouter", api_key, "OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Either:\n"
                "  1. Configure via admin API: POST /admin/keys/openrouter\n"
                "  2. Set OPENROUTER_API_KEY environment variable\n"
                "  3. Add to .env file (development only)"
            )

        from .rate_limiter import get_provider_max_retries
        max_retries = get_provider_max_retries("openrouter")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.OPENROUTER_BASE_URL,
            max_retries=max_retries,
            timeout=120.0,
            default_headers={
                "HTTP-Referer": "https://github.com/aaronsb/knowledge-graph-system",
                "X-OpenRouter-Title": "Knowledge Graph System",
            },
        )
        logger.info(f"OpenRouter client configured with max_retries={max_retries}")

        self.extraction_model = extraction_model or os.getenv(
            "OPENROUTER_EXTRACTION_MODEL", "openai/gpt-4o"
        )
        self.embedding_provider = embedding_provider

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Extract concepts via OpenRouter using the configured model."""
        try:
            response = self.client.chat.completions.create(
                model=self.extraction_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text to analyze:\n\n{text}"},
                ],
                max_tokens=16384,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content

            try:
                result = self._extract_json(response_text)
            except json.JSONDecodeError as json_err:
                raise Exception(
                    f"Failed to parse JSON from OpenRouter response.\n"
                    f"Error: {json_err}\n"
                    f"Response text (first 500 chars): {response_text[:500]}"
                )

            result.setdefault("concepts", [])
            result.setdefault("instances", [])
            result.setdefault("relationships", [])

            tokens = 0
            if hasattr(response, "usage") and response.usage:
                tokens = response.usage.total_tokens

            return {"result": result, "tokens": tokens}

        except Exception as e:
            raise Exception(f"OpenRouter concept extraction failed: {e}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response text (handles markdown code blocks)."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"JSON parsing failed: {e.msg}. Response snippet: {cleaned[:100]}...",
                e.doc,
                e.pos,
            )

    def generate_embedding(
        self, text: str, purpose: Literal["query", "document"] = "document"
    ) -> Dict[str, Any]:
        """Delegate to embedding provider — OpenRouter doesn't serve embeddings."""
        if self.embedding_provider:
            return self.embedding_provider.generate_embedding(text, purpose=purpose)

        raise RuntimeError(
            "No embedding provider configured. OpenRouter does not provide embeddings. "
            "Configure a local embedding model via POST /admin/embedding/config."
        )

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """Translate code/diagram to prose using a cheap model via OpenRouter."""
        try:
            # Use a fast/cheap model for translation; fall back to extraction model
            translation_model = "openai/gpt-4o-mini"

            response = self.client.chat.completions.create(
                model=translation_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical writer who explains code and diagrams in clear, simple prose.",
                    },
                    {"role": "user", "content": f"{prompt}\n\n{code}"},
                ],
                max_tokens=1000,
                temperature=0.5,
            )

            prose = response.choices[0].message.content.strip()
            tokens = 0
            if hasattr(response, "usage") and response.usage:
                tokens = response.usage.total_tokens

            return {"text": prose, "tokens": tokens}

        except Exception as e:
            raise Exception(f"OpenRouter code translation failed: {e}")

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Describe an image using a vision-capable model via OpenRouter."""
        import base64

        try:
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Detect MIME type from magic bytes
            mime_type = "image/png"
            if image_data[:2] == b"\xff\xd8":
                mime_type = "image/jpeg"
            elif image_data[:4] == b"GIF8":
                mime_type = "image/gif"
            elif image_data[:4] == b"RIFF" and image_data[8:12] == b"WEBP":
                mime_type = "image/webp"

            # Use the extraction model if it supports vision, otherwise default
            vision_model = self.extraction_model

            response = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=2000,
                temperature=0.3,
            )

            description = response.choices[0].message.content.strip()
            tokens = 0
            if hasattr(response, "usage") and response.usage:
                tokens = response.usage.total_tokens

            return {"text": description, "tokens": tokens}

        except Exception as e:
            raise Exception(f"OpenRouter image description failed: {e}")

    def get_provider_name(self) -> str:
        return "OpenRouter"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        if self.embedding_provider:
            return self.embedding_provider.get_embedding_model()
        return ""

    @property
    def model_name(self) -> str:
        """Embedding model name, delegating to embedding_provider."""
        if self.embedding_provider and hasattr(self.embedding_provider, "model_name"):
            return self.embedding_provider.model_name
        return ""

    def validate_api_key(self) -> bool:
        """Validate OpenRouter API key by fetching the models list."""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenRouter API key validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available models from OpenRouter catalog."""
        try:
            models_response = self.client.models.list()
            all_models = [model.id for model in models_response.data]

            # Categorize by capability heuristics
            extraction_models = [
                m
                for m in all_models
                if any(
                    x in m
                    for x in [
                        "gpt-4",
                        "claude",
                        "gemini",
                        "llama",
                        "mistral",
                        "qwen",
                        "deepseek",
                    ]
                )
            ]

            return {
                "extraction": extraction_models,
                "embedding": [],  # OpenRouter doesn't serve embeddings
            }
        except Exception:
            return {"extraction": [], "embedding": []}

    def fetch_model_catalog(self) -> List[Dict[str, Any]]:
        """Fetch models from OpenRouter API with pricing (ADR-800)."""
        import requests

        entries = []
        try:
            # OpenRouter models endpoint is public but we use auth for higher rate limits
            resp = requests.get(
                f"{self.OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for model in data.get("data", []):
                mid = model.get("id", "")
                pricing = model.get("pricing", {})
                arch = model.get("architecture", {})
                top = model.get("top_provider", {})
                input_mods = arch.get("input_modalities", [])
                supported_params = model.get("supported_parameters", [])

                # Convert per-token string to per-1M-token numeric
                prompt_per_token = pricing.get("prompt")
                comp_per_token = pricing.get("completion")
                price_prompt = float(prompt_per_token) * 1_000_000 if prompt_per_token else None
                price_comp = float(comp_per_token) * 1_000_000 if comp_per_token else None

                cache_per_token = pricing.get("input_cache_read")
                price_cache = float(cache_per_token) * 1_000_000 if cache_per_token else None

                # Determine upstream provider from model ID (e.g., "openai/gpt-4o" -> "openai")
                upstream = mid.split("/")[0] if "/" in mid else None

                entries.append({
                    "provider": "openrouter",
                    "model_id": mid,
                    "display_name": model.get("name", mid),
                    "category": "extraction",
                    "context_length": model.get("context_length"),
                    "max_completion_tokens": top.get("max_completion_tokens"),
                    "supports_vision": "image" in input_mods,
                    "supports_json_mode": "response_format" in supported_params,
                    "supports_tool_use": "tools" in supported_params,
                    "supports_streaming": True,
                    "price_prompt_per_m": price_prompt,
                    "price_completion_per_m": price_comp,
                    "price_cache_read_per_m": price_cache,
                    "upstream_provider": upstream,
                    "raw_metadata": model,
                })

        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter model catalog: {e}")

        return entries


class OllamaProvider(AIProvider):
    """
    Local LLM inference provider using Ollama (ADR-042).

    Ollama wraps llama.cpp and provides:
    - Local inference (no API costs)
    - Model management (download, update, list)
    - OpenAI-compatible API
    - JSON mode for structured output

    This provider connects to an Ollama instance (local Docker, system install, or remote).
    It does NOT manage the Ollama service itself.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_provider: Optional[AIProvider] = None,
        temperature: float = 0.1,
        top_p: float = 0.9,
        thinking_mode: str = 'off'
    ):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API endpoint (default: http://localhost:11434)
            extraction_model: Model name (e.g., "mistral:7b-instruct")
            embedding_provider: Separate provider for embeddings (OpenAI or local)
            temperature: Sampling temperature (0.0-1.0, lower = more consistent)
            top_p: Nucleus sampling threshold (0.0-1.0)
            thinking_mode: Thinking mode - 'off', 'low', 'medium', 'high' (Ollama 0.12.x+)
        """
        import requests

        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.extraction_model = extraction_model or os.getenv("OLLAMA_EXTRACTION_MODEL", "mistral:7b-instruct")
        self.temperature = temperature
        self.top_p = top_p
        self.thinking_mode = thinking_mode
        logger.info(f"🔍 OllamaProvider.__init__: thinking_mode={self.thinking_mode}")
        self.session = requests.Session()

        # Ollama doesn't provide embeddings - delegate to separate provider
        self.embedding_provider = embedding_provider
        if not self.embedding_provider:
            # Default to OpenAI for embeddings (or will use local if configured)
            try:
                self.embedding_provider = OpenAIProvider(
                    embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                )
            except ValueError:
                # Try local embeddings as fallback
                try:
                    self.embedding_provider = LocalEmbeddingProvider()
                except ValueError:
                    raise ValueError(
                        "Ollama requires an embedding provider. Either:\n"
                        "  1. Set OPENAI_API_KEY for OpenAI embeddings\n"
                        "  2. Configure local embeddings via: POST /admin/embedding/config"
                    )

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Extract concepts using Ollama local LLM.

        Returns dict with 'result' (extracted data) and 'tokens' (always 0 for local).

        **Reasoning Models:**
        For thinking-capable models (deepseek-r1, qwen3, gpt-oss), this provider
        supports configurable thinking modes (off/low/medium/high) via the `think` parameter.
        Requires Ollama 0.12.x+ for `think` parameter support.

        **Recommended Models:**
        - **Standard:** mistral:7b-instruct, llama3.1:8b-instruct, qwen2.5:7b-instruct
        - **Reasoning:** deepseek-r1:8b, gpt-oss:20b, qwen3:8b (with configurable thinking)
        - **Large:** qwen2.5:14b-instruct, llama3.1:70b-instruct (requires more VRAM)

        Note: system_prompt is already formatted by llm_extractor.py
        """
        import requests

        try:
            # Ollama API request (using /api/chat endpoint)
            # Adjust num_predict based on thinking mode (thinking uses tokens too)
            # Token allocation scaled up significantly to handle massive thinking traces
            if self.thinking_mode == 'high':
                num_predict = 32768  # 8x for high thinking (extensive reasoning traces)
            elif self.thinking_mode == 'medium':
                num_predict = 20480  # 5x for medium thinking (supports ~16K token traces)
            else:
                num_predict = 4096  # Default for off/low

            logger.info(f"🔍 extract_concepts: thinking_mode={self.thinking_mode}, num_predict={num_predict}")

            request_data = {
                "model": self.extraction_model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Text to analyze:\n\n{text}"
                    }
                ],
                "format": "json",  # Enable JSON mode
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "num_predict": num_predict  # Max tokens to generate (includes thinking)
                }
            }

            # Map thinking_mode to model-specific parameter
            # thinking_mode: 'off', 'low', 'medium', 'high'
            if "gpt-oss" in self.extraction_model.lower():
                # GPT-OSS requires think levels ("low"/"medium"/"high"), ignores true/false
                # "off" → "low" (minimal reasoning)
                # Note: Higher thinking modes may timeout on complex/long prompts
                think_value = self.thinking_mode if self.thinking_mode != 'off' else 'low'
                request_data["think"] = think_value
                logger.info(f"🤔 GPT-OSS: think={think_value}, num_predict={num_predict}")
            elif self.thinking_mode == 'off':
                # Standard models: off = disabled
                request_data["think"] = False
            else:
                # Standard models: low/medium/high = enabled (they don't distinguish levels)
                request_data["think"] = True
                logger.info(f"🤔 Thinking: {self.thinking_mode}, num_predict={num_predict}")

            # Wrap with retry logic for rate limiting (local Ollama unlikely, but good practice)
            @exponential_backoff_retry(max_retries=3, base_delay=0.5)
            def _make_request():
                resp = self.session.post(
                    f"{self.base_url}/api/chat",
                    json=request_data,
                    timeout=300  # 5 minute timeout for local inference
                )
                resp.raise_for_status()
                return resp

            response = _make_request()
            response_data = response.json()

            # Extract message from /api/chat response
            message = response_data.get("message", {})
            response_text = message.get("content", "")
            thinking_text = message.get("thinking", "")

            # Fallback: If content is empty but thinking has content, try parsing thinking
            # This happens with GPT-OSS reasoning models - they sometimes put JSON in thinking field
            if not response_text.strip() and thinking_text.strip():
                logger.warning("⚠️  Content field empty, attempting to parse thinking field (GPT-OSS reasoning behavior)")
                response_text = thinking_text

            # Parse JSON response
            try:
                result = self._extract_json(response_text)
            except json.JSONDecodeError as json_err:
                # Log both fields for debugging
                logger.error(f"Content field length: {len(message.get('content', ''))}")
                logger.error(f"Thinking field length: {len(thinking_text)}")
                if thinking_text:
                    logger.error(f"Thinking field preview: {thinking_text[:200]}...")
                raise Exception(
                    f"Failed to parse JSON from Ollama response.\n"
                    f"Error: {json_err}\n"
                    f"Response text (first 500 chars): {response_text[:500]}"
                )

            # Validate structure
            result.setdefault("concepts", [])
            result.setdefault("instances", [])
            result.setdefault("relationships", [])

            # Extract performance metrics from Ollama response
            metrics = {
                "tokens": 0,  # No cost for local
                "performance": {}
            }

            # Ollama returns timing information
            if "eval_count" in response_data and "eval_duration" in response_data:
                eval_count = response_data["eval_count"]
                eval_duration_ns = response_data["eval_duration"]
                eval_duration_s = eval_duration_ns / 1e9

                tokens_per_sec = eval_count / eval_duration_s if eval_duration_s > 0 else 0

                metrics["performance"] = {
                    "tokens_generated": eval_count,
                    "eval_duration_s": round(eval_duration_s, 2),
                    "tokens_per_sec": round(tokens_per_sec, 2)
                }

            # Include prompt evaluation if available
            if "prompt_eval_count" in response_data and "prompt_eval_duration" in response_data:
                prompt_count = response_data["prompt_eval_count"]
                prompt_duration_ns = response_data["prompt_eval_duration"]
                prompt_duration_s = prompt_duration_ns / 1e9

                metrics["performance"]["prompt_tokens"] = prompt_count
                metrics["performance"]["prompt_duration_s"] = round(prompt_duration_s, 2)
                metrics["performance"]["total_duration_s"] = round(
                    metrics["performance"]["eval_duration_s"] + prompt_duration_s, 2
                )

            return {
                "result": result,
                "tokens": metrics["tokens"],
                "performance": metrics["performance"]
            }

        except requests.exceptions.ConnectionError:
            raise Exception(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running:\n"
                "  - Local: ollama serve\n"
                "  - Docker: docker run -d -p 11434:11434 ollama/ollama\n"
                "  - System: systemctl status ollama\n"
                "  - Remote: Check base_url configuration"
            )
        except requests.exceptions.Timeout:
            raise Exception(
                f"Ollama request timed out after 300s. "
                f"Model '{self.extraction_model}' may be too large or system is overloaded."
            )
        except Exception as e:
            raise Exception(f"Ollama concept extraction failed: {e}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from response text.

        Handles markdown code blocks and basic whitespace cleanup.
        """
        # Remove markdown code blocks if present
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Provide detailed error for debugging
            raise json.JSONDecodeError(
                f"JSON parsing failed: {e.msg}. Response snippet: {cleaned[:100]}...",
                e.doc,
                e.pos
            )

    def generate_embedding(self, text: str, purpose: Literal["query", "document"] = "document") -> Dict[str, Any]:
        """Generate embedding using the configured embedding provider"""
        return self.embedding_provider.generate_embedding(text, purpose=purpose)

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """
        Translate code/diagram to prose using Ollama.

        Returns dict with 'text' (prose) and 'tokens' (always 0 for local).
        """
        import requests

        try:
            # Wrap with retry logic for rate limiting
            @exponential_backoff_retry(max_retries=3, base_delay=0.5)
            def _make_request():
                resp = self.session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.extraction_model,
                        "prompt": f"You are a technical writer who explains code and diagrams in clear, simple prose.\n\n{prompt}\n\n{code}",
                        "stream": False,
                        "options": {
                            "temperature": 0.5,  # Balanced: clear but not robotic
                            "top_p": self.top_p,
                            "num_predict": 1000
                        }
                    },
                    timeout=120  # 2 minute timeout
                )
                resp.raise_for_status()
                return resp

            response = _make_request()
            response_data = response.json()
            prose = response_data.get("response", "").strip()

            return {
                "text": prose,
                "tokens": 0  # No token costs for local inference
            }

        except Exception as e:
            raise Exception(f"Ollama code translation failed: {e}")

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Describe an image using Ollama vision model (e.g., llava, bakllava).

        Returns dict with 'text' (description) and 'tokens' (always 0 for local).

        Note: Requires a vision-capable model like llava:7b, llava:13b, or bakllava.
        """
        import requests
        import base64

        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Use vision model (override extraction model if it's not vision-capable)
            vision_model = self.extraction_model
            if "llava" not in vision_model.lower() and "bakllava" not in vision_model.lower():
                logger.warning(
                    f"Model '{vision_model}' may not support vision. "
                    "Consider using 'llava:7b' or 'llava:13b' for image description."
                )

            # Wrap with retry logic for rate limiting
            @exponential_backoff_retry(max_retries=3, base_delay=0.5)
            def _make_request():
                resp = self.session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": vision_model,
                        "prompt": prompt,
                        "images": [image_base64],
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Lower for consistency
                            "top_p": self.top_p,
                            "num_predict": 2000
                        }
                    },
                    timeout=180  # 3 minute timeout for vision
                )
                resp.raise_for_status()
                return resp

            response = _make_request()
            response_data = response.json()
            description = response_data.get("response", "").strip()

            return {
                "text": description,
                "tokens": 0  # No token costs for local inference
            }

        except Exception as e:
            raise Exception(f"Ollama image description failed: {e}")

    def get_provider_name(self) -> str:
        return "Ollama (Local)"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        return self.embedding_provider.get_embedding_model()

    @property
    def model_name(self) -> str:
        """Embedding model name, delegating to embedding_provider."""
        if self.embedding_provider and hasattr(self.embedding_provider, 'model_name'):
            return self.embedding_provider.model_name
        return self.extraction_model

    def validate_api_key(self) -> bool:
        """
        Validate that Ollama is accessible and the model is available.

        For local provider, this checks service availability and model presence.
        """
        import requests

        try:
            # Check if Ollama is running
            response = self.session.get(f"{self.base_url}/api/version", timeout=5)
            response.raise_for_status()

            # Check if model is available
            models_response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            models_response.raise_for_status()

            models_data = models_response.json()
            available_models = [m['name'] for m in models_data.get('models', [])]

            if self.extraction_model not in available_models:
                logger.warning(
                    f"Model '{self.extraction_model}' not found. Available models: {available_models}\n"
                    f"Download with: ollama pull {self.extraction_model}"
                )
                return False

            logger.info(f"✅ Ollama validated at {self.base_url} with model '{self.extraction_model}'")
            return True

        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Ollama at {self.base_url}")
            return False
        except Exception as e:
            logger.error(f"Ollama validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available Ollama models. Prefers catalog (ADR-800), falls back to API then hardcoded."""
        import requests

        catalog = _list_models_from_catalog("ollama")
        if catalog:
            return catalog

        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()

            models_data = response.json()
            available_models = [m['name'] for m in models_data.get('models', [])]

            # Separate vision models from text models
            vision_models = [m for m in available_models if any(v in m.lower() for v in ['llava', 'bakllava', 'vision'])]
            text_models = [m for m in available_models if m not in vision_models]

            return {
                "extraction": text_models or AVAILABLE_MODELS["ollama"]["extraction"],
                "embedding": [],  # Ollama doesn't provide embeddings
                "vision": vision_models  # Vision-capable models
            }

        except Exception as e:
            logger.warning(f"Could not fetch Ollama models: {e}")
            # Return recommended models as fallback
            return AVAILABLE_MODELS["ollama"]

    def fetch_model_catalog(self) -> List[Dict[str, Any]]:
        """Fetch installed models from Ollama instance (ADR-800)."""
        import requests

        entries = []
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models_data = response.json()

            for model in models_data.get("models", []):
                name = model.get("name", "")
                details = model.get("details", {})
                is_vision = any(v in name.lower() for v in ["llava", "bakllava", "vision"])
                category = "vision" if is_vision else "extraction"

                entries.append({
                    "provider": "ollama",
                    "model_id": name,
                    "display_name": name,
                    "category": category,
                    "context_length": None,
                    "supports_vision": is_vision,
                    "supports_json_mode": not is_vision,
                    "supports_tool_use": False,
                    "supports_streaming": True,
                    "price_prompt_per_m": 0,
                    "price_completion_per_m": 0,
                    "upstream_provider": None,
                    "raw_metadata": model,
                })

        except Exception as e:
            logger.warning(f"Failed to fetch Ollama model catalog: {e}")

        return entries


def get_embedding_provider() -> Optional[AIProvider]:
    """
    Get the configured embedding provider (may be different from extraction provider).

    Database-first approach (ADR-039):
    - Checks if LocalEmbeddingProvider is available (model manager initialized)
    - If yes, returns LocalEmbeddingProvider
    - If no, returns None (caller will use default provider's embeddings)

    Returns:
        LocalEmbeddingProvider if configured, None otherwise
    """
    # Try to create LocalEmbeddingProvider (will fail if model manager not initialized)
    try:
        return LocalEmbeddingProvider()
    except ValueError:
        # Model manager not initialized (no local embeddings configured in database)
        return None


def get_provider(provider_name: Optional[str] = None) -> AIProvider:
    """
    Factory function to get the configured AI provider (ADR-041).

    Configuration source depends on DEVELOPMENT_MODE:
    - DEVELOPMENT_MODE=true: Uses environment variables (.env file)
    - DEVELOPMENT_MODE=false: Loads from database (kg_api.ai_extraction_config)

    Args:
        provider_name: Name of provider ("openai", "anthropic", "ollama", "openrouter", or "mock")
                      If None, reads from AI_PROVIDER env var or database

    Returns:
        Configured AIProvider instance

    Environment Variables (DEVELOPMENT_MODE=true only):
        AI_PROVIDER: "openai", "anthropic", or "mock" (default: "openai")

        For OpenAI:
            OPENAI_API_KEY: Required
            OPENAI_EXTRACTION_MODEL: Optional (default: "gpt-4o")
            OPENAI_EMBEDDING_MODEL: Optional (default: "text-embedding-3-small")

        For Anthropic:
            ANTHROPIC_API_KEY: Required
            ANTHROPIC_EXTRACTION_MODEL: Optional (default: "claude-sonnet-4-20250514")
            OPENAI_API_KEY: Required for embeddings (or configure local via database)

        For Local Embeddings (ADR-039):
            Configure via database: POST /admin/embedding/config
            See kg_api.embedding_config table for parameters

        For Mock (testing):
            No API keys required
            MOCK_MODE: Optional ("default", "simple", "complex", "empty")
    """
    from .config import is_development_mode, get_config_source
    import logging

    logger = logging.getLogger(__name__)

    # Determine provider and model based on DEVELOPMENT_MODE
    extraction_model = None

    if is_development_mode():
        # Development mode: Use environment variables
        provider_name = provider_name or os.getenv("AI_PROVIDER", "openai").lower()
        # extraction_model will be set by provider constructor from env vars
        logger.debug(f"[DEV MODE] Using .env configuration: provider={provider_name}")
    else:
        # Production mode: Load from database
        from .ai_extraction_config import load_active_extraction_config

        config = load_active_extraction_config()

        if not config:
            raise RuntimeError(
                "No AI extraction configuration found in database. "
                "Either:\n"
                "  1. Set DEVELOPMENT_MODE=true in .env to use environment variables\n"
                "  2. Configure via API: POST /admin/extraction/config\n"
                "  3. Run initialization script: ./scripts/initialize-auth.sh"
            )

        provider_name = provider_name or config['provider']
        extraction_model = config['model_name']
        logger.debug(f"[PROD MODE] Using database configuration: provider={provider_name}, model={extraction_model}")

    # Check for separate embedding provider configuration
    embedding_provider = get_embedding_provider()

    if provider_name == "openai":
        return OpenAIProvider(
            extraction_model=extraction_model,
            embedding_provider=embedding_provider
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            extraction_model=extraction_model,
            embedding_provider=embedding_provider
        )
    elif provider_name == "ollama":
        # Load Ollama-specific config from database (production) or environment (dev)
        if is_development_mode():
            # Dev mode: Read from environment variables
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
            top_p = float(os.getenv("OLLAMA_TOP_P", "0.9"))
            thinking_mode = os.getenv("OLLAMA_THINKING_MODE", "off")
        else:
            # Production mode: Read from database config
            base_url = config.get('base_url') or "http://localhost:11434"
            temperature = config.get('temperature') or 0.1
            top_p = config.get('top_p') or 0.9
            thinking_mode = config.get('thinking_mode') or 'off'
            logger.info(f"🔍 get_provider: thinking_mode={thinking_mode} (from config)")

        return OllamaProvider(
            base_url=base_url,
            extraction_model=extraction_model,
            embedding_provider=embedding_provider,
            temperature=temperature,
            top_p=top_p,
            thinking_mode=thinking_mode
        )
    elif provider_name == "openrouter":
        return OpenRouterProvider(
            extraction_model=extraction_model,
            embedding_provider=embedding_provider,
        )
    elif provider_name == "mock":
        from .mock_ai_provider import MockAIProvider
        mock_mode = os.getenv("MOCK_MODE", "default")
        return MockAIProvider(mode=mock_mode)
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}. Use 'openai', 'anthropic', 'ollama', 'openrouter', or 'mock'")


# Model configurations for reference
AVAILABLE_MODELS = {
    "openai": {
        "extraction": [
            "gpt-4o",           # Latest GPT-4 Omni (recommended)
            "gpt-4o-mini",      # Faster, cheaper GPT-4
            "gpt-4-turbo",      # Previous GPT-4 Turbo
            "o1-preview",       # Reasoning model (slower, more thoughtful)
            "o1-mini",          # Smaller reasoning model
        ],
        "embedding": [
            "text-embedding-3-small",  # 1536 dims (recommended, fast)
            "text-embedding-3-large",  # 3072 dims (more accurate, slower)
            "text-embedding-ada-002",  # Legacy model
        ]
    },
    "anthropic": {
        "extraction": [
            "claude-sonnet-4-20250514",  # Latest Sonnet 4.5 (SOTA, recommended)
            "claude-3-5-sonnet-20241022", # Claude 3.5 Sonnet
            "claude-3-opus-20240229",     # Claude 3 Opus (most capable)
            "claude-3-sonnet-20240229",   # Claude 3 Sonnet (balanced)
            "claude-3-haiku-20240307",    # Claude 3 Haiku (fastest)
        ],
        "embedding": [
            # Anthropic doesn't provide embeddings
            # Falls back to OpenAI text-embedding-3-small
        ]
    },
    "ollama": {
        "extraction": [
            # 7-8B models (recommended for most hardware)
            "mistral:7b-instruct",        # Mistral 7B (balanced, recommended)
            "llama3.1:8b-instruct",       # Llama 3.1 8B (high quality)
            "qwen2.5:7b-instruct",        # Qwen 2.5 7B (excellent reasoning)
            "phi3.5:3.8b-mini-instruct",  # Phi-3.5 Mini (fastest)
            "gemma2:9b-instruct",         # Gemma 2 9B (good quality)

            # 14B models (high-end GPU)
            "qwen2.5:14b-instruct",       # Qwen 2.5 14B (best quality for 16GB VRAM)

            # 70B+ models (professional/enterprise)
            "llama3.1:70b-instruct",      # Llama 3.1 70B (GPT-4 quality)
            "qwen2.5:72b-instruct",       # Qwen 2.5 72B (best reasoning)
            "mixtral:8x7b-instruct",      # Mixtral 8x7B MoE
            "mixtral:8x22b-instruct",     # Mixtral 8x22B MoE
            "deepseek-coder:33b",         # DeepSeek Coder 33B (code-focused)
        ],
        "embedding": [
            # Ollama doesn't provide embeddings
            # Use OpenAI or local embeddings
        ],
        "vision": [
            "llava:7b",                   # LLaVA 7B (image understanding)
            "llava:13b",                  # LLaVA 13B (better quality)
            "bakllava:7b",                # BakLLaVA 7B (alternative)
        ]
    }
}
