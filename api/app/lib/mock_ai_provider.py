"""
Mock AI Provider for testing.

Provides deterministic, predictable responses without requiring API keys.
Useful for unit tests, integration tests, and development without live LLM calls.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
from .ai_providers import AIProvider


class MockAIProvider(AIProvider):
    """
    Mock AI provider that returns deterministic responses.

    Features:
    - No API keys required
    - Deterministic embeddings based on text hash
    - Configurable concept extraction responses
    - Consistent token usage reporting
    - Perfect for testing without LLM API costs

    Usage:
        # Basic usage
        provider = MockAIProvider()

        # With custom configuration
        provider = MockAIProvider(
            embedding_dimension=1536,
            extraction_model="mock-gpt-4",
            concepts_per_chunk=3
        )

        # For specific test scenarios
        provider = MockAIProvider(mode="simple")  # Minimal concepts
        provider = MockAIProvider(mode="complex")  # Rich concept graph
    """

    def __init__(
        self,
        embedding_dimension: int = 1536,
        extraction_model: str = "mock-gpt-4o",
        embedding_model: str = "mock-embedding-3-small",
        concepts_per_chunk: int = 3,
        mode: str = "default"
    ):
        """
        Initialize mock provider.

        Args:
            embedding_dimension: Vector dimension (default 1536 for OpenAI compatibility)
            extraction_model: Model name to report
            embedding_model: Embedding model name to report
            concepts_per_chunk: Number of concepts to generate per extraction
            mode: Preset configuration ("default", "simple", "complex", "empty")
        """
        self.embedding_dimension = embedding_dimension
        self.extraction_model_name = extraction_model
        self.embedding_model_name = embedding_model
        self.concepts_per_chunk = concepts_per_chunk
        self.mode = mode

        # Apply mode presets
        if mode == "simple":
            self.concepts_per_chunk = 1
        elif mode == "complex":
            self.concepts_per_chunk = 5
        elif mode == "empty":
            self.concepts_per_chunk = 0

    def extract_concepts(
        self,
        text: str,
        system_prompt: str,
        existing_concepts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate mock concept extraction results.

        Creates deterministic concepts based on text content:
        - Concept IDs are hashed from text chunks
        - Labels are derived from text keywords
        - Relationships are generated between concepts
        - Instances include text quotes

        Args:
            text: Text to "extract" concepts from
            system_prompt: Ignored (for interface compatibility)
            existing_concepts: Optional list of existing concepts to reference

        Returns:
            Dict with 'result' (extracted data) and 'tokens' (usage)
        """
        if self.mode == "empty":
            return {
                "result": {
                    "concepts": [],
                    "instances": [],
                    "relationships": []
                },
                "tokens": self._calculate_mock_tokens(text)
            }

        # Generate deterministic concepts from text
        concepts = []
        instances = []
        relationships = []

        # Split text into sentences for variety
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        for i in range(min(self.concepts_per_chunk, len(sentences))):
            sentence = sentences[i] if i < len(sentences) else text[:100]

            # Generate deterministic concept ID from sentence hash
            concept_hash = hashlib.md5(sentence.encode()).hexdigest()[:12]
            concept_id = f"mock-concept-{concept_hash}"

            # Extract "label" from first few words
            words = sentence.split()[:3]
            label = " ".join(words).title()

            # Create concept
            concept = {
                "concept_id": concept_id,
                "label": label,
                "search_terms": words[:2],
                "description": f"Mock concept extracted from: {sentence[:50]}..."
            }
            concepts.append(concept)

            # Create instance (evidence)
            instance = {
                "concept_id": concept_id,
                "quote": sentence[:200],  # First 200 chars as quote
                "relevance": 0.9
            }
            instances.append(instance)

            # Create relationships between concepts
            if i > 0 and len(concepts) > 1:
                # Link to previous concept
                relationship = {
                    "from_concept_id": concepts[i-1]["concept_id"],
                    "to_concept_id": concept_id,
                    "relationship_type": "RELATES_TO",
                    "confidence": 0.85
                }
                relationships.append(relationship)

        # Optionally reference existing concepts
        if existing_concepts and concepts:
            # Link first new concept to first existing concept
            relationship = {
                "from_concept_id": concepts[0]["concept_id"],
                "to_concept_id": existing_concepts[0].get("concept_id", "unknown"),
                "relationship_type": "BUILDS_ON",
                "confidence": 0.75
            }
            relationships.append(relationship)

        result = {
            "concepts": concepts,
            "instances": instances,
            "relationships": relationships
        }

        return {
            "result": result,
            "tokens": self._calculate_mock_tokens(text)
        }

    def generate_embedding(self, text: str, purpose: str = "document") -> Dict[str, Any]:
        """
        Generate deterministic embedding vector from text.

        Uses text hash to create consistent vectors:
        - Same text always produces same embedding
        - Vectors are normalized (unit length)
        - Compatible with cosine similarity

        Args:
            text: Text to embed

        Returns:
            Dict with 'embedding' (vector) and 'tokens' (usage)
        """
        # Generate deterministic vector from text hash
        text_hash = hashlib.sha256(text.encode()).digest()

        # Convert hash bytes to floats in range [-1, 1]
        embedding = []
        for i in range(self.embedding_dimension):
            # Use hash bytes cyclically
            byte_index = i % len(text_hash)
            byte_value = text_hash[byte_index]
            # Normalize to [-1, 1]
            normalized = (byte_value / 255.0) * 2 - 1
            embedding.append(normalized)

        # Normalize vector to unit length for cosine similarity
        magnitude = sum(x ** 2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return {
            "embedding": embedding,
            "tokens": len(text.split())  # Simple token approximation
        }

    def get_provider_name(self) -> str:
        """Return mock provider name"""
        return "Mock"

    def get_extraction_model(self) -> str:
        """Return mock extraction model name"""
        return self.extraction_model_name

    def get_embedding_model(self) -> str:
        """Return mock embedding model name"""
        return self.embedding_model_name

    def validate_api_key(self) -> bool:
        """Mock validation always succeeds (no API key needed)"""
        return True

    def list_available_models(self) -> Dict[str, List[str]]:
        """Return mock model list"""
        return {
            "extraction": [
                "mock-gpt-4o",
                "mock-gpt-4o-mini",
                "mock-claude-sonnet-4"
            ],
            "embedding": [
                "mock-embedding-3-small",
                "mock-embedding-3-large"
            ]
        }

    def translate_to_prose(self, prompt: str, code: str) -> Dict[str, Any]:
        """
        Mock translation of code/diagram to prose.

        Returns deterministic prose based on input content.

        Args:
            prompt: Translation prompt (specific to content type)
            code: Code/diagram content to translate

        Returns:
            Dict with 'text' (prose translation) and 'tokens' (usage info)
        """
        prose = f"Mock prose translation of code block ({len(code)} chars): {code[:100]}"
        return {
            "text": prose,
            "tokens": self._calculate_mock_tokens(prompt + code)
        }

    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Mock image description.

        Returns deterministic description based on image data size.

        Args:
            image_data: Raw image bytes
            prompt: Description prompt

        Returns:
            Dict with 'text' (description) and 'tokens' (usage info)
        """
        description = f"Mock image description ({len(image_data)} bytes). Prompt: {prompt[:100]}"
        return {
            "text": description,
            "tokens": self._calculate_mock_tokens(prompt)
        }

    def _calculate_mock_tokens(self, text: str) -> int:
        """
        Calculate mock token count.

        Uses simple word-based approximation:
        - 1 word ≈ 1.3 tokens (rough estimate)
        """
        word_count = len(text.split())
        return int(word_count * 1.3)

    # Utility methods for testing

    def set_mode(self, mode: str):
        """
        Change mock mode dynamically.

        Args:
            mode: "default", "simple", "complex", or "empty"
        """
        self.mode = mode
        if mode == "simple":
            self.concepts_per_chunk = 1
        elif mode == "complex":
            self.concepts_per_chunk = 5
        elif mode == "empty":
            self.concepts_per_chunk = 0
        else:
            self.concepts_per_chunk = 3

    def get_deterministic_embedding(self, seed: str) -> List[float]:
        """
        Get a specific deterministic embedding by seed.

        Useful for testing similarity calculations.

        Args:
            seed: String seed for vector generation

        Returns:
            Normalized embedding vector
        """
        result = self.generate_embedding(seed)
        return result["embedding"]

    @staticmethod
    def create_test_concept(
        concept_id: str,
        label: str,
        search_terms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a test concept dictionary.

        Useful for setting up test scenarios with existing concepts.

        Args:
            concept_id: Unique concept identifier
            label: Human-readable label
            search_terms: Optional search terms

        Returns:
            Concept dictionary
        """
        return {
            "concept_id": concept_id,
            "label": label,
            "search_terms": search_terms or label.lower().split(),
            "description": f"Test concept: {label}"
        }


# Convenience function for tests
def get_mock_provider(mode: str = "default") -> MockAIProvider:
    """
    Create a mock provider with preset configuration.

    Args:
        mode: "default", "simple", "complex", or "empty"

    Returns:
        Configured MockAIProvider instance

    Examples:
        # Default mock provider
        provider = get_mock_provider()

        # Minimal concepts for simple tests
        provider = get_mock_provider("simple")

        # Rich concept graph for complex tests
        provider = get_mock_provider("complex")

        # Empty responses for edge case tests
        provider = get_mock_provider("empty")
    """
    return MockAIProvider(mode=mode)
