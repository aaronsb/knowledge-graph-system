# Local LLM Inference Implementation Guide

**Related ADRs:** ADR-042 (Local Extraction), ADR-039 (Local Embeddings - Reference Pattern)
**Status:** Phase 1 Complete, Phases 2-4 Planned
**Last Updated:** 2025-10-22

---

## Overview

This guide documents the phased implementation of local LLM inference for concept extraction. The architecture follows the same pattern established by ADR-039 (local embeddings):

- **Provider abstraction** - Multiple backends supported via common interface
- **Database-driven configuration** - Runtime-switchable models
- **Flexible deployment** - Docker, external endpoint, or system install
- **Graceful fallback** - Optional hybrid cloud/local mode

---

## Implementation Phases

### ✅ Phase 1: Ollama Integration (MVP) - COMPLETED

**Goal:** Basic local extraction with Ollama, supporting 7-8B models.

**Completed Tasks:**

1. **OllamaProvider Class** (`src/api/lib/ai_providers.py`)
   - ✅ Extends `AIProvider` abstract base class
   - ✅ Implements `extract_concepts()` using Ollama API
   - ✅ JSON mode configuration for structured output
   - ✅ Error handling with helpful troubleshooting messages
   - ✅ Vision model support (llava, bakllava)
   - ✅ Model listing via `/api/tags` endpoint

2. **Database Schema Extension** (Migration 007)
   - ✅ Added `base_url` column for endpoint configuration
   - ✅ Added `temperature`, `top_p` for sampling control
   - ✅ Added `gpu_layers`, `num_threads` for resource tuning
   - ✅ Updated provider CHECK constraint (ollama, vllm)

3. **Docker Compose Profiles** (`docker-compose.ollama.yml`)
   - ✅ NVIDIA GPU variant (most common)
   - ✅ AMD GPU variant (ROCm)
   - ✅ Intel GPU variant (Arc, Iris Xe)
   - ✅ CPU-only variant with resource limits

4. **Management Scripts**
   - ✅ `scripts/start-ollama.sh` - Auto-detection, model pull
   - ✅ `scripts/stop-ollama.sh` - Clean shutdown, optional cleanup

5. **CLI Commands** (`client/src/cli/ai-config.ts`)
   - ✅ `kg admin extraction set --provider ollama --model <model>`
   - ✅ Display local provider configuration
   - ✅ Validation and helpful next steps

**Deliverables:**
- ✅ Working local extraction with Mistral 7B, Llama 8B, Qwen 7B
- ✅ Documentation (ADR-042, CLAUDE.md)
- ✅ Zero-cost alternative to cloud APIs
- ✅ Thinking mode support for reasoning models

---

## Thinking Mode for Reasoning Models

**Status:** ✅ Implemented (Ollama 0.12.x+)
**Migration:** 009_add_thinking_parameter.sql

### What is Thinking Mode?

Ollama 0.12.x+ supports **reasoning models** that can "think before responding":

- **Reasoning models:** `gpt-oss`, `deepseek-r1`, `qwen3`
- **Thinking trace:** Models output their reasoning process separately from the final answer
- **Quality trade-off:** Slower but potentially higher quality extraction

### How It Works

When thinking mode is enabled:

1. Model generates a **thinking trace** (reasoning process)
2. Model generates a **response** (actual JSON output)
3. System uses only the **response** for extraction
4. **Thinking trace is logged** but not used (for debugging)

**API Response Structure** (Ollama `/api/chat` endpoint):

```json
{
  "message": {
    "role": "assistant",
    "content": "{...JSON output...}",    // Used for extraction
    "thinking": "Analyzing concepts..."  // Logged, not used
  }
}
```

### Configuration

**Database-driven** (not .env):

```bash
# Set thinking mode (off, low, medium, high)
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode low

# Disable thinking (default)
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode off
```

**Database Schema** (Migration 010):

```sql
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN thinking_mode VARCHAR(20) DEFAULT 'off'
CHECK (thinking_mode IN ('off', 'low', 'medium', 'high'));
```

### Model-Specific Behavior

**Unified Interface:** All models use `thinking_mode`: `'off'`, `'low'`, `'medium'`, `'high'`

**Internal Mapping:**

