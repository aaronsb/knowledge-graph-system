# API Endpoint Authentication Audit

**Generated:** Wed Nov  5 07:07:39 AM CST 2025

**Total Endpoints:** 112

## Summary

| Category | Count |
|----------|-------|
| Public | 54 |
| Authenticated | 6 |
| Role Based | 0 |
| Permission Based | 0 |
| Unclear | 52 |

## Public Endpoints (54)

| Method | Path | Auth Type | Name |
|--------|------|-----------|------|
| HEAD,GET | `/openapi.json` | none | openapi |
| HEAD,GET | `/docs` | none | swagger_ui_html |
| HEAD,GET | `/docs/oauth2-redirect` | none | swagger_ui_redirect |
| HEAD,GET | `/redoc` | none | redoc_html |
| POST | `/auth/register` | none | register_user |
| PUT | `/auth/me` | none | update_current_user_profile |
| GET | `/users` | none | list_users |
| POST | `/auth/oauth/clients/personal` | none | create_personal_oauth_client |
| POST | `/auth/oauth/clients/personal/new` | none | create_additional_personal_oauth_client |
| DELETE | `/auth/oauth/clients/personal/{client_id}` | none | delete_personal_oauth_client |
| GET | `/auth/oauth/clients/personal` | none | list_personal_oauth_clients |
| POST | `/auth/oauth/clients` | none | create_oauth_client |
| GET | `/auth/oauth/clients` | none | list_oauth_clients |
| GET | `/auth/oauth/clients/{client_id}` | none | get_oauth_client |
| PATCH | `/auth/oauth/clients/{client_id}` | none | update_oauth_client |
| DELETE | `/auth/oauth/clients/{client_id}` | none | delete_oauth_client |
| POST | `/auth/oauth/clients/{client_id}/rotate-secret` | none | rotate_client_secret |
| GET | `/auth/oauth/authorize` | none | authorize |
| POST | `/auth/oauth/login-and-authorize` | none | login_and_authorize |
| POST | `/auth/oauth/device` | none | device_authorization |
| GET | `/auth/oauth/device-status/{user_code}` | none | get_device_code_status |
| POST | `/auth/oauth/token` | none | token_endpoint |
| POST | `/auth/oauth/revoke` | none | revoke_token |
| GET | `/auth/oauth/tokens` | none | list_tokens |
| DELETE | `/auth/oauth/tokens/{token_hash}` | none | revoke_token_by_hash |
| GET | `/rbac/resources` | none | list_resources |
| POST | `/rbac/resources` | none | create_resource |
| GET | `/rbac/resources/{resource_type}` | none | get_resource |
| PUT | `/rbac/resources/{resource_type}` | none | update_resource |
| DELETE | `/rbac/resources/{resource_type}` | none | delete_resource |
| GET | `/rbac/roles` | none | list_roles |
| POST | `/rbac/roles` | none | create_role |
| GET | `/rbac/permissions` | none | list_permissions |
| POST | `/rbac/permissions` | none | create_permission |
| GET | `/rbac/user-roles/{user_id}` | none | list_user_roles |
| POST | `/rbac/user-roles` | none | assign_user_role |
| DELETE | `/rbac/user-roles/{assignment_id}` | none | revoke_user_role |
| POST | `/rbac/check-permission` | none | check_user_permission |
| GET | `/ingest/image/health` | none | check_image_ingestion_health |
| GET | `/sources/{source_id}/image` | none | get_source_image |
| GET | `/sources/{source_id}` | none | get_source |
| POST | `/query/search` | none | search_concepts |
| GET | `/query/concept/{concept_id}` | none | get_concept_details |
| POST | `/query/related` | none | find_related_concepts |
| POST | `/query/connect` | none | find_connection |
| POST | `/query/connect-by-search` | none | find_connection_by_search |
| POST | `/query/cypher` | none | execute_cypher_query |
| GET | `/database/stats` | none | get_database_stats |
| GET | `/database/info` | none | get_database_info |
| GET | `/database/health` | none | check_database_health |
| GET | `/embedding/config` | none | get_embedding_config |
| GET | `/extraction/config` | none | get_extraction_config |
| GET | `/` | none | root |
| GET | `/health` | none | health |

## Authenticated Endpoints (6)

