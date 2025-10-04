"""
LLM-based concept extraction using OpenAI.

Handles concept extraction from text and embedding generation.
"""

import os
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI


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
- instance_id: A unique identifier (e.g., "instance_001")
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
      "instance_id": "instance_001",
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
    existing_concepts: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Extract concepts, instances, and relationships from text using OpenAI GPT-4.

    Args:
        text: The text to analyze
        source_id: Identifier for the source document/paragraph
        existing_concepts: List of existing concepts to avoid duplication
                          Each dict should have 'concept_id' and 'label'

    Returns:
        Dictionary with 'concepts', 'instances', and 'relationships' keys

    Raises:
        ValueError: If OPENAI_API_KEY not set
        Exception: If API call fails or response parsing fails
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Format existing concepts for the prompt
    existing_str = "None"
    if existing_concepts:
        existing_str = "\n".join([
            f"- {c.get('concept_id', 'unknown')}: {c.get('label', 'unknown')}"
            for c in existing_concepts
        ])

    prompt = EXTRACTION_PROMPT.format(existing_concepts=existing_str)

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": f"Text to analyze:\n\n{text}"
                }
            ],
            max_tokens=4096,
            temperature=0.3,  # Lower temperature for more consistent extraction
            response_format={"type": "json_object"}  # Force JSON response
        )

        # Extract text content from response
        response_text = response.choices[0].message.content

        # Parse JSON response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from OpenAI: {e}\nResponse: {response_text}")

        # Validate structure
        if not isinstance(result, dict):
            raise Exception(f"Expected dict response, got {type(result)}")

        # Ensure all required keys exist
        result.setdefault("concepts", [])
        result.setdefault("instances", [])
        result.setdefault("relationships", [])

        # Add source_id context
        result["source_id"] = source_id

        return result

    except Exception as e:
        raise Exception(f"Concept extraction failed: {e}")


def generate_embedding(text: str) -> List[float]:
    """
    Generate vector embedding for text using OpenAI.

    Args:
        text: Text to embed

    Returns:
        List of floats representing the embedding vector

    Raises:
        ValueError: If OPENAI_API_KEY not set
        Exception: If API call fails
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    try:
        client = OpenAI(api_key=api_key)

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )

        return response.data[0].embedding

    except Exception as e:
        raise Exception(f"Embedding generation failed: {e}")
