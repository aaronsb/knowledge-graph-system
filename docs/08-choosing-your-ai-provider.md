# 08 - Choosing Your AI Provider

**Part:** II - Configuration
**Reading Time:** ~20 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 05 - The Extraction Process](05-the-extraction-process.md)

---

This section helps you choose which AI provider to use for concept extraction. The system supports cloud providers (OpenAI, Anthropic) and local inference (Ollama with various models). Each has trade-offs in quality, speed, cost, and privacy.

## The Core Question

Every knowledge graph ingestion requires an LLM to extract concepts from text. You need to decide:

1. **Cloud or local?** Pay per API call vs run models on your hardware
2. **Which model?** Different models produce different quality extractions
3. **Which provider?** Each provider has strengths and weaknesses

The answer depends on your corpus size, budget, privacy requirements, and hardware availability.

---

## Available Providers

### Cloud Providers

**OpenAI (gpt-4o, gpt-4o-mini)**

The system defaults to OpenAI's GPT-4o. It produces high-quality extractions with strong canonical adherence. Cloud API calls cost money but are fast and require no local setup.

- **Models:** gpt-4o, gpt-4o-mini
- **Speed:** 2 seconds per chunk
- **Cost:** ~$0.017 per chunk (~$10 per 600 chunks)
- **Canonical adherence:** 88% (2 non-canonical types per 30 expected)
- **Concepts extracted:** 46 per document (test: Alan Watts lecture)
- **Best for:** Production systems, time-sensitive work, prototyping

**Anthropic (Claude Sonnet 4, Claude 3.5 Sonnet)**

Anthropic's Claude models provide an alternative to OpenAI. Expected quality is similar to GPT-4o with slightly lower costs. The system has not yet run extensive extraction comparisons with Claude.

- **Models:** claude-sonnet-4-20250514, claude-3-5-sonnet-20241022
- **Speed:** Similar to GPT-4o (~2-3 seconds per chunk)
- **Cost:** ~$0.008 per chunk (cheaper than OpenAI)
- **Canonical adherence:** Expected similar to GPT-4o
- **Best for:** Diversification, cost savings, failover option

### Local Provider

**Ollama (Mistral, Qwen, GPT-OSS, Llama)**

Ollama runs models locally on your hardware. Zero ongoing costs, complete privacy, offline capability. Requires GPU for reasonable speed. The system has tested several models with varying results.

**Tested Models:**

1. **Qwen3 14B** - Extraction champion
   - **Concepts:** 57 per document (highest of all tested models)
   - **Canonical adherence:** 74% (10 non-canonical types)
   - **Speed:** 60 seconds per chunk
   - **VRAM:** 16GB (consumer GPU accessible)
   - **Best for:** Maximum concept extraction on accessible hardware

2. **Qwen 2.5 14B** - Schema compliance champion
   - **Concepts:** 24 per document
   - **Canonical adherence:** 92% (highest of all tested models)
   - **Speed:** 15 seconds per chunk
   - **VRAM:** 16GB
   - **Best for:** Strict canonical compliance, professional quality

3. **GPT-OSS 20B** - Dense relationship champion
   - **Concepts:** 48 per document
   - **Relationships:** 190 edges (densest graph)
   - **Canonical adherence:** 65%
   - **Speed:** 20 seconds per chunk
   - **VRAM:** 20GB+ (or CPU+GPU split)
   - **Problem:** Reasoning model architecture - unsuitable for extraction tasks
   - **Best for:** Research requiring dense graphs, if you have powerful hardware

4. **Mistral 7B** - Avoid for production
   - **Concepts:** 32 per document
   - **Canonical adherence:** 38% (severe vocabulary pollution)
   - **Speed:** 10 seconds per chunk
   - **VRAM:** 8GB
   - **Problem:** Creates non-canonical relationship types uncontrollably
   - **Best for:** Nothing - avoid

---

## Cloud vs Local Decision

### Choose Cloud (OpenAI/Anthropic) If:

You have **fewer than 50 documents** to ingest. The cost is negligible ($5-10) and setup is immediate. Cloud providers offer the fastest extraction and highest quality.

You need **speed**. GPT-4o processes chunks in 2 seconds. The fastest local model (Qwen 2.5) takes 15 seconds. Qwen3 takes 60 seconds. For time-sensitive projects, cloud wins by 7-30x.

You don't have **GPU hardware**. Running local models on CPU is extremely slow (5-10 minutes per chunk). Cloud inference is the practical choice without a GPU.

You want the **highest quality** extraction. GPT-4o produces 46 concepts with 88% canonical adherence and a dense 172-edge graph. It balances coverage, schema compliance, and relationship richness better than any local model.

### Choose Local (Ollama) If:

You have **more than 500 documents** to process. GPT-4o costs $10 per 100 documents. A 1000-document corpus costs $100. Local inference is zero cost after initial setup.

You need **privacy**. Cloud providers see your documents. If you're ingesting proprietary research, company documents, or personal notes, local inference keeps everything on your hardware.

You want **maximum concept extraction**. Qwen3 14B extracts 57 concepts per document - more than GPT-4o (46), more than any other tested model - and fits in consumer 16GB VRAM. The trade-off is slower speed (60s/chunk) and acceptable canonical adherence (74%).

You want **strict canonical compliance**. Qwen 2.5 14B achieves 92% canonical adherence - higher than GPT-4o (88%) or any other model. Only 1 non-canonical type appears versus GPT-4o's 2.

You can tolerate **slower extraction**. A 1000-document corpus takes 3 hours with GPT-4o, 25 hours with Qwen 2.5 14B, or 100 hours with Qwen3 14B. If you can run overnight jobs, local models work fine.

### The Break-Even Point

At what corpus size does local inference become worth the setup effort?

- **< 50 documents:** Use GPT-4o. Cost under $5, time savings valuable.
- **50-500 documents:** Local models competitive. $5-50 savings, acceptable time cost.
  - Choose **Qwen 2.5** for canonical purity (92%)
  - Choose **Qwen3** for maximum concepts (2.4x more than Qwen 2.5)
- **500+ documents:** Local models strongly recommended. $50+ savings, time investment pays off.
  - Choose **Qwen3 14B** for maximum extraction (57K concepts vs 24K)
  - Choose **Qwen 2.5 14B** for strict canonical compliance (92%)

---

## Model Comparison Details

### Extraction Quality

The system ran identical extraction tests on an Alan Watts philosophy lecture using all providers. The document was chunked into 6 pieces (~1000 words each). Results:

| Provider | Concepts | Relationships | Canonical % | Speed/Chunk | Cost/Chunk | VRAM |
|----------|----------|---------------|-------------|-------------|------------|------|
| **GPT-4o** | 46 | 172 edges | 88% | 2s | $0.017 | Cloud |
| **Qwen3 14B** | **57** | 61 edges | 74% | 60s | $0.00 | 16GB |
| **Qwen 2.5 14B** | 24 | 98 edges | **92%** | 15s | $0.00 | 16GB |
| **GPT-OSS 20B** | 48 | **190 edges** | 65% | 20s | $0.00 | 20GB+ |
| **Mistral 7B** | 32 | 134 edges | 38% | 10s | $0.00 | 8GB |

**Key findings:**

Qwen3 14B extracts the most concepts (57) - beating even cloud-based GPT-4o. It fits in consumer 16GB VRAM. The trade-off is slower speed (60 seconds per chunk versus GPT-4o's 2 seconds) and acceptable canonical adherence (74% versus Qwen 2.5's 92%).

