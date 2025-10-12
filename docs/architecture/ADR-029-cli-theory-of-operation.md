# ADR-029: CLI Theory of Operation - Hybrid Unix/Domain-Specific Design

**Status:** Proposed
**Date:** 2025-10-12
**Supersedes:** N/A - First formal CLI design specification

## Context

The Knowledge Graph CLI (`kg`) has evolved organically, resulting in inconsistent command structures:

**Current Issues:**
1. **Inconsistent hierarchies**: Some commands use hierarchical patterns (`kg ontology list`), others are flat
2. **Arbitrary aliases**: `db`, `resource`, `role`, `perm` without clear rationale
3. **Mixed verbosity**: Some commands are terse, others verbose
4. **No design philosophy**: Commands added ad-hoc without architectural guidance

**Design Tension:**
Users expect both Unix-style brevity (`ls`, `rm`, `stat`) AND domain-specific organization (`kg job approve`, `kg role assign`). How do we reconcile these competing needs?

**Observation from Code Review:**
> "We're unintentionally building an operating system... maybe we need to use a well-known pattern?"

This is true. The CLI is becoming a **domain-specific shell** for knowledge graph operations. We should embrace Unix/BusyBox patterns deliberately rather than accidentally.

## Decision

Implement a **hybrid architecture** with two command interfaces:

### 1. Primary Interface: Noun → Verb (Domain-Oriented)

**Structure:** `kg <resource> <verb> [args]`

**Rationale:**
- Groups operations by **resource domain** (jobs, ontologies, concepts)
- Namespace isolation: `job.stat` vs `database.stat` can have different output schemas
- Scales naturally for **domain-specific verbs**: `approve`, `assign`, `revoke`, `merge`
- Enables contextual help: `kg job --help` shows all job operations

**Examples:**
```bash
kg job list
kg job stat <id>
kg job approve <id>
kg job cancel <id>

kg ontology list
kg ontology info <name>
kg ontology delete <name>

kg role list
kg role assign <user> <role>
kg role revoke <user> <role>
```

### 2. Convenience Layer: Unix Verb Shortcuts

**Structure:** `kg <verb> <resource> [args]`

**Rationale:**
- Unix muscle memory for common operations
- Reduces typing for frequent commands
- Familiar to users from `ls`, `rm`, `stat`, `cat`, etc.

**Implementation:** Verb shortcuts **delegate** to primary commands via a router

**Examples:**
```bash
# List operations
kg ls job           → kg job list
kg ls ontology      → kg ontology list
kg ls backup        → kg admin backup list

# Status/Stats operations
kg stat job <id>    → kg job stat <id>
kg stat database    → kg database stats

# Remove operations
kg rm job <id>      → kg job cancel <id>
kg rm ontology <name> → kg ontology delete <name>

# Show/Display operations
kg cat concept <id> → kg search details <id>
kg cat config <key> → kg config get <key>
```

### 3. Command Router Architecture

**Clean separation** between verb shortcuts and primary commands:

```typescript
// client/src/cli/verb-router.ts
export function createVerbRouter(): Command {
  const router = new Command();

  // ls - Universal list operation
  router
    .command('ls')
    .description('List resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, ontology, backup, config, role, etc.')
    .action(async (resource, options, command) => {
      // Delegate to primary command
      switch (resource) {
        case 'job':
        case 'jobs':
          return executeCommand(['job', 'list'], command.parent);
        case 'ontology':
        case 'ontologies':
          return executeCommand(['ontology', 'list'], command.parent);
        case 'backup':
        case 'backups':
          return executeCommand(['admin', 'backup', 'list'], command.parent);
        // ... more mappings
        default:
          console.error(`Unknown resource: ${resource}`);
          console.log('Try: kg ls --help');
          process.exit(1);
      }
    });

  // rm - Universal remove operation
  router
    .command('rm')
    .description('Remove/delete resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type')
    .argument('<id>', 'Resource identifier')
    .action(async (resource, id, options, command) => {
      switch (resource) {
        case 'job':
          return executeCommand(['job', 'cancel', id], command.parent);
        case 'ontology':
          return executeCommand(['ontology', 'delete', id], command.parent);
        // ... more mappings
      }
    });

  // stat - Universal status operation
  // cat - Universal display operation
  // ... more verbs

  return router;
}
```

**Helper Function:**
```typescript
function executeCommand(args: string[], rootCommand: Command): void {
  // Navigate command tree and execute
  let cmd = rootCommand;
  for (const arg of args.slice(0, -1)) {
    cmd = cmd.commands.find(c => c.name() === arg);
    if (!cmd) throw new Error(`Command not found: ${arg}`);
  }
  cmd.parse(args, { from: 'user' });
}
```

### 4. Command Naming Conventions

