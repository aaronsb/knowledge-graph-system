# ADR-042: Local LLM Inference for Concept Extraction

**Status:** Accepted
**Date:** 2025-10-22
**Implemented:** 2025-10-22
**Deciders:** System Architects
**Related:** ADR-039 (Local Embedding Service), ADR-041 (AI Extraction Config), ADR-025 (Dynamic Relationship Vocabulary)

## Overview

Imagine you're working on a knowledge base containing sensitive medical records, classified research, or proprietary business data. Every time you ingest a document, the system currently sends chunks of that text to OpenAI or Anthropic for concept extraction. Your private data leaves your infrastructure, travels across the internet, gets processed by someone else's computers, and then returns. This isn't just a privacy concern—it's often a compliance dealbreaker for regulated industries.

Beyond privacy, there's the cost problem. Cloud API extraction scales linearly with your document volume. Ingesting a thousand-page technical manual? That's hundreds of API calls at several cents each. The bills add up quickly, and there's no ceiling—you pay for every chunk, every time. Plus, you're completely dependent on internet connectivity and the provider staying online. No network? No ingestion.

Here's where the landscape has shifted: modern open-source LLMs running on consumer GPUs can now perform concept extraction with quality approaching GPT-4. Tools like Ollama make it dead simple to run models like Llama 3.1, Mistral, or Qwen locally. You download a model once, and then extraction is free—no API calls, no data leaving your system, no network dependency.

This ADR enables local LLM inference as a first-class extraction provider. The system integrates with Ollama (or any OpenAI-compatible local server) just like it integrates with cloud providers, using the same unified configuration system from ADR-041. Switch from GPT-4 to local Mistral with a single API call—no code changes, no architectural rewrites, just configuration. The key insight is that extraction is an abstract operation: "given text, return concepts"—it doesn't care whether those concepts came from a cloud API or a GPU in your server room.

---

## Context

Currently, the system requires cloud API access (OpenAI or Anthropic) for concept extraction during document ingestion. This creates several challenges:

### Current Limitations

1. **External Dependency**
   - System cannot function without API access
   - Network failures block ingestion
   - Subject to provider outages

2. **Cost Considerations**
   - API costs scale linearly with volume
   - Large ingestion jobs can be expensive
   - No cost ceiling for usage

3. **Privacy Concerns**
   - Sensitive documents must be sent to third-party APIs
   - Compliance issues for regulated industries (HIPAA, GDPR, etc.)
   - No air-gapped deployment possible

4. **Latency**
   - Network round-trips for each chunk (~1-3 seconds overhead)
   - Rate limiting can slow batch ingestion
   - Geographic latency for non-US regions

5. **Vendor Lock-in**
   - Tied to specific providers' model availability
   - Cannot use latest open-source models
   - Model deprecation risk

### Current Extraction Architecture

**Processing Pipeline:**
```
Document → Chunking → LLM Extraction → Graph Upsert
           (1000w)    (GPT-4o/Claude)   (PostgreSQL+AGE)
```

**Chunking System** (`src/api/lib/chunker.py`):
- **Target:** 1000 words/chunk (configurable: 800-1500)
- **Overlap:** 200 words between chunks for context
- **Smart Boundaries:** Paragraph > Sentence > Pause > Hard cut
- **Average Document:** 5000-50000 words = 5-50 chunks

**LLM Requirements** (per chunk):
- **Input Tokens:** ~1500-2500 tokens
  - System prompt: ~500-700 tokens (includes relationship types)
  - Chunk text: ~1000-1500 tokens
  - Existing concepts list: 0-300 tokens (variable)
- **Output Tokens:** ~500-2000 tokens (JSON structure)
- **Total:** ~2000-4500 tokens per chunk

**Extraction Output** (JSON structure):
```json
{
  "concepts": [{
    "concept_id": "concept_001",
    "label": "Concept Name",
    "search_terms": ["term1", "term2", "term3"]
  }],
  "instances": [{
    "concept_id": "concept_001",
    "quote": "Exact quote from text"
  }],
  "relationships": [{
    "from_concept_id": "concept_001",
    "to_concept_id": "concept_002",
    "relationship_type": "IMPLIES",  // 30-90 dynamic types (ADR-025)
    "confidence": 0.9
  }]
}
```