Qwen 2.5 14B has the highest canonical adherence (92%) - better than GPT-4o. It produces professional-quality extractions with minimal schema drift. The trade-off is fewer concepts extracted (24 versus GPT-4o's 46).

GPT-4o provides the best balance. It extracts 46 concepts with 88% canonical adherence and a dense 172-edge relationship graph in 2 seconds. For production systems, it's the quality/speed/canonical sweet spot.

GPT-OSS 20B creates the densest relationship graph (190 edges) but suffers from being a reasoning model. Reasoning models analyze concepts philosophically instead of extracting them efficiently. They often timeout or produce inconsistent results. The system calls this the "Abe Simpson problem" - reasoning models ramble about the task instead of completing it.

Mistral 7B should be avoided. It creates non-canonical relationship types uncontrollably, polluting the vocabulary. After 100 documents, Mistral generates ~80 relationship types (30 canonical + 50 invented) versus GPT-4o's ~35 types.

### Canonical Adherence Matters

The system defines 30 canonical relationship types organized in 8 categories (logical, causal, structural, evidential, similarity, temporal, functional, meta). LLMs sometimes create new types like `IS_ALTERNATIVE_TO` instead of the canonical `SIMILAR_TO`.

When an LLM generates a non-canonical type:
1. The fuzzy matcher tries to map it to a canonical type
2. If no match found, the system auto-accepts it as a new type
3. Future chunks can now use this non-canonical type
4. Vocabulary expands uncontrollably

After processing 100 documents:
- **GPT-4o:** ~35 relationship types (30 canonical + 5 creative) ✅
- **Qwen 2.5 14B:** ~32 relationship types (30 canonical + 2 creative) ✅
- **Qwen3 14B:** ~40 relationship types (30 canonical + 10 creative) ⚠️
- **GPT-OSS 20B:** ~50 relationship types (30 canonical + 20 creative) ⚠️
- **Mistral 7B:** ~80 relationship types (30 canonical + 50 creative) ❌

Canonical adherence is critical for long-term schema quality. Systems with low adherence accumulate relationship types over time, making querying and interpretation harder.

### Model Size ≠ Quality

Counter-intuitive result: The 14-billion parameter Qwen 2.5 model achieves 92% canonical adherence while the 20-billion parameter GPT-OSS model only achieves 65%. Parameter count doesn't predict schema compliance.

Qwen3 14B extracts 19% more concepts than GPT-OSS 20B (57 versus 48) while fitting in consumer 16GB VRAM instead of requiring 20GB+. Hardware accessibility matters.

The Qwen3 versus Qwen 2.5 comparison validates that newer model generations achieve higher extraction volume. Qwen3 (January 2025) extracts 2.4x more concepts than Qwen 2.5 (October 2024) from the same architecture.

### The Reasoning Model Problem

GPT-OSS 20B is a reasoning model designed for complex problem-solving. Concept extraction is pattern recognition, not problem-solving. Reasoning models spend thousands of tokens analyzing what concepts mean instead of extracting them.

**Reasoning model behavior:**
```
"To extract concepts from this passage, I must first consider
the epistemological implications of Watts' argument...
[15,000 tokens of meta-analysis]
...which leads me to conclude that the concept of 'ego' should
be separated from... TIMEOUT"
```

**Instruction model behavior (Qwen3):**
```
"Here are 10 concepts with instances and relationships.
JSON attached. Done in 60 seconds."
```

Reasoning models are philosophers. Instruction models are librarians. Concept extraction requires a librarian.

---

## Practical Recommendations

### For Individual Users

**Start with GPT-4o** for your first 10-20 documents. This lets you learn the system, understand extraction quality, and calibrate expectations without Ollama setup complexity.

**Switch to Qwen 2.5 14B** when your corpus exceeds 50 documents, privacy matters, or long-term cost accumulation is a concern. You get professional quality (92% canonical) with zero ongoing cost.

**Switch to Qwen3 14B** when you want maximum concept extraction (57 concepts versus Qwen 2.5's 24). You need 16GB VRAM and can tolerate 60 seconds per chunk. The wait is worth it for 9.5 concepts extracted per chunk.

**Consider GPT-OSS 20B** only if you have 20GB+ VRAM, need the densest relationship network (190 edges), and can accept 65% canonical adherence for exploratory research.

### For Organizations

**Use GPT-4o** for customer-facing knowledge bases, time-sensitive projects, shared/collaborative graphs, or when $100-500/month is acceptable. The speed advantage (30x faster than Qwen3) and balanced quality justify the cost.

**Use Qwen 2.5 14B** for large internal corpora (10,000+ documents), proprietary/sensitive data where canonical schema compliance matters most, budget constraints with professional quality requirements, or departments with GPU infrastructure.

**Use Qwen3 14B** for maximum concept extraction (57 concepts per document), research departments needing comprehensive coverage, consumer-grade GPU infrastructure (16GB VRAM), or when acceptable canonical adherence (74%) with high volume is the right trade-off.

**Consider Anthropic Claude** for diversity, failover, or cost savings. Expected quality is similar to GPT-4o with slightly lower costs ($0.008 versus $0.010 per 1000 words).

---

## Configuration

### Cloud Provider Setup (OpenAI)

Create or edit `.env` in the project root:

```bash
AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_EXTRACTION_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Test the configuration:

```bash
./scripts/configure-ai.sh
# Choose option 1 to test OpenAI connection
```

Start the API server and ingest a document:

```bash
./scripts/start-api.sh
kg ingest file -o "Test Ontology" -y your-document.txt
```

### Cloud Provider Setup (Anthropic)

Edit `.env`:

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Note: Even with Anthropic extraction, embeddings currently use OpenAI's `text-embedding-3-small` model. This requires an OpenAI API key for embeddings:

```bash
OPENAI_API_KEY=sk-your-openai-key-for-embeddings
```

Restart the API server to apply changes:

```bash
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Local Provider Setup (Ollama)

Start the Ollama container:

```bash
./scripts/start-ollama.sh -y
```

Pull your chosen model:

```bash
# For maximum concept extraction (16GB VRAM)
docker exec kg-ollama ollama pull qwen3:14b

# For strict canonical compliance (16GB VRAM)
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# For dense relationship graphs (20GB+ VRAM, not recommended)
docker exec kg-ollama ollama pull gpt-oss:20b
```

Configure the system to use Ollama:

```bash
kg admin extraction set --provider ollama --model qwen3:14b
```

This updates the configuration database. Restart the API server:

```bash
./scripts/stop-api.sh && ./scripts/start-api.sh
```

Test extraction:

```bash
kg admin extraction test
```

Ingest a document:

```bash
kg ingest file -o "Test Ontology" -y your-document.txt
```

### Switching Providers

You can switch providers at any time. Existing concepts in your graph remain unchanged. New ingestions use the new provider.

**Switch from OpenAI to Ollama:**

```bash
# Pull the model
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# Configure
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# Test
kg admin extraction test
```

**Switch back to OpenAI:**

```bash
kg admin extraction set --provider openai --model gpt-4o
./scripts/stop-api.sh && ./scripts/start-api.sh
```

---

## Cost Analysis

### Small Corpus (10 documents, ~60 chunks)

| Provider | Time | Cost | Concepts | Quality |
|----------|------|------|----------|---------|
| GPT-4o | 2 min | $1.02 | ~460 | Excellent (88%) |
| Qwen3 14B | 1 hr | $0.00 | ~570 | Good (74%) |
| Qwen 2.5 14B | 15 min | $0.00 | ~240 | Excellent (92%) |

**Recommendation:** Use GPT-4o. Cost is negligible, time savings valuable.

### Medium Corpus (100 documents, ~600 chunks)

| Provider | Time | Cost | Concepts | Quality |
|----------|------|------|----------|---------|
| GPT-4o | 20 min | $10.20 | ~4,600 | Excellent (88%) |
| Qwen3 14B | 10 hrs | $0.00 | ~5,700 | Good (74%) |
| Qwen 2.5 14B | 2.5 hrs | $0.00 | ~2,400 | Excellent (92%) |

**Recommendation:** Qwen 2.5 or Qwen3 competitive. Choose based on canonical purity (Qwen 2.5) versus maximum concepts (Qwen3).

### Large Corpus (1000 documents, ~6000 chunks)

| Provider | Time | Cost | Concepts | Quality |
|----------|------|------|----------|---------|
| GPT-4o | 3.3 hrs | $102 | ~46,000 | Excellent (88%) |
| Qwen3 14B | 100 hrs | $0.00 | ~57,000 | Good (74%) |
| Qwen 2.5 14B | 25 hrs | $0.00 | ~24,000 | Excellent (92%) |

**Recommendation:** Local models strongly recommended. $100+ savings, time investment pays off. Choose Qwen3 for max concepts, Qwen 2.5 for canonical purity.

---

## Quality vs Speed Trade-offs

### Speed Priority: GPT-4o

If you need results fast, GPT-4o is the only choice. It processes chunks 30x faster than Qwen3, 7.5x faster than Qwen 2.5. For time-sensitive projects, the cost is worth it.

### Quality Priority: Qwen 2.5 14B or GPT-4o

For strict canonical compliance, Qwen 2.5 14B leads with 92% adherence. For balanced quality (concepts + relationships + canonical), GPT-4o leads with 46 concepts, 172 edges, 88% canonical.

### Coverage Priority: Qwen3 14B

For maximum concept extraction, Qwen3 14B extracts 57 concepts per document - more than any other tested model including cloud-based GPT-4o. The trade-off is slower speed (60s/chunk) and acceptable canonical adherence (74%).

### Budget Priority: Any Local Model

Zero ongoing costs. Qwen 2.5 14B offers the best quality/budget ratio for professional work. Qwen3 14B offers the best coverage/budget ratio for research.

---

## Hardware Requirements

### Cloud Providers (OpenAI, Anthropic)

No local hardware requirements. You need internet connectivity and an API key.

### Local Models (Ollama)

**Qwen 2.5 14B / Qwen3 14B:**
- GPU: 16GB VRAM (consumer grade - RTX 4080, RTX 3090, A4000)
- RAM: 32GB system memory recommended
- Storage: 10GB for model weights

**GPT-OSS 20B:**
- GPU: 20GB+ VRAM (RTX 4090, A5000, A6000) or CPU+GPU split
- RAM: 64GB system memory for CPU offloading
- Storage: 15GB for model weights

**CPU-Only:**

Running models on CPU is extremely slow (5-10 minutes per chunk). Not practical for any corpus size. If you don't have a GPU, use cloud providers.

---

## Privacy Considerations

### Cloud Providers

OpenAI and Anthropic see your document content. Their privacy policies state they don't train on API data, but the data leaves your infrastructure. For proprietary research, company documents, or sensitive information, this may be unacceptable.

### Local Models

Ollama runs entirely on your hardware. Documents never leave your machine. The system is offline-capable once models are downloaded. For maximum privacy, use local inference.

---

## Embeddings

All providers currently use OpenAI's `text-embedding-3-small` model to generate 1536-dimensional vector embeddings for semantic search. This means:

- Even with local extraction (Ollama), embeddings require OpenAI API calls
- Future versions will support local embedding models (sentence-transformers)
- For complete privacy, wait for local embedding support

---

## What's Next

Now that you understand provider options, you can:

- **[Section 09 - Common Workflows and Use Cases](09-common-workflows-and-use-cases.md)**: Practical workflows with chosen provider
- **[Section 10 - AI Extraction Configuration](10-ai-extraction-configuration.md)**: Fine-tune extraction behavior
- **[Section 12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)**: Deep dive into Ollama setup

For detailed comparisons:
- **Architecture:** [ADR-042 - Local LLM Inference](architecture/ADR-042-local-extraction-inference.md)
- **Quality Analysis:** [Extraction Quality Comparison](guides/EXTRACTION_QUALITY_COMPARISON.md)
- **Configuration:** [AI Providers Guide](guides/AI_PROVIDERS.md)

---

← [Previous: Real World Example](07-real-world-example-project-history.md) | [Documentation Index](README.md) | [Next: Common Workflows and Use Cases →](09-common-workflows-and-use-cases.md)