| Method | Path | Auth Type | Name |
|--------|------|-----------|------|
| GET | `/jobs/{job_id}` | user | get_job_status |
| GET | `/jobs` | user | list_jobs |
| DELETE | `/jobs/{job_id}` | user | cancel_job |
| POST | `/jobs/{job_id}/approve` | user | approve_job |
| DELETE | `/jobs` | user | clear_all_jobs |
| GET | `/jobs/{job_id}/stream` | user | stream_job_progress |

## Unclear Endpoints (52)

| Method | Path | Auth Type | Name |
|--------|------|-----------|------|
| GET | `/users/me` | none | get_current_user_from_oauth |
| GET | `/users/{user_id}` | none | get_user |
| PUT | `/users/{user_id}` | none | update_user |
| DELETE | `/users/{user_id}` | none | delete_user |
| GET | `/rbac/roles/{role_name}` | none | get_role |
| PUT | `/rbac/roles/{role_name}` | none | update_role |
| DELETE | `/rbac/roles/{role_name}` | none | delete_role |
| DELETE | `/rbac/permissions/{permission_id}` | none | delete_permission |
| POST | `/ingest` | none | ingest_document |
| POST | `/ingest/text` | none | ingest_text |
| POST | `/ingest/image` | none | ingest_image |
| GET | `/ontology/` | none | list_ontologies |
| GET | `/ontology/{ontology_name}` | none | get_ontology_info |
| GET | `/ontology/{ontology_name}/files` | none | get_ontology_files |
| DELETE | `/ontology/{ontology_name}` | none | delete_ontology |
| POST | `/ontology/{ontology_name}/rename` | none | rename_ontology |
| GET | `/admin/status` | none | get_system_status |
| GET | `/admin/backups` | none | list_backups |
| POST | `/admin/backup` | none | create_backup |
| POST | `/admin/restore` | none | restore_backup |
| GET | `/admin/scheduler/status` | none | get_scheduler_status |
| POST | `/admin/scheduler/cleanup` | none | trigger_scheduler_cleanup |
| POST | `/admin/keys/{provider}` | none | set_api_key |
| GET | `/admin/keys` | none | list_api_keys |
| DELETE | `/admin/keys/{provider}` | none | delete_api_key |
| POST | `/admin/regenerate-concept-embeddings` | none | regenerate_concept_embeddings |
| GET | `/vocabulary/status` | none | get_vocabulary_status |
| GET | `/vocabulary/types` | none | list_edge_types |
| POST | `/vocabulary/types` | none | add_edge_type |
| POST | `/vocabulary/merge` | none | merge_edge_types |
| POST | `/vocabulary/consolidate` | none | consolidate_vocabulary |
| POST | `/vocabulary/generate-embeddings` | none | generate_embeddings |
| GET | `/vocabulary/category-scores/{relationship_type}` | none | get_category_scores |
| POST | `/vocabulary/refresh-categories` | none | refresh_categories |
| GET | `/vocabulary/similar/{relationship_type}` | none | get_similar_types |
| GET | `/vocabulary/analyze/{relationship_type}` | none | analyze_vocabulary_type |
| GET | `/vocabulary/config` | none | get_vocabulary_config |
| GET | `/admin/vocabulary/config` | none | get_vocabulary_config_detail |
| PUT | `/admin/vocabulary/config` | none | update_vocabulary_config_endpoint |
| GET | `/admin/vocabulary/profiles` | none | list_profiles |
| GET | `/admin/vocabulary/profiles/{profile_name}` | none | get_profile |
| POST | `/admin/vocabulary/profiles` | none | create_profile |
| DELETE | `/admin/vocabulary/profiles/{profile_name}` | none | delete_profile |
| GET | `/admin/embedding/config` | none | get_embedding_config_detail |
| POST | `/admin/embedding/config` | none | create_embedding_config |
| POST | `/admin/embedding/config/reload` | none | reload_embedding_model |
| GET | `/admin/embedding/configs` | none | list_embedding_configs |
| POST | `/admin/embedding/config/{config_id}/protect` | none | protect_embedding_config |
| DELETE | `/admin/embedding/config/{config_id}` | none | delete_embedding_config_endpoint |
| POST | `/admin/embedding/config/{config_id}/activate` | none | activate_embedding_config_endpoint |
| GET | `/admin/extraction/config` | none | get_extraction_config_detail |
| POST | `/admin/extraction/config` | none | update_extraction_config |

