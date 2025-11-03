# Switching Extraction Providers - Quick Guide

**A simple guide to switching between OpenAI, Anthropic, and Ollama (local) for concept extraction**

> **📊 Before switching:** See [Extraction Quality Comparison](./06-EXTRACTION_QUALITY_COMPARISON.md) for empirical comparison of extraction quality, canonical adherence, and cost-benefit analysis across providers.

---

## What's the Default?

Out of the box, the Knowledge Graph system uses **OpenAI GPT-4o** for extracting concepts from documents.

Check what you're currently using:

```bash
kg admin extraction config
```

You'll see something like:

```
🤖 AI Extraction Configuration
================================

  Provider:       openai      ← This is what you're using
  Model:          gpt-4o
  Vision Support: Yes
  JSON Mode:      Yes
  Max Tokens:     16384
```

---

## Your Three Options

| Provider | Speed | Cost | Privacy | Best For |
|----------|-------|------|---------|----------|
| **OpenAI (default)** | ⚡ Fast (2s/chunk) | 💰 $0.01/1000 words | ☁️ Cloud | Quick testing, high quality |
| **Anthropic** | ⚡ Fast (2s/chunk) | 💰 $0.008/1000 words | ☁️ Cloud | Alternative to OpenAI |
| **Ollama (local)** | 🐌 Slower (8-30s/chunk) | 🆓 Free | 🔒 Private | Large jobs, sensitive docs |

---

## Scenario 1: Start with OpenAI (Default)

**You already have this!** The system defaults to OpenAI.

### If you need to set it up:

1. **Get API key** from [OpenAI Platform](https://platform.openai.com/)

2. **Add to `.env` file:**
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ```

3. **Restart API:**
   ```bash
   ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
   ```

4. **Test it:**
   ```bash
   kg ingest file -o "Test" -y test-document.txt
   ```

✅ **Done!** You're using OpenAI.

---

## Scenario 2: Switch to Anthropic (Cloud Alternative)

**Why?** Slightly cheaper than OpenAI, different AI reasoning style.

### Steps:

1. **Get API key** from [Anthropic Console](https://console.anthropic.com/)

2. **Add to `.env` file:**
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here

   # You still need OpenAI for embeddings
   OPENAI_API_KEY=sk-your-openai-key-here
   ```

3. **Switch the provider:**
   ```bash
   kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514
   ```

4. **Restart API:**
   ```bash
   ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
   ```

5. **Test it:**
   ```bash
   kg admin extraction config  # Verify it says "anthropic"
   kg ingest file -o "Test" -y test-document.txt
   ```

✅ **Done!** Now using Anthropic Claude.

---

## Scenario 3: Switch to Ollama (Local, Free)

**Why?** Zero API costs, complete privacy, offline capable.

**Trade-off:** Slower extraction (8-30 seconds per chunk vs 2 seconds for cloud).

### Step-by-Step Setup:

#### Step 1: Start Ollama Service

```bash
./scripts/start-ollama.sh -y
```

**What this does:**
- Auto-detects your GPU (NVIDIA, AMD, Intel, or CPU-only)
- Starts Ollama Docker container
- Tells you next steps

**Output:**
```
🔍 Auto-detected hardware: nvidia
🚀 Starting Ollama (nvidia profile)...
✅ Ollama is ready!

Next Steps:
  # Pull a model
  docker exec kg-ollama ollama pull mistral:7b-instruct

  # Configure Knowledge Graph
  kg admin extraction set --provider ollama --model mistral:7b-instruct
```

#### Step 2: Download a Model

**Recommended models by hardware:**

| Your GPU VRAM | Recommended Model | Download Command |
|---------------|-------------------|------------------|
| 8-12 GB | Mistral 7B | `docker exec kg-ollama ollama pull mistral:7b-instruct` |
| 16 GB | Qwen 14B (best quality) | `docker exec kg-ollama ollama pull qwen2.5:14b-instruct` |
| 48+ GB | Llama 70B (GPT-4 level) | `docker exec kg-ollama ollama pull llama3.1:70b-instruct` |
| No GPU (CPU) | Mistral 7B | `docker exec kg-ollama ollama pull mistral:7b-instruct` |

**For most users (16GB GPU):**
```bash
docker exec kg-ollama ollama pull mistral:7b-instruct
```

**Wait ~5 minutes for download to complete.**

#### Step 3: Configure Knowledge Graph

```bash
kg admin extraction set --provider ollama --model mistral:7b-instruct
```

**Output:**
```
✓ Configuration updated successfully

  Next Steps:
    1. Ensure Ollama is running: ./scripts/start-ollama.sh -y
    2. Pull model: docker exec kg-ollama ollama pull mistral:7b-instruct
    3. Test extraction: kg admin extraction test

  ⚠️  API restart required to apply changes
  Run: ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

#### Step 4: Restart API

```bash
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

#### Step 5: Test It

```bash
kg admin extraction config  # Should show "ollama"
kg ingest file -o "Test" -y test-document.txt
```

**Expect slower extraction (8-30s per chunk), but it's free!**

✅ **Done!** Now using local Ollama inference.

---

## Scenario 4: Switch Back from Ollama to OpenAI

**Why?** Ollama too slow, need faster extraction.

### Quick Switch:

```bash
# 1. Switch back to OpenAI
kg admin extraction set --provider openai --model gpt-4o

# 2. Restart API
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# 3. Optional: Stop Ollama to free resources
./scripts/stop-ollama.sh -y
```

✅ **Done!** Back to fast cloud extraction.

---

## Scenario 5: Switch Back from Ollama to Anthropic

```bash
# 1. Switch to Anthropic
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514

# 2. Restart API
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# 3. Optional: Stop Ollama
./scripts/stop-ollama.sh -y
```

✅ **Done!**

---

## Scenario 6: Try Different Ollama Models

**Want better quality?** Try a larger model (if you have VRAM):

```bash
# Pull the larger model
docker exec kg-ollama ollama pull qwen2.5:14b-instruct

# Switch to it
kg admin extraction set --provider ollama --model qwen2.5:14b-instruct

# Restart API
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

**Want fastest local?** Try a smaller model:

```bash
docker exec kg-ollama ollama pull phi3.5:3.8b-mini-instruct
kg admin extraction set --provider ollama --model phi3.5:3.8b-mini-instruct
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

---

## Scenario 7: Using Reasoning Models with Thinking Mode

**What are reasoning models?** Some Ollama models can "think before responding" - they show their reasoning process before giving the final answer.

### Reasoning Models:
- **gpt-oss** (20B, 72B) - Open source reasoning model
- **deepseek-r1** (various sizes) - DeepSeek reasoning model
- **qwen3** (various sizes) - Qwen reasoning model

### How Thinking Mode Works

**With thinking enabled:**
1. Model generates reasoning trace ("Let me think about this...")
2. Model generates final JSON output
3. System uses only the JSON, logs the thinking (for debugging)

**Trade-off:** Slower extraction but potentially higher quality for complex documents.

### Example: GPT-OSS

```bash
# 1. Pull reasoning model (requires 16GB+ VRAM)
docker exec kg-ollama ollama pull gpt-oss:20b

# 2. Configure with thinking mode
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode low

# 3. Restart API
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# 4. Test it
kg ingest file -o "Test" -y complex-document.txt
```

### Thinking Modes Explained

**Available modes:** `off`, `low`, `medium`, `high`

| Mode | GPT-OSS Behavior | Standard Models | Speed | Quality | Tokens |
|------|-----------------|-----------------|-------|---------|--------|
| `off` | `think="low"` | Disabled | Fastest | Good | 4,096 |
| `low` | `think="low"` | Enabled | Fast | Good+ | 4,096 |
| `medium` | `think="medium"` | Enabled | Slower | Better | 12,288 |
| `high` | `think="high"` | Enabled | Slowest | Best | 16,384 |

**Token allocation:** Higher thinking modes generate extensive reasoning traces (sometimes 7,000+ tokens). System scales token limits to fit both reasoning and JSON output:
- **medium**: 3x tokens (12,288) for moderate reasoning
- **high**: 4x tokens (16,384) for extensive reasoning

Standard models (Mistral, Llama) treat low/medium/high identically as "enabled".

### When to Use Higher Thinking Modes

**Use `medium` or `high` if:**
- ✅ Complex philosophical or theoretical documents
- ✅ Technical papers requiring deep reasoning
- ✅ Quality is critical, speed is secondary
- ✅ Debugging model reasoning (check logs)

**Use `off` or `low` if:**
- ✅ Simple straightforward documents
- ✅ Speed is critical
- ✅ Using standard models (they don't distinguish levels)

### Change Thinking Mode

```bash
# Fastest (GPT-OSS: minimal thinking, others: disabled)
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode off

# Maximum quality (GPT-OSS: deep thinking, others: enabled)
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode high

./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

### Performance Comparison

**Example: 10,000-word complex document**

| Model | Without Thinking | With Thinking | Quality |
|-------|-----------------|---------------|---------|
| Mistral 7B | 2 min | N/A (not supported) | Good |
| GPT-OSS 20B | 4 min (think=low) | 6.5 min (think=high) | Excellent |
| DeepSeek-R1 | 2.5 min | 4.5 min | Excellent |

---

## Quick Comparison

### Example: 10,000-word document (10 chunks)

| Provider | Total Time | Cost | Notes |
|----------|-----------|------|-------|
| OpenAI GPT-4o | ~30 seconds | $0.10 | Fastest, highest quality |
| Anthropic Claude | ~28 seconds | $0.08 | Fast, slightly cheaper |
| Ollama Mistral 7B (GPU) | ~2 minutes | $0.00 | 4x slower, free |
| Ollama Qwen 14B (GPU) | ~3 minutes | $0.00 | Better quality, slower |
| Ollama (CPU only) | ~15 minutes | $0.00 | Very slow, works everywhere |

### When does Ollama make sense?

**Use Ollama if:**
- ✅ You have 100+ documents to process (cost savings)
- ✅ Documents contain sensitive/private data
- ✅ You need offline capability
- ✅ You have a GPU (makes it much faster)

**Stick with cloud if:**
- ❌ You have < 10 documents
- ❌ You need maximum speed
- ❌ You don't have a GPU (CPU-only is very slow)

---

## Troubleshooting

### "Cannot connect to Ollama"

```bash
# Check if Ollama is running
docker ps | grep ollama

# If not running, start it
./scripts/start-ollama.sh -y
```

### "Model not found"

```bash
# List downloaded models
docker exec kg-ollama ollama list

# Pull the missing model
docker exec kg-ollama ollama pull mistral:7b-instruct
```

### "Extraction is very slow (>60s per chunk)"

**Likely cause:** CPU-only mode (no GPU detected)

```bash
# Check if GPU is being used
nvidia-smi  # Should show ollama process

# Force NVIDIA profile
./scripts/stop-ollama.sh -y
./scripts/start-ollama.sh -y --nvidia
```

### "Out of VRAM"

**Model too large for your GPU.**

```bash
# Use smaller model
docker exec kg-ollama ollama pull mistral:7b-instruct
kg admin extraction set --provider ollama --model mistral:7b-instruct
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
```

---

## The Complete Switch Workflow

### OpenAI → Ollama → Back to OpenAI

```bash
# Start with OpenAI (default)
kg admin extraction config  # Shows: openai, gpt-4o

# Try Ollama (local, free)
./scripts/start-ollama.sh -y
docker exec kg-ollama ollama pull mistral:7b-instruct
kg admin extraction set --provider ollama --model mistral:7b-instruct
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# Test it
kg ingest file -o "Test" -y test.txt  # Slower, but free

# Go back to OpenAI (need speed)
kg admin extraction set --provider openai --model gpt-4o
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
./scripts/stop-ollama.sh -y  # Free up resources

# Test it
kg ingest file -o "Test" -y test.txt  # Fast again
```

---

## Summary Cheat Sheet

```bash
# Check current provider
kg admin extraction config

# Switch to OpenAI
kg admin extraction set --provider openai --model gpt-4o
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# Switch to Anthropic
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# Switch to Ollama (local)
./scripts/start-ollama.sh -y
docker exec kg-ollama ollama pull mistral:7b-instruct
kg admin extraction set --provider ollama --model mistral:7b-instruct
./scripts/services/stop-api.sh && ./scripts/services/start-api.sh

# Stop Ollama (free resources)
./scripts/stop-ollama.sh -y
```

**Remember:** After every switch, you must restart the API!

---

**Related Guides:**
- Full extraction config details: `docs/guides/02-EXTRACTION_CONFIGURATION.md`
- Local inference implementation: `docs/guides/05-LOCAL_INFERENCE_IMPLEMENTATION.md`
- Ollama architecture: `docs/architecture/ADR-042-local-extraction-inference.md`

**Last Updated:** 2025-10-22