**Dynamic Vocabulary Challenge** (ADR-025):
- Relationship types grow from 30 (baseline) to 30-90 (curator-approved)
- Prompt size varies: ~150 tokens (30 types) to ~450 tokens (90 types)
- Local models must handle variable-length relationship lists
- JSON structure must support any valid type from active vocabulary

### Success Criteria for Local Inference

1. **Quality:** 90-95%+ of GPT-4o extraction quality
2. **Reliability:** 99%+ valid JSON responses
3. **Performance:** < 30 seconds per chunk (acceptable for batch ingestion)
4. **Resource Efficiency:** Run alongside PostgreSQL and embedding model
5. **Deployment Simplicity:** Easy installation and model management

---

## Decision

**Extend the existing extraction provider system to support local inference backends.**

### Architectural Approach

Follow the same pattern established for embeddings (ADR-039):

1. **Provider Abstraction**
   - Add `ollama`, `vllm`, and `llama-cpp` as new provider types
   - Extend `ai_extraction_config` table to support local providers
   - Same API/CLI as existing providers (openai, anthropic)

2. **Configuration Pattern**
   - Users can choose between remote (openai, anthropic) and local (ollama, vllm) providers
   - Similar to embeddings: `kg admin extraction set --provider ollama --model mistral:7b-instruct`
   - Hot reload support (if model is already loaded)
   - Provider-specific settings (base_url, temperature, etc.)

3. **Deployment Options**
   - **Docker Compose (Recommended):** Self-contained stack with Ollama service
   - **External Endpoint:** Point to existing local inference server
   - **System Installation:** User installs Ollama/vLLM themselves

### Technology Choices

#### Primary: Ollama (Default Local Provider)

**Why Ollama:**

1. **Simplest Deployment**
   - Docker image available: `ollama/ollama`
   - OpenAI-compatible API (drop-in replacement)
   - Automatic model management
   - JSON mode support
   - Model listing API: `GET /api/tags`

2. **Uses llama.cpp Under the Hood**
   - Ollama wraps llama.cpp for inference
   - Gets llama.cpp's performance and quantization
   - Adds management layer (download, update, list models)
   - Better API ergonomics than raw llama.cpp

3. **Docker Compose Integration**
   ```yaml
   services:
     ollama:
       image: ollama/ollama:latest
       ports:
         - "11434:11434"
       volumes:
         - ollama-models:/root/.ollama
       environment:
         - OLLAMA_NUM_PARALLEL=2
         - OLLAMA_MAX_LOADED_MODELS=1
   ```

4. **Flexibility**
   - Users can run Ollama externally and point to it
   - Or use included Docker Compose service
   - Or install Ollama system-wide
   - Model discovery via API (`GET /api/tags`)

#### Secondary: vLLM (Optional - Enterprise)

**Why Support vLLM:**
- Highest throughput for GPU deployments
- Tensor parallelism for 70B+ models
- Production-grade with load balancing
- Users may already have vLLM running

**Integration:**
```yaml
# docker-compose.yml (optional vLLM service)
services:
  vllm:
    image: vllm/vllm-openai:latest
    ports:
      - "8000:8000"
    command: --model meta-llama/Llama-3.1-8B-Instruct --gpu-memory-utilization 0.9
```

#### Tertiary: llama.cpp (Future)

**Why Consider:**
- Pure CPU inference
- Extremely low resource usage
- Good for edge deployments

**Integration:** Via llama-cpp-python or standalone server

### Configuration Schema

Extend `ai_extraction_config` table (follows embedding pattern from ADR-039):