#### GPT-OSS (Requires Think Levels)
- `'off'` → `think="low"` (minimal reasoning, 4096 tokens)
- `'low'` → `think="low"` (4096 tokens)
- `'medium'` → `think="medium"` (12,288 tokens - 3x)
- `'high'` → `think="high"` (16,384 tokens - 4x)

**Token allocation:** Higher thinking modes generate extensive reasoning traces. Token limits are scaled to ensure both thinking trace and JSON output fit:
- **off/low**: 4096 tokens (standard)
- **medium**: 12,288 tokens (3x for moderate reasoning)
- **high**: 16,384 tokens (4x for extensive reasoning)

#### Standard Models (mistral, llama, qwen2.5)
- `'off'` → `think=false` (no thinking)
- `'low'`, `'medium'`, `'high'` → `think=true` (enabled, no level distinction)

Standard models don't support graduated thinking levels.

**Implementation** (`src/api/lib/ai_providers.py`):

```python
# Map thinking_mode to model-specific parameter
if "gpt-oss" in self.extraction_model.lower():
    # GPT-OSS: off→low, others pass through
    think_value = self.thinking_mode if self.thinking_mode != 'off' else 'low'
    request_data["think"] = think_value
elif self.thinking_mode == 'off':
    request_data["think"] = False  # Disabled
else:
    request_data["think"] = True  # Enabled (all levels)
```

### When to Enable Thinking

**Enable thinking if:**
- ✅ Using reasoning models (gpt-oss, deepseek-r1, qwen3)
- ✅ Complex philosophical or technical documents
- ✅ Quality is more important than speed
- ✅ You want to debug model reasoning

**Disable thinking if:**
- ❌ Speed is critical (thinking adds latency)
- ❌ Simple straightforward documents
- ❌ Using standard models (mistral, llama)

**GPT-OSS Note:** Always uses `think="low"` internally for clean JSON output, regardless of user setting.

### Performance Impact

| Model | Without Thinking | With Thinking | Difference |
|-------|-----------------|---------------|------------|
| Mistral 7B | 8s/chunk | N/A (not supported) | N/A |
| GPT-OSS 20B | 25s/chunk (think=low) | 40s/chunk (think=high) | +60% |
| DeepSeek-R1 | 15s/chunk | 28s/chunk | +87% |

### Troubleshooting

**Problem:** Empty JSON response, error parsing

**Cause:** GPT-OSS was putting all output in `thinking` field, nothing in `content`

**Solution:** Always use `think="low"` for GPT-OSS (implemented in code)

**Problem:** Thinking text mixed with JSON

**Cause:** Using old `/api/generate` endpoint

**Solution:** Use `/api/chat` endpoint (Ollama 0.12.x+) which separates thinking from content

### Example Output

**Logs with thinking enabled:**

```
🤔 GPT-OSS: think=low (minimal reasoning)
💭 Model thinking (54 chars): Need concepts, instances, relationships...
✓ Extracted 9 concepts, 9 instances, 7 relationships
```

**Logs with thinking disabled:**

```
✓ Extracted 9 concepts, 9 instances, 7 relationships
```

---

## 📋 Phase 2: Quality Validation & Testing

**Goal:** Validate extraction quality vs GPT-4o, establish reliability metrics, test edge cases.

**Reference Pattern (ADR-039):**
- Local embeddings validated against OpenAI embeddings
- Cosine similarity tests ensure quality
- Dimension checks, performance benchmarks

**Tasks:**

### 2.1 Quality Testing Suite

**Test Corpus (100 documents):**
```
docs/test_corpus/
├── technical/          # 30 docs - code, APIs, technical specs
├── academic/           # 30 docs - research papers, citations
├── conversational/     # 20 docs - dialogues, informal text
├── structured/         # 10 docs - tables, lists, hierarchies
└── edge_cases/         # 10 docs - malformed, ambiguous, minimal
```

**Create:** `tests/integration/test_extraction_quality.py`

