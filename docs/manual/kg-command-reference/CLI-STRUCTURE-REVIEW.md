# CLI Structure Review & Refactoring Opportunities

**Date:** 2025-01-27
**Purpose:** Analyze the as-built kg CLI structure and identify refactoring opportunities
**Scope:** Full command tree documented in `docs/manual/kg-command-reference/`

## Executive Summary

**Documentation Created:**
- 15 comprehensive README files
- ~7,834 lines of documentation
- Complete command tree coverage
- All subcommands documented with examples

**Key Findings:**
1. **Generally well-organized** - Logical command grouping
2. **Some inconsistencies** - Naming patterns vary
3. **Unix shortcuts useful** - But add cognitive overhead
4. **Deep nesting works** - Subdirectories aid organization
5. **Opportunities exist** - For consolidation and simplification

---

## Command Inventory

### Top-Level Commands (15)

| Command | Subcommands | Complexity | Notes |
|---------|-------------|------------|-------|
| `health` | 0 | Simple | ✓ Perfect as-is |
| `config` | 13 | Moderate | Has `json` subtree |
| `ingest` | 3 | Simple | Clear purpose |
| `job` (jobs) | 5 | Moderate | Has `list/`, `approve/` subtrees |
| `search` | 4 | Simple | Well-organized |
| `database` (db) | 3 | Simple | ✓ Good alias |
| `ontology` (onto) | 5 | Simple | ✓ Good alias |
| `vocabulary` (vocab) | 7 | Complex | Rich feature set |
| `admin` | 12 | Very Complex | Largest command tree |
| `login` | 0 | Simple | Auth command |
| `logout` | 0 | Simple | Auth command |
| `ls` | 0 | Simple | Unix shortcut |
| `stat` | 0 | Simple | Unix shortcut |
| `rm` | 0 | Simple | Unix shortcut |
| `cat` (bat) | 0 | Simple | Unix shortcut |

**Total:** 15 top-level commands + 4 aliases

---

## Structural Patterns

### Aliases (Good)

**Consistent aliases improve usability:**

✅ **Good Examples:**
- `job` / `jobs` - Natural plural
- `database` / `db` - Common abbreviation
- `ontology` / `onto` - Reasonable shortening
- `vocabulary` / `vocab` - Standard abbreviation
- `cat` / `bat` - Playful alternative

**Pattern:** All major commands have single-letter or intuitive aliases

### Subcommand Organization

**Well-Organized Trees:**

✅ **job command:**
```
job
├── status
├── list
│   ├── pending
│   ├── approved
│   ├── done
│   ├── failed
│   └── cancelled
├── approve
│   ├── job
│   ├── pending
│   └── filter
├── cancel
└── clear
```
- Clear hierarchy
- Logical grouping
- Convenience shortcuts (pending, done, etc.)

✅ **admin command:**
```
admin
├── status
├── backup/restore
├── scheduler
│   ├── status
│   └── cleanup
├── user
│   ├── list
│   ├── create
│   └── ...
├── rbac
├── embedding
├── extraction
└── keys
```
- Central admin namespace
- Grouped by concern
- Subdirectories for complex trees

---

## Refactoring Opportunities

### 1. Consolidate Authentication Commands

**Current:**
```
kg login
kg logout
```

**Proposed:**
```
kg auth login
kg auth logout
kg auth status
kg auth token
```

**Rationale:**
- Reduces top-level clutter
- Provides namespace for auth operations
- Allows future expansion (token, refresh, etc.)

**Impact:** Medium
**Breaking Change:** Yes
**Migration:** Add `auth` command, deprecate `login`/`logout` with warnings

---

### 2. Group Unix Shortcuts Under Namespace

**Current:**
```
kg ls <resource>
kg stat <resource>
kg rm <resource>
kg cat <resource>
```

**Problem:**
- 4 top-level commands for shortcuts
- Overlap with standard commands
- Cognitive overhead

