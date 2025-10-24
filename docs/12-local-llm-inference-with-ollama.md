# 12 - Local LLM Inference with Ollama

**Part:** II - Configuration
**Reading Time:** ~22 minutes
**Prerequisites:** [Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md), [Section 10 - AI Extraction Configuration](10-ai-extraction-configuration.md)

---

This section explains how to set up local LLM inference for concept extraction. Local inference eliminates cloud API costs, enables offline operation, and keeps your documents completely private. The system uses Ollama as the default local inference engine.

## Why Local Inference

**Benefits over cloud APIs:**

**Cost:**
- **Cloud:** $10-100+ per 1000-document corpus (ongoing)
- **Local:** $0 after initial setup (hardware you already have)

**Privacy:**
- **Cloud:** Documents sent to external servers
- **Local:** Documents never leave your machine

**Availability:**
- **Cloud:** Requires internet access, subject to outages
- **Local:** Works offline, no external dependencies

**Control:**
- **Cloud:** Limited to provider's available models
- **Local:** Use any open-source model (Mistral, Llama, Qwen, etc.)

**Trade-offs:**

**Speed:**
- **Cloud:** 2 seconds per chunk (GPT-4o)
- **Local:** 10-60 seconds per chunk (depends on model and hardware)

**Setup:**
- **Cloud:** Immediate (just set API key)
- **Local:** Requires Ollama installation and model download

**Hardware:**
- **Cloud:** No requirements
- **Local:** 16GB+ VRAM recommended (or CPU with 32GB+ RAM)

---

## What Is Ollama

Ollama is a local inference engine that runs LLMs on your hardware. It wraps llama.cpp (the engine powering most local models) with a simple API and automatic model management.

**Key features:**
- Automatic model downloading
- OpenAI-compatible API
- JSON mode support for structured extraction
- GPU acceleration (NVIDIA, AMD, Intel)
- CPU-only fallback
- Easy model switching

**Models supported:**
- Mistral (7B, 8x7B)
- Llama 3.1 (8B, 70B, 405B)
- Qwen 2.5 & 3 (7B, 14B, 32B, 72B)
- GPT-OSS (20B reasoning model)
- DeepSeek Coder (specialized for code)
- Many more from https://ollama.com/library

---

## Hardware Requirements

### Recommended Setup (Mid-Range GPU)

**GPU:** NVIDIA RTX 4060 Ti (16GB VRAM) or equivalent
- Runs 7B models: excellent
- Runs 14B models: good
- Runs 20B+ models: CPU offload required

**RAM:** 32GB system memory

**Disk:** 20-50GB free (for model storage)

**Speed:** 10-15 seconds per chunk (Qwen 2.5 14B)

### High-End GPU Setup

**GPU:** NVIDIA RTX 4080/4090 (16-24GB VRAM) or A100 (40-80GB)
- Runs all models up to 70B efficiently
- Multiple concurrent extractions possible
- Can handle 14B-20B models at full precision

**Speed:** 5-10 seconds per chunk (Qwen 2.5 14B)

### CPU-Only Setup

**CPU:** Modern multi-core (8+ cores)

**RAM:** 64GB+ recommended for 14B models

**Speed:** 60-120 seconds per chunk (much slower)

**Note:** CPU-only works but is significantly slower. Only recommended if you have no GPU or for testing.

### Supported GPU Types

**NVIDIA (CUDA)** - Best support, fastest inference
- GeForce RTX 20/30/40 series
- Tesla/A100/H100 datacenter GPUs
- Quadro professional GPUs

**AMD (ROCm)** - Good support, slightly slower
- Radeon RX 6000/7000 series
- MI100/MI200 datacenter GPUs

**Intel (OneAPI)** - Basic support, slower
- Arc A-series discrete GPUs
- Iris Xe integrated graphics

**Apple Silicon (Metal)** - Mac support
- M1/M2/M3 with unified memory

---

## Installation

### Quick Start (Docker)

The easiest way to run Ollama is with Docker Compose. The system includes hardware-optimized profiles.

**Start Ollama with automatic hardware detection:**

```bash
# From project root
./scripts/start-ollama.sh -y
```

This script:
1. Detects your GPU type (NVIDIA, AMD, Intel, or CPU-only)
2. Starts appropriate Docker container
3. Prompts you to pull a model

**Manual Docker Compose (if auto-detection fails):**

```bash
# NVIDIA GPU (most common)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile nvidia up -d

# AMD GPU (ROCm)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile amd up -d

# Intel GPU (Arc, Iris Xe)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile intel up -d

# CPU-only (no GPU)
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile cpu up -d
```

**Verify Ollama is running:**