**Use singular nouns** (shorter by default):
```bash
job         not jobs
ontology    not ontologies
role        not roles
permission  not permissions
resource    not resources
```

**Descriptions can be plural:**
```
kg job list         # "List all jobs"
kg role list        # "List all roles"
```

**Sensible aliases** (5-6 chars max, well-known only):
```bash
config      → cfg (3)
database    → db (2)
ontology    → onto (4)
job         (already 3)
permission  → perm (4)
resource    → res (3)
```

### 5. Universal JSON Mode

**Machine-Readable Interface:** All commands support JSON input/output for automation.

**Global Toggle:**
```bash
# Set JSON mode globally
kg config set output_format json

# Check current mode
kg config get output_format
```

**Per-Command Override:**
```bash
# Override to JSON for single command
kg job list --json

# Override to table when in JSON mode
kg job list --table
```

**Consistent Behavior:**
- **ALL commands** respect output mode
- **ALL output** is valid JSON (no mixed formats)
- **ALL input** accepts JSON where applicable

**Examples:**
```bash
# Table mode (default)
kg job list
# ─────────────────────────────
# Job ID    Status    Progress
# ─────────────────────────────
# job-123   running   45%
# job-456   completed 100%

# JSON mode
kg job list --json
# [
#   {"job_id": "job-123", "status": "running", "progress": 0.45},
#   {"job_id": "job-456", "status": "completed", "progress": 1.0}
# ]

# Piping for automation
kg job list --json | jq '.[] | select(.status == "failed")' | kg job cancel --json
```

**Configuration Integration:**
```typescript
// client/src/lib/config.ts
export interface KgConfig {
  // ... existing fields
  output_format?: 'table' | 'json';  // Default: 'table'
}

// Usage in commands
function getOutputFormat(options: any): 'table' | 'json' {
  const config = getConfig();

  // 1. Command-line flag takes precedence
  if (options.json) return 'json';
  if (options.table) return 'table';

  // 2. Fall back to config
  return config.get('output_format') || 'table';
}
```

**Implementation:**
- Add `--json` flag to ALL commands (Commander.js parent option)
- Add `--table` flag to ALL commands (override JSON mode)
- Refactor all output to check format before printing
- Ensure error messages are also JSON in JSON mode

### 6. Verb Vocabulary

**Unix-Inspired Verbs:**
- `ls` - List resources
- `rm` - Remove/delete
- `stat` - Status/statistics
- `cat` - Display/show details
- `mv` - Move/rename (future)
- `cp` - Copy/duplicate (future)

**Domain-Specific Verbs:**
- `approve` - Approve jobs, vocabulary
- `cancel` - Cancel jobs
- `assign` - Assign roles to users
- `revoke` - Revoke permissions
- `grant` - Grant permissions
- `ingest` - Ingest documents
- `search` - Search concepts
- `connect` - Find connections

## Benefits

1. **Best of Both Worlds**
   - Power users: Use domain commands (`kg job approve <id>`)
   - Unix users: Use verb shortcuts (`kg ls job`)

2. **Scalability**
   - Domain-specific operations don't need Unix analogs
   - Easy to add specialized verbs without polluting Unix verb namespace

3. **Discoverability**
   - `kg <resource> --help` shows all operations for that resource
   - `kg ls --help` shows all listable resources
   - Tab completion works naturally

