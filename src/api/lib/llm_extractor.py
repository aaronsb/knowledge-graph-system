"""
LLM-based concept extraction using configurable AI providers.

Supports OpenAI and Anthropic with model configuration.
"""

import os
from typing import Dict, List, Any, Optional
from src.api.lib.ai_providers import get_provider
from src.api.constants import RELATIONSHIP_TYPES_LIST


# System prompt template for concept extraction
# Note: {existing_concepts_list} will be filled in dynamically per request
EXTRACTION_PROMPT_TEMPLATE = """You are a knowledge graph extraction agent. Your task is to analyze text and extract:

1. **Concepts**: Key ideas, entities, or topics mentioned in the text
2. **Instances**: Specific quotes that evidence each concept
3. **Relationships**: How concepts relate to each other

For each concept, provide:
- concept_id: A unique identifier (e.g., "concept_001", "concept_002", etc.)
- label: A clear, concise name for the concept
- search_terms: Alternative terms/phrases that refer to this concept

For each instance, provide:
- concept_id: The concept this instance evidences
- quote: The exact quote from the text

For relationships between concepts, provide:
- from_concept_id: Source concept (use actual ID from existing concepts if referencing them)
- to_concept_id: Target concept (use actual ID from existing concepts if referencing them)
- relationship_type: One of [{relationship_types}]
- confidence: A score from 0.0 to 1.0 indicating confidence in the relationship

IMPORTANT: When creating relationships to existing concepts, use their actual concept_id from the list below.
When creating relationships between newly extracted concepts, use the concept_001, concept_002 style IDs.

Existing concepts to consider (to avoid duplication and for relationships):
{existing_concepts_list}

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
        Dictionary with 'result' (concepts/instances/relationships), 'tokens', and 'source_id'

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

        # Format existing concepts list for prompt
        if existing_concepts and len(existing_concepts) > 0:
            concepts_lines = []
            for concept in existing_concepts:
                concept_id = concept.get('concept_id', '')
                label = concept.get('label', '')
                concepts_lines.append(f"- {concept_id}: {label}")
            existing_concepts_str = "\n".join(concepts_lines)
        else:
            existing_concepts_str = "None"

        # Format the prompt template with relationship types and existing concepts
        formatted_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            relationship_types=RELATIONSHIP_TYPES_LIST,  # Already a comma-separated string
            existing_concepts_list=existing_concepts_str
        )

        # Extract concepts using provider (returns dict with 'result' and 'tokens')
        response = provider.extract_concepts(
            text=text,
            system_prompt=formatted_prompt,
            existing_concepts=existing_concepts
        )

        # Extract result and tokens
        result = response.get("result", {})
        tokens = response.get("tokens", 0)

        # Add source_id context
        result["source_id"] = source_id

        return {
            "result": result,
            "tokens": tokens
        }

    except Exception as e:
        raise Exception(f"Concept extraction failed: {e}")


# DEPRECATED: generate_embedding() has been removed
# All embedding generation now goes through the unified EmbeddingWorker (ADR-045)
#
# Migration:
#   from src.api.services.embedding_worker import get_embedding_worker
#   worker = get_embedding_worker()
#   result = worker.generate_concept_embedding(text)
#
# Benefits:
#   - Automatic queueing for local embeddings (prevents GPU contention)
#   - Unified interface for all embedding operations
#   - Better resource management


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
