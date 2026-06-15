---
id: 8.H.01
domain: ai
mode: how-to
---

# Configure AI Providers

Kappa Graph uses an LLM to extract concepts and relationships from documents during ingestion. This page covers how to set an extraction provider, store API keys, tune extraction parameters, and switch providers.

Embeddings are configured separately — see [Configure Embeddings](embeddings.md). For a side-by-side quality comparison of providers, see [Compare Extraction Quality](extraction-quality.md).

---

## Supported providers

| Provider | Default model | Notes |
|---|---|---|
| `openai` | `gpt-4o` | Default. Requires OpenAI API key. |
| `anthropic` | `claude-sonnet-4-20250514` | Requires Anthropic API key. Anthropic does not provide embeddings; configure a separate embedding provider. |
| `ollama` | `mistral:7b-instruct` | Local inference — no API key required. Install Ollama on the host or wire up your own container. |
| `openrouter` | `openai/gpt-4o` | Routes to many providers under one API. Set the routed model slug via `--model`. |

Provider classes live in `api/app/lib/ai_providers.py`. The model catalog is stored in `kg_api.provider_model_catalog` (ADR-800).

---

## Set an extraction provider

```bash
# Via operator
./operator.sh ai-provider <provider> [--model <model>] [--max-tokens <n>]

# Via kg CLI
kg admin extraction set --provider <provider> --model <model>
```

**Extraction configuration is read from the database at the start of each ingestion job.** Changes apply to the next job you submit — no API restart required.

---

## Store API keys

Keys are validated against the provider before being stored encrypted in `kg_api.system_api_keys` (ADR-031). Plaintext is never returned after storage.

```bash
# Via operator (interactive prompt)
./operator.sh api-key <provider>

# Non-interactive
./operator.sh api-key <provider> --key <key>

# Via kg CLI
kg admin keys set <provider>
kg admin keys set <provider> --key <key>
```

OpenAI key format: `sk-...`  
Anthropic key format: `sk-ant-...`

### View key status

```bash
kg admin keys list
```

Output shows validation status, a masked key, and last validated time:

```
  ✓ openai
    Status:         Valid
    Key:            sk-...abc123
    Last Validated: 10/22/2025, 9:11:14 AM

  ⚠ anthropic
    Status:         Invalid
    Error:          Authentication failed: invalid API key

  ○ ollama
    Not configured
```

Icons: `✓` valid · `⚠` invalid or expired · `○` not configured

### Delete a key

```bash
kg admin keys delete <provider>
```

---

## View current extraction configuration

```bash
kg admin extraction config
```

```
  Provider:      openai
  Model:         gpt-4o
  Vision Support: Yes
  JSON Mode:     Yes
  Max Tokens:    4096
```

---

## Extraction parameters

```bash
kg admin extraction set [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--provider <provider>` | `openai`, `anthropic`, `ollama`, `openrouter` | `openai` |
| `--model <model>` | Model name | Provider default |
| `--vision` / `--no-vision` | Enable or disable vision API support | `true` for gpt-4o |
| `--json-mode` / `--no-json-mode` | Enable or disable JSON mode | `true` |
| `--max-tokens <n>` | Max output tokens (1024–16384) | `16384` |

For Ollama and vllm local providers, additional options are available:

| Option | Description |
|---|---|
| `--base-url <url>` | Base URL for the local inference server (e.g. `http://localhost:11434`) |
| `--temperature <n>` | Sampling temperature 0.0–1.0 |
| `--top-p <n>` | Nucleus sampling threshold 0.0–1.0 |
| `--gpu-layers <n>` | GPU layers: `-1` = auto, `0` = CPU only, `>0` = specific count |
| `--num-threads <n>` | CPU threads for inference |
| `--thinking-mode <mode>` | `off`, `low`, `medium`, `high` — Ollama 0.12.x+ reasoning models only |

---

## Common workflows

### Set up OpenAI (default)

```bash
# 1. Store the API key
kg admin keys set openai

# 2. Verify the key is valid
kg admin keys list

# 3. Check the active config (gpt-4o is the default)
kg admin extraction config

# 4. Run a test ingestion
kg ingest text "The universe is vast and complex." -o "test"
kg job list done -l 1
```

### Switch to Anthropic

```bash
# 1. Store the Anthropic key
kg admin keys set anthropic

# 2. If embeddings use OpenAI, store that key too
kg admin keys set openai

# 3. Switch the extraction provider
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514

# 4. Verify
kg admin extraction config
```

### Switch to Ollama (local inference)

