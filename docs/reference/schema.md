---
id: 2.R.01
domain: db
mode: reference
---

# Database Schema

Relational schema for the Kappa Graph control plane. The knowledge graph itself (concepts, sources, instances, and their typed edges) lives in the Apache AGE `knowledge_graph` graph; the tables below hold operational state, authorization, and observability around it.

Backed by PostgreSQL 18 with Apache AGE 1.7.0. This page is generated from `schema/00_baseline.sql` and `schema/migrations/*.sql`; do not edit it by hand.

<!-- GENERATED FILE — edit the SQL DDL, then run `make docs-schema`. -->
<!-- Generated: 2026-06-15 -->

## Schemas

| Schema | Purpose | Tables |
|---|---|---|
| `public` | Cross-schema bookkeeping (migration tracking). | 2 |
| `kg_api` | API operational state: jobs, sessions, vocabulary, ontology. | 42 |
| `kg_auth` | Authentication and authorization (dynamic RBAC). | 15 |
| `kg_logs` | Observability: audit trails, metrics, health. | 4 |

## `public`

Cross-schema bookkeeping (migration tracking).

### `graph_metrics`

Change counters for triggering periodic epistemic status measurement

| Column | Type | Constraints | Description |
|---|---|---|---|
| `metric_name` | `VARCHAR(255)` | PK | Unique metric identifier (e.g., vocabulary_change_counter, concept_count) |
| `counter` | `BIGINT` | NOT NULL; DEFAULT 0 | Increments on every change (create/delete/consolidate) - never decrements |
| `last_measured_counter` | `BIGINT` | NOT NULL; DEFAULT 0 | Counter value when epistemic status was last measured |
| `last_measured_at` | `TIMESTAMP` |  | Timestamp when epistemic status was last measured |
| `updated_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Timestamp of last counter increment |
| `notes` | `TEXT` |  |  |

### `schema_migrations`

Tracks applied schema migrations for safe schema evolution - ADR-040

| Column | Type | Constraints | Description |
|---|---|---|---|
| `version` | `INTEGER` | PK | Sequential migration number (001, 002, 003, ...) |
| `name` | `TEXT` | NOT NULL | Descriptive migration name (e.g., baseline, add_embedding_config) |
| `applied_at` | `TIMESTAMP` | NOT NULL; DEFAULT NOW() | Timestamp when migration was applied |

## `kg_api`

API operational state: jobs, sessions, vocabulary, ontology.

### `aggressiveness_profiles`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `profile_name` | `VARCHAR(50)` | PK |  |
| `control_x1` | `FLOAT` | NOT NULL; CHECK (control_x1 >= 0.0 AND control_x1 <= 1.0) |  |
| `control_y1` | `FLOAT` | NOT NULL |  |
| `control_x2` | `FLOAT` | NOT NULL; CHECK (control_x2 >= 0.0 AND control_x2 <= 1.0) |  |
| `control_y2` | `FLOAT` | NOT NULL |  |
| `description` | `TEXT` |  |  |
| `is_builtin` | `BOOLEAN` | DEFAULT FALSE |  |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() |  |
| `updated_at` | `TIMESTAMP` | DEFAULT NOW() |  |

### `ai_extraction_config`

AI extraction provider configuration for runtime-switchable models - ADR-041

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `supports_vision` | `BOOLEAN` | DEFAULT FALSE | Whether the model supports vision/image inputs |
| `supports_json_mode` | `BOOLEAN` | DEFAULT TRUE | Whether the model supports JSON mode for structured outputs |
| `max_tokens` | `INTEGER` |  | Maximum token limit for the model |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |
| `updated_by` | `VARCHAR(100)` |  |  |
| `active` | `BOOLEAN` | DEFAULT TRUE | Only one config can be active at a time (enforced by unique index) |

### `ai_vision_config`

Active vision (image->prose) provider selection — ADR-802 / #378. Selection-only; connectivity reused from per-provider config.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `optional` | `` |  |  |
| `applied` | `to` |  |  |
| `temperature` | `DOUBLE` | CHECK (temperature IS NULL OR (temperature >= 0.0 AND temperature <= 1.0)) |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |
| `updated_by` | `VARCHAR(100)` |  |  |

**Table constraints:**

- `CONSTRAINT ai_vision_config_provider_key UNIQUE (provider)`

### `annealing_options`

Tunable parameters for ontology annealing cycles (ADR-200 Phase 3b).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `key` | `VARCHAR(100)` | PK |  |
| `value` | `TEXT` | NOT NULL |  |
| `description` | `TEXT` |  |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |

### `annealing_pressure_history`

One row per annealing cycle: ecological snapshot + Bezier pressure

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `epoch` | `INT` | NOT NULL |  |
| `total_ontologies` | `INT` | NOT NULL |  |
| `total_concepts` | `INT` | NOT NULL |  |
| `avg_concepts_per_ontology` | `DOUBLE` | NOT NULL |  |
| `pressure_score` | `DOUBLE` | NOT NULL; CHECK (pressure_score >= 0.0 AND pressure_score <= 1.0) |  |
| `pressure_zone` | `VARCHAR(20)` | NOT NULL |  |
| `pressure_recommendation` | `JSONB` | NOT NULL; DEFAULT '{}'::jsonb |  |
| `recorded_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |

### `annealing_proposals`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `proposal_type` | `VARCHAR(20)` | NOT NULL; CHECK (proposal_type IN ('promotion', 'demotion')) |  |
| `ontology_name` | `VARCHAR(200)` | NOT NULL |  |
| `anchor_concept_id` | `VARCHAR(100)` |  |  |
| `mass_score` | `NUMERIC(10,4)` |  |  |
| `coherence_score` | `NUMERIC(10,4)` |  |  |
| `protection_score` | `NUMERIC(10,4)` |  |  |
| `status` | `VARCHAR(20)` | NOT NULL; DEFAULT 'pending'; CHECK (status IN ('pending', 'approved', 'rejected', 'expired')) |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `created_at_epoch` | `INT` | NOT NULL; DEFAULT 0 |  |
| `reviewed_at` | `TIMESTAMPTZ` |  |  |
| `reviewed_by` | `VARCHAR(100)` |  |  |
| `reviewer_notes` | `TEXT` |  |  |
| `expires_at` | `TIMESTAMPTZ` | DEFAULT (NOW() + INTERVAL '7 days') |  |

