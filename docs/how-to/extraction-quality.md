---
id: 8.H.03
domain: ai
mode: how-to
---

# Compare Extraction Quality

Different AI providers produce different graph characteristics from the same document. This page helps you choose a provider based on measured trade-offs between concept volume, schema compliance, speed, and cost.

All providers flow through the same Kappa Graph ingestion pipeline — the same chunker, relationship normalizer, and embeddings. Quality differences are model-dependent, not architectural (ADR-806).

---

## Quick decision table

| Goal | Provider | Why |
|---|---|---|
| Production knowledge base | OpenAI GPT-4o | 46 concepts, 88% canonical, 2 s/chunk |
| Maximum concept extraction | Ollama Qwen3 14B | 57 concepts, 74% canonical, 16 GB VRAM |
| Strictest schema compliance | Ollama Qwen 2.5 14B | 92% canonical, zero cost |
| Large private corpus (1 000+ docs) | Ollama Qwen 2.5 14B | 92% canonical, privacy-preserving, zero cost |
| Quick prototyping | OpenAI GPT-4o | 30× faster than local models, no setup |
| Avoid | Ollama Mistral 7B | 38% canonical — vocabulary pollution |

---

## Measured results

The figures below come from a single test document (a 6-chunk philosophical lecture transcript) run through each provider with identical settings. The test establishes relative rankings; absolute numbers will vary with document type.

### Summary statistics

| Metric | Mistral 7B | Qwen 2.5 14B | Qwen3 14B | GPT-OSS 20B | GPT-4o |
|---|---|---|---|---|---|
| Concepts extracted | 32 | 24 | **57** | 48 | 46 |
| Evidence instances | 36 | 27 | **70** | 49 | 48 |
| Total relationships | 134 | 98 | 61 | **190** | 172 |
| Unique relationship types | 16 | 13 | **22** | 17 | 17 |
| Canonical adherence | 38% | **92%** | 74% | 65% | 88% |
| Non-canonical types created | 10 | **1** | 5 | 6 | 2 |
| Inference speed | ~10 s/chunk | ~15 s/chunk | ~60 s/chunk | ~20 s/chunk | **~2 s/chunk** |
| Cost per document | $0.00 | $0.00 | $0.00 | $0.00 | ~$0.10 |

### What "canonical adherence" means for your graph

Each time a model emits a relationship type that is not in the canonical 30-type taxonomy, the fuzzy matcher tries to correct it. When no good match exists, the system accepts the new type and adds it to the vocabulary (ADR-603). After 100 documents:

| Provider | Estimated relationship types | Canonical | Non-canonical |
|---|---|---|---|
| GPT-4o | ~35 | 30 | ~5 |
| Qwen 2.5 14B | ~32 | 30 | ~2 |
| Qwen3 14B | ~40 | 30 | ~10 |
| GPT-OSS 20B | ~50 | 30 | ~20 |
| Mistral 7B | ~80 | 30 | ~50 |

Vocabulary that grows unboundedly makes queries less predictable and vocabulary consolidation more expensive.

---

## Provider profiles

### OpenAI GPT-4o

**Extraction philosophy:** balanced coverage with high schema compliance.

- 46 concepts, 172-edge graph, 88% canonical adherence
- 2 s/chunk — 30× faster than Qwen3 at 60 s/chunk
- Cost: ~$0.10 per 6-chunk document ($10 per 100 documents)
- Only 2 non-canonical relationship types in the test run

Best for production deployments, shared knowledge bases, and any workload where speed or schema quality cannot be compromised.

### Ollama Qwen3 14B

**Extraction philosophy:** high concept volume with moderate schema compliance.

- 57 concepts — highest of all models tested
- 74% canonical adherence; 5 non-canonical types
- 60 s/chunk; fits in 16 GB VRAM (consumer GPU)
- Zero inference cost after hardware is provisioned

Qwen3 (released January 2025) extracts 2.4× more concepts than Qwen 2.5 from identical hardware. The 60-second wait per chunk is the main trade-off.