```bash
curl http://localhost:11434/api/tags
```

Should return: `{"models":[]}`

### Alternative: System Installation

Install Ollama directly on your host machine:

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download/windows
```

**Start Ollama:**

```bash
ollama serve
```

Runs on `http://localhost:11434` by default.

---

## Downloading Models

After Ollama is running, download models you want to use.

### Recommended Models

**For quality (Section 08 details):**
- `qwen2.5:14b-instruct` - Best canonical adherence (92%)
- `qwen3:14b` - Most concepts extracted (57 per doc)

**For speed:**
- `mistral:7b-instruct` - Fast but lower quality (38% canonical)
- `llama3.1:8b-instruct` - Good balance

**For specialized use:**
- `gpt-oss:20b` - Reasoning model, dense relationships
- `deepseek-coder:33b` - Code-heavy documents

### Pull Commands

**If using Docker:**

```bash
# Recommended: Qwen 2.5 14B (best quality/hardware balance)
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# Alternative: Qwen3 14B (maximum concept extraction)
docker exec kg-ollama ollama pull qwen3:14b

# Lightweight: Mistral 7B (fastest, lower quality)
docker exec kg-ollama ollama pull mistral:7b-instruct
```

**If using system installation:**

```bash
ollama pull qwen2.5:14b-instruct
```

**Download progress:**

```
pulling manifest
pulling 8934d96d3f08... 100% ▕██████████████▏ 8.9 GB
pulling 8c17c2ebb0ea... 100% ▕██████████████▏  7.0 KB
pulling 7c23fb36d801... 100% ▕██████████████▏  4.8 KB
pulling 2e0493f67d0c... 100% ▕██████████████▏   59 B
pulling fa8235e5b48f... 100% ▕██████████████▏  485 B
verifying sha256 digest
writing manifest
success
```

Models are cached in `/root/.ollama` (Docker) or `~/.ollama` (system install).

### List Downloaded Models

```bash
# Docker
docker exec kg-ollama ollama list

# System
ollama list
```

**Example output:**

```
NAME                     ID            SIZE      MODIFIED
qwen2.5:14b-instruct     abc123def     8.9 GB    2 hours ago
mistral:7b-instruct      xyz789ghi     4.1 GB    1 day ago
```

---

## Configuration

Once Ollama is running and you've downloaded a model, configure the system to use it.

### Basic Configuration

```bash
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct
```

### Advanced Configuration

```bash
kg admin extraction set \
  --provider ollama \
  --model qwen2.5:14b-instruct \
  --base-url http://localhost:11434 \
  --temperature 0.1 \
  --max-tokens 4096
```

**Parameters:**
- `--base-url`: Ollama endpoint (default: `http://localhost:11434` or `http://kg-ollama:11434` in Docker)
- `--temperature`: Lower = more consistent (0.0-1.0, default: 0.1)
- `--max-tokens`: Maximum output tokens (default: 4096)

### Restart API

Unlike embeddings, extraction configuration requires API restart:

```bash
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Verify Configuration

```bash
kg admin extraction config
```

**Example output:**

```
🤖 AI Extraction Configuration
────────────────────────────────────────

  Provider:       ollama
  Model:          qwen2.5:14b-instruct
  Base URL:       http://kg-ollama:11434
  Temperature:    0.1
  Max Tokens:     4096

  Config ID: 3
```

---

## Testing Local Extraction

Test with a small document:

```bash
kg admin extraction test
```

**Expected output:**

```
🔄 Testing extraction with ollama / qwen2.5:14b-instruct

Test text: "The quick brown fox jumps over the lazy dog..."

✓ Extracted 3 concepts
✓ Extracted 2 relationships
✓ Valid JSON output
✓ Response time: 12.4s

Extraction test passed!
```

**Full document test:**

```bash
kg ingest file test-document.txt --ontology "Test" -y
```

Monitor the progress. Local models are slower but produce good results.

---

## Resource Management

### VRAM Allocation

Ollama automatically manages VRAM. You can configure parallelism:

**Docker environment variables (docker-compose.ollama.yml):**

```yaml
environment:
  - OLLAMA_NUM_PARALLEL=2       # Process 2 chunks at once
  - OLLAMA_MAX_LOADED_MODELS=1  # Keep 1 model in VRAM