```python
def test_concept_extraction_quality():
    """Compare Ollama vs GPT-4o concept extraction on test corpus"""

    # For each test document:
    # 1. Extract with GPT-4o (baseline)
    # 2. Extract with Ollama (Mistral 7B, Llama 8B, Qwen 7B)
    # 3. Compare:
    #    - Concept overlap (F1 score)
    #    - Relationship accuracy (type correctness)
    #    - Quote precision (exact match vs semantic)
    #    - JSON validity rate

    # Success criteria:
    # - Concept F1 >= 0.90 (90% overlap with GPT-4o)
    # - Relationship accuracy >= 0.90
    # - JSON validity >= 0.99
```

**Metrics to Track:**
- Concept extraction F1 score (precision/recall vs GPT-4o)
- Relationship type accuracy (% correct vs GPT-4o baseline)
- JSON parsing success rate (% valid responses)
- Quote extraction precision (% exact matches)
- Inference time per chunk (7B, 14B, 70B models)

**Create:** `scripts/benchmark-extraction.sh`
```bash
#!/bin/bash
# Run extraction benchmarks across models and hardware profiles

# Test models
MODELS=("mistral:7b-instruct" "llama3.1:8b-instruct" "qwen2.5:7b-instruct" "qwen2.5:14b-instruct")

# Test each model
for model in "${MODELS[@]}"; do
    kg admin extraction set --provider ollama --model "$model"
    python tests/integration/test_extraction_quality.py --model "$model"
done

# Generate comparison report
python tests/integration/generate_quality_report.py
```

### 2.2 Relationship Type Accuracy Testing

**Dynamic Vocabulary Challenge (ADR-025):**
- Baseline: 30 relationship types
- Expanded: 30-90 types (curator-approved)
- Test model's ability to handle variable-length lists

**Create:** `tests/integration/test_relationship_accuracy.py`

```python
def test_relationship_type_accuracy():
    """Test accuracy with 30, 60, and 90 relationship types"""

    # Test with different vocabulary sizes
    for vocab_size in [30, 60, 90]:
        # Use test documents with known ground-truth relationships
        # Compare model output to ground truth
        # Measure:
        #   - Type selection accuracy
        #   - Confidence calibration
        #   - Hallucination rate (invented relationships)
```

### 2.3 Edge Case Handling

**Test Scenarios:**
- **Malformed JSON recovery** - Retry logic, fallback strategies
- **Timeout handling** - Large chunks, slow models
- **Empty/minimal text** - 1-2 sentence chunks
- **Ambiguous concepts** - Homonyms, context-dependent
- **Unicode/special characters** - Non-ASCII, emojis, symbols

**Create:** `tests/integration/test_edge_cases.py`

### 2.4 Performance Benchmarking

**Hardware Profiles to Test:**
- CPU-only (8 cores, 16GB RAM)
- Mid-range GPU (RTX 4060 Ti, 16GB VRAM)
- High-end GPU (RTX 4080, 16GB VRAM)
- Professional GPU (A100, 40GB VRAM)

**Metrics:**
- Tokens/second by model size (7B, 14B, 70B)
- Memory usage (RAM, VRAM)
- CPU/GPU utilization
- Throughput (chunks/minute)
- End-to-end document ingestion time

**Create:** `scripts/benchmark-performance.sh`

**Deliverables:**
- ✅ Quality validation report (quality vs GPT-4o)
- ✅ Edge case test suite with 99%+ pass rate
- ✅ Performance benchmarks by hardware profile
- ✅ Model recommendations matrix (quality/speed trade-offs)

**Acceptance Criteria:**
- 99%+ valid JSON responses
- 90%+ relationship type accuracy
- 90-95% extraction quality (F1 vs GPT-4o)
- <5% quote extraction errors

---

## 🔀 Phase 3: Advanced Features & Optimization

**Goal:** Model switching, resource optimization, hybrid cloud/local mode, hot reload.

**Reference Pattern (ADR-039):**
- Embedding model hot reload without API restart
- Resource allocation configuration
- Fallback strategies

**Tasks:**

### 3.1 Model Management & Hot Reload

**Feature:** Switch models without API restart

**Implementation:**
1. **Model caching** - Keep frequently-used models loaded
2. **Lazy loading** - Load on first request
3. **Automatic unloading** - Free VRAM when switching models
4. **Status endpoint** - Show loaded models, VRAM usage

**Create:** `src/api/routes/models.py`

