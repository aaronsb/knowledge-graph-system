# ontology

> Auto-generated from MCP tool schema

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "create" (new ontology), "rename" (change name), "delete" (remove), "lifecycle" (set state), "scores" (cached scores), "score" (recompute one), "score_all" (recompute all), "candidates" (top concepts), "affinity" (cross-ontology overlap), "edges" (ontology-to-ontology edges), "reassign" (move sources), "dissolve" (non-destructive demotion), "proposals" (list annealing proposals), "proposal_review" (approve/reject proposal), "annealing_cycle" (trigger annealing cycle)
  - Allowed values: `list`, `info`, `files`, `create`, `rename`, `delete`, `lifecycle`, `scores`, `score`, `score_all`, `candidates`, `affinity`, `edges`, `reassign`, `dissolve`, `proposals`, `proposal_review`, `annealing_cycle`
- `ontology_name` (`string`) - Ontology name (required for info, files, create, rename, delete)
- `description` (`string`) - What this knowledge domain covers (for create action)
- `new_name` (`string`) - New ontology name (required for rename action)
- `lifecycle_state` (`string`) - Target lifecycle state (required for lifecycle action)
  - Allowed values: `active`, `pinned`, `frozen`
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`
- `target_ontology` (`string`) - Target ontology for reassign/dissolve actions
- `source_ids` (`array`) - Source IDs to move (for reassign action)
- `limit` (`number`) - Max results for candidates/affinity (default: 20/10)
- `proposal_id` (`number`) - Proposal ID (for proposal_review action)
- `status` (`string`) - Filter proposals by status, or review status (approved/rejected)
  - Allowed values: `pending`, `approved`, `rejected`, `executing`, `executed`, `failed`
- `proposal_type` (`string`) - Filter proposals by type
  - Allowed values: `promotion`, `demotion`
- `notes` (`string`) - Review notes (for proposal_review action)
- `dry_run` (`boolean`) - Preview candidates without proposals (for annealing_cycle)
  - Default: `false`
- `demotion_threshold` (`number`) - Protection score below which to consider demotion (default: 0.15)
- `promotion_min_degree` (`number`) - Minimum concept degree for promotion candidacy (default: 10)
- `max_proposals` (`number`) - Maximum proposals per annealing cycle (default: 5)

---