4. **Consistency**
   - All commands follow noun→verb structure
   - Verb shortcuts are additive (don't break existing usage)
   - Clean separation via router pattern

5. **Maintainability**
   - Router is single source of truth for verb mappings
   - Primary commands remain unchanged
   - Easy to add/remove verb shortcuts

6. **CLI as API Abstraction** (JSON Mode)
   - **Safety layer**: Client-side validation, confirmation prompts
   - **Type safety**: TypeScript ensures correct data structures
   - **Protocol versioning**: Handle API changes transparently
   - **Automation-friendly**: No HTTP client needed in scripts
   - **Offline operations**: Local config, batch processing (future)
   - **Composability**: Pipe between commands or integrate with Unix tools

## Consequences

### Positive

- ✅ Intuitive for both Unix and domain experts
- ✅ Reduces typing without sacrificing clarity
- ✅ Scales to complex domain operations
- ✅ Clean, maintainable architecture
- ✅ Universal JSON mode enables complete automation
- ✅ Consistent interface for scripting/piping

### Negative

- ⚠️ Two ways to do the same thing (may confuse new users)
  - *Mitigation:* Documentation emphasizes primary commands, verb shortcuts as "convenience aliases"
- ⚠️ Router adds indirection
  - *Mitigation:* Router is simple delegation, no business logic
- ⚠️ Breaking change for existing users
  - *Mitigation:* Phase migration (add singulars as aliases first, deprecate plurals later)
- ⚠️ JSON mode requires refactoring ALL commands
  - *Mitigation:* Implement incrementally, starting with high-value commands

### Neutral

- Router pattern adds ~100 lines of code
- Help text needs to explain both interfaces
- Tab completion needs to support both patterns

## Examples

### Before (Current)
```bash
kg jobs list                    # Inconsistent plural
kg job status <id>              # Inconsistent with above
kg database stats               # Why not db stats?
kg ontology list                # Verbose
kg config mcp                   # Custom structure
kg admin rbac resources list    # Too deep
```

### After (Hybrid)
```bash
# Primary interface (noun → verb)
kg job list
kg job stat <id>
kg database stats
kg ontology list
kg config mcp list
kg rbac resource list

# Convenience shortcuts (verb → noun)
kg ls job
kg stat job <id>
kg stat database
kg ls ontology
kg ls config
kg ls resource
```

### Complex Operations (Domain-Specific)
```bash
# These don't have Unix verb equivalents - and that's OK!
kg job approve <id>
kg role assign <user> <role>
kg permission grant <role> <resource> <action>
kg ontology merge <source> <target>
kg search connect <from> <to>
```

## Migration Path

### Phase 1: Add Verb Router (Non-Breaking)
- Implement verb router with delegation
- Add verb shortcuts alongside existing commands
- Both work simultaneously

### Phase 2: Singularize Resources (Breaking)
- Rename `jobs` → `job`, `roles` → `role`, etc.
- Add deprecation warnings for plural forms
- Update documentation

### Phase 3: Add Useful Aliases
- `cfg`, `db`, `onto`, `perm`, `res`
- Document recommended shortcuts

### Phase 4: Deprecation (Optional)
- After 6 months, optionally remove plural commands
- Or keep both indefinitely (user preference)

## Implementation Checklist

### Phase 1: Verb Router
- [ ] Create `client/src/cli/verb-router.ts`
- [ ] Implement `executeCommand()` helper
- [ ] Add `ls` verb with resource delegation
- [ ] Add `rm` verb with resource delegation
- [ ] Add `stat` verb with resource delegation
- [ ] Add `cat` verb with resource delegation
- [ ] Register verb router in main CLI

### Phase 2: Singularization
- [ ] Rename `jobs` → `job`
- [ ] Rename `roles` → `role`
- [ ] Rename `permissions` → `permission`
- [ ] Rename `resources` → `resource`
- [ ] Update all references in codebase

### Phase 3: Aliases
- [ ] Add `db` alias for `database`
- [ ] Add `cfg` alias for `config`
- [ ] Add `onto` alias for `ontology`
- [ ] Add `perm` alias for `permission`
- [ ] Add `res` alias for `resource`

### Phase 4: Universal JSON Mode
- [ ] Add `output_format` field to config schema
- [ ] Add `--json` global flag (Commander.js parent option)
- [ ] Add `--table` global flag (override JSON mode)
- [ ] Create `getOutputFormat()` utility
- [ ] Refactor ALL commands to check output format
- [ ] Ensure Table utility supports JSON output
- [ ] Ensure error messages are JSON in JSON mode
- [ ] Test JSON mode with piping/automation

### Phase 5: Documentation & Testing
- [ ] Update help text to explain both interfaces
- [ ] Add tab completion for verb shortcuts
- [ ] Update user documentation
- [ ] Update QUICKSTART guide
- [ ] Write integration tests
- [ ] Test backwards compatibility

## Future Enhancements

1. **Interactive Mode**
   ```bash
   kg ls
   # Interactive: "What would you like to list?"
   # Shows: jobs, ontologies, roles, backups, etc.
   ```

2. **Fuzzy Matching**
   ```bash
   kg ls ont   # Matches "ontology"
   kg rm j 123 # Matches "job 123"
   ```

3. **Shell Completion**
   ```bash
   kg ls <TAB>  # Shows: job, ontology, backup, config, role, ...
   kg job <TAB> # Shows: list, stat, approve, cancel
   ```

4. **Piping Support**
   ```bash
   kg ls job --format=json | jq '.[] | select(.status == "failed")'
   ```

## References

- BusyBox Design: https://busybox.net/
- Git Command Design: https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain
- Kubectl Command Patterns: https://kubernetes.io/docs/reference/kubectl/
- Commander.js Documentation: https://github.com/tj/commander.js

## Conclusion

By embracing a **hybrid design**, we get:
- **Organized complexity** via noun→verb (domain operations)
- **Unix familiarity** via verb shortcuts (common operations)
- **Clean architecture** via router delegation (maintainable)

This positions `kg` as a **professional domain-specific shell** rather than an ad-hoc collection of commands. The design scales from simple CRUD to complex workflows while remaining intuitive for both Unix users and domain experts.
