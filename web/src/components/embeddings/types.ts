/**
 * Type definitions for Embedding Landscape visualization (ADR-078)
 */

export type ColorScheme = 'ontology' | 'grounding' | 'position';

// Color scale for grounding visualization
export type GroundingScale = 'linear' | 'sqrt' | 'log';

// Color ramps for grounding (diverging tri-color palettes)
export type GroundingColorRamp =
  | 'pink-gray-cyan'    // Default: hot pink → gray → electric cyan
  | 'blue-white-red'    // Classic: cold → neutral → hot
  | 'purple-white-green' // Colorblind-friendly
  | 'brown-white-teal'  // Colorblind-safe, earthy
  | 'purple-white-orange'; // High contrast

// Embedding sources available for projection
export type EmbeddingSource = 'concepts' | 'sources' | 'vocabulary' | 'combined';

// Item types in projections (for different sprites)
export type ProjectionItemType = 'concept' | 'source' | 'vocabulary';

export interface ProjectionConcept {
  concept_id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  grounding_strength: number | null;
  diversity_score: number | null;
  diversity_related_count: number | null;
  ontology?: string;  // Source ontology (for cross-ontology mode)
  item_type?: ProjectionItemType;  // For distinguishing in combined view
}

// Distance metric for projection algorithm
export type DistanceMetric = 'cosine' | 'euclidean';

export interface ProjectionData {
  ontology: string;
  changelist_id: string;
  algorithm: string;
  parameters: {
    n_components: number;
    perplexity: number | null;       // t-SNE: local vs global (5-100)
    n_neighbors: number | null;      // UMAP: local structure
    min_dist: number | null;         // UMAP: cluster tightness
    spread: number | null;           // UMAP: cluster separation
    metric: DistanceMetric | null;   // cosine (angular) or euclidean (L2)
    normalize_l2: boolean | null;    // L2 normalization applied
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
  itemType: ProjectionItemType;
}

export interface OntologySelection {
  ontology: string;
  enabled: boolean;
  color: string;
  conceptCount: number;
  // Which embedding sources are enabled for this ontology (can have multiple)
  enabledSources: {
    concepts: boolean;
    sources: boolean;
    vocabulary: boolean;
  };
}