**Proposed Option A - Subcommand:**
```
kg unix ls <resource>
kg unix stat <resource>
kg unix rm <resource>
kg unix cat <resource>
```

**Proposed Option B - Keep but Document:**
- Keep as-is
- Clearly mark as "shortcuts" in help
- Emphasize in documentation

**Recommendation:** **Option B** - Keep shortcuts at top level
- They're meant to be convenient
- Grouping defeats the purpose
- Document clearly instead

**Impact:** Low (if keeping), High (if changing)
**Breaking Change:** Yes (if changing)

---

### 3. Flatten config json Subtree

**Current:**
```
kg config json
├── get
├── set
└── dto
```

**Proposed:**
```
kg config get --json
kg config set --json
kg config dto
```

**Rationale:**
- `--json` flag more standard than subcommand
- Reduces nesting
- Simpler mental model

**Impact:** Medium
**Breaking Change:** Yes
**Migration:** Support both, deprecate `json` subcommand

---

### 4. Consolidate Job List Shortcuts

**Current:**
```
kg job list
kg job list pending    # shortcut
kg job list approved   # shortcut
kg job list done       # shortcut
kg job list failed     # shortcut
kg job list cancelled  # shortcut
```

**Observation:**
- Shortcuts are valuable
- BUT: Could be flags instead

**Proposed Alternative:**
```
kg job list --status pending
kg job list --status approved
# OR via Unix style:
kg ls job --status pending
```

**Recommendation:** **Keep current structure**
- Shortcuts are intuitive
- Flags are already available (`--status`)
- Both approaches coexist nicely

**Impact:** N/A (keep as-is)

---

### 5. Simplify admin Command

**Current Structure:**
- 12 top-level subcommands under `admin`
- Some overlap with other commands
- Very large surface area

**Observations:**
- `admin status` - Could be `kg status --all`
- `admin backup/restore` - Could be separate `kg backup` command
- `admin regenerate-embeddings` - Fits better under `kg vocabulary generate-embeddings` or `kg embedding regenerate`

**Proposed Restructuring:**

```
# System-level commands move to top level
kg status --all           # Instead of admin status
kg backup                 # Instead of admin backup
kg restore                # Instead of admin restore

# Keep under admin:
admin
├── reset                 # Destructive, belongs in admin
├── scheduler             # System management
├── user                  # User management
├── rbac                  # Access control
├── embedding             # Model config
├── extraction            # Model config
└── keys                  # Credentials
```

**Impact:** High
**Breaking Change:** Yes
**Benefit:** Clearer separation of concerns

---

### 6. Unify Embedding Commands

**Current:**
- `kg admin embedding` - Configuration
- `kg admin regenerate-embeddings` - Regeneration
- `kg vocabulary generate-embeddings` - Vocabulary embeddings

**Proposed:**
```
kg embedding
├── config                # Model configuration
├── list                  # List configs
├── activate              # Activate config
├── regenerate            # Regenerate concept embeddings
│   ├── --concepts
│   ├── --vocabulary
│   └── --all
└── test                  # Test embedding generation
```

**Rationale:**
- Single namespace for all embedding operations
- Clearer purpose
- Easier discovery

**Impact:** High
**Breaking Change:** Yes

---

### 7. Consider Extraction Consolidation

**Current:**
- `kg admin extraction config`
- `kg admin extraction set`

**Observation:**
- Only 2 subcommands
- Similar to embedding pattern

**Proposed:**
```
kg extraction
├── config                # Show current
├── set                   # Update
├── test                  # Test extraction
└── list                  # List providers/models
```

**Rationale:**
- Parallel to `kg embedding`
- Room for growth
- Clearer purpose

**Impact:** Medium
**Breaking Change:** Yes

---

## Naming Consistency Issues

### Inconsistent Naming Patterns

| Command | Pattern | Example |
|---------|---------|---------|
| `job list` | noun verb | ✓ Standard |
| `ontology delete` | noun verb | ✓ Standard |
| `vocab status` | noun noun | ✗ Inconsistent (should be "show status") |
| `search query` | verb noun | ✓ Standard |
| `admin reset` | noun verb | ✓ Standard |