Ollama must be reachable from the API container before ingestion starts. Install Ollama on the host (`https://ollama.com/`) and run `ollama serve`, or configure `OLLAMA_BASE_URL` to point at your Ollama instance.

```bash
# 1. Pull a model into your Ollama instance
#    (command depends on how you're running Ollama)
ollama pull mistral:7b-instruct

# 2. Configure Kappa Graph
kg admin extraction set --provider ollama --model mistral:7b-instruct

# 3. Test ingestion (expect 8–30s per chunk, not 2s)
kg ingest file -o "Test" -y test-document.txt
```

**Recommended models by GPU VRAM:**

| VRAM | Model | Pull command |
|---|---|---|
| 8–12 GB | `mistral:7b-instruct` | `ollama pull mistral:7b-instruct` |
| 16 GB | `qwen2.5:14b-instruct` | `ollama pull qwen2.5:14b-instruct` |
| 48+ GB | `llama3.1:70b-instruct` | `ollama pull llama3.1:70b-instruct` |
| CPU only | `mistral:7b-instruct` | `ollama pull mistral:7b-instruct` |

### Switch to a cost-optimized model

```bash
kg admin extraction set --provider openai --model gpt-4o-mini --max-tokens 2048
```

Changes take effect on the next submitted job.

### Use a reasoning model with thinking mode (Ollama 0.12.x+)

Reasoning models generate an internal chain of thought before producing the final JSON. The system uses only the JSON output; the reasoning trace is logged for debugging.

```bash
# Configure with thinking mode
kg admin extraction set \
  --provider ollama \
  --model gpt-oss:20b \
  --thinking-mode medium
```

**Thinking modes:**

| Mode | Speed | Max tokens | Use when |
|---|---|---|---|
| `off` | Fastest | 4,096 | Simple documents, speed is critical |
| `low` | Fast | 4,096 | Standard workloads |
| `medium` | Slower | 12,288 | Technical or philosophical content |
| `high` | Slowest | 16,384 | Quality is critical, speed is secondary |

Standard models (Mistral, Llama) treat all non-`off` modes identically as enabled.

---

## Choosing a provider

| Factor | OpenAI | Anthropic | Ollama |
|---|---|---|---|
| Setup | Single API key covers extraction and embeddings | Two keys required (extraction + separate embedding provider) | No API key; install Ollama separately |
| Speed | ~2s/chunk | ~2s/chunk | 8–30s/chunk (GPU); ~60s/chunk (CPU only) |
| Cost | Paid per token | Paid per token | Free |
| Privacy | Cloud | Cloud | Local — data stays on your machine |
| Context window | 128K (gpt-4o) | 200K (claude models) | Model-dependent |

**Use Ollama if:** you have 100+ documents to process, your documents contain sensitive data, or you need offline capability with a GPU available.

**Use a cloud provider if:** you have fewer than ~10 documents, need maximum speed, or are running CPU-only.

---

## Hybrid configuration

Extraction provider and embedding provider are configured independently. Run extraction on Anthropic and embeddings on local sentence-transformers, for example:

```bash
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514
kg admin embedding activate <embedding-profile-id>
```

---

## Troubleshooting

### "No API key configured"

```bash
kg admin keys set openai
kg admin keys list     # confirm status is Valid
```

### "API key validation failed"

The key is rejected before storage — the stored key is not changed. Check that you are using the correct provider's key format (`sk-...` for OpenAI, `sk-ant-...` for Anthropic) and try again.

### "Extraction model not found"

Model name is invalid or not in the catalog. Check the model name spelling. Valid examples: `gpt-4o`, `gpt-4o-mini`, `claude-sonnet-4-20250514`, `mistral:7b-instruct`.

### "Rate limit exceeded"

Reduce concurrent ingestion jobs, wait for the provider rate limit window to reset, or switch to a model tier with higher limits.

### Ingestion still uses old model after config change

Extraction config is read at the start of each job, so any job submitted before the config change will use the old model. Jobs submitted after the change will use the new model. No restart is needed; confirm the new config with `kg admin extraction config`.

### "Cannot connect to Ollama"

Check that Ollama is running and reachable from the API container:

```bash
# If Ollama is on the host, check it's listening
curl http://localhost:11434/api/tags
```

If `OLLAMA_BASE_URL` is not set, the API container defaults to `http://localhost:11434`. Set it to the correct address if Ollama is on a different host or port.

### Out of VRAM (Ollama)

Switch to a smaller model:

```bash
ollama pull mistral:7b-instruct
kg admin extraction set --provider ollama --model mistral:7b-instruct
```
