# 11 - Embedding Models and Vector Search

**Part:** II - Configuration
**Reading Time:** ~18 minutes
**Prerequisites:** [Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md), [Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)

---

This section explains how vector embeddings power semantic search in the knowledge graph. Embeddings transform text into numerical vectors that capture meaning. The system uses these vectors to find similar concepts, deduplicate extractions, and power the `kg search query` command.

## What Are Embeddings

An embedding is a list of numbers representing text meaning. Similar concepts have similar numbers. The system compares embeddings using cosine similarity (0.0-1.0 scale).

**Example:**

```
"distributed systems"    → [0.23, -0.45, 0.67, ...] (768 numbers)
"decentralized networks" → [0.21, -0.43, 0.69, ...] (similar!)
"cooking recipes"        → [-0.78, 0.12, -0.34, ...] (different)
```

When you run `kg search query "distributed systems"`, the system:
1. Converts your query text into an embedding
2. Compares it against all concept embeddings in the graph
3. Returns concepts with similarity ≥ 0.7 (default threshold)

---

## Embedding Providers

The system supports two providers:

### OpenAI (Cloud API)

**Model:** `text-embedding-3-small`
- **Dimensions:** 1536 (more detail, larger vectors)
- **Cost:** ~$0.0001 per embedding (~$0.10 per 1000 queries)
- **Speed:** 100-300ms per query (network latency)
- **Privacy:** Query text sent to OpenAI servers
- **Requires:** Internet access, valid API key

**Use when:**
- Getting started (default configuration)
- Small query volume (<10,000/month)
- Don't want to manage local models
- Need high-quality embeddings without setup

### Local (Self-Hosted)

**Model:** `nomic-ai/nomic-embed-text-v1.5`
- **Dimensions:** 768 (efficient, smaller vectors)
- **Cost:** $0 (zero ongoing costs)
- **Speed:** <50ms per query (local inference)
- **Privacy:** Complete - queries never leave your machine
- **Requires:** 400MB RAM, 275MB disk space

**Use when:**
- High query volume (>10,000/month)
- Privacy requirements (sensitive documents)
- Offline capability needed
- Want to eliminate API costs
- Have spare server resources

---

## Viewing Current Configuration

Check which embedding model is active:

```bash
kg admin embedding config
```

**Example output:**

```
🎯 Embedding Configuration
────────────────────────────────────────

  Provider:   openai
  Model:      text-embedding-3-small
  Dimensions: 1536

  Config ID: 1
```

This shows what model generates embeddings for all queries and concept matching.

---

## Switching Embedding Models

### Important: Model Consistency

**The system requires the same embedding model for everything.**

All concept embeddings stored in the database must match the model used for queries. Mixing models (storing concepts with OpenAI embeddings, querying with local embeddings) produces meaningless similarity scores.

**When you switch models, you must re-embed all existing concepts.**

### Configuration Protection

The system prevents accidental model changes that would break vector search.

**View all configurations and protection status:**

```bash
kg admin embedding list
```

**Example output:**

```
📋 Embedding Configurations
────────────────────────────────────────

  ✓ ACTIVE Config 1 🔒 🔐
    Provider:   openai
    Model:      text-embedding-3-small
    Dimensions: 1536
    Protection: delete-protected, change-protected
    Updated:    10/22/2025, 9:06:23 AM

  ○ Inactive Config 2
    Provider:   local
    Model:      nomic-ai/nomic-embed-text-v1.5
    Dimensions: 768
    Updated:    10/21/2025, 3:45:12 PM
```

**Icons:**
- ✓ ACTIVE - Currently used for all embeddings
- ○ Inactive - Historical configuration, not used
- 🔒 - Delete-protected (cannot delete this config)
- 🔐 - Change-protected (cannot change provider/dimensions)

**Protection flags prevent:**
- Accidentally deleting the active configuration
- Changing embedding dimensions without explicit approval
- Breaking vector search across the entire graph

### Switch from OpenAI to Local

Complete workflow for changing embedding providers:

```bash
# 1. View current config and note the ID
kg admin embedding list

# 2. Remove change protection from active config
kg admin embedding unprotect 1 --change

# 3. Create new local embedding configuration
kg admin embedding set \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --device cpu \
  --memory 512 \
  --threads 4 \
  --batch-size 8

# 4. Hot reload to apply changes (zero-downtime swap)
kg admin embedding reload

# 5. Verify new config is active and auto-protected
kg admin embedding list
```

**What happens:**
- New local model configuration becomes active
- System downloads the model from HuggingFace (~30-60 seconds first time)
- Model loaded into memory (~400MB RAM)
- Hot reload swaps models with zero downtime
- New config automatically protected to prevent immediate follow-up accidents

**After switching models, re-embed all concepts:**

```bash
# Option 1: Delete and re-ingest ontologies
kg ontology delete "My Ontology"
kg ingest file -o "My Ontology" -y document.txt

# Option 2: Use embedding migration tool (if available)
kg embedding migrate --model nomic-ai/nomic-embed-text-v1.5
```

The old embeddings (1536-dimensional) are incompatible with the new model (768-dimensional). All concepts need fresh embeddings.

