-- Migration 073: Catalog Browse Index + RBAC (ADR-501)
--
-- Backs the catalog browse facade — a deterministic projection of the
-- ontology -> document -> concept hierarchy. The graph (Apache AGE) is the
-- source of truth; these relational tables are a materialized read index that
-- makes listing fast: child-counts without per-readdir aggregation, and
-- fragment (substring) filtering via pg_trgm without scanning the graph.
--
-- Why two tables: the hierarchy is a DAG, not a tree. A concept appears in
-- MANY documents and ontologies (automatic cross-domain merging is a defining
-- feature, ADR-068/ADR-200), so a concept has many parents. Membership is
-- therefore an edge relation, separate from node identity:
--
--   catalog_node  — one row per distinct node (identity, name, own child_count)
--   catalog_edge  — parent -> child membership edges (the DAG)
--
-- Freshness model (ADR-501 §5, ADR-203): every row carries the
-- graph_change_counter (graph epoch) it was built at. The facade compares the
-- index epoch to kg_api.get_graph_epoch() — the same signal artifact freshness
-- uses (migration 035) — and rebuilds when the graph has advanced. Annealing
-- (ADR-200) mutates the hierarchy autonomously, so counts may briefly lag a
-- cycle and then self-heal. Membership is always rebuilt live from canonical
-- :SCOPED_BY / :HAS_SOURCE / :APPEARS edges — never from the Source.document
-- denormalized string.
--
-- Idempotent: safe to run multiple times.

BEGIN;

-- =============================================================================
-- Extension: pg_trgm for fragment / substring matching on node names
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- Catalog Node Table — node identity + own metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS kg_api.catalog_node (
    kind          VARCHAR(16)  NOT NULL,   -- 'ontology' | 'document' | 'concept'
    node_id       TEXT         NOT NULL,   -- ontology_id | document_id | concept_id
    name          TEXT         NOT NULL,   -- display label
    name_lower    TEXT         NOT NULL,   -- lower(name) for case-insensitive trigram match
    child_count   INTEGER      NOT NULL DEFAULT 0,  -- direct children this node has
    content_type  VARCHAR(32),             -- document nodes: 'document'|'image'|future media
    properties    JSONB        NOT NULL DEFAULT '{}'::jsonb,  -- kind-specific extras
    graph_epoch   INTEGER      NOT NULL,   -- graph_change_counter when this row was built
    indexed_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (kind, node_id)
);

COMMENT ON TABLE kg_api.catalog_node IS
'ADR-501: materialized identity/metadata for catalog nodes (ontology/document/concept). Source of truth is the AGE graph; rebuilt on graph epoch advance.';
COMMENT ON COLUMN kg_api.catalog_node.child_count IS
'Number of direct children (documents-in-ontology, concepts-in-document); 0 for leaf concepts.';
COMMENT ON COLUMN kg_api.catalog_node.graph_epoch IS
'graph_change_counter at build time; compared to kg_api.get_graph_epoch() for staleness.';

-- Root-level listing (ontologies) and per-kind scans, ordered by name.
CREATE INDEX IF NOT EXISTS idx_catalog_node_kind
    ON kg_api.catalog_node (kind, name);

-- Fragment / substring filter on names (case-insensitive) across all nodes.
CREATE INDEX IF NOT EXISTS idx_catalog_node_name_trgm
    ON kg_api.catalog_node USING gin (name_lower gin_trgm_ops);

-- =============================================================================
-- Catalog Edge Table — parent -> child membership (the DAG)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kg_api.catalog_edge (
    parent_kind   VARCHAR(16)  NOT NULL,   -- 'ontology' | 'document'
    parent_id     TEXT         NOT NULL,
    child_kind    VARCHAR(16)  NOT NULL,   -- 'document' | 'concept'
    child_id      TEXT         NOT NULL,
    graph_epoch   INTEGER      NOT NULL,
    PRIMARY KEY (parent_kind, parent_id, child_kind, child_id)
);

COMMENT ON TABLE kg_api.catalog_edge IS
'ADR-501: parent->child membership edges projecting canonical :SCOPED_BY (ontology<-document) and :HAS_SOURCE/:APPEARS (document<-concept). A concept may have many parent documents (DAG).';

-- List a parent's children: the hot path. Join to catalog_node for name/filter.
CREATE INDEX IF NOT EXISTS idx_catalog_edge_parent
    ON kg_api.catalog_edge (parent_kind, parent_id, child_kind);

-- Reverse lookup: which parents does a child belong to (breadcrumbs).
CREATE INDEX IF NOT EXISTS idx_catalog_edge_child
    ON kg_api.catalog_edge (child_kind, child_id);

-- =============================================================================
-- RBAC: register the 'catalog' resource and grant read broadly
-- =============================================================================
-- Browse ("what is in the graph?") is the most basic read capability. Every
-- authenticated role gets catalog:read, mirroring the read-only baseline that
-- read_only holds for graph objects (migration 040). No scoping at the resource
-- level: the facade applies per-row ownership/visibility at query time where
-- relevant.

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES (
    'catalog',
    'Hierarchical browse of ontologies, documents, and concepts (ADR-501)',
    ARRAY['read'],
    FALSE,
    'system'
)
ON CONFLICT (resource_type) DO NOTHING;

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('read_only',      'catalog', 'read', 'global', NULL, TRUE),
    ('contributor',    'catalog', 'read', 'global', NULL, TRUE),
    ('curator',        'catalog', 'read', 'global', NULL, TRUE),
    ('admin',          'catalog', 'read', 'global', NULL, TRUE),
    ('platform_admin', 'catalog', 'read', 'global', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Record Migration
-- =============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (73, 'catalog_index')
ON CONFLICT (version) DO NOTHING;

DO $$
BEGIN
    RAISE NOTICE 'Migration 073: catalog browse index (node + edge) + RBAC installed';
END $$;

COMMIT;
