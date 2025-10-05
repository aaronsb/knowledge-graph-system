"""
LLM-based concept extraction using configurable AI providers.

Supports OpenAI and Anthropic with model configuration.
"""

import os
from typing import Dict, List, Any, Optional
from ingest.ai_providers import get_provider


# System prompt for concept extraction
EXTRACTION_PROMPT = """You are a knowledge graph extraction agent. Your task is to analyze text and extract:

1. **Concepts**: Key ideas, entities, or topics mentioned in the text
2. **Instances**: Specific quotes that evidence each concept
3. **Relationships**: How concepts relate to each other

For each concept, provide:
- concept_id: A unique identifier (e.g., "concept_001")
- label: A clear, concise name for the concept
- search_terms: Alternative terms/phrases that refer to this concept

For each instance, provide:
- concept_id: The concept this instance evidences
- quote: The exact quote from the text

For relationships between concepts, provide:
- from_concept_id: Source concept
- to_concept_id: Target concept
- relationship_type: One of [IMPLIES, CONTRADICTS, SUPPORTS, PART_OF]
- confidence: A score from 0.0 to 1.0 indicating confidence in the relationship

Consider the following existing concepts when extracting to avoid duplication:
{existing_concepts}

Return your response as a JSON object with this structure:
{{
  "concepts": [
    {{
      "concept_id": "concept_001",
      "label": "Concept Name",
      "search_terms": ["term1", "term2", "term3"]
    }}
  ],
  "instances": [
    {{
      "concept_id": "concept_001",
      "quote": "Exact quote from text"
    }}
  ],
  "relationships": [
    {{
      "from_concept_id": "concept_001",
      "to_concept_id": "concept_002",
      "relationship_type": "IMPLIES",
      "confidence": 0.9
    }}
  ]
}}

Only return the JSON object, no additional text."""


def extract_concepts(
    text: str,
    source_id: str,
    existing_concepts: Optional[List[Dict[str, Any]]] = None,
    provider_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract concepts, instances, and relationships from text using configured AI provider.

    Args:
        text: The text to analyze
        source_id: Identifier for the source document/paragraph
        existing_concepts: List of existing concepts to avoid duplication
                          Each dict should have 'concept_id' and 'label'
        provider_name: Override provider (default: from AI_PROVIDER env var)

    Returns:
        Dictionary with 'concepts', 'instances', and 'relationships' keys

    Raises:
        ValueError: If API key not set
        Exception: If API call fails or response parsing fails

    Environment Variables:
        AI_PROVIDER: "openai" or "anthropic" (default: "openai")
        OPENAI_API_KEY / ANTHROPIC_API_KEY: Required based on provider
        OPENAI_EXTRACTION_MODEL / ANTHROPIC_EXTRACTION_MODEL: Optional model override
    """
    try:
        # Get configured provider
        provider = get_provider(provider_name)

        # Extract concepts using provider
        result = provider.extract_concepts(
            text=text,
            system_prompt=EXTRACTION_PROMPT,
            existing_concepts=existing_concepts
        )

        # Add source_id context
        result["source_id"] = source_id

        return result

    except Exception as e:
        raise Exception(f"Concept extraction failed: {e}")


def generate_embedding(
    text: str,
    provider_name: Optional[str] = None
) -> List[float]:
    """
    Generate vector embedding for text using configured AI provider.

    Args:
        text: Text to embed
        provider_name: Override provider (default: from AI_PROVIDER env var)

    Returns:
        List of floats representing the embedding vector

    Raises:
        ValueError: If API key not set
        Exception: If API call fails

    Environment Variables:
        AI_PROVIDER: "openai" or "anthropic" (default: "openai")
        OPENAI_API_KEY: Required (even for Anthropic, which uses OpenAI for embeddings)
        OPENAI_EMBEDDING_MODEL: Optional embedding model override
    """
    try:
        # Get configured provider
        provider = get_provider(provider_name)

        # Generate embedding using provider
        return provider.generate_embedding(text)

    except Exception as e:
        raise Exception(f"Embedding generation failed: {e}")


def validate_provider_config(provider_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate provider configuration and return status info.

    Args:
        provider_name: Provider to validate (default: from AI_PROVIDER env var)

    Returns:
        Dictionary with validation results:
        {
            "provider": "openai",
            "api_key_valid": True,
            "extraction_model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
            "available_models": {...}
        }
    """
    try:
        provider = get_provider(provider_name)

        result = {
            "provider": provider.get_provider_name(),
            "extraction_model": provider.get_extraction_model(),
            "embedding_model": provider.get_embedding_model(),
            "api_key_valid": provider.validate_api_key(),
            "available_models": provider.list_available_models()
        }

        return result

    except Exception as e:
        return {
            "error": str(e),
            "provider": provider_name or os.getenv("AI_PROVIDER", "openai")
        }