```python
@router.get("/models/status")
async def get_model_status():
    """Show loaded models and resource usage"""
    return {
        "loaded_models": [
            {
                "name": "mistral:7b-instruct",
                "vram_mb": 4500,
                "last_used": "2025-10-22T10:30:00Z"
            }
        ],
        "available_vram_mb": 11500,
        "total_vram_mb": 16000
    }

@router.post("/models/reload")
async def reload_model(model_name: str):
    """Hot reload extraction model"""
    # Similar to embedding model reload (ADR-039)
    pass
```

**CLI Command:**
```bash
kg admin extraction reload --model qwen2.5:14b-instruct
```

### 3.2 Hybrid Cloud/Local Fallback Mode

**Feature:** Try local first, fallback to cloud on error or timeout

**Configuration:**
```python
# ai_extraction_config table
fallback_provider VARCHAR(50)        # "openai" or "anthropic"
fallback_on_error BOOLEAN            # Fallback if local fails
fallback_on_timeout BOOLEAN          # Fallback if local times out
local_timeout_seconds INTEGER        # Max wait for local (default: 300s)
```

**Implementation:**
```python
async def extract_with_fallback(text: str, prompt: str):
    """Try local extraction, fallback to cloud if needed"""

    try:
        # Try local provider first
        return await ollama_provider.extract_concepts(text, prompt)
    except (TimeoutError, ConnectionError) as e:
        if config.fallback_on_error:
            logger.warning(f"Local extraction failed, falling back to {config.fallback_provider}")
            return await cloud_provider.extract_concepts(text, prompt)
        else:
            raise
```

**Metrics to Track:**
- Fallback trigger rate (% of requests)
- Cost tracking (local vs cloud requests)
- Fallback latency overhead

### 3.3 Resource Optimization

**Quantization Recommendations:**
- Auto-detect available VRAM
- Suggest optimal quantization level (FP16, 8-bit, 4-bit)
- Warn if model too large for hardware

**Implementation:**
```python
def recommend_quantization(model_size_gb: float, available_vram_gb: float):
    """Suggest optimal quantization based on VRAM"""

    if model_size_gb * 1.2 <= available_vram_gb:
        return "FP16"  # Full precision fits comfortably
    elif model_size_gb * 0.6 <= available_vram_gb:
        return "8-bit"  # 8-bit quantization fits
    elif model_size_gb * 0.35 <= available_vram_gb:
        return "4-bit"  # 4-bit quantization required
    else:
        return "CPU"  # Offload to CPU, too large for GPU
```

**CLI Helper:**
```bash
kg admin extraction recommend --model llama3.1:70b-instruct

# Output:
# Model: llama3.1:70b-instruct (70B parameters)
# Size: ~140GB (FP16), ~70GB (8-bit), ~35GB (4-bit)
# Your VRAM: 16GB
# Recommendation: Use 4-bit quantization or offload to CPU
# Command: ollama pull llama3.1:70b-instruct-q4_k_m
```

### 3.4 Batch Processing Optimization

**Feature:** Process multiple chunks in parallel

**Implementation:**
```python
async def extract_batch(chunks: List[str], max_parallel: int = 2):
    """Process multiple chunks in parallel"""

    # Respect OLLAMA_NUM_PARALLEL setting
    semaphore = asyncio.Semaphore(max_parallel)

    async def process_chunk(chunk):
        async with semaphore:
            return await extract_concepts(chunk)

    return await asyncio.gather(*[process_chunk(c) for c in chunks])
```

**Configuration:**
```bash
# docker-compose.ollama.yml
environment:
  - OLLAMA_NUM_PARALLEL=2  # Process 2 chunks at once
  - OLLAMA_MAX_LOADED_MODELS=1  # Keep 1 model in VRAM
```

### 3.5 Cost Tracking & Analytics

**Feature:** Track local vs cloud API costs over time

**Create:** `kg_api.extraction_analytics` table

```sql
CREATE TABLE kg_api.extraction_analytics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    provider VARCHAR(50),           -- "ollama", "openai", "anthropic"
    model_name VARCHAR(200),
    chunks_processed INTEGER,
    tokens_processed INTEGER,       -- 0 for local
    cost_usd DECIMAL(10, 4),        -- 0 for local
    avg_latency_ms INTEGER,
    success_rate DECIMAL(5, 2)      -- % successful extractions
);
```

