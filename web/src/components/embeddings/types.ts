/**
 * Type definitions for Embedding Landscape visualization (ADR-078)
 */

export interface ProjectionConcept {
  concept_id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  grounding_strength: number | null;
  diversity_score: number | null;
  diversity_related_count: number | null;
}

export interface ProjectionData {
  ontology: string;
  changelist_id: string;
  algorithm: string;
  parameters: {
    n_components: number;
    perplexity: number | null;
    n_neighbors: number | null;
    min_dist: number | null;
  };
  computed_at: string;
  concepts: ProjectionConcept[];
  statistics: {
    concept_count: number;
    computation_time_ms: number;
    embedding_dims: number;
    grounding_range: [number, number] | null;
    diversity_range: [number, number] | null;
  };
}

export interface EmbeddingPoint {
  id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  ontology: string;
  grounding: number | null;
  color: string;
}

export interface OntologySelection {
  ontology: string;
  enabled: boolean;
  color: string;
  conceptCount: number;
}
