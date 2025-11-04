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
- description: A factual 1-2 sentence statement defining what this concept IS (not opinion, just objective definition)
- search_terms: Alternative terms/phrases that refer to this concept

For each instance, provide:
- concept_id: The concept this instance evidences
- quote: The exact quote from the text

For relationships between concepts, you must determine DIRECTION SEMANTICS based on frame of reference:

**OUTWARD (from → to):** The "from" concept ACTS on the "to" concept
  Examples:
  - "Meditation ENABLES enlightenment" → from=meditation (actor), to=enlightenment (target), direction="outward"
  - "Ego PREVENTS awareness" → from=ego (blocker), to=awareness (blocked), direction="outward"
  - "Wheel PART_OF car" → from=wheel (component), to=car (whole), direction="outward"

**INWARD (from ← to):** The "from" concept RECEIVES/RESULTS from the "to" concept
  Examples:
  - "Suffering RESULTS_FROM attachment" → from=suffering (result), to=attachment (cause), direction="inward"
  - "Temperature MEASURED_BY thermometer" → from=temperature (measured), to=thermometer (measurer), direction="inward"

**BIDIRECTIONAL:** Symmetric relationship (both directions equivalent)
  Examples:
  - "Ego SIMILAR_TO self-identity" → direction="bidirectional"
  - "Apple COMPETES_WITH Microsoft" → direction="bidirectional"

**Key Principle:** Consider which concept is the SUBJECT of the sentence:
- Active voice: "A enables B" → A is actor (outward)
- Passive voice: "A is caused by B" → A is receiver (inward)
- Mutual: "A competes with B" = "B competes with A" → bidirectional

**Existing vocabulary types with direction patterns:**{direction_examples}

For each relationship, provide:
- from_concept_id: The subject concept (use actual ID from existing concepts if referencing them)
- to_concept_id: The object concept (use actual ID from existing concepts if referencing them)
- relationship_type: One of [{relationship_types}] or a clear new type
- direction_semantics: One of ["outward", "inward", "bidirectional"]
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
      "description": "A concise factual statement about what this concept represents.",
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
      "direction_semantics": "outward",
      "confidence": 0.9
    }}
  ]
}}

Only return the JSON object, no additional text."""


def _get_direction_examples(age_client) -> str:
    """
    Query vocabulary to build dynamic direction examples for prompt.

    Returns formatted string with existing types grouped by direction.
    """
    if age_client is None:
        # Fallback to static examples if no client available
        return """
  OUTWARD: CAUSES, ENABLES, PREVENTS (examples from seed vocabulary)
  INWARD: RESULTS_FROM, MEASURED_BY (examples from seed vocabulary)
  BIDIRECTIONAL: SIMILAR_TO, EQUIVALENT_TO (examples from seed vocabulary)"""

    try:
        # Query vocabulary graph for types with direction
        query = """
        MATCH (v:VocabType)
        WHERE v.is_active = 't' AND v.direction_semantics IS NOT NULL
        RETURN v.name as type_name,
               v.direction_semantics as direction,
               v.usage_count as usage_count
        ORDER BY v.direction_semantics, v.usage_count DESC
        """
        results = age_client._execute_cypher(query)

        # Group by direction
        outward = []
        inward = []
        bidirectional = []

        for row in results:
            type_name = row.get('type_name', '')
            direction = row.get('direction', 'outward')
            usage_count = row.get('usage_count', 0)

            # Format: TYPE (N uses) or just TYPE if no uses
            if usage_count and int(str(usage_count)) > 0:
                formatted = f"{type_name} ({usage_count} uses)"
            else:
                formatted = type_name

            if direction == 'outward':
                outward.append(formatted)
            elif direction == 'inward':
                inward.append(formatted)
            elif direction == 'bidirectional':
                bidirectional.append(formatted)

        # Build formatted examples (limit to top 10 per direction)
        lines = []
        if outward:
            lines.append(f"  OUTWARD: {', '.join(outward[:10])}")
        if inward:
            lines.append(f"  INWARD: {', '.join(inward[:10])}")
        if bidirectional:
            lines.append(f"  BIDIRECTIONAL: {', '.join(bidirectional[:10])}")

        if lines:
            return "\n" + "\n".join(lines)
        else:
            # No vocabulary with direction yet, use seed examples
            return """
  OUTWARD: CAUSES, ENABLES, PREVENTS (seed examples)
  INWARD: RESULTS_FROM, MEASURED_BY (seed examples)
  BIDIRECTIONAL: SIMILAR_TO, EQUIVALENT_TO (seed examples)"""

    except Exception as e:
        # Fallback to static examples on error
        return """
  OUTWARD: CAUSES, ENABLES, PREVENTS (examples)
  INWARD: RESULTS_FROM, MEASURED_BY (examples)
  BIDIRECTIONAL: SIMILAR_TO, EQUIVALENT_TO (examples)"""


def extract_concepts(
    text: str,
    source_id: str,
    existing_concepts: Optional[List[Dict[str, Any]]] = None,
    provider_name: Optional[str] = None,
    age_client = None
) -> Dict[str, Any]:
    """
    Extract concepts, instances, and relationships from text using configured AI provider.

    Args:
        text: The text to analyze
        source_id: Identifier for the source document/paragraph
        existing_concepts: List of existing concepts to avoid duplication
                          Each dict should have 'concept_id' and 'label'
        provider_name: Override provider (default: from AI_PROVIDER env var)
        age_client: Optional AGEClient for dynamic vocabulary examples (ADR-049)

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

        # Get dynamic direction examples from vocabulary (ADR-049)
        direction_examples = _get_direction_examples(age_client)

        # Format the prompt template with relationship types and existing concepts
        formatted_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            relationship_types=RELATIONSHIP_TYPES_LIST,  # Already a comma-separated string
            existing_concepts_list=existing_concepts_str,
            direction_examples=direction_examples
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