```sql
-- Existing columns
provider VARCHAR(50)       -- "openai", "anthropic", "ollama", "vllm", "llama-cpp"
model_name VARCHAR(200)    -- "gpt-4o", "claude-sonnet-4", "mistral:7b-instruct"
supports_vision BOOLEAN
supports_json_mode BOOLEAN
max_tokens INTEGER

-- New columns for local providers
base_url VARCHAR(255)              -- "http://localhost:11434" or "http://ollama:11434"
temperature FLOAT DEFAULT 0.1      -- Lower for consistent JSON
top_p FLOAT DEFAULT 0.9
gpu_layers INTEGER DEFAULT -1      -- -1 = auto, 0 = CPU only (llama.cpp)
num_threads INTEGER DEFAULT 4      -- CPU threads (llama.cpp)
```

### Deployment Scenarios

#### Scenario 1: Docker Compose All-in-One (Recommended)

We provide hardware-optimized docker-compose profiles:

##### docker-compose.ollama.yml (Main Ollama Config)

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    container_name: kg-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=2
      - OLLAMA_MAX_LOADED_MODELS=1
    restart: unless-stopped
    profiles:
      - nvidia
      - intel
      - amd
      - cpu

  # NVIDIA GPU variant
  ollama-nvidia:
    extends: ollama
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    profiles:
      - nvidia

  # Intel GPU variant (Arc, Iris Xe)
  ollama-intel:
    extends: ollama
    image: ollama/ollama:latest
    devices:
      - /dev/dri:/dev/dri  # Intel GPU device
    environment:
      - OLLAMA_INTEL_GPU=1
      - NEOReadDebugKeys=1
      - ClDeviceGlobalMemSizeAvailablePercent=100
    profiles:
      - intel

  # AMD GPU variant (ROCm)
  ollama-amd:
    extends: ollama
    image: ollama/ollama:rocm
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    group_add:
      - video
      - render
    environment:
      - HSA_OVERRIDE_GFX_VERSION=11.0.0  # Adjust for your AMD GPU
    profiles:
      - amd

  # CPU-only variant (optimized for AVX2/AVX512)
  ollama-cpu:
    extends: ollama
    image: ollama/ollama:latest
    environment:
      - OLLAMA_NUM_THREADS=8
      - OLLAMA_USE_MMAP=true
    cpus: 8
    mem_limit: 16g
    profiles:
      - cpu

volumes:
  ollama-models:
```

##### Usage by Hardware Type

```bash
# NVIDIA GPU (default for most users)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile nvidia up -d

# Intel GPU (Arc, Iris Xe)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile intel up -d

# AMD GPU (ROCm-compatible)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile amd up -d

# CPU-only (no GPU)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile cpu up -d
```

##### Main docker-compose.yml Integration

```yaml
services:
  api:
    build: .
    depends_on:
      - postgres
      - ollama  # Any ollama variant
    environment:
      - EXTRACTION_PROVIDER=ollama
      - EXTRACTION_BASE_URL=http://kg-ollama:11434
      - EXTRACTION_MODEL=mistral:7b-instruct
```

**Usage:**
```bash
# Start everything
docker-compose up -d

# Pull model (first time)
docker exec ollama ollama pull mistral:7b-instruct

# Configure extraction
kg admin extraction set --provider ollama --model mistral:7b-instruct

# Test
kg ingest file -o "Test" -y document.txt
```

#### Scenario 2: External Ollama Instance

User already has Ollama running elsewhere:

```bash
# Point to existing Ollama
kg admin extraction set \
  --provider ollama \
  --model mistral:7b-instruct \
  --base-url http://my-gpu-server:11434

# System connects to external endpoint
```

#### Scenario 3: System-Wide Ollama Installation

User installs Ollama on host machine:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull mistral:7b-instruct

# Configure to use localhost
kg admin extraction set --provider ollama --model mistral:7b-instruct
# (base_url defaults to http://localhost:11434)
```

#### Scenario 4: vLLM for Enterprise

```bash
# Start vLLM container
docker run -d --gpus all \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3.1-70B-Instruct

# Configure extraction
kg admin extraction set \
  --provider vllm \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --base-url http://localhost:8000
```

---

## Hardware Deployment Profiles

Based on development machine specifications and realistic deployment scenarios:

### Reference Hardware (Development Machine)
```
CPU:    AMD Ryzen 9 9950X3D (16 cores, 32 threads)
RAM:    123 GB DDR5
GPU:    NVIDIA GeForce RTX 4060 Ti (16 GB VRAM)
Disk:   1.9 TB NVMe SSD
```

### Profile 1: Budget CPU-Only (Entry Level)
```
CPU:    Intel i7-12700K or AMD Ryzen 7 5800X (12 cores, 20 threads)
RAM:    32 GB DDR4 (recommend 48-64 GB)
GPU:    None
Disk:   512 GB NVMe SSD
Cost:   ~$800-1000

Resource Allocation:
- PostgreSQL + AGE:      4-8 GB RAM, 2-4 CPU cores
- Embedding Model:       2-4 GB RAM, 2 CPU cores (quantized)
- Extraction Model:      12-16 GB RAM, 6-8 CPU cores (quantized)
- FastAPI + Workers:     2-4 GB RAM, 2 CPU cores
- System Overhead:       4-6 GB RAM
Total:                   24-38 GB RAM

Recommended Models:
- Mistral 7B Instruct (Q4_K_M: ~4GB)
- Llama 3.1 8B (Q4_K_M: ~4.5GB)
- Phi-3 Medium 14B (Q4_K_M: ~8GB)

Performance:
- ~2-5 tokens/second
- ~30-90 seconds per chunk
- ~5-75 minutes per document (10-50 chunks)
- Best for: Personal use, low-volume ingestion, testing
```

### Profile 2: Mid-Range GPU (Prosumer)
```
CPU:    AMD Ryzen 9 7900X (12 cores, 24 threads)
RAM:    64 GB DDR5
GPU:    NVIDIA RTX 4070 (12 GB VRAM) or RTX 3060 (12 GB VRAM)
Disk:   1 TB NVMe SSD
Cost:   ~$1500-2000

Resource Allocation:
- PostgreSQL + AGE:      8-12 GB RAM, 3-4 CPU cores
- Embedding Model (GPU): 2-3 GB VRAM, 1 GB RAM
- Extraction Model (GPU):8-10 GB VRAM, 4-6 GB RAM
- FastAPI + Workers:     3-5 GB RAM, 2-3 CPU cores
- System Overhead:       6-8 GB RAM
Total:                   23-32 GB RAM, 10-13 GB VRAM

Recommended Models:
- Mistral 7B Instruct (FP16: ~14GB or 8-bit: ~7GB)
- Llama 3.1 8B Instruct (FP16: ~16GB or 8-bit: ~8GB)
- Qwen2.5 7B Instruct (FP16: ~14GB)
- Mixtral 8x7B (Q4: ~24GB model size, needs CPU offload)

Performance:
- ~20-40 tokens/second
- ~10-20 seconds per chunk
- ~2-17 minutes per document (10-50 chunks)
- Best for: Small teams, moderate volume, development
```

### Profile 3: High-End GPU (Production - Reference Machine)
```
CPU:    AMD Ryzen 9 9950X3D (16 cores, 32 threads)
RAM:    128 GB DDR5
GPU:    NVIDIA RTX 4060 Ti (16 GB VRAM) or RTX 4080 (16 GB VRAM)
Disk:   2 TB NVMe SSD
Cost:   ~$2500-3500

Resource Allocation:
- PostgreSQL + AGE:      12-16 GB RAM, 4-6 CPU cores
- Embedding Model (GPU): 2-3 GB VRAM, 512 MB RAM
- Extraction Model (GPU):12-14 GB VRAM, 6-8 GB RAM
- FastAPI + Workers:     4-6 GB RAM, 2-3 CPU cores
- System Overhead:       8-10 GB RAM
Total:                   32-43 GB RAM, 14-17 GB VRAM

Recommended Models:
- Llama 3.1 8B Instruct (FP16: ~16GB)
- Mistral 7B Instruct (FP16: ~14GB)
- Qwen2.5 7B Instruct (FP16: ~14GB, excellent reasoning)
- Qwen2.5 14B Instruct (8-bit: ~14GB, highest quality)
- Phi-3.5 Mini Instruct (FP16: ~7.6GB, fastest)
- Gemma 2 9B Instruct (8-bit: ~9GB)

Performance:
- ~30-60 tokens/second (7-8B models)
- ~20-40 tokens/second (14B models)
- ~5-15 seconds per chunk
- ~1-13 minutes per document (10-50 chunks)
- Best for: Production deployments, high-volume ingestion
```

