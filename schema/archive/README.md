# Archived Schema Files

**Date:** 2025-10-16
**Reason:** Consolidation into baseline schema v2.0.0

These files have been archived because their contents have been fully merged into
the single consolidated baseline schema file: `schema/00_baseline.sql`

## Archived Files

### init_age.sql
- **Original Purpose:** Initialize Apache AGE extension and create legacy public schema tables
- **Status:** Replaced by baseline (tables moved to kg_api/kg_auth/kg_logs schemas)

### multi_schema.sql
- **Original Purpose:** Create kg_api, kg_auth, kg_logs schemas with modern tables (ADR-024, ADR-025, ADR-026)
- **Status:** Fully merged into baseline
- **Note:** Included partial ADR-032 additions (lines 589-705)

### adr032_additions.sql / adr032_additions_fixed.sql
- **Original Purpose:** Add vocabulary embedding support (ADR-032)
- **Status:** Fully merged into baseline
- **Note:** These were duplicate files, both superseded by baseline

### migrations/
- **001_dynamic_rbac.sql:** Dynamic RBAC system (ADR-028) - merged into baseline
- **002_fix_content_hash_length.sql:** Content hash VARCHAR(80) fix - merged into baseline

## Current State

All schema definition, migrations, and patches have been consolidated into:
- **schema/00_baseline.sql** (v2.0.0)

This single file includes:
- Apache AGE initialization
- All multi-schema tables (kg_api, kg_auth, kg_logs)
- Dynamic RBAC system (ADR-028)
- Vocabulary management (ADR-025, ADR-026, ADR-032)
- All seed data
- All applied migrations

## Migration Notes

If you need to roll back to the old multi-file approach:
1. Restore files from this archive
2. Update docker-compose.yml to reference the old files
3. Run `docker-compose down -v && docker-compose up -d`

However, the baseline schema is the recommended approach going forward as it:
- Eliminates schema drift
- Ensures all migrations are applied
- Simplifies database resets
- Provides a single source of truth