### `artifacts`

Computed artifact metadata with Garage blob pointers (ADR-083)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `representation` | `VARCHAR(50)` | NOT NULL | Source UI/tool: polarity_explorer, cli, mcp_server, etc. |
| `name` | `VARCHAR(200)` |  |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `expires_at` | `TIMESTAMPTZ` |  |  |
| `metadata` | `JSONB` |  |  |
| `inline_result` | `JSONB` |  | Small results (<10KB) stored inline |
| `garage_key` | `VARCHAR(200)` |  | Pointer to Garage blob for large results |
| `ontology` | `VARCHAR(200)` |  |  |
| `concept_ids` | `TEXT[]` |  | Concept IDs involved in this artifact |

**Table constraints:**

- `CONSTRAINT valid_representation CHECK (representation IN ( 'polarity_explorer', 'embedding_landscape', 'block_builder', 'edge_explorer', 'vocabulary_chord', 'force_graph_2d', 'force_graph_3d', 'report_workspace', 'cli', 'mcp_server', 'api_direct' ))`
- `CONSTRAINT has_content CHECK ( inline_result IS NOT NULL OR garage_key IS NOT NULL )`

### `catalog_edge`

ADR-501: parent->child membership edges projecting canonical :SCOPED_BY (ontology<-document) and :HAS_SOURCE/:APPEARS (document<-concept). A concept may have many parent documents (DAG).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `parent_kind` | `VARCHAR(16)` | NOT NULL |  |
| `child_kind` | `VARCHAR(16)` | NOT NULL |  |
| `graph_epoch` | `INTEGER` | NOT NULL |  |

**Table constraints:**

- `PRIMARY KEY (parent_kind, parent_id, child_kind, child_id)`

### `catalog_node`

ADR-501: materialized identity/metadata for catalog nodes (ontology/document/concept). Source of truth is the AGE graph; rebuilt on graph epoch advance.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `kind` | `VARCHAR(16)` | NOT NULL |  |

**Table constraints:**

- `PRIMARY KEY (kind, node_id)`

### `concept_access_stats`

Node-level access patterns for caching - ADR-025

| Column | Type | Constraints | Description |
|---|---|---|---|
| `concept_id` | `VARCHAR(100)` | PK |  |
| `access_count` | `INTEGER` | DEFAULT 0 |  |
| `last_accessed` | `TIMESTAMPTZ` |  |  |
| `avg_query_time_ms` | `NUMERIC(10,2)` |  |  |
| `queries_as_start` | `INTEGER` | DEFAULT 0 |  |
| `queries_as_result` | `INTEGER` | DEFAULT 0 |  |

### `concept_version_metadata`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `concept_id` | `VARCHAR(100)` | PK |  |
| `created_in_version` | `INTEGER` | FK → kg_api.ontology_versions(version_id) |  |
| `last_modified_version` | `INTEGER` | FK → kg_api.ontology_versions(version_id) |  |

### `edge_usage_stats`

Performance tracking for graph traversals - ADR-025

| Column | Type | Constraints | Description |
|---|---|---|---|
| `from_concept_id` | `VARCHAR(100)` | NOT NULL |  |
| `to_concept_id` | `VARCHAR(100)` | NOT NULL |  |
| `relationship_type` | `VARCHAR(100)` | NOT NULL |  |
| `traversal_count` | `INTEGER` | DEFAULT 0 |  |
| `last_traversed` | `TIMESTAMPTZ` |  |  |
| `avg_query_time_ms` | `NUMERIC(10,2)` |  |  |

**Table constraints:**

- `PRIMARY KEY (from_concept_id, to_concept_id, relationship_type)`

### `embedding_config`

Resource-aware embedding configuration for local and remote models - ADR-039. Includes preset for nomic-embed-text-v1.5.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `embedding_dimensions` | `INTEGER` | NOT NULL |  |
| `precision` | `VARCHAR(20)` | NOT NULL; CHECK (precision IN ('float16', 'float32')) |  |
| `num_threads` | `INTEGER` |  | CPU threads for inference (local provider only) |
| `device` | `VARCHAR(20)` | CHECK (device IN ('cpu', 'cuda', 'mps')) | Compute device: cpu, cuda, or mps (local provider only) |
| `batch_size` | `INTEGER` | DEFAULT 8 | Batch size for embedding generation |
| `normalize_embeddings` | `BOOLEAN` | DEFAULT TRUE |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |
| `updated_by` | `VARCHAR(100)` |  |  |
| `active` | `BOOLEAN` | DEFAULT TRUE | Only one config can be active at a time (enforced by unique constraint) |

### `embedding_generation_jobs`

ADR-045: Tracks embedding generation jobs for audit trail and progress monitoring

| Column | Type | Constraints | Description |
|---|---|---|---|
| `job_id` | `UUID` | PK; DEFAULT gen_random_uuid() |  |
| `processed_count` | `INTEGER` | DEFAULT 0 |  |
| `failed_count` | `INTEGER` | DEFAULT 0 |  |
| `embedding_provider` | `VARCHAR(50)` |  |  |
| `started_at` | `TIMESTAMPTZ` |  |  |
| `completed_at` | `TIMESTAMPTZ` |  |  |
| `duration_ms` | `INTEGER` |  |  |
| `error_message` | `TEXT` |  |  |

### `embedding_profile`

