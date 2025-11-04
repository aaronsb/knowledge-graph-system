# kg ingest

> Auto-generated

## ingest

Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-014) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.

**Usage:**
```bash
kg ingest [options]
```

**Subcommands:**

- `file` - Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-014), -w to wait for completion (polls until complete, shows progress).
- `directory` - Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default *.md *.txt), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.
- `text` - Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.
- `image` - Ingest an image file using multimodal vision AI (ADR-057). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

---

### file

Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-014), -w to wait for completion (polls until complete, shows progress).

**Usage:**
```bash
kg file <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (named collection or knowledge domain) | - |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses hash check, creates new job) | `false` |
| `--no-approve` | Require manual approval before processing (job enters awaiting_approval state, must approve via "kg job approve <id>"). Default: auto-approve. | - |
| `--parallel` | Process in parallel (all chunks simultaneously, chunks don't see each other, may duplicate concepts, faster). Default: serial (sequential, cleaner deduplication, recommended). | `false` |
| `--filename <name>` | Override filename for tracking (displayed in ontology files list) | - |
| `--target-words <n>` | Target words per chunk (actual may vary based on natural boundaries, range 500-2000 typically effective) | `"1000"` |
| `--overlap-words <n>` | Word overlap between chunks (provides context continuity, helps LLM understand cross-chunk relationships) | `"200"` |
| `-w, --wait` | Wait for job completion (polls status, shows progress, returns final results). Default: submit and exit (returns immediately with job ID, monitor via "kg job status <id>"). | `false` |

### directory

Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default *.md *.txt), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.

**Usage:**
```bash
kg directory <dir>
```

**Arguments:**

- `<dir>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required unless --directories-as-ontologies). Single ontology receives all files. | - |
| `-p, --pattern <patterns...>` | File patterns to match (glob patterns like *.md *.txt) | `["*.md","*.txt"]` |
| `-r, --recurse` | Recursively scan subdirectories. Use "--recurse --depth all" for unlimited depth, "--recurse --depth 2" for 2 levels, etc. | `false` |
| `-d, --depth <n>` | Maximum recursion depth: 0=current dir only, 1=one level, 2=two levels, "all"=unlimited (use with --recurse) | `"0"` |
| `--directories-as-ontologies` | Use directory names as ontology names (auto-creates ontologies from folder structure, cannot be combined with -o) | `false` |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses hash check for all files) | `false` |
| `--dry-run` | Show what would be ingested without submitting jobs (validates files, checks duplicates, displays skip/submit counts, cancels test jobs) | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (faster but may create duplicate concepts) | `false` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |

### text

Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.

**Usage:**
```bash
kg text <text>
```

**Arguments:**

- `<text>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (named collection or knowledge domain) | - |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses content hash check) | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (faster but may create duplicate concepts) | `false` |
| `--filename <name>` | Filename for tracking (displayed in ontology files list, temporary path context) | `"text_input"` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `-w, --wait` | Wait for job completion (polls until complete, shows progress). Default: submit and exit. | `false` |

### image

Ingest an image file using multimodal vision AI (ADR-057). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

**Usage:**
```bash
kg image <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing. Default: auto-approve. | - |
| `--vision-provider <provider>` | Vision provider: openai (default), anthropic, ollama | `"openai"` |
| `--vision-model <model>` | Vision model name (optional, uses provider default) | - |
| `--filename <name>` | Override filename for tracking | - |
| `-w, --wait` | Wait for job completion | `false` |
