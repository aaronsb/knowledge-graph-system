-- Migration: 079_search_default_threshold
-- Description: Configurable default similarity threshold for concept search (ADR-508)
-- Date: 2026-07-01
--
-- Root cause (ADR-508): the active embedding model (nomic-embed-text-v1.5) has a
-- compressed cosine distribution — irrelevant/gibberish queries score ~0.47-0.51,
-- relevant matches ~0.60-0.65. The "right" threshold is model- and corpus-dependent,
-- so it belongs in configuration rather than hardcoded across three clients (API,
-- CLI, FUSE) whose split defaults (0.7 / 0.7 / 0.5) produced the noise problem.
--
-- Clients omit min_similarity to inherit this server-side default; /query/search
-- reads it via kg_api.get_platform_config('search_default_similarity_threshold').

BEGIN;

-- Seed the default. 0.6 sits below relevant matches (~0.62) and above the nomic
-- gibberish floor (~0.51). Tunable at runtime via the admin API / kg config /
-- operator configure.py without a redeploy.
INSERT INTO kg_api.platform_config (key, value, description) VALUES
    ('search_default_similarity_threshold', '0.6',
     'Default min cosine similarity for /query/search when a client omits min_similarity (0.0-1.0). ADR-508.')
ON CONFLICT (key) DO NOTHING;

INSERT INTO public.schema_migrations (version, name)
VALUES (79, 'search_default_threshold')
ON CONFLICT (version) DO NOTHING;

COMMIT;