Unified embedding profile with text + image model slots. Replaces embedding_config.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `name` | `VARCHAR(200)` | NOT NULL |  |
| `vector_space` | `VARCHAR(100)` | NOT NULL | Compatibility key for the universal TEXT/prose space (concepts, edges, docs, |
| `text_model_name` | `VARCHAR(200)` | NOT NULL |  |
| `text_loader` | `VARCHAR(50)` | NOT NULL | How to load text model: sentence-transformers, transformers (AutoModel), or api |
| `'transformers'` | `` |  |  |
| `'api'` | `text_revision` |  |  |
| `text_precision` | `VARCHAR(20)` | DEFAULT 'float16' |  |
| `text_trust_remote_code` | `BOOLEAN` | DEFAULT FALSE |  |
| `image_model_name` | `VARCHAR(200)` |  |  |
| `image_loader` | `VARCHAR(50)` |  | How to load image model: sentence-transformers, transformers (AutoModel), or api |
| `image_revision` | `VARCHAR(200)` |  |  |
| `image_dimensions` | `INTEGER` |  |  |
| `image_precision` | `VARCHAR(20)` | DEFAULT 'float16' |  |
| `image_trust_remote_code` | `BOOLEAN` | DEFAULT FALSE |  |
| `max_memory_mb` | `INTEGER` |  |  |
| `num_threads` | `INTEGER` |  |  |
| `batch_size` | `INTEGER` | DEFAULT 8 |  |
| `max_seq_length` | `INTEGER` |  |  |
| `normalize_embeddings` | `BOOLEAN` | DEFAULT TRUE |  |
| `delete_protected` | `BOOLEAN` | DEFAULT FALSE |  |
| `change_protected` | `BOOLEAN` | DEFAULT FALSE |  |
| `created_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |
| `updated_by` | `VARCHAR(100)` |  |  |

**Table constraints:**

- `CONSTRAINT chk_image_loader CHECK ( image_loader IN ('sentence-transformers', 'transformers', 'api') OR image_loader IS NULL )`
- `CONSTRAINT chk_multimodal_no_image CHECK (`
- `CONSTRAINT chk_image_dimensions_match CHECK (`

### `graph_epoch_kinds`

ADR-203: Discriminator for graph_epochs.kind. semantic_wallclock distinguishes events whose occurred_at is semantically primary (ingestion, edit) from those where it is forensic-only (reasoning, annealing).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `kind` | `TEXT` | PK |  |
| `semantic_wallclock` | `BOOLEAN` | NOT NULL | When TRUE, occurred_at is the meaningful timestamp for downstream consumers. When FALSE, occurred_at is recorded for audit/forensics but should not drive time-based queries on the resulting graph state. |
| `description` | `TEXT` |  |  |

### `graph_epochs`

ADR-203: Monotonic event log of graph mutations. Distinct from graph_change_counter (ADR-079) which is a composite cache-invalidation checksum.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `event_id` | `BIGSERIAL` | PK | Monotonic logical-time id. Foreign-keyed by Instance.created_at_event_id. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `kind` | `TEXT` | NOT NULL; CHECK (kind IN ('ingestion', 'reasoning', 'annealing', 'edit')) | ingestion \| reasoning \| annealing \| edit. Determines whether occurred_at is semantically meaningful for the rows attributable to this event. |
| `actor` | `TEXT` |  |  |
| `counter_after` | `BIGINT` |  |  |
| `metadata` | `JSONB` | NOT NULL; DEFAULT '{}'::jsonb |  |

### `ingestion_jobs`

Job queue (replaces SQLite jobs.db) - ADR-014, ADR-024, ADR-100

| Column | Type | Constraints | Description |
|---|---|---|---|
| `job_id` | `VARCHAR(50)` | PK |  |
| `job_type` | `VARCHAR(50)` | NOT NULL |  |
| `status` | `VARCHAR(50)` | NOT NULL; CHECK (status IN ( 'pending', 'awaiting_approval', 'approved', 'queued', 'running', 'completed', 'failed', 'cancelled' )) |  |
| `ontology` | `VARCHAR(200)` | NOT NULL |  |
| `client_id` | `VARCHAR(100)` |  |  |
| `content_hash` | `VARCHAR(80)` |  |  |
| `progress` | `JSONB` |  |  |
| `result` | `JSONB` |  |  |
| `analysis` | `JSONB` |  |  |
| `started_at` | `TIMESTAMPTZ` |  |  |
| `completed_at` | `TIMESTAMPTZ` |  |  |
| `approved_at` | `TIMESTAMPTZ` |  |  |
| `approved_by` | `VARCHAR(100)` |  |  |
| `expires_at` | `TIMESTAMPTZ` |  |  |
| `error_message` | `TEXT` |  |  |

### `jobs`

Unified job queue for all background tasks (ingestion, backup, vocab, scheduled)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `job_id` | `TEXT` | PK | Unique job identifier (UUID) |
| `job_type` | `TEXT` | NOT NULL | Type of job: ingestion, restore, backup, vocab_refresh, vocab_consolidate |
| `content_hash` | `TEXT` |  | SHA256 hash for deduplication (used with ontology to detect duplicates) |
| `ontology` | `TEXT` |  | Target ontology for the job |
| `client_id` | `TEXT` |  | Client identifier for SSE streaming |
| `status` | `TEXT` | NOT NULL | Job status: pending_approval, approved, running, completed, failed, cancelled |
| `progress` | `TEXT` |  | Progress message for UI display |
| `result` | `TEXT` |  | Final result data (JSON) |
| `error` | `TEXT` |  | Error message if failed |
| `created_at` | `TIMESTAMP` | NOT NULL; DEFAULT NOW() |  |
| `started_at` | `TIMESTAMP` |  |  |
| `completed_at` | `TIMESTAMP` |  |  |
| `job_data` | `JSONB` | NOT NULL | Job-specific parameters (JSON) |
| `approved_at` | `TIMESTAMP` |  | When job was approved by user |
| `approved_by` | `TEXT` |  | Who approved the job |
| `expires_at` | `TIMESTAMP` |  | When pending approval expires |
| `processing_mode` | `TEXT` | DEFAULT 'serial' | Execution mode: serial or parallel |
| `created_by` | `VARCHAR(100)` | DEFAULT 'unknown' | User or system identifier that created the job |
| `is_system_job` | `BOOLEAN` | DEFAULT FALSE | True for system-scheduled jobs (cannot be deleted by users) |

### `launcher_config`

| Column | Type | Constraints | Description |
|---|---|---|---|

### `ontology_tombstones`

Positive operator-intent signal that an ontology was deliberately

| Column | Type | Constraints | Description |
|---|---|---|---|
| `name` | `VARCHAR(200)` | PK |  |
| `removed_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `removed_by` | `VARCHAR(100)` |  |  |
| `reason` | `TEXT` |  |  |

### `ontology_versions`

Formal ontology versioning with immutable snapshots - ADR-026

| Column | Type | Constraints | Description |
|---|---|---|---|
| `version_id` | `SERIAL` | PK |  |
| `version_number` | `VARCHAR(20)` | UNIQUE; NOT NULL |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `created_by` | `VARCHAR(100)` |  |  |
| `change_summary` | `TEXT` |  |  |
| `is_active` | `BOOLEAN` | DEFAULT TRUE |  |
| `vocabulary_snapshot` | `JSONB` | NOT NULL |  |
| `types_added` | `TEXT[]` |  |  |
| `types_aliased` | `JSONB` |  |  |
| `types_deprecated` | `TEXT[]` |  |  |
| `backward_compatible` | `BOOLEAN` | DEFAULT TRUE |  |
| `migration_required` | `BOOLEAN` | DEFAULT FALSE |  |

### `platform_config`

Platform lifecycle configuration for operator control plane (ADR-061)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `key` | `VARCHAR(100)` | PK |  |
| `value` | `TEXT` | NOT NULL |  |
| `description` | `TEXT` |  |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |
| `updated_by` | `VARCHAR(100)` | DEFAULT 'system' |  |

### `provider_model_catalog`

Cached model catalog per AI provider with curation and pricing (ADR-800)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `provider` | `VARCHAR(50)` | NOT NULL |  |
| `'anthropic'` | `` |  |  |
| `'ollama'` | `` |  |  |
| `'openrouter'` | `model_id` | NOT NULL |  |
| `'embedding'` | `` |  |  |
| `'vision'` | `` |  |  |
| `'translation'` | `context_length` |  |  |
| `max_completion_tokens` | `INTEGER` |  |  |
| `supports_vision` | `BOOLEAN` | DEFAULT FALSE |  |
| `supports_json_mode` | `BOOLEAN` | DEFAULT FALSE |  |
| `supports_tool_use` | `BOOLEAN` | DEFAULT FALSE |  |
| `supports_streaming` | `BOOLEAN` | DEFAULT TRUE |  |
| `price_completion_per_m` | `NUMERIC` |  |  |
| `price_cache_read_per_m` | `NUMERIC` |  |  |
| `is_default` | `BOOLEAN` | DEFAULT FALSE |  |
| `sort_order` | `INTEGER` | DEFAULT 0 |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |

**Table constraints:**

- `UNIQUE(provider, model_id, category)`

### `pruning_recommendations`

Pending vocabulary management actions - ADR-032

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `relationship_type` | `VARCHAR(100)` | NOT NULL |  |
| `target_type` | `VARCHAR(100)` |  |  |
| `action_type` | `VARCHAR(50)` | NOT NULL; CHECK (action_type IN ('merge', 'prune', 'deprecate', 'skip')) |  |
| `review_level` | `VARCHAR(20)` | NOT NULL; CHECK (review_level IN ('none', 'ai', 'human')) |  |
| `reasoning` | `TEXT` | NOT NULL |  |
| `similarity` | `NUMERIC(4,3)` |  |  |
| `value_score` | `NUMERIC(10,2)` |  |  |
| `metadata` | `JSONB` |  |  |
| `status` | `VARCHAR(50)` | NOT NULL; DEFAULT 'pending'; CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'expired')) |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `reviewed_at` | `TIMESTAMPTZ` |  |  |
| `reviewed_by` | `VARCHAR(100)` |  |  |
| `reviewer_notes` | `TEXT` |  |  |
| `executed_at` | `TIMESTAMPTZ` |  |  |
| `expires_at` | `TIMESTAMPTZ` |  |  |

### `query_definitions`

Saved query recipes that can be re-executed (ADR-083)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `name` | `VARCHAR(200)` | NOT NULL |  |
| `definition_type` | `VARCHAR(50)` | NOT NULL | Type of query: block_diagram, cypher, search, polarity, connection, exploration, program |
| `definition` | `JSONB` | NOT NULL | Query parameters/structure as JSON |
| `owner_id` | `INTEGER` | FK → kg_auth.users(id) |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |

**Table constraints:**

- `CONSTRAINT valid_definition_type CHECK (definition_type IN ( 'block_diagram', 'cypher', 'search', 'polarity', 'connection' ))`

### `rate_limits`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `client_id` | `VARCHAR(100)` | NOT NULL |  |
| `endpoint` | `VARCHAR(200)` | NOT NULL |  |
| `window_start` | `TIMESTAMPTZ` | NOT NULL |  |
| `request_count` | `INTEGER` | NOT NULL; DEFAULT 0 |  |

**Table constraints:**

- `PRIMARY KEY (client_id, endpoint, window_start)`

### `relationship_vocabulary`

Canonical relationship types with embeddings - ADR-025, ADR-032

| Column | Type | Constraints | Description |
|---|---|---|---|
| `relationship_type` | `VARCHAR(100)` | PK |  |
| `description` | `TEXT` |  |  |
| `category` | `VARCHAR(50)` |  |  |
| `added_by` | `VARCHAR(100)` |  |  |
| `added_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `usage_count` | `INTEGER` | DEFAULT 0 |  |
| `is_active` | `BOOLEAN` | DEFAULT TRUE |  |
| `is_builtin` | `BOOLEAN` | DEFAULT FALSE |  |
| `synonyms` | `VARCHAR(100)[]` |  |  |
| `deprecation_reason` | `TEXT` |  |  |

### `scheduled_jobs`

Configuration for scheduled background jobs (ADR-050)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `name` | `VARCHAR(100)` | UNIQUE; NOT NULL | Unique identifier for the scheduled job |
| `launcher_class` | `VARCHAR(255)` | NOT NULL | Python class name in launcher registry (e.g., CategoryRefreshLauncher) |
| `schedule_cron` | `VARCHAR(100)` | NOT NULL | Cron expression for schedule (e.g., "0 */6 * * *" = every 6 hours) |
| `enabled` | `BOOLEAN` | DEFAULT TRUE | Whether this schedule is active (can be disabled on failure) |
| `max_retries` | `INTEGER` | DEFAULT 5 | Max consecutive failures before auto-disabling schedule |
| `retry_count` | `INTEGER` | DEFAULT 0 | Current consecutive failure count (reset on success or skip) |
| `last_run` | `TIMESTAMP` |  | Last time the schedule was checked (success, skip, or failure) |
| `last_success` | `TIMESTAMP` |  | Last time a job was successfully enqueued |
| `last_failure` | `TIMESTAMP` |  | Last time the launcher failed with an exception |
| `next_run` | `TIMESTAMP` |  | Calculated next run time (from cron expression or backoff) |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() |  |
| `updated_at` | `TIMESTAMP` | DEFAULT NOW() |  |

### `schema_migrations`

Tracks applied database migrations for backup/restore compatibility. Schema version is included in backups to ensure restore compatibility when database schema evolves. See ADR-015 for details.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `version` | `INTEGER` | PK | Migration number matching schema/migrations/NNN_*.sql files |
| `description` | `TEXT` | NOT NULL | Human-readable description of what this migration does |
| `applied_at` | `TIMESTAMP` | NOT NULL; DEFAULT NOW() | When this migration was applied to the database |

### `sessions`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `session_id` | `VARCHAR(100)` | PK |  |
| `user_id` | `INTEGER` |  |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL |  |
| `last_activity` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `metadata` | `JSONB` |  |  |

### `skipped_relationships`

Capture layer for unmatched relationship types - ADR-025

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `relationship_type` | `VARCHAR(100)` | NOT NULL |  |
| `from_concept_label` | `VARCHAR(500)` |  |  |
| `to_concept_label` | `VARCHAR(500)` |  |  |
| `job_id` | `VARCHAR(50)` |  |  |
| `ontology` | `VARCHAR(200)` |  |  |
| `first_seen` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `last_seen` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `occurrence_count` | `INTEGER` | DEFAULT 1 |  |
| `sample_context` | `JSONB` |  |  |

**Table constraints:**

- `UNIQUE(relationship_type, from_concept_label, to_concept_label)`

### `source_embeddings`

ADR-068: Embeddings for source text chunks with offset tracking and hash verification

| Column | Type | Constraints | Description |
|---|---|---|---|
| `embedding_id` | `SERIAL` | PK |  |
| `chunk_strategy` | `TEXT` | NOT NULL | Chunking strategy used: sentence, paragraph, semantic, or count |
| `end_offset` | `INTEGER` | NOT NULL; CHECK (end_offset > start_offset) | Character offset in Source.full_text where chunk ends (exclusive) |
| `chunk_text` | `TEXT` | NOT NULL | Actual chunk content stored for verification (should match Source.full_text[start_offset:end_offset]) |
| `embedding_provider` | `TEXT` |  |  |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT CURRENT_TIMESTAMP |  |

### `synonym_clusters`

ADR-046: Tracks groups of synonymous edge types discovered through embedding-based semantic similarity (threshold > 0.85)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `cluster_id` | `UUID` | PK; DEFAULT gen_random_uuid() |  |
| `total_usage_count` | `INTEGER` |  |  |
| `detection_method` | `VARCHAR(50)` | DEFAULT 'embedding_similarity' |  |
| `merge_recommended` | `BOOLEAN` | DEFAULT FALSE |  |
| `merge_completed_at` | `TIMESTAMPTZ` |  |  |

### `system_api_keys`

Encrypted system API keys for LLM providers (ADR-031, ADR-041)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `provider` | `VARCHAR(50)` | PK | Provider name: openai, anthropic |
| `encrypted_key` | `BYTEA` | NOT NULL | Fernet-encrypted API key (AES-128-CBC + HMAC-SHA256) |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Last time key was updated |
| `last_validated_at` | `TIMESTAMPTZ` |  | Timestamp of last validation check (typically at API startup) |
| `validation_error` | `TEXT` |  | Error message from last failed validation attempt |

### `system_initialization_status`

ADR-045: Tracks completion of system initialization tasks like cold start embedding generation

| Column | Type | Constraints | Description |
|---|---|---|---|
| `component` | `VARCHAR(50)` | PK |  |
| `initialized` | `BOOLEAN` | DEFAULT FALSE |  |
| `initialized_at` | `TIMESTAMPTZ` |  |  |
| `initialization_job_id` | `UUID` | FK → kg_api.embedding_generation_jobs(job_id) |  |
| `version` | `VARCHAR(20)` |  |  |
| `metadata` | `JSONB` |  |  |

### `vocabulary_audit`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `relationship_type` | `VARCHAR(100)` |  |  |
| `action` | `VARCHAR(50)` | NOT NULL |  |
| `performed_by` | `VARCHAR(100)` |  |  |
| `performed_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `details` | `JSONB` |  |  |

### `vocabulary_config`

System configuration for automatic vocabulary management (ADR-032)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `key` | `VARCHAR(100)` | PK |  |
| `value` | `TEXT` | NOT NULL |  |
| `description` | `TEXT` |  |  |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `updated_by` | `VARCHAR(100)` |  |  |

### `vocabulary_history`

Detailed vocabulary change tracking with context (ADR-032)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `relationship_type` | `VARCHAR(100)` | NOT NULL |  |
| `action` | `VARCHAR(50)` | NOT NULL; CHECK (action IN ('added', 'merged', 'pruned', 'deprecated', 'reactivated')) |  |
| `performed_by` | `VARCHAR(100)` | NOT NULL |  |
| `performed_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `target_type` | `VARCHAR(100)` |  |  |
| `reason` | `TEXT` |  |  |
| `metadata` | `JSONB` |  |  |
| `aggressiveness` | `NUMERIC(4,3)` |  |  |
| `zone` | `VARCHAR(20)` |  |  |
| `vocab_size_before` | `INTEGER` |  |  |
| `vocab_size_after` | `INTEGER` |  |  |

### `vocabulary_suggestions`

LLM-assisted vocabulary curation suggestions - ADR-026

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `relationship_type` | `VARCHAR(100)` | NOT NULL |  |
| `suggestion_type` | `VARCHAR(50)` | NOT NULL; CHECK (suggestion_type IN ('alias', 'new_type')) |  |
| `confidence` | `NUMERIC(3,2)` | NOT NULL; CHECK (confidence BETWEEN 0 AND 1) |  |
| `suggested_canonical_type` | `VARCHAR(100)` |  |  |
| `suggested_category` | `VARCHAR(50)` |  |  |
| `suggested_description` | `TEXT` |  |  |
| `similar_types` | `JSONB` |  |  |
| `reasoning` | `TEXT` |  |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `reviewed` | `BOOLEAN` | DEFAULT FALSE |  |
| `curator_decision` | `VARCHAR(50)` |  |  |
| `curator_notes` | `TEXT` |  |  |

### `worker_lanes`

Worker lane configuration for database-driven job dispatch (ADR-100)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `name` | `TEXT` | PK |  |
| `job_types` | `TEXT[]` | NOT NULL |  |
| `max_slots` | `INTEGER` | NOT NULL; DEFAULT 1 |  |
| `poll_interval_ms` | `INTEGER` | NOT NULL; DEFAULT 5000 |  |
| `stale_timeout_minutes` | `INTEGER` | NOT NULL; DEFAULT 30 |  |
| `enabled` | `BOOLEAN` | NOT NULL; DEFAULT TRUE |  |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |

### `worker_status`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `worker_id` | `VARCHAR(100)` | PK |  |
| `last_heartbeat` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `current_job_id` | `VARCHAR(50)` |  |  |
| `status` | `VARCHAR(50)` | NOT NULL; CHECK (status IN ('idle', 'running', 'error', 'stopped')) |  |
| `metadata` | `JSONB` |  |  |

## `kg_auth`

Authentication and authorization (dynamic RBAC).

### `api_keys`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `key_hash` | `VARCHAR(255)` | UNIQUE; NOT NULL |  |
| `user_id` | `INTEGER` | FK → kg_auth.users(id) |  |
| `name` | `VARCHAR(200)` |  |  |
| `scopes` | `TEXT[]` |  |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `last_used` | `TIMESTAMPTZ` |  |  |
| `expires_at` | `TIMESTAMPTZ` |  |  |

### `groups`

Group definitions for collaborative access control (ADR-082)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | PK |  |
| `group_name` | `VARCHAR(100)` | UNIQUE; NOT NULL |  |
| `display_name` | `VARCHAR(200)` |  |  |
| `description` | `TEXT` |  |  |
| `is_system` | `BOOLEAN` | DEFAULT FALSE | System groups (public, admins) cannot be deleted |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `created_by` | `INTEGER` | FK → kg_auth.users(id) |  |

### `oauth_access_tokens`

OAuth access tokens issued to clients

| Column | Type | Constraints | Description |
|---|---|---|---|
| `token_hash` | `VARCHAR(255)` | PK | SHA256 hash of the actual token (tokens are not stored in plaintext) |
| `client_id` | `VARCHAR(255)` | NOT NULL; FK → kg_auth.oauth_clients(client_id) |  |
| `user_id` | `INTEGER` | FK → kg_auth.users(id) | NULL for client_credentials grant (machine-to-machine), set for user-delegated grants |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Access tokens expire in 1 hour |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |

### `oauth_authorization_codes`

Temporary authorization codes for OAuth Authorization Code flow (web apps)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `code` | `VARCHAR(255)` | PK |  |
| `client_id` | `VARCHAR(255)` | NOT NULL; FK → kg_auth.oauth_clients(client_id) |  |
| `user_id` | `INTEGER` | NOT NULL; FK → kg_auth.users(id) |  |
| `redirect_uri` | `TEXT` | NOT NULL |  |
| `scopes` | `TEXT[]` |  |  |
| `code_challenge` | `VARCHAR(255)` |  | PKCE code challenge (hash of code verifier) |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Authorization codes expire in 10 minutes |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |

### `oauth_clients`

OAuth 2.0 client applications registered to use the API

| Column | Type | Constraints | Description |
|---|---|---|---|
| `client_id` | `VARCHAR(255)` | PK |  |
| `client_secret_hash` | `VARCHAR(255)` |  |  |
| `NULL` | `for` | NOT NULL |  |
| `client_type` | `VARCHAR(50)` | NOT NULL; CHECK (client_type IN ('public', 'confidential')) | public = no client secret (CLI, web apps), confidential = has client secret (MCP server) |
| `grant_types` | `TEXT[]` | NOT NULL | Allowed OAuth grant types: authorization_code, urn:ietf:params:oauth:grant-type:device_code, client_credentials, refresh_token |
| `created_by` | `INTEGER` | FK → kg_auth.users(id) |  |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |
| `metadata` | `JSONB` | DEFAULT '{}'::jsonb |  |

### `oauth_device_codes`

Device authorization codes for OAuth Device Authorization Grant flow (CLI tools)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `device_code` | `VARCHAR(255)` | PK | Long code used by device for polling |
| `user_code` | `VARCHAR(50)` | UNIQUE; NOT NULL | Human-friendly code displayed to user (e.g., ABCD-1234) |
| `user_id` | `INTEGER` | FK → kg_auth.users(id) |  |
| `status` | `VARCHAR(50)` | DEFAULT 'pending'; CHECK (status IN ('pending', 'authorized', 'denied', 'expired')) |  |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Device codes expire in 10 minutes |

### `oauth_refresh_tokens`

OAuth refresh tokens for long-lived sessions

| Column | Type | Constraints | Description |
|---|---|---|---|
| `token_hash` | `VARCHAR(255)` | PK |  |
| `client_id` | `VARCHAR(255)` | NOT NULL; FK → kg_auth.oauth_clients(client_id) |  |
| `user_id` | `INTEGER` | NOT NULL; FK → kg_auth.users(id) |  |
| `scopes` | `TEXT[]` |  |  |
| `access_token_hash` | `VARCHAR(255)` | FK → kg_auth.oauth_access_tokens(token_hash) |  |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Refresh tokens expire in 7 days (CLI) or 30 days (web) |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() |  |
| `last_used` | `TIMESTAMPTZ` |  | Updated when refresh token is used to obtain new access token |

### `oauth_tokens`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `token_hash` | `VARCHAR(255)` | PK |  |
| `user_id` | `INTEGER` | FK → kg_auth.users(id) |  |
| `provider` | `VARCHAR(50)` |  |  |
| `scopes` | `TEXT[]` |  |  |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL |  |

### `resource_grants`

Instance-level access grants for owned resources (ADR-082)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `resource_type` | `VARCHAR(50)` | NOT NULL | Type: ontology, artifact, report, etc. |
| `resource_id` | `VARCHAR(200)` | NOT NULL | Specific resource identifier |
| `principal_type` | `VARCHAR(20)` | NOT NULL; CHECK (principal_type IN ('user', 'group')) | Grant to user or group |
| `principal_id` | `INTEGER` | NOT NULL |  |
| `permission` | `VARCHAR(20)` | NOT NULL; CHECK (permission IN ('read', 'write', 'admin')) | read, write, or admin access |
| `granted_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `granted_by` | `INTEGER` | FK → kg_auth.users(id) |  |

**Table constraints:**

- `UNIQUE(resource_type, resource_id, principal_type, principal_id, permission)`

### `resources`

Dynamic resource type registry (ADR-028)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `resource_type` | `VARCHAR(100)` | PK |  |
| `description` | `TEXT` |  |  |
| `parent_type` | `VARCHAR(100)` | FK → kg_auth.resources(resource_type) |  |
| `available_actions` | `VARCHAR(50)[]` | NOT NULL |  |
| `supports_scoping` | `BOOLEAN` | DEFAULT FALSE |  |
| `metadata` | `JSONB` | DEFAULT '{}' |  |
| `registered_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `registered_by` | `VARCHAR(100)` |  |  |

### `role_permissions`

Dynamic role permissions with scoping (ADR-028)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `role_name` | `VARCHAR(50)` | NOT NULL; FK → kg_auth.roles(role_name) |  |
| `resource_type` | `VARCHAR(100)` | NOT NULL; FK → kg_auth.resources(resource_type) |  |
| `action` | `VARCHAR(50)` | NOT NULL |  |
| `scope_type` | `VARCHAR(50)` |  |  |
| `scope_id` | `VARCHAR(200)` |  |  |
| `scope_filter` | `JSONB` |  |  |
| `granted` | `BOOLEAN` | NOT NULL; DEFAULT TRUE |  |
| `inherited_from` | `VARCHAR(50)` | FK → kg_auth.roles(role_name) |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `created_by` | `INTEGER` | FK → kg_auth.users(id) |  |

### `roles`

Dynamic role definitions with inheritance (ADR-028)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `role_name` | `VARCHAR(50)` | PK |  |
| `display_name` | `VARCHAR(100)` | NOT NULL |  |
| `description` | `TEXT` |  |  |
| `is_builtin` | `BOOLEAN` | DEFAULT FALSE |  |
| `is_active` | `BOOLEAN` | DEFAULT TRUE |  |
| `parent_role` | `VARCHAR(50)` | FK → kg_auth.roles(role_name) |  |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `created_by` | `INTEGER` |  |  |

### `user_groups`

Group membership assignments (ADR-082)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `user_id` | `INTEGER` | NOT NULL; FK → kg_auth.users(id) |  |
| `group_id` | `INTEGER` | NOT NULL; FK → kg_auth.groups(id) |  |
| `added_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `added_by` | `INTEGER` | FK → kg_auth.users(id) |  |

**Table constraints:**

- `PRIMARY KEY (user_id, group_id)`

### `user_roles`

User role assignments with optional scoping (ADR-028)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `user_id` | `INTEGER` | NOT NULL; FK → kg_auth.users(id) |  |
| `role_name` | `VARCHAR(50)` | NOT NULL; FK → kg_auth.roles(role_name) |  |
| `scope_type` | `VARCHAR(50)` |  |  |
| `scope_id` | `VARCHAR(200)` |  |  |
| `assigned_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `assigned_by` | `INTEGER` | FK → kg_auth.users(id) |  |
| `expires_at` | `TIMESTAMPTZ` |  |  |

**Table constraints:**

- `UNIQUE(user_id, role_name, scope_type, scope_id)`

### `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `username` | `VARCHAR(100)` | UNIQUE; NOT NULL |  |
| `password_hash` | `VARCHAR(255)` | NOT NULL |  |
| `primary_role` | `VARCHAR(50)` | NOT NULL; FK → kg_auth.roles(role_name) | Primary role (backwards compatibility) - user can have additional roles in user_roles table |
| `created_at` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `last_login` | `TIMESTAMPTZ` |  |  |
| `disabled` | `BOOLEAN` | DEFAULT FALSE |  |

## `kg_logs`

Observability: audit trails, metrics, health.

### `api_metrics`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `endpoint` | `VARCHAR(200)` | NOT NULL |  |
| `method` | `VARCHAR(10)` | NOT NULL |  |
| `status_code` | `INTEGER` | NOT NULL |  |
| `duration_ms` | `NUMERIC(10,2)` | NOT NULL |  |
| `client_id` | `VARCHAR(100)` |  |  |
| `error_message` | `TEXT` |  |  |

### `audit_trail`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `user_id` | `INTEGER` |  |  |
| `action` | `VARCHAR(100)` | NOT NULL |  |
| `resource_type` | `VARCHAR(50)` | NOT NULL |  |
| `resource_id` | `VARCHAR(200)` |  |  |
| `details` | `JSONB` |  |  |
| `ip_address` | `INET` |  |  |
| `user_agent` | `TEXT` |  |  |
| `outcome` | `VARCHAR(50)` | NOT NULL; CHECK (outcome IN ('success', 'denied', 'error')) |  |

### `health_checks`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `service` | `VARCHAR(50)` | NOT NULL |  |
| `status` | `VARCHAR(50)` | NOT NULL; CHECK (status IN ('healthy', 'degraded', 'down')) |  |
| `metrics` | `JSONB` |  |  |

### `job_events`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | PK |  |
| `job_id` | `VARCHAR(50)` | NOT NULL |  |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL; DEFAULT NOW() |  |
| `event_type` | `VARCHAR(50)` | NOT NULL |  |
| `details` | `JSONB` |  |  |

## Migration history

Schema evolves through numbered migrations under `schema/migrations/`. Each is recorded in `public.schema_migrations` when applied. The baseline (`00_baseline.sql`) is the consolidated starting point; migrations after it are applied in order.

| # | Migration | ADRs | Description |
|---|---|---|---|
| 1 | baseline | ADR-025, ADR-026, ADR-028, ADR-032, ADR-039, ADR-040 | Baseline schema snapshot (v2.0.0) |
| 3 | add embedding config | ADR-039 | Add resource-aware embedding configuration table for local/remote models |
| 4 | add ai extraction config | ADR-041 | Add AI extraction provider configuration table for runtime-switchable models |
| 5 | add api key validation | ADR-031, ADR-041 | Create system_api_keys table with validation state tracking |
| 6 | add embedding config protection | ADR-039 | Add delete and change protection flags to embedding configurations |
| 7 | add local extraction providers | ADR-042 | Extend AI extraction config to support local inference providers (Ollama, vLLM) |
| 8 | add nomic embedding preset | ADR-039 | Add nomic-embed-text-v1.5 as a pre-configured local embedding option |
| 9 | add thinking mode | ADR-042 | Add thinking_mode parameter for Ollama reasoning models |
| 11 | add grounding metrics | ADR-044, ADR-046 | Add grounding-aware metrics to vocabulary table for ADR-044/046 |
| 12 | add embedding worker support | ADR-045 | Add infrastructure for unified embedding generation (ADR-045) |
| 13 | Add Schema Version Tracking | ADR-015 | Adds schema_migrations table to track applied migrations |
| 14 | Vocabulary as Graph Nodes (ADR-048 Phase 3) | ADR-047, ADR-048 |  |
| 15 | Probabilistic Vocabulary Categorization (ADR-047) | ADR-044, ADR-045, ADR-047 | Adds fields for probabilistic category assignment using embedding similarity. |
| 16 | LLM-Determined Relationship Direction Semantics (ADR-049) | ADR-047, ADR-048, ADR-049 | Adds direction_semantics field for LLM-determined relationship directionality. |
| 17 | Vocabulary Configuration System |  |  |
| 18 | add rate limiting config |  | Add rate limiting and concurrency configuration for AI providers |
| 19 | Scheduled Jobs System | ADR-050 |  |
| 20 | Track Authenticated Users in Jobs | ADR-027, ADR-028, ADR-082 |  |
| 21 | Graph-Based Provenance Tracking | ADR-014, ADR-044, ADR-051 |  |
| 22 | OAuth 2.0 Client Management | ADR-054 | Implements OAuth 2.0 flows (Authorization Code + PKCE, Device Authorization Grant, Client Credentials) |
| 23 | Image Storage Source Properties (ADR-057) | ADR-057 | Extends Source nodes to support multimodal image ingestion with S3-compatible |
| 24 | Add Description Field to Concept Nodes |  |  |
| 25 | Graph Metrics Table |  | Track graph change counters to trigger periodic epistemic status measurement |
| 26 | Add epistemic re-measurement scheduled job | ADR-065 |  |
| 27 | source text embeddings | ADR-068 | Add source text embeddings with offset tracking and hash verification (ADR-068) |
| 28 | Platform Admin Resources and Role (ADR-074) | ADR-074 |  |
| 29 | Fix Role Hierarchy (ADR-074) | ADR-074 |  |
| 30 | Add 'create' action to users resource type | ADR-074 |  |
| 31 | platform config |  | Platform lifecycle configuration for operator-as-control-plane pattern |
| 32 | Add projection refresh scheduled job | ADR-078 |  |
| 33 | Graph Metrics Snapshot Refresh | ADR-079 | Provide reliable graph change detection for projection cache invalidation |
| 34 | User Scoping and Groups (ADR-082) | ADR-082 |  |
| 35 | Artifact Persistence (ADR-083) | ADR-082, ADR-083 |  |
| 36 | Job Artifact Linking (ADR-083 Phase 4) | ADR-083 |  |
| 37 | Grant admin role backup create/restore permissions |  |  |
| 38 | Upgrade admin user to platform_admin | ADR-074 |  |
| 39 | Add metadata column to query_definitions |  |  |
| 40 | Graph CRUD Permissions (ADR-089) | ADR-089 |  |
| 41 | Job RBAC Permissions |  |  |
| 42 | Storage Admin RBAC Permissions |  |  |
| 43 | Backfill content_type and storage_key on DocumentMeta Nodes |  |  |
| 44 | Ontology Graph Nodes (ADR-200 Phase 1) | ADR-200 |  |
| 45 | Ontology Lifecycle Permissions (ADR-200 Phase 2) | ADR-200 |  |
| 46 | Annealing Proposals (ADR-200 Phase 3b) | ADR-200 |  |
| 47 | Annealing cycle infrastructure | ADR-200 |  |
| 48 | Ontology-to-Ontology Edge Types (ADR-200 Phase 5) | ADR-200 |  |
| 49 | Proposal Execution Schema (ADR-200 Phase 4) | ADR-200 |  |
| 50 | Add 'exploration' to query_definitions definition_type |  |  |
| 51 | Create graph_accel extension (if available) | ADR-201 |  |
| 52 | Add 'program' to query_definitions definition_type | ADR-500 |  |
| 53 | Change annealing automation_level default to autonomous |  |  |
| 54 | Add delete action to sources resource |  |  |
| 55 | embedding profile | ADR-039 | Unified embedding profile with text + image model slots |
| 56 | embedding task prefix |  | Add task prefix columns to embedding_profile for purpose-aware embedding |
| 57 | Worker lanes and database-driven job dispatch (ADR-100) | ADR-100 |  |
| 59 | Provider model catalog and OpenRouter support (ADR-800) | ADR-800 |  |
| 60 | Remove hardcoded Ollama catalog seeds (ADR-800) | ADR-800 |  |
| 61 | Allow llama.cpp as an extraction provider | ADR-800 |  |
| 62 | ai_extraction_config becomes one row PER PROVIDER (ADR-800 / #8) | ADR-800 |  |
| 63 | Graph epoch event log (ADR-203) | ADR-079, ADR-203 |  |
| 64 | Replace graph_epochs.kind CHECK constraint with a lookup table. | ADR-203 |  |
| 65 | Raise annealing cadence floors (#402 Defect C) |  |  |
| 66 | Ontology tombstones (#402 Defect B2) |  |  |
| 67 | Annealing Vocabulary v2 (ADR-206) | ADR-200, ADR-206 |  |
| 68 | Annealing Pressure History (#249, ADR-206 §Phase 3) | ADR-200, ADR-206 |  |
| 69 | Vocabulary embedding lifecycle (#420 follow-up) |  | Track vocab embedding generation events independently from vocab membership, |
| 70 | Schedule the VocabEmbeddingLauncher |  |  |
| 71 | Open-registration feature flag (ADR-400, internet-hardening #431) | ADR-400 |  |
| 72 | Grant admin oauth_clients:write (ADR-400, internet-hardening #441) | ADR-400 |  |
| 73 | Catalog Browse Index + RBAC (ADR-501) | ADR-068, ADR-200, ADR-203, ADR-501 |  |
| 74 | ai_vision_config — active vision provider selection (ADR-802 / #378) | ADR-801, ADR-802 |  |
| 75 | decouple the image embedding slot from the text vector space | ADR-057, ADR-803 |  |
| 76 | Trustworthy freshness clock (ADR-207, #384) | ADR-079, ADR-203, ADR-207 |  |
| 77 | Add the 'restore' graph-epoch kind (ADR-102 P5) | ADR-102, ADR-207 |  |
| 78 | seed primordial ontology | ADR-200 | Seed the reserved 'primordial' ontology pool on clean install (#505) |