## ⚠️ Endpoints Requiring Review

These endpoints may need authentication:

| Method | Path | Current Status |
|--------|------|----------------|
| GET | `/users/me` | ❌ NO AUTH |
| GET | `/users/{user_id}` | ❌ NO AUTH |
| PUT | `/users/{user_id}` | ❌ NO AUTH |
| DELETE | `/users/{user_id}` | ❌ NO AUTH |
| GET | `/rbac/roles/{role_name}` | ❌ NO AUTH |
| PUT | `/rbac/roles/{role_name}` | ❌ NO AUTH |
| DELETE | `/rbac/roles/{role_name}` | ❌ NO AUTH |
| DELETE | `/rbac/permissions/{permission_id}` | ❌ NO AUTH |
| POST | `/ingest` | ❌ NO AUTH |
| POST | `/ingest/text` | ❌ NO AUTH |
| POST | `/ingest/image` | ❌ NO AUTH |
| GET | `/ontology/` | ❌ NO AUTH |
| GET | `/ontology/{ontology_name}` | ❌ NO AUTH |
| GET | `/ontology/{ontology_name}/files` | ❌ NO AUTH |
| DELETE | `/ontology/{ontology_name}` | ❌ NO AUTH |
| POST | `/ontology/{ontology_name}/rename` | ❌ NO AUTH |
| GET | `/admin/status` | ❌ NO AUTH |
| GET | `/admin/backups` | ❌ NO AUTH |
| POST | `/admin/backup` | ❌ NO AUTH |
| POST | `/admin/restore` | ❌ NO AUTH |
| GET | `/admin/scheduler/status` | ❌ NO AUTH |
| POST | `/admin/scheduler/cleanup` | ❌ NO AUTH |
| POST | `/admin/keys/{provider}` | ❌ NO AUTH |
| GET | `/admin/keys` | ❌ NO AUTH |
| DELETE | `/admin/keys/{provider}` | ❌ NO AUTH |
| POST | `/admin/regenerate-concept-embeddings` | ❌ NO AUTH |
| GET | `/vocabulary/status` | ❌ NO AUTH |
| GET | `/vocabulary/types` | ❌ NO AUTH |
| POST | `/vocabulary/types` | ❌ NO AUTH |
| POST | `/vocabulary/merge` | ❌ NO AUTH |
| POST | `/vocabulary/consolidate` | ❌ NO AUTH |
| POST | `/vocabulary/generate-embeddings` | ❌ NO AUTH |
| GET | `/vocabulary/category-scores/{relationship_type}` | ❌ NO AUTH |
| POST | `/vocabulary/refresh-categories` | ❌ NO AUTH |
| GET | `/vocabulary/similar/{relationship_type}` | ❌ NO AUTH |
| GET | `/vocabulary/analyze/{relationship_type}` | ❌ NO AUTH |
| GET | `/vocabulary/config` | ❌ NO AUTH |
| GET | `/admin/vocabulary/config` | ❌ NO AUTH |
| PUT | `/admin/vocabulary/config` | ❌ NO AUTH |
| GET | `/admin/vocabulary/profiles` | ❌ NO AUTH |
| GET | `/admin/vocabulary/profiles/{profile_name}` | ❌ NO AUTH |
| POST | `/admin/vocabulary/profiles` | ❌ NO AUTH |
| DELETE | `/admin/vocabulary/profiles/{profile_name}` | ❌ NO AUTH |
| GET | `/admin/embedding/config` | ❌ NO AUTH |
| POST | `/admin/embedding/config` | ❌ NO AUTH |
| POST | `/admin/embedding/config/reload` | ❌ NO AUTH |
| GET | `/admin/embedding/configs` | ❌ NO AUTH |
| POST | `/admin/embedding/config/{config_id}/protect` | ❌ NO AUTH |
| DELETE | `/admin/embedding/config/{config_id}` | ❌ NO AUTH |
| POST | `/admin/embedding/config/{config_id}/activate` | ❌ NO AUTH |
| GET | `/admin/extraction/config` | ❌ NO AUTH |
| POST | `/admin/extraction/config` | ❌ NO AUTH |