**CLI Command:**
```bash
kg admin extraction analytics --last-30-days

# Output:
# Extraction Analytics (Last 30 Days)
# =====================================
# Provider: ollama (mistral:7b-instruct)
#   Chunks: 5,432
#   Cost: $0.00
#   Avg Latency: 8.2s/chunk
#   Success Rate: 98.5%
#
# Provider: openai (gpt-4o)
#   Chunks: 1,234
#   Cost: $24.68
#   Avg Latency: 2.1s/chunk
#   Success Rate: 99.8%
#
# Total Savings: $109.28 (vs all cloud)
```

**Deliverables:**
- ✅ Model hot reload without API restart
- ✅ Hybrid cloud/local fallback mode
- ✅ Resource optimization and recommendations
- ✅ Cost tracking and analytics dashboard

**Acceptance Criteria:**
- Model switch < 10 seconds
- Fallback trigger rate < 5%
- Cost tracking accurate to $0.01
- Quantization recommendations match VRAM constraints

---

## 🚀 Phase 4: Enterprise Features

**Goal:** vLLM backend, multi-model deployment, vision integration, advanced routing.

**Reference Pattern (ADR-039):**
- Multiple embedding providers coexist
- Provider-specific optimizations
- Enterprise-grade features

**Tasks:**

### 4.1 vLLM Backend Support

**Why vLLM:**
- Highest throughput for GPU deployments (2-5x faster than Ollama)
- Tensor parallelism for 70B+ models across multiple GPUs
- Production-grade load balancing
- OpenAI-compatible API

**Create:** `VLLMProvider` class

```python
class VLLMProvider(AIProvider):
    """
    vLLM inference provider (ADR-042 Phase 4).

    Optimized for production deployments with:
    - Tensor parallelism (multi-GPU)
    - Continuous batching
    - PagedAttention memory optimization
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "meta-llama/Llama-3.1-70B-Instruct",
        tensor_parallel_size: int = 1  # GPUs to use
    ):
        # vLLM uses OpenAI-compatible API
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")
        self.model = model
```

**Docker Compose:**
```yaml
# docker-compose.vllm.yml
services:
  vllm:
    image: vllm/vllm-openai:latest
    ports:
      - "8000:8000"
    command: >
      --model meta-llama/Llama-3.1-70B-Instruct
      --gpu-memory-utilization 0.95
      --tensor-parallel-size 2  # Use 2 GPUs
      --max-model-len 8192
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2  # 2 GPUs required
              capabilities: [gpu]
```

**Startup Script:**
```bash
# scripts/start-vllm.sh
#!/bin/bash
# Start vLLM with multi-GPU tensor parallelism

MODEL="meta-llama/Llama-3.1-70B-Instruct"
GPUS=2

docker-compose -f docker-compose.vllm.yml \
  -e MODEL="$MODEL" \
  -e TENSOR_PARALLEL_SIZE="$GPUS" \
  up -d
```

### 4.2 Multi-Model Deployment & Routing

**Feature:** Run multiple models, route by complexity or content type

**Architecture:**
```
Ingestion Pipeline
        ↓
   Router (analyze chunk)
   ├─→ Simple chunk → Mistral 7B (fast)
   ├─→ Complex chunk → Qwen 14B (quality)
   └─→ Code chunk → DeepSeek Coder 33B (specialized)
```

**Implementation:**
```python
class MultiModelRouter:
    """Route chunks to appropriate model based on complexity"""

    def analyze_complexity(self, text: str) -> str:
        """Determine chunk complexity: simple, medium, complex"""

        # Heuristics:
        # - Word count, sentence length
        # - Technical terms density
        # - Relationship density (references, citations)
        # - Code blocks, formulas

        if avg_sentence_length < 15 and technical_term_density < 0.1:
            return "simple"
        elif avg_sentence_length > 25 or technical_term_density > 0.3:
            return "complex"
        else:
            return "medium"

    async def route_extraction(self, chunk: str) -> Dict:
        """Route to appropriate model"""

        complexity = self.analyze_complexity(chunk)

        if complexity == "simple":
            return await mistral_7b.extract_concepts(chunk)
        elif complexity == "complex":
            return await qwen_14b.extract_concepts(chunk)
        else:
            return await llama_8b.extract_concepts(chunk)
```