```

**Trade-offs:**
- `OLLAMA_NUM_PARALLEL=2`: Faster ingestion, uses 2x VRAM
- `OLLAMA_NUM_PARALLEL=1`: Slower ingestion, uses 1x VRAM

### CPU Fallback (ADR-043)

When using local embeddings + local extraction on the same GPU, VRAM contention can occur. The system handles this automatically:

**Sufficient VRAM (>500MB free):**
- Embeddings run on GPU (~1-2ms per concept)
- Extraction runs on GPU (~10-60s per chunk)

**VRAM contention (<500MB free):**
- Embeddings automatically fall back to CPU (~5-10ms per concept)
- Extraction continues on GPU
- Warning logged: "⚠️ GPU VRAM low, embedding service using CPU fallback"

**Performance impact:**
- ~100ms slowdown per chunk (negligible in 10-60 second extraction)
- Allows both services to coexist on single-GPU systems

### Model Offloading

If a model doesn't fit in VRAM, Ollama can offload layers to CPU:

**Automatic offloading:**

Ollama detects available VRAM and offloads layers automatically. You'll see:

```
loaded 20/48 layers to GPU (remaining on CPU)
```

**Performance:**
- Full GPU: 10s per chunk
- Partial GPU (50% layers): 25s per chunk
- CPU only (0% layers): 120s per chunk

---

## Air-Gapped Deployment

For offline or secure environments, you can deploy without internet access.

### Preparation (With Internet)

1. **Pull models on internet-connected machine:**

```bash
docker run --rm -v ollama-models:/root/.ollama ollama/ollama:latest pull qwen2.5:14b-instruct
```

2. **Export Docker volume:**

```bash
docker run --rm -v ollama-models:/data -v $(pwd):/backup alpine tar czf /backup/ollama-models.tar.gz -C /data .
```

3. **Copy to air-gapped machine:**

Transfer `ollama-models.tar.gz` via approved media (USB, secure file transfer).

### Deployment (Without Internet)

1. **Create volume and import models:**

```bash
docker volume create ollama-models
docker run --rm -v ollama-models:/data -v $(pwd):/backup alpine tar xzf /backup/ollama-models.tar.gz -C /data
```

2. **Start Ollama:**

```bash
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml --profile nvidia up -d
```

3. **Configure system:**

```bash
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct
./scripts/stop-api.sh && ./scripts/start-api.sh
```

Models are now available offline.

---

## Model Selection Guide

See [Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md) for detailed quality comparisons.

**Quick recommendations:**

### For Production

**Qwen 2.5 14B** - Best quality/hardware balance
- 92% canonical adherence (highest)
- 24 concepts per document
- 15 seconds per chunk
- 16GB VRAM

**When to use:** Professional deployments, strict schema compliance requirements

### For Research

**Qwen3 14B** - Maximum concept extraction
- 57 concepts per document (highest)
- 74% canonical adherence (acceptable)
- 60 seconds per chunk
- 16GB VRAM

**When to use:** Exploratory research, comprehensive coverage priority

### For Testing

**Mistral 7B** - Fastest option
- 32 concepts per document
- 38% canonical adherence (low - vocabulary pollution)
- 10 seconds per chunk
- 8GB VRAM

**When to use:** Quick tests, prototyping (not production)

### For Dense Relationships

**GPT-OSS 20B** - Reasoning model
- 48 concepts per document
- 190 relationships (densest graph)
- 65% canonical adherence
- 20-40 seconds per chunk
- 20GB+ VRAM

**When to use:** Research requiring extensive relationship mapping, slower but thoughtful extraction

---

## Troubleshooting

### Error: "Connection refused"

**Cause:** Ollama not running.

**Solution:**

```bash
# Check if Ollama container is running
docker ps | grep ollama

# If not running, start it
./scripts/start-ollama.sh -y

# Or restart
docker-compose -f docker-compose.ollama.yml --profile nvidia restart
```

### Error: "Model not found"

**Cause:** Model not downloaded.

**Solution:**

```bash
# List available models
docker exec kg-ollama ollama list

