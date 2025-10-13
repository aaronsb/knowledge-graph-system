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
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


def _load_api_key(provider: str, explicit_key: Optional[str] = None, env_var: Optional[str] = None) -> Optional[str]:
    """
    Load API key with fallback chain (ADR-031).

    Priority order:
    1. Explicit key provided as parameter
    2. Encrypted key from database (system_api_keys table)
    3. Environment variable
    4. None (will raise error in provider __init__)

    Args:
        provider: Provider name ('openai' or 'anthropic')
        explicit_key: API key passed explicitly to constructor
        env_var: Environment variable name (e.g., 'OPENAI_API_KEY')

    Returns:
        API key if found, None otherwise
    """
    # 1. Explicit key takes precedence
    if explicit_key:
        logger.debug(f"Using explicit API key for {provider}")
        return explicit_key

    # 2. Try encrypted key store
    try:
        from .encrypted_keys import get_system_api_key
        from .age_client import AGEClient

        try:
            client = AGEClient()
            key = get_system_api_key(client.conn, provider)
            if key:
                logger.info(f"Loaded encrypted API key for {provider} from database")
                return key
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
    def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text"""
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


class OpenAIProvider(AIProvider):
    """OpenAI provider for GPT models and embeddings"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_model: Optional[str] = None
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

        self.client = OpenAI(api_key=self.api_key)

        # Configurable models with defaults
        self.extraction_model = extraction_model or os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o")
        self.embedding_model = embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

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

    def generate_embedding(self, text: str) -> Dict[str, Any]:
        """Generate embedding using OpenAI embedding models

        Returns dict with 'embedding' (vector) and 'tokens' (usage info)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )

            embedding = response.data[0].embedding

            # Extract token usage
            tokens = 0
            if hasattr(response, 'usage') and response.usage:
                tokens = response.usage.total_tokens

            return {
                "embedding": embedding,
                "tokens": tokens
            }

        except Exception as e:
            raise Exception(f"OpenAI embedding generation failed: {e}")

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

    def get_provider_name(self) -> str:
        return "OpenAI"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        return self.embedding_model

    def validate_api_key(self) -> bool:
        """Validate OpenAI API key by making a simple API call"""
        try:
            # Try to list models (lightweight check)
            self.client.models.list()
            return True
        except Exception as e:
            print(f"OpenAI API key validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available OpenAI models"""
        try:
            models_response = self.client.models.list()
            all_models = [model.id for model in models_response.data]

            # Filter to relevant models
            extraction_models = [m for m in all_models if any(x in m for x in ["gpt-4", "gpt-3.5", "o1"])]
            embedding_models = [m for m in all_models if "embedding" in m]

            return {
                "extraction": extraction_models or AVAILABLE_MODELS["openai"]["extraction"],
                "embedding": embedding_models or AVAILABLE_MODELS["openai"]["embedding"]
            }
        except Exception:
            # Fallback to hardcoded list
            return AVAILABLE_MODELS["openai"]


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

        self.client = Anthropic(api_key=self.api_key)

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

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using the configured embedding provider"""
        return self.embedding_provider.generate_embedding(text)

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

    def get_provider_name(self) -> str:
        return "Anthropic"

    def get_extraction_model(self) -> str:
        return self.extraction_model

    def get_embedding_model(self) -> str:
        return self.embedding_provider.get_embedding_model()

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
            print(f"Anthropic API key validation failed: {e}")
            return False

    def list_available_models(self) -> Dict[str, List[str]]:
        """List available Anthropic models (returns hardcoded list as Anthropic doesn't have a models endpoint)"""
        return AVAILABLE_MODELS["anthropic"]


def get_provider(provider_name: Optional[str] = None) -> AIProvider:
    """
    Factory function to get the configured AI provider.

    Args:
        provider_name: Name of provider ("openai", "anthropic", or "mock")
                      If None, reads from AI_PROVIDER env var (default: "openai")

    Returns:
        Configured AIProvider instance

    Environment Variables:
        AI_PROVIDER: "openai", "anthropic", or "mock" (default: "openai")

        For OpenAI:
            OPENAI_API_KEY: Required
            OPENAI_EXTRACTION_MODEL: Optional (default: "gpt-4o")
            OPENAI_EMBEDDING_MODEL: Optional (default: "text-embedding-3-small")

        For Anthropic:
            ANTHROPIC_API_KEY: Required
            ANTHROPIC_EXTRACTION_MODEL: Optional (default: "claude-sonnet-4-20250514")
            OPENAI_API_KEY: Required for embeddings
            OPENAI_EMBEDDING_MODEL: Optional (default: "text-embedding-3-small")

        For Mock (testing):
            No API keys required
            MOCK_MODE: Optional ("default", "simple", "complex", "empty")
    """
    provider_name = provider_name or os.getenv("AI_PROVIDER", "openai").lower()

    if provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "mock":
        from .mock_ai_provider import MockAIProvider
        mock_mode = os.getenv("MOCK_MODE", "default")
        return MockAIProvider(mode=mock_mode)
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}. Use 'openai', 'anthropic', or 'mock'")


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
    }
}