**Most commands follow noun-verb pattern - Good!**

### Verb Consistency

**Delete vs Remove vs Cancel:**
- `ontology delete` - Delete ontology
- `job cancel` - Cancel job
- `rm` shortcut - Remove resources

**Recommendation:**
- Keep domain-specific verbs (cancel for jobs makes sense)
- `delete` for permanent removal
- `cancel` for stopping in-progress
- Document the distinction

---

## Command Depth Analysis

### Depth Distribution

| Depth | Count | Examples |
|-------|-------|----------|
| 0 (top-level) | 15 | `health`, `login`, `logout`, etc. |
| 1 (subcommand) | ~60 | `job status`, `search query`, etc. |
| 2 (sub-subcommand) | ~20 | `job list pending`, `config json get` |
| 3+ | 0 | None |

**Observation:** Max depth is 2 - Good!
- Avoids over-nesting
- Easy to navigate
- Clear mental model

**Recommendation:** **Maintain max depth of 2**
- Deeper than 2 becomes unwieldy
- Use flags for further filtering

---

## Feature Distribution

### Commands by Concern

**Data Operations (40%):**
- `ingest` - Input
- `search` - Query
- `ontology` - Organization
- `database` - Info

**Job Management (15%):**
- `job` - Jobs
- `admin scheduler` - Scheduling

**System Admin (25%):**
- `admin` - Most admin operations
- `config` - Configuration
- `health` - Status

**Vocabulary (10%):**
- `vocabulary` - Edge types

**User/Auth (5%):**
- `login`, `logout`
- `admin user`, `admin rbac`

**Model Config (5%):**
- `admin embedding`
- `admin extraction`
- `admin keys`

**Observation:** Well-distributed, admin is heavy

---

## Identified Patterns

### Good Patterns to Keep

1. **Alias Support**
   - Every major command has intuitive alias
   - Reduces typing, improves UX

2. **Subcommand Hierarchies**
   - `job list/` and `job approve/` subdirectories
   - Organized, maintainable

3. **Consistent Options**
   - `--json` for machine output
   - `-f, --force` for confirmation skip
   - `-h, --help` everywhere

4. **Unix Shortcuts**
   - Familiar for Unix users
   - Maps to existing commands
   - Well-documented

5. **Nested Help**
   - Every level has `--help`
   - Discoverable

### Patterns to Improve

1. **Top-Level Clutter**
   - 15 commands at top level
   - Could group auth, unix shortcuts

2. **admin Megacommand**
   - 12 subcommands under admin
   - Some could be promoted

3. **Embedding/Extraction Separation**
   - Scattered across `admin` and `vocabulary`
   - Could unify

4. **Backup/Restore**
   - Under `admin` but conceptually separate
   - Could be top-level

---

## Recommendations Summary

### Priority 1 (High Value, Low Risk)

1. **Document Clearly**
   - Mark Unix shortcuts clearly in help text
   - Add "shortcut for" to descriptions
   - Create cheat sheet

2. **Enhance Help Text**
   - Add examples to `--help` output
   - Show common use cases
   - Link to docs

3. **Add `kg status --all`**
   - Alias for `admin status`
   - Non-breaking addition

### Priority 2 (High Value, Medium Risk)

4. **Create `kg auth` Command**
   - Group `login`/`logout`
   - Keep old commands with deprecation warnings
   - Add `auth status`, `auth token`

5. **Promote Backup/Restore**
   - Move to top level
   - Keep `admin backup` as alias
   - Clearer discoverability

### Priority 3 (High Value, High Risk)

6. **Unify Embedding Commands**
   - Create `kg embedding` top-level
   - Consolidate from `admin` and `vocab`
   - Big refactor but clearer

7. **Unify Extraction Commands**
   - Create `kg extraction` top-level
   - Parallel to embedding
   - Breaking change