### Switch Back to OpenAI

```bash
# 1. Remove change protection
kg admin embedding unprotect <active-config-id> --change

# 2. Switch back to OpenAI
kg admin embedding set --provider openai

# 3. Hot reload
kg admin embedding reload

# 4. Re-embed all concepts (dimensions changed: 768→1536)
kg embedding migrate --model text-embedding-3-small
```

---

## Local Model Setup

### Requirements

**System Resources:**
- RAM: 400-500MB for nomic-embed-text-v1.5
- Disk: 275MB for model weights
- CPU: Any modern CPU (GPU not required)
- Network: Internet access for initial model download only

### Model Download

The first time you switch to local embeddings, the system downloads the model from HuggingFace:

```bash
kg admin embedding set --provider local --model "nomic-ai/nomic-embed-text-v1.5" --dimensions 768
kg admin embedding reload
```

**What happens:**
1. System checks cache: `~/.cache/huggingface/`
2. If not cached, downloads from HuggingFace (~30-60 seconds)
3. Caches model locally
4. Loads into memory
5. Subsequent reloads use cached version (fast)

**Progress output:**

```
Downloading nomic-ai/nomic-embed-text-v1.5...
  [████████████████████] 275.2 MB / 275.2 MB
Model cached successfully
Loading model into memory...
✓ Model loaded (768 dimensions)
```

### Persistent Model Storage

In Docker deployments, add a volume for the HuggingFace cache to persist models across container restarts:

**docker-compose.yml:**

```yaml
services:
  api:
    volumes:
      - ./src:/app/src
      - huggingface-cache:/root/.cache/huggingface  # Persist models

volumes:
  postgres_data:
  huggingface-cache:
```

This prevents re-downloading models after `docker-compose restart`.

### Resource Tuning

Adjust resource allocation for local embeddings:

```bash
kg admin embedding set \
  --memory 1024 \      # Increase RAM limit (MB)
  --threads 8 \        # Use more CPU threads
  --batch-size 16      # Process more embeddings at once
```

**Note:** Resource changes don't require removing protection (dimensions unchanged).

---

## Hot Reload

The system supports zero-downtime model swapping.

```bash
kg admin embedding reload
```

**What happens:**
1. System loads new embedding configuration from database
2. New model initialized in parallel (old model still serving requests)
3. Atomic swap to new model
4. Old model released from memory
5. New configuration automatically protected

**During reload:**
- In-flight queries complete with old model
- New queries wait briefly (~1-2 seconds) then use new model
- API remains responsive throughout
- Brief memory spike (2x model size for 1-2 seconds)

**No API restart required.**

---

## Embedding Dimensions

Different models produce different-sized embeddings:

| Model | Provider | Dimensions | Use Case |
|-------|----------|------------|----------|
| text-embedding-3-small | OpenAI | 1536 | Default, high quality |
| nomic-embed-text-v1.5 | Local | 768 | Efficient, cost-free |
| bge-base-en-v1.5 | Local | 768 | Alternative local model |
| bge-large-en-v1.5 | Local | 1024 | High accuracy local |

**Higher dimensions ≠ better quality.** Model architecture matters more than dimension count.

**Dimension changes break compatibility:**
- Switching from 1536→768 requires re-embedding all concepts
- Switching between models with same dimensions (768→768) still requires re-embedding (incompatible vector spaces)

---

## Model Comparison

### OpenAI vs Local Performance

**OpenAI text-embedding-3-small:**
- ✅ Zero setup, works immediately
- ✅ High quality embeddings
- ✅ No server resources needed
- ❌ $0.0001 per embedding
- ❌ 100-300ms latency (network)
- ❌ Requires internet access
- ❌ Query text sent to external service

**Local nomic-embed-text-v1.5:**
- ✅ $0 cost after initial setup
- ✅ <50ms latency (local inference)
- ✅ Complete privacy (offline capable)
- ✅ No internet required after download
- ❌ 400MB RAM usage
- ❌ 275MB disk space
- ❌ Initial download time (~60 seconds)

### Quality Comparison

Both models produce excellent semantic search results for the knowledge graph use case. Nomic-embed has been tested extensively with this system and performs on par with OpenAI for concept matching and query similarity.

**Benchmark (internal testing):**
- Concept deduplication accuracy: 94% (nomic) vs 95% (OpenAI)
- Semantic query relevance: 92% (nomic) vs 93% (OpenAI)
- Processing speed: 20x faster (nomic local inference)

The 1-2% quality difference is negligible for knowledge graph applications. Cost savings and privacy benefits outweigh the minor accuracy trade-off.

---

## Configuration Commands

### View Configuration

```bash
# Active configuration (public)
kg admin embedding config

# All configurations with protection status (admin)
kg admin embedding list
```

### Set Configuration

```bash
# OpenAI
kg admin embedding set --provider openai

# Local (full parameters)
kg admin embedding set \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --device cpu \
  --memory 512 \
  --threads 4 \
  --batch-size 8

# Local (minimal - uses defaults)
kg admin embedding set \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768
```

