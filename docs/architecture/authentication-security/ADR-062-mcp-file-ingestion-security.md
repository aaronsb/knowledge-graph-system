---
status: Draft
date: 2025-11-08
deciders:
  - System Architect
---

# ADR-062: MCP File Ingestion Security Model

## Overview

Giving an AI agent the ability to ingest files into a knowledge graph is incredibly powerful - imagine pointing Claude at your entire research folder and having it extract concepts automatically. But it's also incredibly dangerous if done naively. What stops the agent from ingesting `/etc/passwd` or your `.ssh/private_key`? What prevents path traversal attacks like `../../../sensitive-data`? You need guardrails.

The challenge is balancing utility with security. You want the agent to easily ingest your Documents folder or project documentation, but you don't want it anywhere near your shell history, environment variables, or SSH keys. And you definitely don't want an attacker exploiting prompt injection to exfiltrate arbitrary files through the ingestion pipeline.

The traditional approach might be to make the agent responsible for safety - have it analyze each path, check for sensitive patterns, and decide what's safe. But that's backwards. AI agents make mistakes, can be manipulated through prompts, and shouldn't be security gatekeepers. Instead, the system should enforce security boundaries that the agent can't bypass, period.

This ADR implements a path allowlist security model where users explicitly configure which directories and file patterns are permitted. The agent's job is beautifully simple: just point at files. The system handles everything else - validation, file type detection, vision AI for images, concept extraction, and storage. If the agent tries to access something outside the allowlist, the system refuses before the agent even sees an error. It's fail-secure by design.

---

## Context

The MCP server provides AI agents with tools to interact with the knowledge graph. Adding file and directory ingestion capabilities would significantly enhance utility - agents could ingest documentation, images, and research materials directly from the filesystem.

However, unrestricted file access poses serious security risks:
- **Path traversal attacks** - `../../../etc/passwd`
- **Sensitive file exposure** - `.env`, `.ssh/`, credentials
- **Unintended data exfiltration** - Agent reads arbitrary files
- **Resource exhaustion** - Massive files or directories

We need a security model that enables useful file ingestion while preventing abuse.

### Key Constraint

