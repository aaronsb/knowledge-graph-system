-- Migration: 081_modernbert_siglip2_default_profile
-- Description: Seed the ModernBERT + SigLIP 2 embedding profile and make it the default (ADR-814)
-- Date: 2026-09-18
--
-- The seeded `Nomic v1.5` profile (migration 056, baseline) loads both of its
-- models through the nomic-bert-2048 remote code, which is broken on
-- transformers 5.x (#565). ADR-814 replaces the default pair with two native
-- models, no trust_remote_code on either slot:
--
--   text  : nomic-ai/modernbert-embed-base        768d, 8192 tokens, sentence-transformers
--   image : google/siglip2-base-patch16-256       768d, independent image index (ADR-803)
--
-- Installs whose ACTIVE profile is the seeded Nomic row are switched to the
-- new profile here, mirroring activate_embedding_config(): protection flags
-- move, vocabulary embeddings are marked stale. Any other active profile
-- (OpenAI, custom) is left untouched. The Nomic row stays for history and for
-- restores of old backups; it is inactive and unprotected afterwards.
--
-- Existing text embeddings (concepts, sources, vocabulary) are in the old
-- vector space until the operator re-embeds:
--   POST /admin/embedding/regenerate?embedding_type=all&only_incompatible=true

BEGIN;

INSERT INTO kg_api.embedding_profile (
    name, vector_space, multimodal,
    text_provider, text_model_name, text_loader, text_revision,
    text_dimensions, text_precision, text_trust_remote_code,
    text_query_prefix, text_document_prefix,
    image_provider, image_model_name, image_loader, image_revision,
    image_dimensions, image_precision, image_trust_remote_code, image_vector_space,
    device, max_memory_mb, num_threads, batch_size, max_seq_length, normalize_embeddings,
    active, delete_protected, change_protected, updated_by
)
SELECT
    'ModernBERT + SigLIP 2', 'modernbert-embed-base', FALSE,
    'local', 'nomic-ai/modernbert-embed-base', 'sentence-transformers', NULL,
    768, 'float16', FALSE,
    'search_query: ', 'search_document: ',
    'local', 'google/siglip2-base-patch16-256', 'transformers', NULL,
    768, 'float16', FALSE, 'siglip2-base-p16-256',
    'cpu', 512, 4, 8, 8192, TRUE,
    FALSE, FALSE, FALSE, 'migration-081'
WHERE NOT EXISTS (
    SELECT 1 FROM kg_api.embedding_profile
    WHERE text_model_name = 'nomic-ai/modernbert-embed-base'
      AND image_model_name = 'google/siglip2-base-patch16-256'
);

DO $$
DECLARE
    new_id      INTEGER;
    nomic_id    INTEGER;
    stale_count INTEGER;
BEGIN
    SELECT id INTO new_id FROM kg_api.embedding_profile
    WHERE text_model_name = 'nomic-ai/modernbert-embed-base'
      AND image_model_name = 'google/siglip2-base-patch16-256'
    ORDER BY id LIMIT 1;

    -- The seeded Nomic profile, only if it is what is active right now.
    SELECT id INTO nomic_id FROM kg_api.embedding_profile
    WHERE active = TRUE
      AND text_provider = 'local'
      AND text_model_name = 'nomic-ai/nomic-embed-text-v1.5';

    IF nomic_id IS NULL THEN
        IF NOT EXISTS (SELECT 1 FROM kg_api.embedding_profile WHERE active = TRUE) THEN
            -- Fresh database (baseline seeds Nomic active, so this branch is
            -- for hand-built or emptied tables): activate the new default.
            UPDATE kg_api.embedding_profile
            SET active = TRUE, delete_protected = TRUE, change_protected = TRUE,
                updated_at = CURRENT_TIMESTAMP, updated_by = 'migration-081'
            WHERE id = new_id;
            RAISE NOTICE 'Migration 081: no active profile; activated ModernBERT + SigLIP 2 (id %)', new_id;
        ELSE
            RAISE NOTICE 'Migration 081: active profile is not the seeded Nomic row; left unchanged. ModernBERT + SigLIP 2 seeded inactive as id %', new_id;
        END IF;
        RETURN;
    END IF;

    UPDATE kg_api.embedding_profile
    SET active = FALSE, delete_protected = FALSE, change_protected = FALSE,
        updated_at = CURRENT_TIMESTAMP, updated_by = 'migration-081'
    WHERE id = nomic_id;

    UPDATE kg_api.embedding_profile
    SET active = TRUE, delete_protected = TRUE, change_protected = TRUE,
        updated_at = CURRENT_TIMESTAMP, updated_by = 'migration-081'
    WHERE id = new_id;

    -- Same side effect as activate_embedding_config(): the universal text
    -- space changed, so vocabulary embeddings are stale (ADR-803 §4).
    UPDATE kg_api.relationship_vocabulary
    SET embedding_validation_status = 'stale'
    WHERE embedding IS NOT NULL
      AND embedding_validation_status != 'stale';
    GET DIAGNOSTICS stale_count = ROW_COUNT;

    RAISE NOTICE 'Migration 081: switched active embedding profile % (Nomic v1.5) -> % (ModernBERT + SigLIP 2); % vocabulary embeddings marked stale', nomic_id, new_id, stale_count;
    RAISE NOTICE 'Migration 081: existing concept/source/vocabulary embeddings are in the old vector space. After the API is up, run: POST /admin/embedding/regenerate?embedding_type=all&only_incompatible=true';
END $$;

INSERT INTO public.schema_migrations (version, name)
VALUES (81, 'modernbert_siglip2_default_profile')
ON CONFLICT (version) DO NOTHING;

COMMIT;