### Priority 4 (Nice to Have)

8. **Flatten `config json`**
   - Use `--json` flag instead
   - Long migration period
   - Low priority

---

## Migration Strategy

### For Breaking Changes

**Phase 1: Addition (v1.x)**
- Add new commands alongside old
- No deprecation warnings yet
- Document both approaches

**Phase 2: Deprecation (v2.0)**
- Add warnings to old commands
- "Use `kg auth login` instead"
- Update all documentation

**Phase 3: Removal (v3.0)**
- Remove old commands
- Clean up codebase
- Major version bump

### Versioning

- Use semantic versioning
- Breaking changes = major version
- New commands = minor version
- Bug fixes = patch version

---

## Conclusion

### Current State Assessment

**Strengths:**
- ✅ Well-organized hierarchies
- ✅ Consistent naming (mostly)
- ✅ Good use of aliases
- ✅ Comprehensive feature coverage
- ✅ Unix shortcuts add value

**Weaknesses:**
- ⚠️ `admin` command is overloaded
- ⚠️ Embedding/extraction commands scattered
- ⚠️ Top-level could be cleaner
- ⚠️ Some inconsistencies in patterns

**Overall:** 8/10 - Very good structure with room for improvement

### Recommended Actions

**Immediate (No Breaking Changes):**
1. Enhance documentation and help text
2. Add `kg status --all` as alias
3. Create refactoring roadmap

**Short-Term (v2.0 - Breaking Changes OK):**
1. Introduce `kg auth` command
2. Promote backup/restore to top-level
3. Deprecate old patterns

**Long-Term (v3.0 - Major Refactor):**
1. Unify embedding/extraction commands
2. Remove deprecated commands
3. Streamline admin namespace

---

## Next Steps

1. **Review with team** - Discuss recommendations
2. **Prioritize** - Choose which changes to implement
3. **Create issues** - Track refactoring work
4. **Update roadmap** - Plan breaking changes carefully
5. **Communicate** - Document migration paths

---

## Appendix: Full Command Tree

```
kg
├── health
├── config (cfg)
│   ├── get/set/delete/list/init/reset/path
│   ├── enable-mcp/disable-mcp/mcp
│   ├── auto-approve
│   ├── update-secret
│   └── json
│       ├── get
│       ├── set
│       └── dto
├── ingest
│   ├── file
│   ├── directory
│   └── text
├── job (jobs)
│   ├── status
│   ├── list
│   │   ├── pending
│   │   ├── approved
│   │   ├── done
│   │   ├── failed
│   │   └── cancelled
│   ├── approve
│   │   ├── job
│   │   ├── pending
│   │   └── filter
│   ├── cancel
│   └── clear
├── search
│   ├── query
│   ├── details
│   ├── related
│   └── connect
├── database (db)
│   ├── stats
│   ├── info
│   └── health
├── ontology (onto)
│   ├── list
│   ├── info
│   ├── files
│   ├── rename
│   └── delete
├── vocabulary (vocab)
│   ├── status
│   ├── list
│   ├── consolidate
│   ├── merge
│   ├── generate-embeddings
│   ├── category-scores
│   └── refresh-categories
├── admin
│   ├── status
│   ├── backup
│   ├── list-backups
│   ├── restore
│   ├── reset
│   ├── scheduler
│   │   ├── status
│   │   └── cleanup
│   ├── regenerate-embeddings
│   ├── user
│   │   ├── list/get/create/update/delete
│   ├── rbac
│   │   ├── resource/role/permission/assign
│   ├── embedding
│   │   ├── list/create/activate/reload/protect/unprotect/delete
│   ├── extraction
│   │   ├── config
│   │   └── set
│   └── keys
│       ├── list/set/delete
├── login
├── logout
├── ls <resource>
├── stat <resource> [id]
├── rm <resource> <id>
└── cat (bat) <resource> [id]
```

**Total Commands:** ~100+
**Top-Level:** 15
**Max Depth:** 2
**Documentation:** Complete
