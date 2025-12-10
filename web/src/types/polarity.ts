/**
 * Type definitions for Polarity Axis Analysis (ADR-070)
 */

export interface PolarityAxisParams {
  positive_pole_id: string;
  negative_pole_id: string;
  candidate_ids?: string[];
  auto_discover?: boolean;
  max_candidates?: number;
  max_hops?: number;
}

export interface PoleInfo {
  concept_id: string;
  label: string;
  grounding: number;
  description: string | null;
}

export interface AxisInfo {
  positive_pole: PoleInfo;
  negative_pole: PoleInfo;
  magnitude: number;
  axis_quality: 'strong' | 'weak';
}

export interface ConceptAlignment {
  positive_pole_similarity: number;
  negative_pole_similarity: number;
}

export interface ProjectedConcept {
  concept_id: string;
  label: string;
  position: number;
  axis_distance: number;
  direction: 'positive' | 'negative' | 'neutral';
  grounding: number;
  alignment: ConceptAlignment;
}

export interface DirectionDistribution {
  positive: number;
  negative: number;
  neutral: number;
}

export interface Statistics {
  total_concepts: number;
  position_range: [number, number];
  mean_position: number;
  std_deviation: number;
  mean_axis_distance: number;
  direction_distribution: DirectionDistribution;
}

export interface GroundingCorrelation {
  pearson_r: number;
  p_value: number;
  interpretation: string;
  strength?: 'weak' | 'moderate' | 'strong';
  direction?: 'positive' | 'negative' | 'none';
}

export interface PolarityAxisResponse {
  success: boolean;
  axis: AxisInfo;
  projections: ProjectedConcept[];
  statistics: Statistics;
  grounding_correlation: GroundingCorrelation;
}

export interface ConceptSearchResult {
  concept_id: string;
  label: string;
  description?: string;
  similarity?: number;
  score?: number;          // Alias for similarity in some API responses
  evidence_count?: number; // Number of evidence instances
}

export interface ConceptSearchResponse {
  results: ConceptSearchResult[];
  total: number;
  // Smart search recommendation fields (optional)
  below_threshold_count?: number;
  suggested_threshold?: number;
  top_match?: ConceptSearchResult;
}