### Protection Management

```bash
# Enable protection
kg admin embedding protect <config-id> --change --delete

# Remove protection (required before switching models)
kg admin embedding unprotect <config-id> --change

# Remove delete protection
kg admin embedding unprotect <config-id> --delete
```

### Delete Configuration

```bash
# Delete inactive configuration
kg admin embedding delete <config-id>

# Prompts: Delete embedding config 2? (yes/no):
```

Cannot delete if:
- Configuration is active
- Configuration is delete-protected (remove protection first)

---

## Troubleshooting

### Error: "Active config is change-protected"

**Full error:**
```
✗ Failed to update embedding configuration
Active config (ID 1) is change-protected. Changing provider or dimensions
breaks vector search. Remove protection first with:
  kg admin embedding unprotect 1 --change
```

**Solution:**

```bash
# Remove change protection
kg admin embedding unprotect 1 --change

# Then update configuration
kg admin embedding set --provider local --model "..." --dimensions 768

# Reload
kg admin embedding reload
```

### Error: "Config is delete-protected"

**Full error:**
```
✗ Failed to delete configuration
Config is delete-protected. Remove protection first with:
  kg admin embedding unprotect <id> --delete
```

**Solution:**

```bash
kg admin embedding unprotect <config-id> --delete
kg admin embedding delete <config-id>
```

### Vector Search Returns Wrong Results

**Symptom:** Search results don't make sense, irrelevant concepts returned.

**Cause:** Embedding model changed but concepts not re-embedded.

**Solution:**

When you change embedding dimensions or models, all existing concept embeddings become incompatible. Re-embed everything:

```bash
# Option 1: Delete and re-ingest ontologies
kg ontology delete "My Ontology"
kg ingest file -o "My Ontology" -y document.txt

# Option 2: Use migration tool (if available)
kg embedding migrate --model nomic-ai/nomic-embed-text-v1.5
```

### Local Model Download Fails

**Error:** Model not found or download timeout.

**Causes:**
- No internet access
- Wrong model name format
- HuggingFace service down

**Solution:**

**Verify model name format:**
```bash
# Correct format
nomic-ai/nomic-embed-text-v1.5

# Incorrect formats
nomic-embed-text-v1.5          # Missing organization
nomic-ai/nomic-embed           # Incomplete model name
```

**Check internet access:**
```bash
curl -I https://huggingface.co
```

**Retry download:**
```bash
kg admin embedding reload
```

### Memory Issues with Local Model

**Error:** Out of memory (OOM) during model load.

**Solution:**

Reduce memory allocation or use lighter precision:

```bash
kg admin embedding set \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \  # Use float16 instead of float32
  --memory 256 \          # Reduce from default 512
  --batch-size 4          # Reduce from default 8
```

---

## Best Practices

### Always Use Hot Reload

Never restart the API to apply embedding changes. Use hot reload:

```bash
# Good
kg admin embedding reload

# Bad (causes downtime)
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Test Before Production

Test model switches on non-production data first:

```bash
# 1. Switch model
kg admin embedding unprotect <id> --change
kg admin embedding set --provider local --model "..." --dimensions 768
kg admin embedding reload

# 2. Test with small query
kg search query "test concept"

# 3. Verify results make sense

# 4. If good, re-embed all production data
```

### Don't Delete Default Config

The default OpenAI configuration is delete-protected for good reason. Keep it for rollback purposes.

### Plan for Re-Embedding

Switching models requires re-embedding all concepts. Plan downtime or staged migration:

**Staged migration:**
1. Switch model
2. Re-ingest Ontology A
3. Verify search works
4. Re-ingest Ontology B
5. Continue until all ontologies migrated

### Document Model Changes

Track which model was used when:

```bash
kg admin embedding list  # Shows history with timestamps
```

If search quality degrades, check if model changed recently.

---

## When to Switch Models

### Stay with OpenAI If:

- Query volume <1,000/month (~$0.10/month cost)
- You want zero server overhead
- You're prototyping or testing
- You don't have privacy requirements

### Switch to Local If:

- Query volume >10,000/month (>$1/month cost)
- Privacy matters (sensitive documents)
- You want offline capability
- You have spare server resources (400MB RAM)
- Long-term cost optimization

**Break-even point:** ~50,000 queries/month (~$5/month). Local models pay for themselves in reduced API costs.

---

## What's Next

Now that you understand embeddings, you can:

- **[Section 12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)**: Setup local extraction models
- **[Section 13 - Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md)**: Customize relationship types
- **[Section 14 - Advanced Query Patterns](14-advanced-query-patterns.md)**: Complex graph queries

For technical details:
- **Architecture:** [ADR-039 - Local Embedding Service](architecture/ADR-039-local-embedding-service.md)
- **Configuration Guide:** [guides/EMBEDDING_CONFIGURATION.md](guides/EMBEDDING_CONFIGURATION.md)

---

← [Previous: AI Extraction Configuration](10-ai-extraction-configuration.md) | [Documentation Index](README.md) | [Next: Local LLM Inference with Ollama →](12-local-llm-inference-with-ollama.md)