# Pull the model
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# Verify
docker exec kg-ollama ollama list
```

### Error: "CUDA out of memory"

**Cause:** Model too large for your VRAM.

**Solutions:**

1. **Use smaller model:**
   ```bash
   kg admin extraction set --provider ollama --model mistral:7b-instruct
   ```

2. **Use quantized version:**
   ```bash
   docker exec kg-ollama ollama pull qwen2.5:14b-instruct-q4_k_m  # 4-bit quantization
   ```

3. **Reduce parallel processing:**
   Edit `docker-compose.ollama.yml`:
   ```yaml
   environment:
     - OLLAMA_NUM_PARALLEL=1  # Reduce from 2
   ```

4. **CPU offload (automatic):**
   Ollama will automatically offload layers to CPU if needed. Expect slower inference.

### Slow Extraction (>120s per chunk)

**Causes:**
- Running on CPU instead of GPU
- Model too large for GPU (heavy offloading)
- Insufficient system resources

**Solutions:**

1. **Verify GPU is used:**
   ```bash
   docker exec kg-ollama nvidia-smi  # Check GPU usage during extraction
   ```

2. **Use smaller/faster model:**
   ```bash
   kg admin extraction set --provider ollama --model mistral:7b-instruct
   ```

3. **Increase CPU resources (if offloading):**
   Edit `docker-compose.ollama.yml`:
   ```yaml
   cpus: 16  # Increase CPU allocation
   ```

### Empty or Malformed JSON

**Cause:** Model not following instructions, temperature too high, or model not suitable for structured output.

**Solutions:**

1. **Lower temperature:**
   ```bash
   kg admin extraction set --provider ollama --model qwen2.5:14b-instruct --temperature 0.05
   ```

2. **Use model with better instruction following:**
   - Qwen 2.5/3 models: excellent
   - Mistral: good
   - Avoid non-instruct models

3. **Check logs for errors:**
   ```bash
   tail -f logs/api_*.log | grep -i error
   ```

---

## Performance Tuning

### Increase Throughput

**Enable parallel processing:**

Edit `docker-compose.ollama.yml`:

```yaml
environment:
  - OLLAMA_NUM_PARALLEL=4  # Process 4 chunks at once (requires 4x VRAM)
```

Restart:

```bash
docker-compose -f docker-compose.ollama.yml --profile nvidia restart
```

**Trade-off:** 4x faster ingestion, 4x VRAM usage.

### Reduce Memory Usage

**Limit concurrent requests:**

```yaml
environment:
  - OLLAMA_NUM_PARALLEL=1
  - OLLAMA_MAX_LOADED_MODELS=1
```

### Optimize for Specific Hardware

**NVIDIA GPU:**
- Use latest CUDA drivers
- Enable tensor cores: `--gpus all`

**AMD GPU:**
- Set `HSA_OVERRIDE_GFX_VERSION` for your GPU
- Use ROCm-optimized container

**CPU:**
- Increase thread count:
  ```yaml
  environment:
    - OLLAMA_NUM_THREADS=16
  ```
- Enable memory mapping:
  ```yaml
  environment:
    - OLLAMA_USE_MMAP=true
  ```

---

## Cost Comparison

### 1000-Document Corpus (~6000 chunks)

| Provider | Time | Cost | Quality |
|----------|------|------|---------|
| GPT-4o | 3.3 hrs | $102 | Excellent (88% canonical) |
| Qwen 2.5 14B | 25 hrs | $0 | Excellent (92% canonical) |
| Qwen3 14B | 100 hrs | $0 | Good (74% canonical) |

**Break-even:** After ~500 documents, local inference saves money despite longer processing time.

**Annual savings (10,000 documents/year):**
- Cloud: $1,020/year
- Local: $0/year (after initial hardware investment)

---

## Best Practices

### Model Management

**Keep models updated:**

```bash
# Check for updates
docker exec kg-ollama ollama list

# Update model
docker exec kg-ollama ollama pull qwen2.5:14b-instruct
```

### Resource Monitoring

**Monitor GPU usage during extraction:**

```bash
# NVIDIA
watch -n 1 nvidia-smi

# AMD
watch -n 1 rocm-smi
```

**Monitor Ollama logs:**

```bash
docker logs -f kg-ollama
```

### Hybrid Cloud/Local

Start with local, fall back to cloud if needed:

1. **Try local first:**
   ```bash
   kg admin extraction set --provider ollama --model qwen2.5:14b-instruct
   ```

2. **If slow or errors, switch to cloud:**
   ```bash
   kg admin extraction set --provider openai --model gpt-4o
   ```

---

## What's Next

Now that you have local inference configured, you can:

- **[Section 13 - Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md)**: Customize relationship types
- **[Section 14 - Advanced Query Patterns](14-advanced-query-patterns.md)**: Complex graph queries
- **[Section 15 - Integration with Claude Desktop (MCP)](15-integration-with-claude-desktop-mcp.md)**: MCP server setup

For technical details:
- **Architecture:** [ADR-042 - Local LLM Inference](architecture/ADR-042-local-extraction-inference.md)
- **Resource Management:** [ADR-043 - Single-Node Resource Management](architecture/ADR-043-single-node-resource-management.md)
- **Implementation Guide:** [guides/LOCAL_INFERENCE_IMPLEMENTATION.md](guides/LOCAL_INFERENCE_IMPLEMENTATION.md)

---

← [Previous: Embedding Models and Vector Search](11-embedding-models-and-vector-search.md) | [Documentation Index](README.md) | [Next: Managing Relationship Vocabulary →](13-managing-relationship-vocabulary.md)
