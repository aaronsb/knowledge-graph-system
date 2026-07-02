-- Migration 075: decouple the image embedding slot from the text vector space
-- (ADR-803). Corrects the migration-055 category error.
--
-- Migration 055 modelled the embedding profile as two CO-SPATIAL slots: a text
-- model and an image model sharing one `vector_space`, with
-- chk_image_dimensions_match forcing text_dimensions = image_dimensions. The
-- implicit premise was that image and text embeddings are comparable
-- (cross-modal matching). They are not: the image embedding is stored on Source
-- nodes and never vector-searched or compared to Concept/text embeddings — the
-- concept graph is built entirely from PROSE (the hairpin, ADR-057). The
-- constraint therefore enforces a property the system never uses and forbids
-- otherwise-valid configurations (e.g. a 768-dim text embedder + a 1024-dim
-- image embedder).
--
-- ADR-803: the graph has ONE universal text/prose embedding space; a modality's
-- native embedding (the image vector) is an INDEPENDENT same-modality search
-- index with its own space and dimensions, never compared to the text space.
-- This migration makes the schema express that independence. It does NOT design
-- a general N-modality registry (that is a deferred, non-committal follow-up).

BEGIN;

-- 1. Drop the co-spatiality dimension constraint: the image slot may now have
--    its own dimensions, independent of the text slot.
ALTER TABLE kg_api.embedding_profile
    DROP CONSTRAINT IF EXISTS chk_image_dimensions_match;

-- 2. Give the image slot its own vector_space compatibility key, independent of
--    the profile's text `vector_space`. Nullable: text-only profiles and
--    multimodal profiles (image served by the text model) leave it NULL. This
--    is the image index's OWN space tag, used for same-modality search only —
--    never compared to the text vector_space.
ALTER TABLE kg_api.embedding_profile
    ADD COLUMN IF NOT EXISTS image_vector_space VARCHAR(100);

COMMENT ON COLUMN kg_api.embedding_profile.image_vector_space IS
    'Independent vector_space of the image (modality) embedding index (ADR-803). '
    'NULL for text-only / multimodal profiles. Never compared to text vector_space.';

COMMENT ON COLUMN kg_api.embedding_profile.vector_space IS
    'Compatibility key for the universal TEXT/prose space (concepts, edges, docs, '
    'image-prose). Profiles with the same text vector_space produce comparable '
    'text embeddings. Image embeddings are independent — see image_vector_space (ADR-803).';

INSERT INTO public.schema_migrations (version, name)
VALUES (75, 'decouple_image_embedding_space')
ON CONFLICT (version) DO NOTHING;

COMMIT;