### Profile 4: Professional GPU (Enterprise)
```
CPU:    AMD Threadripper PRO 5975WX (32 cores, 64 threads)
RAM:    256 GB DDR4 ECC
GPU:    NVIDIA RTX 6000 Ada (48 GB VRAM) or A100 (40-80 GB VRAM)
Disk:   4 TB NVMe RAID
Cost:   ~$8000-15000

Resource Allocation:
- PostgreSQL + AGE:      32-48 GB RAM, 8-12 CPU cores
- Embedding Model (GPU): 2-3 GB VRAM, 1 GB RAM
- Extraction Model (GPU):40-45 GB VRAM, 12-16 GB RAM
- FastAPI + Workers:     8-12 GB RAM, 4-6 CPU cores
- System Overhead:       16-24 GB RAM
Total:                   69-102 GB RAM, 42-48 GB VRAM

Recommended Models:
- Llama 3.1 70B Instruct (8-bit: ~35GB or 4-bit: ~20GB)
- Qwen2.5 72B Instruct (8-bit: ~36GB, best reasoning)
- Mixtral 8x22B (Q4: ~42GB)
- DeepSeek Coder 33B (8-bit: ~17GB, code-focused)
- Hybrid: 70B + 8B routing by complexity

Performance:
- ~40-100 tokens/second (7-8B models)
- ~10-30 tokens/second (70B models)
- ~3-10 seconds per chunk
- ~0.5-8 minutes per document (10-50 chunks)
- Best for: Enterprise, highest quality extraction
```

### Profile 5: Cloud/Bare Metal (Hyperscale)
```
CPU:    Dual EPYC 7763 (128 cores, 256 threads)
RAM:    512 GB - 1 TB DDR4 ECC
GPU:    4x NVIDIA A100 (80 GB VRAM each) or 8x A40
Disk:   10+ TB NVMe RAID
Cost:   ~$50000-100000

Resource Allocation:
- PostgreSQL + AGE:      64-128 GB RAM, 16-24 CPU cores
- Embedding Model:       4-6 GB VRAM, 2 GB RAM
- Extraction Models:     2-3 GPUs for parallel 70B models
- Vision Model:          1 GPU @ 20-40GB VRAM
- FastAPI + Workers:     16-32 GB RAM, 8-12 CPU cores
Total:                   128-210 GB RAM, tensor parallelism

Recommended Deployment:
- vLLM with multiple models:
  - 2x Llama 3.1 70B Instruct (load balanced)
  - 1x Qwen2.5 72B (fallback/comparison)
  - 1x Llama 3.2 Vision 90B (multimodal)
- Model routing:
  - Complexity-based (simple → 8B, complex → 70B)
  - Content-based (code → Qwen/DeepSeek, general → Llama)
  - Real-time load balancing

Performance:
- ~200+ tokens/second aggregate
- <5 seconds per chunk
- <5 minutes per document (parallel ingestion)
- Best for: Large enterprises, 24/7 production, batch processing
```

### Model Size Recommendations by Profile

| Profile | VRAM | Best Model Size | Quantization | Expected Quality |
|---------|------|-----------------|--------------|------------------|
| CPU-Only | 0 GB | 7B | 4-bit (Q4_K_M) | Good (85-90% of GPT-4o) |
| Mid-Range | 12 GB | 7-8B | FP16 or 8-bit | Very Good (90-95% of GPT-4o) |
| High-End | 16 GB | 7-14B | FP16 | Excellent (95-98% of GPT-4o) |
| Professional | 48 GB | 70B | 8-bit or 4-bit | Near-GPT-4o (98-100%) |
| Enterprise | 320+ GB | 70B+ | FP16 or multiple | GPT-4o equivalent or better |

