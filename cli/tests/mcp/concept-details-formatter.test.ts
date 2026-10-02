/**
 * formatConceptDetails relationship sections (#587)
 *
 * Incoming edges drive grounding_strength (ADR-808), so the details view must
 * show them alongside outgoing edges, with how each edge was made.
 */

import { formatConceptDetails } from '../../src/mcp/formatters/concept';
import type { ConceptDetailsResponse } from '../../src/types';

/** Build a details response with no evidence and the given edges. */
function details(overrides: Partial<ConceptDetailsResponse> = {}): ConceptDetailsResponse {
  return {
    concept_id: 'c_concealment',
    label: 'Concealment breaks the loop',
    search_terms: [],
    documents: ['human-in-the-loop'],
    instances: [],
    relationships: [],
    ...overrides,
  };
}

describe('formatConceptDetails relationships', () => {
  it('should list incoming edges with source concept, type, confidence and provenance', () => {
    const output = formatConceptDetails(details({
      relationships: [
        { to_id: 'c_conflict', to_label: 'Human-AI Conflict', rel_type: 'CAUSES', confidence: 0.9, source: 'llm_extraction' },
      ],
      incoming_relationships: [
        {
          from_id: 'c_revised', from_label: 'Revised transparency claim',
          to_id: 'c_concealment', to_label: 'Concealment breaks the loop',
          rel_type: 'CRITIQUES', confidence: 0.6, source: 'api_creation',
        },
      ],
    }));

    expect(output).toContain('## Outgoing Relationships (1)');
    expect(output).toContain('CAUSES -> Human-AI Conflict (90%, llm_extraction)');
    expect(output).toContain('## Incoming Relationships (1)');
    expect(output).toContain('Revised transparency claim -> CRITIQUES (60%, api_creation)');
  });

  it('should say so when there are no incoming edges', () => {
    const output = formatConceptDetails(details({ incoming_relationships: [] }));
    expect(output).toContain('No outgoing relationships');
    expect(output).toContain('No incoming relationships');
  });

  it('should treat a response without incoming_relationships as having none', () => {
    // Older API servers omit the field entirely
    const output = formatConceptDetails(details());
    expect(output).toContain('No incoming relationships');
  });
});