Claude Desktop MCP agents have **read-only tool access** - they can call tools but cannot edit configuration files (unless the MCP server provides a file-editing tool, which we won't). Claude Code agents with file editing capabilities can modify anything, but that's an accepted risk for development environments.

---

## Decision

Implement a **path allowlist** security model with fail-secure validation for MCP file ingestion.

### Agent Responsibility vs System Responsibility

**CRITICAL: Keep It Simple**

The AI agent's job is **extremely simple** - just point at files. Everything else is handled by the system.

**Agent Responsibilities (Minimal):**
1. ✅ Know the file/directory path
2. ✅ Choose which ontology to use
3. ✅ Optionally check metadata first (via `inspect-file`)
4. ✅ Submit the path via `ingest-file` or `ingest-directory`
5. ✅ That's it. Done.

**Agent Does NOT:**
- ❌ Read file contents (except optional preview via `inspect-file`)
- ❌ Describe images (vision AI does this automatically)
- ❌ Analyze images (vision AI does this automatically)
- ❌ Process text (extraction pipeline does this automatically)
- ❌ Provide metadata (auto-detected by file type)
- ❌ Wait for jobs to complete (async processing)
- ❌ Poll job status (user checks when ready)

**System Responsibilities (Automatic):**
1. ✅ Validate path against allowlist
2. ✅ Detect file type (text, image, PDF, etc.)
3. ✅ Generate vision AI description for images
4. ✅ Extract concepts from content
5. ✅ Create graph nodes and relationships
6. ✅ Store images in object storage
7. ✅ Process jobs asynchronously
8. ✅ Return job IDs for tracking

**Example:**
```typescript
// Agent sees a directory of images
// Agent does: submit path
ingest-directory({
  path: "~/Screenshots/ui-mockups",
  ontology: "UI Design"
})

// System does: everything else
// → Finds 50 PNG files
// → Vision AI describes each image
// → Extracts concepts from descriptions
// → Creates graph nodes
// → Stores images in S3
// → Returns job IDs

// Agent: done in 1 API call
// System: processes for 5-10 minutes in background
```

### 1. Allowlist Configuration

**File:** `~/.config/kg/mcp-allowed-paths.json`

```json
{
  "version": "1.0",
  "allowed_directories": [
    "~/Documents/knowledge-base",
    "~/Projects/*/docs",
    "/home/user/research"
  ],
  "allowed_patterns": [
    "**/*.md",
    "**/*.txt",
    "**/*.pdf",
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg"
  ],
  "blocked_patterns": [
    "**/.env",
    "**/.env.*",
    "**/.git/**",
    "**/node_modules/**",
    "**/.ssh/**",
    "**/*_history",
    "**/*.key",
    "**/*.pem"
  ],
  "max_file_size_mb": 10,
  "max_files_per_directory": 1000
}
```

**Management:** CLI only (not modifiable by MCP tools)

```bash
kg mcp-config init-allowlist
kg mcp-config allow-dir ~/Documents/research
kg mcp-config allow-pattern "**/*.md"
kg mcp-config block-pattern "**/.env*"
kg mcp-config show-allowlist
kg mcp-config test-path ~/Documents/notes.md
```

### 2. MCP Tools

**Tool: `inspect-file`**

Preview file contents before ingestion (prevents "oops" moments).

```typescript
{
  path: string,              // File path (validated against allowlist)
  mode: 'head' | 'tail' | 'range' | 'search' | 'metadata',
  limit?: number,            // Max lines/bytes to return (default: 50 lines, max: 500)
  offset?: number,           // Starting line/byte (for range mode)
  pattern?: string           // Search pattern (for search mode)
}
```

**Modes:**

- **head** - First N lines (like `head -n`)
- **tail** - Last N lines (like `tail -n`)
- **range** - Lines from offset to offset+limit
- **search** - Lines matching pattern (like `grep`)
- **metadata** - File info only (size, type, line count)

**Image Inspection:**

For image files (`.png`, `.jpg`, `.jpeg`):
- **metadata** mode returns: dimensions, format, file size, EXIF data
- No description needed - ingestion will auto-generate via vision AI

**Example Workflow:**

```typescript
// 1. Check metadata of text file
inspect-file({
  path: "~/Documents/notes.md",
  mode: "metadata"
})
// → { size: "45 KB", lines: 823, type: "text/markdown" }

// 2. Preview first few lines
inspect-file({
  path: "~/Documents/notes.md",
  mode: "head",
  limit: 20
})
// → Returns first 20 lines (verify it's the right file)

// 3. Search for specific content
inspect-file({
  path: "~/Projects/app/config.yaml",
  mode: "search",
  pattern: "database"
})
// → Returns lines containing "database"

// 4. Check image metadata
inspect-file({
  path: "~/Documents/diagram.png",
  mode: "metadata"
})
// → { size: "1.2 MB", dimensions: "1920x1080", format: "PNG" }

// 5. Confirmed correct files, now ingest
ingest-file({
  path: "~/Documents/notes.md",
  ontology: "Research Notes"
})

ingest-file({
  path: "~/Documents/diagram.png",
  ontology: "Architecture"
})
// → Auto-description via vision AI, no manual input needed
```

**Security:**
- Same allowlist validation as ingestion tools
- Size limits prevent context consumption (max 500 lines per request)
- Read-only access (inspection cannot modify files)
- Audit logged like other file operations

**Tool: `ingest-file`**

Ingest a single file from local filesystem.

```typescript
{
  path: string,              // Absolute or relative path (validated)
  ontology: string,          // Ontology name
  auto_approve?: boolean,    // Default: true
  force?: boolean            // Re-ingest if exists (default: false)
}
```

**Automatic Image Handling:**

Images (`.png`, `.jpg`, `.jpeg`) are **fully automatic** - agent does NOTHING except submit path:

1. Detect image file by extension
2. Vision AI generates description automatically (ADR-057a)
3. Extract concepts from AI description
4. Store image in object storage with metadata

**Agent does NOT need to:**
- ❌ View the image
- ❌ Describe the image
- ❌ Analyze the image
- ❌ Provide metadata
- ❌ Do anything except submit the path

**Agent ONLY needs to:**
- ✅ Know the path to the image
- ✅ Choose which ontology to use
- ✅ Submit it (optionally after checking metadata)

```typescript
// Literally the same as text files - zero special handling
ingest-file({
  path: "~/Documents/diagrams/architecture.png",
  ontology: "System Architecture"
})
// System handles everything:
// → Detects it's an image
// → Vision AI auto-generates description
// → Extracts concepts automatically
// → Stores image for later retrieval
```

**Tool: `ingest-directory`**

Ingest all files in a directory (optionally recursive).

```typescript
{
  path: string,              // Directory path (validated)
  ontology?: string,         // Explicit ontology (optional if auto_naming=true)
  recursive?: boolean,       // Traverse subdirectories (default: false)
  auto_naming?: boolean,     // Auto-name ontologies by directory (default: true if no ontology)
  pattern?: string,          // Glob pattern filter (default: allowed_patterns)
  auto_approve?: boolean,    // Default: true
  force?: boolean            // Re-ingest existing (default: false)
}
```

**Asynchronous Processing:**

Directory ingestion creates multiple jobs that process asynchronously. The tool returns immediately with job IDs, but extraction happens in the background.

**Agent Guidance:**
- ✅ **DO:** Submit directory, receive job IDs, inform user processing has started
- ✅ **DO:** Continue with other work while jobs process
- ❌ **DON'T:** Poll job status immediately after submission
- ❌ **DON'T:** Wait for jobs to complete (can take minutes for large directories)

**Why:** Extraction is expensive (LLM API calls, embedding generation). Large directories may take 5-10 minutes. Polling wastes context on "still processing" messages.

**User can check status later:**
```bash
kg jobs list                    # See all jobs
kg jobs status <job-id>         # Check specific job
```

**Auto-Naming Modes:**

1. **Single Ontology** (ontology specified):
   - All files → same ontology name

2. **Directory-as-Ontology** (auto_naming=true, no ontology):
   - Each directory → separate ontology
   - Ontology name = directory name

3. **Path-based** (recursive + auto_naming):
   - Each subdirectory → separate ontology
   - Preserves project structure

### 3. MCP Resource

**Resource: `mcp/allowed-paths`**

Agent-readable (not writable) resource showing current allowlist.

```json
{
  "allowed_directories": [...],
  "allowed_patterns": [...],
  "blocked_patterns": [...],
  "max_file_size_mb": 10
}
```

Agent can check this resource to understand constraints before attempting ingestion.

### 4. Validation Logic

**Fail-Secure Path Validation:**

```typescript
function validatePath(filePath: string, config: AllowlistConfig): ValidationResult {
  // 1. Resolve to absolute path (prevents ../../../ attacks)
  const absolutePath = path.resolve(filePath);

  // 2. Check blocked patterns FIRST (fail-secure)
  for (const pattern of config.blocked_patterns) {
    if (minimatch(absolutePath, pattern)) {
      return { allowed: false, reason: `Matches blocked pattern: ${pattern}` };
    }
  }

  // 3. Must match at least one allowed directory
  let matchesAllowedDir = false;
  for (const dir of config.allowed_directories) {
    const expandedDir = expandTilde(dir);
    if (absolutePath.startsWith(expandedDir) || minimatch(absolutePath, expandedDir)) {
      matchesAllowedDir = true;
      break;
    }
  }

  if (!matchesAllowedDir) {
    return {
      allowed: false,
      reason: "Path not in any allowed directory",
      hint: `Allowed directories: ${config.allowed_directories.join(', ')}`
    };
  }

  // 4. Must match at least one allowed file pattern
  let matchesPattern = false;
  for (const pattern of config.allowed_patterns) {
    if (minimatch(absolutePath, pattern)) {
      matchesPattern = true;
      break;
    }
  }

  if (!matchesPattern) {
    return {
      allowed: false,
      reason: "File extension not allowed",
      hint: `Allowed patterns: ${config.allowed_patterns.join(', ')}`
    };
  }

  // 5. Check file size
  const stats = fs.statSync(absolutePath);
  const sizeMB = stats.size / (1024 * 1024);

  if (sizeMB > config.max_file_size_mb) {
    return {
      allowed: false,
      reason: `File too large: ${sizeMB.toFixed(2)}MB (max: ${config.max_file_size_mb}MB)`
    };
  }

  return { allowed: true };
}
```

### 5. Security Guarantees

**Fail-Secure Defaults:**
- Missing config file → deny all file access
- Empty allowed_directories → deny all
- Path validation failure → clear error to agent
- File too large → reject with size info

**Audit Trail:**

All file access attempts logged to `~/.config/kg/mcp-access.log`:

```
2025-11-08T22:50:00Z [INSPECT] /home/user/Documents/notes.md mode=head lines=20
2025-11-08T22:50:05Z [INGEST]  /home/user/Documents/notes.md -> Ontology: "Notes"
2025-11-08T22:50:15Z [DENIED]  /home/user/.env -> Reason: Matches blocked pattern
2025-11-08T22:50:30Z [DENIED]  /etc/passwd -> Reason: Not in allowed directory
2025-11-08T22:50:45Z [INSPECT] /home/user/wrong-file.txt mode=metadata (agent checks before rejecting)
```

**Agent Experience:**

When validation fails, agent receives helpful error:

```json
{
  "error": "Path not allowed",
  "reason": "Path '/home/user/secrets.txt' not in any allowed directory",
  "hint": "Allowed directories: ~/Documents/knowledge-base, ~/Projects/*/docs",
  "suggest": "Check mcp/allowed-paths resource for full allowlist"
}
```

### 6. Example Workflows

**Workflow 1: Research Paper Collection**

User configures allowlist:
```bash
kg mcp-config allow-dir ~/Documents/research
kg mcp-config allow-pattern "**/*.pdf"
```

Agent ingests:
```typescript
// Single file
ingest-file({
  path: "~/Documents/research/transformer-paper.pdf",
  ontology: "AI Research Papers"
})

// Whole directory
ingest-directory({
  path: "~/Documents/research/ml-papers",
  ontology: "Machine Learning Papers",
  pattern: "*.pdf"
})
```

**Workflow 2: Multi-Project Documentation**

User configures:
```bash
kg mcp-config allow-dir ~/Projects/*/docs
kg mcp-config allow-pattern "**/*.md"
```

Agent ingests with auto-naming:
```typescript
// Submit directory ingestion
const result = ingest-directory({
  path: "~/Projects",
  pattern: "docs/**/*.md",
  recursive: true,
  auto_naming: true
})

// Result: { job_ids: ["job_abc123", "job_def456"], message: "Processing 15 files..." }

// ✅ CORRECT: Inform user and move on
// "I've submitted 15 files for processing (jobs: job_abc123, job_def456).
//  This will take a few minutes. You can check status with: kg jobs list"

// ❌ WRONG: Don't poll immediately
// job.status("job_abc123")  // Don't do this!
// job.status("job_def456")  // Still processing, wastes context

// Results (when done):
// ~/Projects/project-a/docs/*.md → Ontology: "project-a"
// ~/Projects/project-b/docs/*.md → Ontology: "project-b"
```

**Workflow 3: Image Ingestion (Zero Agent Effort)**

```typescript
// Single image - agent does NOTHING but submit path
ingest-file({
  path: "~/Documents/diagrams/architecture.png",
  ontology: "System Architecture"
})
// Agent is done. System handles everything:
// → Vision AI generates: "A diagram showing microservices architecture with..."
// → Extracts concepts: "microservices architecture", "API gateway", etc.
// → Stores image for later retrieval

// Directory of images - agent does NOTHING but point at folder
ingest-directory({
  path: "~/Documents/screenshots",
  ontology: "UI Screenshots",
  pattern: "*.png"
})
// Agent is done. System processes each image:
// → screenshot-1.png → Vision AI → concepts → stored
// → screenshot-2.png → Vision AI → concepts → stored
// → screenshot-3.png → Vision AI → concepts → stored
// Agent doesn't see images, doesn't describe them, just submits the path

// Mixed content (text + images) - still just submit path
ingest-directory({
  path: "~/Documents/project-docs",
  ontology: "Project Documentation",
  recursive: true
})
// → *.md files → direct text extraction
// → *.png files → vision AI auto-description → extraction
// Agent does the same thing regardless of file type
```

---

## Consequences

### Positive

✅ **Security by Default**
- Fail-secure validation prevents path traversal
- Blocked patterns protect sensitive files
- File size limits prevent resource exhaustion

✅ **User Control**
- User explicitly configures allowed paths (CLI only)
- Agent can read allowlist but not modify
- Transparent - agent knows constraints upfront

✅ **Utility**
- Agent can ingest from pre-approved locations
- Directory recursion enables bulk ingestion
- Auto-naming preserves organizational structure

✅ **Preview Before Commit**
- `inspect-file` prevents ingestion mistakes
- Agent can verify file contents before submitting
- Avoids "oops" moments (hard to delete individual documents)
- Low context cost - inspect small portions, ingest full file

✅ **Auditability**
- All access attempts logged
- Clear error messages for debugging
- Allowlist visible to both user and agent

### Negative

⚠️ **Initial Configuration Burden**
- User must set up allowlist before agent can ingest files
- May be confusing for new users
- Mitigation: Provide safe defaults + clear onboarding

⚠️ **Claude Code Can Bypass**
- Claude Code agents with file editing can modify allowlist
- Acceptable risk - development environments need flexibility
- Mitigation: Document that allowlist is for Claude Desktop protection

⚠️ **Pattern Complexity**
- Users may struggle with glob patterns
- Mitigation: Provide examples, `test-path` command for validation

### Risks

🔴 **Path Validation Bugs**
- Risk: Bug in validation logic allows unauthorized access
- Mitigation: Comprehensive test suite, security review

🔴 **Symlink Attacks**
- Risk: Symlink inside allowed directory points outside
- Mitigation: Resolve symlinks, validate final path

🔴 **TOCTOU (Time-of-Check-Time-of-Use)**
- Risk: File changes between validation and read
- Mitigation: Read file immediately after validation, use file locks

---

## Alternatives Considered

### Alternative 1: No File Access

**Approach:** Don't add file ingestion to MCP server.

**Pros:**
- No security risks
- Simpler implementation

**Cons:**
- Severely limits utility
- Forces manual file management
- Agent can't help with documentation organization

**Rejected:** Utility gain worth the security investment.

### Alternative 2: Sandbox Directory Only

**Approach:** Only allow ingestion from `~/.config/kg/sandbox/`

**Pros:**
- Very simple security model
- Clear boundary

**Cons:**
- Forces users to move files to sandbox
- Breaks natural workflows
- Doesn't support multi-project scenarios

**Rejected:** Too restrictive, allowlist more flexible.

### Alternative 3: Agent-Modifiable Allowlist

**Approach:** Provide MCP tool to modify allowlist.

**Pros:**
- Agent can request access as needed
- More automated

**Cons:**
- Defeats security model entirely
- Agent could add any path
- No protection against malicious prompts

**Rejected:** Unacceptable security risk.

### Alternative 4: Per-Request Approval

**Approach:** User approves each file access in real-time.

**Pros:**
- Maximum control
- No configuration needed

**Cons:**
- Terrible UX - constant interruptions
- Breaks agent autonomy
- Impractical for bulk operations

**Rejected:** Too disruptive.

---

## Implementation Plan

### Phase 1: Configuration & Validation (ADR-062a)
- [ ] Allowlist configuration schema
- [ ] CLI commands for allowlist management
- [ ] Path validation logic with security tests
- [ ] MCP resource for allowed-paths visibility

### Phase 2: File Inspection & Ingestion (ADR-062b)
- [ ] `inspect-file` MCP tool (preview before commit)
  - Head/tail/range/search/metadata modes
  - Image metadata extraction (dimensions, EXIF)
- [ ] `ingest-file` MCP tool
  - Text file ingestion
  - Automatic image detection (by extension)
  - Vision AI auto-description for images (ADR-057a)
  - Object storage integration for images
- [ ] Access logging (INSPECT, INGEST, DENIED)

### Phase 3: Directory Ingestion (ADR-062c)
- [ ] `ingest-directory` MCP tool
- [ ] Recursive traversal logic
- [ ] Auto-naming strategies
- [ ] Bulk operation limits

### Phase 4: Security Hardening (ADR-062d)
- [ ] Symlink resolution and validation
- [ ] TOCTOU mitigation
- [ ] Security test suite
- [ ] Penetration testing

---

## Related ADRs

- **ADR-013:** Unified TypeScript Client (MCP server architecture)
- **ADR-051:** Silent Enrichment (source metadata)
- **ADR-057:** Image Ingestion (visual source handling)
- **ADR-060:** Endpoint Security Architecture (authentication model)

---

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Principle of Least Privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege)
- [Fail-Secure Design](https://en.wikipedia.org/wiki/Fail-safe)

---

## Notes

This ADR establishes the security foundation for MCP file ingestion. Implementation will be split into phases (ADR-062a-d) to allow iterative development and testing.

The allowlist approach provides strong security guarantees while maintaining utility. It assumes users are trustworthy (they control the allowlist) but agents are not (they can only read configuration).

**Key Insight:** By making the allowlist agent-readable but not agent-writable, we give agents transparency into constraints without giving them control. This enables helpful error messages and lets agents guide users to add paths via CLI.