---

## Performance Analysis

### Document Ingestion Timeline

**Example:** 25,000-word technical document

| Profile | Model | Chunking | Extraction (25 chunks) | Total | Cost |
|---------|-------|----------|------------------------|-------|------|
| GPT-4o API | gpt-4o | 2s | 50s (parallel) | ~52s | $0.25 |
| Anthropic API | claude-sonnet-4 | 2s | 45s (parallel) | ~47s | $0.20 |
| CPU-Only | Mistral 7B Q4 | 2s | 37min (serial) | ~37min | $0 |
| Mid-Range GPU | Llama 8B FP16 | 2s | 7min (serial) | ~7min | $0 |
| High-End GPU | Qwen 14B 8-bit | 2s | 4min (serial) | ~4min | $0 |
| Professional | Llama 70B 8-bit | 2s | 3min (serial) | ~3min | $0 |
| Enterprise | 2x 70B parallel | 2s | 90s (parallel) | ~92s | $0 |

**Key Insights:**
- **Cloud APIs:** Fastest for single documents (~1min), but costs scale linearly
- **CPU-Only:** Slow but functional for batch/overnight processing
- **Mid-Range GPU:** Sweet spot for most users (7min acceptable for batch)
- **High-End GPU (16GB):** Production-ready performance (~4min/document)
- **Enterprise:** Approaches cloud speed with parallel processing

### Batch Ingestion Analysis

**Scenario:** 100 documents @ 10,000 words each (1000 chunks total)

| Profile | Model | Total Time | Throughput | Total Cost |
|---------|-------|------------|------------|------------|
| GPT-4o API | gpt-4o | ~17 hours* | 6 docs/hour | $100 |
| Anthropic API | claude-sonnet-4 | ~15 hours* | 7 docs/hour | $80 |
| CPU-Only | Mistral 7B Q4 | ~62 hours | 2 docs/hour | $0 |
| Mid-Range GPU | Llama 8B FP16 | ~12 hours | 8 docs/hour | $0 |
| High-End GPU | Qwen 14B 8-bit | ~7 hours | 14 docs/hour | $0 |
| Professional | Llama 70B 8-bit | ~5 hours | 20 docs/hour | $0 |
| Enterprise | 2x 70B parallel | ~2.5 hours | 40 docs/hour | $0 |

*Rate limits and throttling included

**Break-Even Analysis:**
- **Mid-Range GPU ($1500):** Pays for itself after ~1,200 documents (vs GPT-4o)
- **High-End GPU ($3000):** Pays for itself after ~2,400 documents
- **No ongoing costs** - only electricity (~$0.10-0.50/hour for GPU)

---

## Implementation Plan

### Phase 1: Ollama Integration (MVP) - Week 1-2

**Goals:**
- Basic local extraction with Ollama
- Support 7-8B models (Mistral, Llama, Qwen)
- JSON mode for structured output
- Configuration and CLI commands

**Tasks:**
1. Create `OllamaProvider` class extending `AIProvider`
   - Implement `extract_concepts()` using Ollama API
   - JSON mode configuration
   - Error handling and retries

2. Add extraction config fields (migration 007):
   ```sql
   ALTER TABLE kg_api.ai_extraction_config
   ADD COLUMN backend VARCHAR(50),           -- "ollama", "vllm", "openai", "anthropic"
   ADD COLUMN base_url VARCHAR(255),         -- "http://localhost:11434"
   ADD COLUMN temperature FLOAT DEFAULT 0.1, -- Low for consistent JSON
   ADD COLUMN top_p FLOAT DEFAULT 0.9,
   ADD COLUMN gpu_layers INTEGER DEFAULT -1, -- -1 = auto, 0 = CPU only
   ADD COLUMN num_threads INTEGER DEFAULT 4; -- CPU threads
   ```

3. CLI commands:
   ```bash
   kg admin extraction set --provider local --backend ollama --model mistral:7b-instruct
   kg admin extraction test  # Test current config
   ```

