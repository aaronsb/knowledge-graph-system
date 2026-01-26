"""
Tests for MockAIProvider.

Verifies that the mock provider:
- Generates deterministic responses
- Returns consistent embeddings
- Works without API keys
- Provides predictable concept extraction
"""

import pytest
from api.app.lib.mock_ai_provider import MockAIProvider, get_mock_provider


def test_mock_provider_initialization():
    """Test that mock provider initializes correctly"""
    provider = MockAIProvider()

    assert provider.get_provider_name() == "Mock"
    assert provider.get_extraction_model() == "mock-gpt-4o"
    assert provider.get_embedding_model() == "mock-embedding-3-small"
    assert provider.validate_api_key() == True  # No API key needed


def test_mock_provider_modes():
    """Test different mock provider modes"""
    # Simple mode
    simple = get_mock_provider("simple")
    simple_result = simple.extract_concepts("Test text.", "")
    assert len(simple_result["result"]["concepts"]) <= 1

    # Complex mode
    complex_provider = get_mock_provider("complex")
    complex_result = complex_provider.extract_concepts("Test text. More text. Even more.", "")
    assert len(complex_result["result"]["concepts"]) > 1

    # Empty mode
    empty = get_mock_provider("empty")
    empty_result = empty.extract_concepts("Test text.", "")
    assert len(empty_result["result"]["concepts"]) == 0


def test_deterministic_embeddings():
    """Test that embeddings are deterministic"""
    provider = MockAIProvider()

    text = "This is a test sentence"

    # Generate embedding twice
    result1 = provider.generate_embedding(text)
    result2 = provider.generate_embedding(text)

    # Should be identical
    assert result1["embedding"] == result2["embedding"]
    assert len(result1["embedding"]) == 1536  # Default dimension

    # Different text should produce different embedding
    result3 = provider.generate_embedding("Different text")
    assert result1["embedding"] != result3["embedding"]


def test_concept_extraction_structure():
    """Test that concept extraction returns valid structure"""
    provider = MockAIProvider()

    text = "Linear thinking involves sequential processing. It contrasts with parallel thinking."
    result = provider.extract_concepts(text, "Extract concepts")

    # Check structure
    assert "result" in result
    assert "tokens" in result

    extraction = result["result"]
    assert "concepts" in extraction
    assert "instances" in extraction
    assert "relationships" in extraction

    # Check concepts have required fields
    if extraction["concepts"]:
        concept = extraction["concepts"][0]
        assert "concept_id" in concept
        assert "label" in concept
        assert "search_terms" in concept


def test_existing_concepts_integration():
    """Test that existing concepts are referenced in extraction"""
    provider = MockAIProvider()

    existing = [
        {"concept_id": "existing-1", "label": "Previous Concept"}
    ]

    text = "New concept builds on previous ideas."
    result = provider.extract_concepts(text, "", existing_concepts=existing)

    relationships = result["result"]["relationships"]

    # Should reference existing concept
    if relationships:
        existing_refs = [r for r in relationships if r.get("to_concept_id") == "existing-1"]
        assert len(existing_refs) > 0


def test_token_counting():
    """Test token usage reporting"""
    provider = MockAIProvider()

    short_text = "Short"
    long_text = "This is a much longer piece of text with many more words."

    short_result = provider.extract_concepts(short_text, "")
    long_result = provider.extract_concepts(long_text, "")

    # Longer text should have more tokens
    assert long_result["tokens"] > short_result["tokens"]


def test_embedding_normalization():
    """Test that embeddings are normalized (unit vectors)"""
    provider = MockAIProvider()

    result = provider.generate_embedding("Test text")
    embedding = result["embedding"]

    # Calculate magnitude
    magnitude = sum(x ** 2 for x in embedding) ** 0.5

    # Should be approximately 1.0 (unit vector)
    assert abs(magnitude - 1.0) < 0.0001


def test_factory_function():
    """Test the get_mock_provider factory function"""
    default = get_mock_provider()
    simple = get_mock_provider("simple")
    complex_provider = get_mock_provider("complex")
    empty = get_mock_provider("empty")

    assert all(p.get_provider_name() == "Mock" for p in [default, simple, complex_provider, empty])
    assert simple.concepts_per_chunk == 1
    assert complex_provider.concepts_per_chunk == 5
    assert empty.concepts_per_chunk == 0


def test_create_test_concept():
    """Test the test concept creation utility"""
    concept = MockAIProvider.create_test_concept(
        "test-id",
        "Test Label",
        ["test", "label"]
    )

    assert concept["concept_id"] == "test-id"
    assert concept["label"] == "Test Label"
    assert concept["search_terms"] == ["test", "label"]


def test_deterministic_by_seed():
    """Test getting deterministic embeddings by seed"""
    provider = MockAIProvider()

    # Same seed should produce same embedding
    emb1 = provider.get_deterministic_embedding("seed123")
    emb2 = provider.get_deterministic_embedding("seed123")
    assert emb1 == emb2

    # Different seed should produce different embedding
    emb3 = provider.get_deterministic_embedding("seed456")
    assert emb1 != emb3


if __name__ == "__main__":
    # Run simple verification
    print("Testing MockAIProvider...")

    provider = get_mock_provider()
    print(f"✓ Provider initialized: {provider.get_provider_name()}")

    text = "Knowledge graphs represent concepts and relationships."
    result = provider.extract_concepts(text, "")
    print(f"✓ Extracted {len(result['result']['concepts'])} concepts")

    embedding_result = provider.generate_embedding(text)
    print(f"✓ Generated {len(embedding_result['embedding'])}-dim embedding")

    print("\nAll basic tests passed!")
