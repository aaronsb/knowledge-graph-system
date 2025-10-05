# AI Provider Configuration

## Overview

The Knowledge Graph System uses a modular AI provider architecture that supports:
- **OpenAI** (GPT-4, embeddings)
- **Anthropic** (Claude models)

Both providers can be used for concept extraction, with OpenAI providing embeddings for both.

## Configuration

### Environment Variables

```bash
# Provider Selection
AI_PROVIDER=openai  # or "anthropic"

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_EXTRACTION_MODEL=gpt-4o  # optional override
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # optional override

# Anthropic Configuration (optional)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514  # optional override
```

## Supported Models

### OpenAI

**Extraction Models:**
- `gpt-4o` (default) - Latest GPT-4 Omni, recommended for concept extraction
- `gpt-4o-mini` - Faster, cheaper variant
- `o1-preview` - Reasoning model for complex analysis
- `o1-mini` - Smaller reasoning model

**Embedding Models:**
- `text-embedding-3-small` (default) - 1536 dimensions, fast and efficient
- `text-embedding-3-large` - 3072 dimensions, more accurate
- `text-embedding-ada-002` - Legacy model

### Anthropic

**Extraction Models:**
- `claude-sonnet-4-20250514` (default) - Latest Claude Sonnet 4.5 (SOTA)
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet
- `claude-3-opus-20240229` - Claude 3 Opus (most capable)
- `claude-3-sonnet-20240229` - Claude 3 Sonnet (balanced)
- `claude-3-haiku-20240307` - Claude 3 Haiku (fastest)

**Note:** Anthropic doesn't provide embeddings, so `OPENAI_API_KEY` is required even when using Anthropic for extraction.

## Interactive Configuration

Use the configuration script:

```bash
./scripts/configure-ai.sh
```

Options:
1. Test current provider
2. Test OpenAI
3. Test Anthropic
4. Switch to OpenAI
5. Switch to Anthropic
6. Configure OpenAI models
7. Configure Anthropic models
8. Exit

## Provider Architecture

### OpenAIProvider

```python
from ingest.ai_providers import OpenAIProvider

provider = OpenAIProvider(
    extraction_model="gpt-4o",
    embedding_model="text-embedding-3-small"
)

# Validate API key
if provider.validate_api_key():
    print("✓ OpenAI configured")

# Extract concepts
result = provider.extract_concepts(
    text="your text",
    system_prompt=EXTRACTION_PROMPT,
    existing_concepts=[]
)

# Generate embeddings
embedding = provider.generate_embedding("your text")
```

### AnthropicProvider

```python
from ingest.ai_providers import AnthropicProvider, OpenAIProvider

# Anthropic requires an embedding provider
embedding_provider = OpenAIProvider(
    embedding_model="text-embedding-3-small"
)

provider = AnthropicProvider(
    extraction_model="claude-sonnet-4-20250514",
    embedding_provider=embedding_provider
)

# Same interface as OpenAI
result = provider.extract_concepts(...)
embedding = provider.generate_embedding(...)  # delegates to OpenAI
```

## Choosing a Provider

### OpenAI (GPT-4)

**Pros:**
- Single API key for everything
- Fast inference
- JSON mode ensures structured output
- Good at following extraction schema
- Cost-effective with gpt-4o-mini

**Cons:**
- Less capable than Claude Sonnet 4 for complex reasoning
- Token limits can be restrictive for long documents

**Best for:**
- Simple concept extraction
- High-volume processing
- When cost is a concern

### Anthropic (Claude)

**Pros:**
- Claude Sonnet 4.5 is current SOTA for reasoning
- Better at understanding nuanced relationships
- Larger context windows (200K tokens)
- More thoughtful analysis

**Cons:**
- Requires two API keys (Anthropic + OpenAI)
- Slower inference
- Higher cost
- Requires JSON extraction from response

**Best for:**
- Complex philosophical/technical documents
- When quality > speed
- Nuanced relationship extraction

## Model Selection Guide

### For Extraction

**Quality Priority:**
1. `claude-sonnet-4-20250514` (Anthropic) - SOTA
2. `gpt-4o` (OpenAI) - Excellent balance
3. `o1-preview` (OpenAI) - Complex reasoning

**Speed Priority:**
1. `gpt-4o-mini` (OpenAI) - Fast and cheap
2. `claude-3-haiku-20240307` (Anthropic) - Fast Claude
3. `gpt-4o` (OpenAI) - Good balance

**Cost Priority:**
1. `gpt-4o-mini` (OpenAI) - Cheapest capable model
2. `gpt-4o` (OpenAI) - Best value
3. `claude-3-haiku-20240307` (Anthropic) - Cheapest Claude

### For Embeddings

**Recommended:**
- `text-embedding-3-small` - Best balance of quality/speed/cost

**High Accuracy:**
- `text-embedding-3-large` - 2x dimensions, better similarity

**Legacy:**
- `text-embedding-ada-002` - Older model, still works

## Testing and Validation

### Validate API Keys

```bash
# Via script
./scripts/configure-ai.sh  # Option 1

# Via Python
python -c "
from ingest.ai_providers import get_provider
provider = get_provider('openai')
print('✓ Valid' if provider.validate_api_key() else '✗ Invalid')
"
```

### List Available Models

```bash
python -c "
from ingest.ai_providers import get_provider
provider = get_provider('openai')
models = provider.list_available_models()
print('Extraction:', models['extraction'][:5])
print('Embedding:', models['embedding'])
"
```

### Test Extraction

```bash
python -c "
from ingest.llm_extractor import extract_concepts

result = extract_concepts(
    text='The universe is vast and complex.',
    source_id='test-1',
    existing_concepts=[]
)

print('Concepts:', [c['label'] for c in result['concepts']])
"
```

## Troubleshooting

### "API key invalid"

```bash
# Check environment
echo $OPENAI_API_KEY
cat .env | grep API_KEY

# Test directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### "Rate limit exceeded"

- Reduce ingestion batch size
- Add delays between requests
- Upgrade API plan

### "Model not found"

- Check model name spelling
- Verify API access (some models require approval)
- Use `list_available_models()` to see what's accessible

### "JSON parsing failed" (Anthropic)

- Claude may include markdown
- Provider handles cleaning automatically
- Check `_extract_json()` method if issues persist

## Advanced Usage

### Custom Provider

Extend the base `AIProvider` class:

```python
from ingest.ai_providers import AIProvider

class CustomProvider(AIProvider):
    def extract_concepts(self, text, system_prompt, existing_concepts):
        # Your implementation
        pass

    def generate_embedding(self, text):
        # Your implementation
        pass

    # Implement all abstract methods
```

### Provider Switching

```python
# Switch providers at runtime
from ingest.ai_providers import get_provider

openai_result = get_provider('openai').extract_concepts(...)
anthropic_result = get_provider('anthropic').extract_concepts(...)
```

### Hybrid Approach

```python
# Use Claude for extraction, OpenAI for embeddings
from ingest.ai_providers import AnthropicProvider, OpenAIProvider

provider = AnthropicProvider(
    extraction_model="claude-sonnet-4-20250514",
    embedding_provider=OpenAIProvider(
        embedding_model="text-embedding-3-large"
    )
)
```