### Ollama Qwen 2.5 14B

**Extraction philosophy:** conservative, precise, canonical.

- 24 concepts, 98-edge graph, 92% canonical adherence — highest of all models tested
- Only 1 non-canonical relationship type in the test run
- 15 s/chunk; fits in 16 GB VRAM
- Zero inference cost

Best for large private corpora, sensitive documents, or any context where long-term schema cleanliness matters more than concept volume.

### GPT-OSS 20B (Ollama)

**Extraction philosophy:** maximum relationship density.

- 48 concepts, 190-edge graph — densest relationship count of all models tested
- 65% canonical adherence; 6 non-canonical types
- ~20 s/chunk; requires 20 GB+ VRAM or CPU+GPU split
- Zero inference cost

GPT-OSS is a reasoning model. Reasoning models generate extended internal analysis before producing output, which increases token usage and reduces output consistency for structured extraction tasks. An instruction model of equivalent or smaller size will usually produce better JSON output. Use GPT-OSS when relationship density is the priority and schema compliance can be traded away.

### Ollama Mistral 7B

- 38% canonical adherence; 10 non-canonical types
- Creates vocabulary pollution that compounds across documents
- Sparse graph — many isolated concepts with zero relationships

Do not use Mistral 7B for production ingestion. If you need a local model with a small VRAM footprint, Qwen 2.5 14B on 16 GB is the better choice.

---

## Cost and time at scale

### 1 000-document corpus (~6 000 chunks)

| Provider | Time | Cost | Concepts | Canonical |
|---|---|---|---|---|
| GPT-4o | ~3.3 hours | ~$100 | ~46 000 | 88% |
| Qwen3 14B | ~100 hours | $0 | ~57 000 | 74% |
| Qwen 2.5 14B | ~25 hours | $0 | ~24 000 | 92% |
| GPT-OSS 20B | ~33 hours | $0 | ~48 000 | 65% |
| Mistral 7B | ~17 hours | $0 | ~32 000 | 38% |

### Break-even by corpus size

- **Under 50 documents** — GPT-4o costs under $5 and saves significant time. Start here.
- **50–500 documents** — Local models become competitive. Choose Qwen 2.5 14B for canonical quality or Qwen3 14B for concept volume.
- **500+ documents** — Local models are strongly recommended. GPT-4o at 500 documents costs ~$50.

---

## Switch and test providers

Extraction configuration is hot-reloadable. No API restart is required when you change provider or model.

```bash
# Switch to GPT-4o
kg admin extraction set --provider openai --model gpt-4o

# Switch to Qwen3 14B (Ollama)
kg admin extraction set --provider ollama --model qwen3:14b

# Switch to Qwen 2.5 14B (Ollama)
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct

# Verify active config
kg admin extraction config
```

### Run a comparison yourself

Pick a document you know well — a few pages of dense text works well.

```bash
# Pull local models (one-time)
docker exec kg-ollama ollama pull qwen3:14b
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# Test GPT-4o
kg admin extraction set --provider openai --model gpt-4o
kg ontology delete "quality_test"
kg ingest file -o "quality_test" -y your-document.txt
kg database stats

# Test Qwen3 14B
kg admin extraction set --provider ollama --model qwen3:14b
kg ontology delete "quality_test"
kg ingest file -o "quality_test" -y your-document.txt
kg database stats   # expect ~60 s/chunk

# Test Qwen 2.5 14B
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct
kg ontology delete "quality_test"
kg ingest file -o "quality_test" -y your-document.txt
kg database stats
```

Compare: concept count, relationship count, unique relationship types, and canonical adherence in the stats output.

---

## Related

- [Configure AI Providers](ai-providers.md) — set API keys, switch providers, configure Ollama
- [Consolidate Vocabulary](vocabulary.md) — repair schema drift from non-canonical types
- ADR-806 — local LLM inference architecture
- ADR-603 — relationship type acceptance and vocabulary growth policy
