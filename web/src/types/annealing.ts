/**
 * Ontology annealing lifecycle types (ADR-200 / ADR-206 / ADR-703).
 *
 * Mirrors the Pydantic models in api/app/models/ontology.py.
 */

/**
 * ADR-206 closed action vocabulary plus the Opus-tier meta-action.
 * The server normalizes legacy `promotion` / `demotion` rows to
 * CLEAVE / DISSOLVE before they reach the UI, but the type stays
 * `string` to remain permissive on inbound payloads.
 */
export type ProposalType =
  | 'CLEAVE'
  | 'DISSOLVE'
  | 'MERGE'
  | 'RENAME'
  | 'NO_ACTION'
  | 'ESCALATE'
  | 'ADJUST_CONTROL'
  | string;

export type ProposalKind = 'ontology' | 'control' | string;

export interface AnnealingProposal {
  id: number;
  proposal_type: ProposalType;
  proposal_kind?: ProposalKind;
  ontology_name: string;
  anchor_concept_id?: string | null;
  target_ontology?: string | null;
  reasoning: string;
  /** ADR-206 §1 verb-specific parameter shape. */
  params?: Record<string, unknown> | null;
  mass_score?: number | null;
  coherence_score?: number | null;
  protection_score?: number | null;
  status: string;
  created_at: string;
  created_at_epoch: number;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  reviewer_notes?: string | null;
  executed_at?: string | null;
  execution_result?: Record<string, unknown> | null;
  execution_job_id?: string | null;
  suggested_name?: string | null;
  suggested_description?: string | null;
}

export interface AnnealingProposalListResponse {
  proposals: AnnealingProposal[];
  count: number;
}

export interface AnnealingCycleResult {
  proposals_generated: number;
  demotion_candidates: number;
  promotion_candidates: number;
  scores_updated: number;
  centroids_updated: number;
  edges_created: number;
  edges_deleted: number;
  cycle_epoch: number;
  dry_run: boolean;
}

/** Health, configuration, and schedule of the annealing loop (ADR-703). */
export interface AnnealingStatus {
  enabled: boolean;
  automation_level: string;
  options: Record<string, string>;
  schedule_cron?: string | null;
  schedule_enabled: boolean;
  last_run?: string | null;
  last_success?: string | null;
  last_failure?: string | null;
  next_run?: string | null;
  current_epoch: number;
  last_annealing_epoch: number;
  epoch_interval: number;
  ontology_count: number;
  proposals_by_status: Record<string, number>;
}

export interface AnnealingProposalFilters {
  status?: string;
  proposal_type?: string;
  ontology?: string;
  limit?: number;
}