4. Ollama installation documentation

**Deliverables:**
- Working local extraction with Ollama
- Documentation and user guide
- Performance benchmarks

### Phase 2: Quality Validation - Week 2-3

**Goals:**
- Validate extraction quality vs GPT-4o
- Test relationship type accuracy
- JSON reliability testing
- Edge case handling

**Tasks:**
1. Quality Testing Suite
   - 100 test documents (diverse domains)
   - Compare local vs GPT-4o extraction
   - Relationship type accuracy metrics
   - JSON parsing success rate

2. Benchmarking
   - Tokens/second across models
   - Memory usage profiling
   - CPU vs GPU performance
   - Concurrent extraction + embedding

3. Error Handling
   - Malformed JSON recovery
   - Timeout handling
   - Retry logic
   - Fallback to cloud if needed

**Acceptance Criteria:**
- 99%+ valid JSON responses
- 90%+ relationship type accuracy
- 90-95% extraction quality vs GPT-4o baseline

### Phase 3: Advanced Features - Week 3-4

**Goals:**
- Model switching and hot reload
- Resource optimization
- Hybrid mode (local + cloud fallback)
- Multi-model support

**Tasks:**
1. Model Management
   - Hot reload local models
   - Model size detection and warnings
   - Automatic quantization selection

2. Hybrid Mode
   - Try local first, fallback to cloud on error
   - Configurable fallback threshold
   - Cost tracking for hybrid mode

3. Performance Optimization
   - Batch processing for parallel chunks
   - Model quantization recommendations
   - Memory usage optimization

**Deliverables:**
- Production-ready local extraction
- Hybrid cloud/local mode
- Performance tuning guide

### Phase 4: Enterprise Features (Future)

**Goals:**
- vLLM backend support
- Multi-model deployment
- Vision support (code translation, image description)

**Tasks:**
1. vLLM Integration
   - Alternative backend for GPU deployments
   - Tensor parallelism for 70B+ models
   - Load balancing across models

2. Vision Models
   - Llama 3.2 Vision for `describe_image()`
   - Multimodal extraction pipeline
   - Code diagram understanding

3. Advanced Routing
   - Complexity-based model selection
   - Content-type routing (code → Qwen, general → Llama)
   - Cost/quality optimization

---

## Consequences

### Positive

1. **Self-Hosted Capability**
   - Complete air-gapped deployment possible
   - No external dependencies for extraction
   - Full control over models and versions

2. **Cost Reduction**
   - Zero ongoing API costs after hardware investment
   - Predictable infrastructure costs
   - ROI after ~1,000-2,000 documents

3. **Privacy & Compliance**
   - Sensitive documents never leave premises
   - HIPAA, GDPR, SOC2 compliant deployments
   - No data sharing with third parties

4. **Performance**
   - No network latency
   - Parallel processing on local hardware
   - Batch ingestion without rate limits

5. **Flexibility**
   - Use latest open-source models
   - Custom fine-tuned models
   - Model switching based on workload

6. **Hybrid Capability**
   - Can combine local + cloud
   - Fallback to cloud for peak loads
   - Cost optimization per document

### Negative

1. **Hardware Requirements**
   - Minimum 32GB RAM, ideally 64GB+
   - GPU strongly recommended for production
   - Storage for model files (5-50GB per model)

2. **Initial Setup Complexity**
   - Ollama installation required
   - Model downloading (one-time, 5-50GB)
   - GPU drivers and CUDA (if using GPU)

3. **Quality Trade-offs**
   - 7-8B models: 90-95% of GPT-4o quality
   - 14B models: 95-98% of GPT-4o quality
   - 70B models needed to match GPT-4o

4. **Maintenance**
   - Model updates manual
   - Monitoring resource usage
   - Troubleshooting local inference issues

