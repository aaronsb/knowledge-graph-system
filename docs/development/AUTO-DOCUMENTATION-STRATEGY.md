# Auto-Documentation Strategy for CLI Tools

**Status:** Proposed
**Date:** 2025-01-28
**Goal:** Automatically generate CLI documentation from source code to keep docs in sync with implementation

---

## Problem

Current manual documentation process:
- **Time-consuming:** ~7,834 lines across 15 README files
- **Drift risk:** Docs can become outdated as code changes
- **Duplication:** Command definitions exist in both code and docs
- **Maintenance burden:** Every CLI change requires doc update

**Ideal solution:**
- Documentation generated from actual CLI code
- Runs automatically during build
- Maintains quality of current manual docs
- Minimal overhead for developers

---

## Available Tools & Approaches

### 1. **commander-to-markdown** (npm package)

```bash
npm install --save-dev commander-to-markdown
```

**Pros:**
- Simple, drop-in solution
- Works with existing Commander.js code
- No code changes required

**Cons:**
- Basic formatting (doesn't match our detailed style)
- Limited customization
- No support for examples, ADR references, etc.

**Verdict:** ❌ Too basic for our needs

---

### 2. **oclif** (CLI framework with built-in docs)

Full-featured CLI framework by Heroku/Salesforce:
- Built-in doc generation
- Auto-generated help
- Plugin system
- Testing framework

**Pros:**
- Professional, battle-tested
- Rich documentation features
- Active maintenance

**Cons:**
- Requires complete CLI rewrite
- Different command structure
- Significant migration effort

**Verdict:** ❌ Too much work to migrate

---

### 3. **Custom Commander.js Introspection** (Recommended)

Write a TypeScript script that:
1. Imports Commander.js program
2. Introspects command tree
3. Generates markdown matching our style
4. Runs during build process

**Pros:**
- Full control over output format
- Matches existing documentation style
- Works with current codebase
- Can extract metadata from JSDoc
- Supports examples, ADRs, related commands

**Cons:**
- Need to write and maintain the generator
- Requires metadata in code (`.metadata()` calls)

**Verdict:** ✅ Best fit for our needs

---

## Recommended Implementation

### **Phase 1: Hybrid Approach** (Start here)

Keep current manual docs but add auto-generation for reference material.

#### 1.1 Add Metadata to Commands

Extend Commander.js commands with documentation metadata:

```typescript
// client/src/cli/ingest.ts
export const ingestCommand = new Command('ingest')
  .description('Ingest documents into the knowledge graph')
  .metadata({  // <-- Add this
    examples: [
      {
        cmd: 'kg ingest file -o "My Docs" document.txt',
        desc: 'Ingest a single file'
      },
      {
        cmd: 'kg ingest directory -o "Papers" ./research/',
        desc: 'Ingest all files in a directory'
      }
    ],
    adrs: ['ADR-014', 'ADR-032'],
    related: ['job', 'ontology'],
    useCases: [
      'Initial data import',
      'Incremental updates',
      'Batch processing'
    ]
  });
```

#### 1.2 Generate Docs at Build Time

Add to `package.json`:

```json
{
  "scripts": {
    "build": "npm run generate-docs && tsc && npm run postbuild",
    "generate-docs": "node --loader ts-node/esm scripts/generate-docs-enhanced.ts"
  }
}
```

#### 1.3 Dual Output

Generate two doc sets:
- `docs/manual/kg-command-reference/` - Manual (existing)
- `docs/reference/cli-auto/` - Auto-generated

Use manual for complex explanations, auto-generated for quick reference.

---

### **Phase 2: Full Auto-Generation** (Future)

Once confident in the generator:

1. **Migrate examples to code**
   - Move all examples from manual docs to `.metadata()` calls
   - Generate comprehensive docs automatically

2. **Single source of truth**
   - Code becomes the documentation source
   - Markdown generated from code

3. **CI/CD integration**
   - Fail builds if docs are out of date
   - Auto-commit doc updates

---

## MCP Server Documentation

MCP tools already have structured schemas - easy to auto-generate:

```typescript
// Extract from MCP tool definitions
const tools = server.listTools();

// Generate markdown
tools.forEach(tool => {
  generateMCPToolDoc(tool.name, tool.inputSchema, tool.description);
});
```

**MCP Doc Generator:** `client/scripts/generate-mcp-docs.ts`

---

## Implementation Roadmap

### Immediate (This Week)

- [x] Create `generate-cli-docs.ts` basic version
- [x] Create `generate-docs-enhanced.ts` with metadata support
- [ ] Add `.metadata()` to 2-3 commands as proof-of-concept
- [ ] Generate docs for those commands
- [ ] Compare auto-generated vs manual docs

### Short-Term (Next Sprint)

- [ ] Add metadata to all major commands (health, config, ingest, job, search)
- [ ] Integrate into build process
- [ ] Configure mkdocs to include auto-generated docs
- [ ] Document the `.metadata()` pattern for developers

### Long-Term (Future)

- [ ] Migrate all commands to use metadata
- [ ] Replace manual docs with auto-generated
- [ ] Add MCP server doc generation
- [ ] CI check to ensure docs are up-to-date

---

## Example: Before & After

### Before (Manual)

```markdown
# kg ingest file

Ingest a single file into the knowledge graph.

**Usage:**
\`\`\`bash
kg ingest file [options] <file>
\`\`\`

**Options:**
- `-o, --ontology <name>` - Ontology name
...
```

**Maintenance:** Update manually when command changes

### After (Auto-Generated)

```typescript
// Code
ingestFileCommand
  .option('-o, --ontology <name>', 'Ontology name')
  .metadata({
    examples: [/* ... */],
    adrs: ['ADR-014']
  });

// Docs generated automatically
npm run build
```

**Maintenance:** Update code, docs auto-sync ✓

---

## Additional Features to Consider

### 1. **Video/GIF Examples**

```typescript
.metadata({
  examples: [
    { cmd: '...', desc: '...', video: 'demos/ingest.gif' }
  ]
})
```

### 2. **Interactive Docs**

Generate JSON schema for interactive documentation site.

### 3. **Shell Completion**

Same metadata can generate bash/zsh completions:

```bash
kg ingest <TAB>  # Shows: file, directory, text
```

### 4. **Version Tracking**

Track when commands were added/changed:

```typescript
.metadata({
  since: '0.2.0',
  deprecated: '0.5.0'
})
```

---

## Comparison: Manual vs Auto-Generated

| Aspect | Manual Docs | Auto-Generated | Recommended |
|--------|-------------|----------------|-------------|
| **Accuracy** | Can drift | Always correct | Auto ✓ |
| **Detail** | Very detailed | Basic → Rich | Hybrid |
| **Examples** | Rich, contextual | Requires metadata | Hybrid |
| **Maintenance** | High effort | Automatic | Auto ✓ |
| **Initial setup** | Done (7,834 lines) | Needs generator | - |
| **Flexibility** | Full control | Template-based | Hybrid |

**Verdict:** Start with hybrid, migrate to full auto-generation over time.

---

## Tools We're Using

### CLI Documentation
- **Commander.js** - Command definitions
- **Custom generator** - `generate-docs-enhanced.ts`
- **TypeScript** - Type safety for metadata
- **MkDocs** - Static site generation

### MCP Documentation
- **MCP SDK** - Tool schemas
- **JSON Schema** - Input validation
- **Custom generator** - `generate-mcp-docs.ts`

---

## Getting Started

### 1. Try the Basic Generator

```bash
cd client
npm install --save-dev ts-node

# Run basic generator
node --loader ts-node/esm scripts/generate-cli-docs.ts
```

### 2. Add Metadata to a Command

```typescript
// Pick a simple command (e.g., health)
export const healthCommand = new Command('health')
  .description('Check API server health')
  .metadata({
    examples: [
      { cmd: 'kg health', desc: 'Check if API is running' }
    ],
    related: ['database', 'admin']
  });
```

### 3. Compare Output

Look at `docs/reference/cli-auto/health/README.md` vs manual version.

### 4. Decide on Approach

Based on the comparison, choose:
- Full auto-generation?
- Hybrid (auto-reference + manual guides)?
- Enhanced manual with validation?

---

## Questions to Answer

1. **Quality:** Does auto-generated match manual docs quality?
2. **Examples:** Can we express all examples in `.metadata()`?
3. **Workflow:** Does build-time generation slow down development?
4. **Migration:** Worth migrating all 15 command files?
5. **MCP:** Should MCP docs follow same pattern?

---

## Next Steps

1. **Review this strategy document**
2. **Run proof-of-concept with 2-3 commands**
3. **Decide on approach** (full auto vs hybrid)
4. **Update CLAUDE.md** with chosen workflow
5. **Create ADR** if we proceed with full auto-generation

---

## Resources

- [Commander.js Docs](https://github.com/tj/commander.js)
- [oclif Documentation](https://oclif.io/docs/introduction)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [TypeDoc](https://typedoc.org/) (for API docs)

---

## Related

- Current manual docs: `docs/manual/kg-command-reference/`
- CLI structure review: `docs/manual/kg-command-reference/CLI-STRUCTURE-REVIEW.md`
- CLI refactoring ideas in review document (7 recommendations)