**Configuration:**
```sql
-- ai_extraction_routing table
CREATE TABLE kg_api.ai_extraction_routing (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100),
    condition VARCHAR(200),         -- "complexity = 'simple'"
    target_provider VARCHAR(50),
    target_model VARCHAR(200),
    priority INTEGER,               -- Higher = evaluated first
    active BOOLEAN DEFAULT TRUE
);

-- Example routing rules
INSERT INTO kg_api.ai_extraction_routing VALUES
    (1, 'Simple chunks', 'complexity = simple', 'ollama', 'mistral:7b-instruct', 10, TRUE),
    (2, 'Complex chunks', 'complexity = complex', 'ollama', 'qwen2.5:14b-instruct', 20, TRUE),
    (3, 'Code chunks', 'content_type = code', 'ollama', 'deepseek-coder:33b', 30, TRUE);
```

### 4.3 Vision Model Integration

**Feature:** Extract concepts from images using multimodal models

**Models:**
- **Llama 3.2 Vision (11B, 90B)** - General vision understanding
- **LLaVA (7B, 13B)** - Lightweight image description
- **BakLLaVA (7B)** - Improved visual reasoning

**Implementation:**

```python
async def ingest_image(image_path: str, ontology: str):
    """Extract concepts from an image"""

    # 1. Load image
    image_data = load_image(image_path)

    # 2. Generate description using vision model
    vision_provider = OllamaProvider(model="llava:13b")
    description = await vision_provider.describe_image(
        image_data,
        IMAGE_DESCRIPTION_PROMPT  # From ai_providers.py
    )

    # 3. Extract concepts from description
    text_provider = OllamaProvider(model="mistral:7b-instruct")
    concepts = await text_provider.extract_concepts(
        description,
        EXTRACTION_PROMPT
    )

    # 4. Store in graph with image source reference
    await store_concepts(concepts, source_type="IMAGE", source_path=image_path)
```

**CLI Command:**
```bash
kg ingest image -o "Presentation Slides" slide_01.png slide_02.png ...

# Output:
# Processing slide_01.png...
#   ✓ Described with llava:13b (2.3s)
#   ✓ Extracted 12 concepts (mistral:7b-instruct, 8.1s)
# Processing slide_02.png...
#   ✓ Described with llava:13b (2.1s)
#   ✓ Extracted 15 concepts (mistral:7b-instruct, 9.2s)
#
# Total: 27 concepts from 2 images
```

### 4.4 Load Balancing & High Availability

**Feature:** Multiple Ollama/vLLM instances for parallel ingestion

**Architecture:**
```
API Server
    ↓
Load Balancer
  ├─→ Ollama Instance 1 (mistral:7b-instruct)
  ├─→ Ollama Instance 2 (mistral:7b-instruct)
  └─→ Ollama Instance 3 (mistral:7b-instruct)
```

**Docker Compose:**
```yaml
services:
  ollama-1:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']  # GPU 0
              capabilities: [gpu]

  ollama-2:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']  # GPU 1
              capabilities: [gpu]

  ollama-lb:
    image: nginx:alpine
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    ports:
      - "11434:11434"
```

**Load Balancing Config:**
```nginx
# nginx-lb.conf
upstream ollama_backends {
    least_conn;  # Route to instance with fewest connections
    server ollama-1:11434;
    server ollama-2:11434;
    server ollama-3:11434;
}

server {
    listen 11434;
    location / {
        proxy_pass http://ollama_backends;
    }
}
```

### 4.5 Model Fine-Tuning Support

**Feature:** Fine-tune models on domain-specific data

**Workflow:**
1. Export training data from existing extractions
2. Fine-tune model with LoRA/QLoRA
3. Deploy fine-tuned model to Ollama
4. Configure as extraction provider

**Create:** `scripts/export-training-data.sh`

```bash
#!/bin/bash
# Export extraction examples for fine-tuning

kg admin extraction export-training-data \
  --ontology "Technical Documentation" \
  --min-quality 0.9 \
  --format jsonl \
  --output training_data.jsonl

# Format: {"prompt": "...", "completion": "..."}
```