5. **Performance Variability**
   - Depends heavily on hardware
   - CPU-only deployments slow (30-90s/chunk)
   - Concurrent load affects other services

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Poor JSON reliability | High | Extensive testing, retry logic, schema validation |
| Relationship type accuracy | High | Quality benchmarking, 70B models for production |
| Resource contention | Medium | Resource limits, monitoring, load balancing |
| Model availability | Low | Ollama handles downloads, model caching |
| User confusion | Medium | Clear documentation, CLI helpers, error messages |

---

## Security Considerations

1. **Local Model Files**
   - Models stored in `~/.ollama/models` (Linux/macOS)
   - Large files (5-50GB) - ensure disk space
   - Consider model file integrity checks

2. **Network Access**
   - Ollama API on localhost:11434 by default
   - Can expose for distributed deployments (add auth)
   - Firewall rules for remote access

3. **Resource Limits**
   - Set memory limits to prevent OOM
   - GPU allocation management
   - Process isolation for Ollama

4. **Data Privacy**
   - All inference happens locally
   - No telemetry by default
   - Audit logs for extraction requests

---

## Open Questions

1. **Default Model:** Which model should be default? (Mistral 7B vs Llama 8B vs Qwen 7B)
2. **Fallback Strategy:** Auto-fallback to cloud or explicit user choice?
3. **Installation:** Bundle Ollama installer or document separate install?
4. **Vision Support:** Include in Phase 1 or defer to Phase 4?
5. **Quantization:** Auto-detect optimal quantization based on VRAM?
6. **Monitoring:** Built-in performance metrics or rely on external tools?

---

## Success Metrics

### Quality Metrics
- ✅ 99%+ valid JSON responses
- ✅ 90%+ relationship type accuracy (compared to GPT-4o baseline)
- ✅ 95%+ concept extraction quality (F1 score vs GPT-4o)
- ✅ <5% quote extraction errors (exact match failures)

### Performance Metrics
- ✅ < 30 seconds/chunk on mid-range GPU (acceptable for batch)
- ✅ < 15 seconds/chunk on high-end GPU (production ready)
- ✅ < 10 minutes for 10,000-word document (end-to-end)

### Adoption Metrics
- ✅ 50% of users try local inference within 6 months
- ✅ 25% of production deployments use local inference
- ✅ Positive user feedback on cost savings

### Reliability Metrics
- ✅ 99.9% uptime for local inference service
- ✅ <1% error rate during extraction
- ✅ Graceful degradation under load

---

## Related ADRs

- **ADR-039:** Local Embedding Service - Similar architectural decision for embeddings
- **ADR-041:** AI Extraction Config - Existing config system this extends
- **ADR-025:** Dynamic Relationship Vocabulary - Variable prompt size requirement
- **ADR-040:** Database Schema Migrations - Migration 007 for new config fields

---

## References

- Ollama: https://ollama.com
- vLLM: https://github.com/vllm-project/vllm
- llama.cpp: https://github.com/ggerganov/llama.cpp
- HuggingFace TGI: https://github.com/huggingface/text-generation-inference
- Llama 3.1 Model Card: https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct
- Mistral AI: https://mistral.ai/
- Qwen 2.5: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct

---

**Document Status:** Accepted - Implemented
**Author:** System Architects
**Date:** 2025-10-22
**Implemented:** 2025-10-22

## Implementation Status

**Phase 1 (MVP) - Completed:**
- ✅ OllamaProvider class extending AIProvider (`src/api/lib/ai_providers.py`)
- ✅ Database migration 007 for extraction config fields (`schema/migrations/007_add_local_extraction_providers.sql`)
- ✅ CLI commands for Ollama configuration (`client/src/cli/ai-config.ts`)
- ✅ Hardware-optimized Docker Compose profiles (`docker-compose.ollama.yml`)
  - NVIDIA GPU profile
  - AMD GPU (ROCm) profile
  - Intel GPU profile
  - CPU-only profile
- ✅ Startup/stop scripts (`scripts/start-ollama.sh`, `scripts/stop-ollama.sh`)

**Phase 2-4 (Future):**
- ⏳ Quality validation testing suite
- ⏳ Hybrid cloud/local fallback mode
- ⏳ vLLM backend support
- ⏳ Vision model integration
