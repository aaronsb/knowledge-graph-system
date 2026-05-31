/**
 * Vocabulary administration types (ADR-701).
 *
 * Mirrors the Pydantic models in api/app/models/vocabulary.py. The vocabulary
 * consolidation cycle is the sibling of ontology annealing (ADR-200) — these
 * types back the Vocabulary admin tab cohort (loop / pressure / config /
 * actions), parallel to the annealing types in ./annealing.ts.
 */

/**
 * Vocabulary pressure zone (ADR-032 / ZoneEnum). Lowercase to match the API.
 * Kept as a permissive string union so alternate labels don't break typing.
 */
export type VocabularyZone =
  | 'comfort'
  | 'watch'
  | 'merge'
  | 'mixed'
  | 'emergency'
  | 'block'
  | string;

/** Current vocabulary status — mirrors VocabularyStatusResponse. */
export interface VocabularyStatus {
  vocab_size: number;
  vocab_min: number;
  vocab_max: number;
  vocab_emergency: number;
  aggressiveness: number;
  zone: VocabularyZone;
  builtin_types: number;
  custom_types: number;
  categories: number;
  profile: string;
}

/** Full durable vocabulary configuration (admin view) — mirrors VocabularyConfigDetail. */
export interface VocabularyConfig {
  vocab_min: number;
  vocab_max: number;
  vocab_emergency: number;
  pruning_mode: string;
  aggressiveness_profile: string;
  auto_expand_enabled: boolean;
  synonym_threshold_strong: number;
  synonym_threshold_moderate: number;
  low_value_threshold: number;
  consolidation_similarity_threshold: number;
  embedding_model: string;
  updated_at?: string | null;
  updated_by?: string | null;
  // Computed fields
  current_size?: number | null;
  zone?: VocabularyZone | null;
  aggressiveness?: number | null;
}

/** Aggressiveness profile Bézier control points — mirrors AggressivenessProfile. */
export interface AggressivenessProfile {
  profile_name: string;
  control_x1: number;
  control_y1: number;
  control_x2: number;
  control_y2: number;
  description?: string | null;
  is_builtin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/**
 * The four worker-backed vocabulary operations dispatchable as jobs
 * (ADR-701 §1a). Maps server-side to job_type via VOCAB_JOB_KIND_TO_TYPE:
 *   consolidate → vocab_consolidate
 *   refresh     → vocab_refresh
 *   remeasure   → epistemic_remeasurement
 *   embed       → vocab_embedding
 */
export type VocabJobKind = 'consolidate' | 'refresh' | 'remeasure' | 'embed';

/** Result of POST /vocabulary/jobs — returns immediately; poll job status. */
export interface VocabularyJobDispatchResponse {
  job_id: string;
  kind: VocabJobKind;
  job_type: string;
  status: string;
}