**Documentation:** Create `docs/guides/FINE_TUNING.md` with:
- Data export procedures
- LoRA fine-tuning with HuggingFace
- Model deployment to Ollama
- Quality validation checklist

**Deliverables:**
- ✅ vLLM backend support for enterprise deployments
- ✅ Multi-model routing by complexity/content
- ✅ Vision model integration for image ingestion
- ✅ Load balancing across multiple inference instances
- ✅ Fine-tuning guide and tooling

**Acceptance Criteria:**
- vLLM throughput 2x+ Ollama for 70B models
- Multi-model routing improves avg quality by 5%+
- Vision models achieve 85%+ concept accuracy on slides/diagrams
- Load balancer distributes requests evenly (±10%)
- Fine-tuned models show 10%+ improvement on domain data

---

## Success Metrics (Overall)

### Quality Metrics
- ✅ 99%+ valid JSON responses across all models
- ✅ 90%+ relationship type accuracy (vs GPT-4o)
- ✅ 95%+ concept extraction quality (F1 score)
- ✅ <5% quote extraction errors

### Performance Metrics
- ✅ <30s/chunk on mid-range GPU (acceptable)
- ✅ <15s/chunk on high-end GPU (production)
- ✅ <10min for 10,000-word document (end-to-end)

### Adoption Metrics
- ✅ 50% of users try local inference within 6 months
- ✅ 25% of production deployments use local
- ✅ Positive user feedback on cost savings

### Reliability Metrics
- ✅ 99.9% uptime for local inference service
- ✅ <1% error rate during extraction
- ✅ Graceful degradation under load

---

## Testing Strategy

### Unit Tests
- `tests/unit/test_ollama_provider.py` - Provider methods
- `tests/unit/test_vllm_provider.py` - vLLM integration
- `tests/unit/test_model_router.py` - Routing logic

### Integration Tests
- `tests/integration/test_extraction_quality.py` - Quality validation
- `tests/integration/test_relationship_accuracy.py` - Type correctness
- `tests/integration/test_edge_cases.py` - Error handling
- `tests/integration/test_fallback.py` - Cloud fallback

### Performance Tests
- `tests/performance/test_throughput.py` - Chunks/minute
- `tests/performance/test_latency.py` - Response time
- `tests/performance/test_memory.py` - VRAM/RAM usage
- `tests/performance/test_batch.py` - Parallel processing

### End-to-End Tests
- `tests/e2e/test_document_ingestion.py` - Full pipeline
- `tests/e2e/test_model_switching.py` - Hot reload
- `tests/e2e/test_hybrid_mode.py` - Fallback scenarios

---

## Monitoring & Observability

### Metrics to Track (Prometheus/Grafana)
- Inference latency (p50, p95, p99)
- Throughput (chunks/second)
- Error rate (% failed extractions)
- Fallback rate (% cloud requests)
- VRAM usage (% utilized)
- Model load/unload events
- Cost savings ($ saved vs cloud)

### Alerts
- Inference latency > 60s
- Error rate > 5%
- VRAM usage > 95%
- Ollama service down
- Fallback rate > 20%

---

## Rollout Plan

### Phase 2 (Weeks 3-4)
1. Create test corpus (100 documents)
2. Run quality benchmarks (Ollama vs GPT-4o)
3. Edge case testing and fixes
4. Performance profiling by hardware

### Phase 3 (Weeks 5-6)
1. Implement model hot reload
2. Hybrid fallback mode
3. Resource optimization helpers
4. Cost tracking analytics

### Phase 4 (Weeks 7-10)
1. vLLM provider implementation
2. Multi-model routing
3. Vision model integration
4. Load balancing setup
5. Fine-tuning guide

---

## References

- **ADR-042:** Local LLM Inference Decision
- **ADR-039:** Local Embedding Service (reference pattern)
- **ADR-041:** AI Extraction Config
- **ADR-025:** Dynamic Relationship Vocabulary
- **Ollama Documentation:** https://ollama.com/
- **vLLM Documentation:** https://github.com/vllm-project/vllm
- **Llama.cpp:** https://github.com/ggerganov/llama.cpp

---

**Last Updated:** 2025-10-22
**Status:** Phase 1 Complete ✅, Phases 2-4 Planned 📋
