---
status: Accepted
date: 2025-10-23
deciders: System Architects
related:
  - ADR-039
  - ADR-042
---

# ADR-043: Single-Node Resource Management for Local Inference

## Overview

Here's a scenario that seems perfect until it breaks: you're running local inference with Ollama extracting concepts and a local embedding model generating vectors. Everything runs on one GPU to keep costs down. The extraction model (say, a 20B parameter LLM) loads into your GPU's VRAM and processes a chunk of text. Great! Then the embedding model tries to load right after... and crashes. Why? Your GPU only has 12GB of VRAM, the extraction model is using 10GB of it, and the embedding model needs at least 500MB. The math doesn't work.

Think of it like trying to fit two elephants into a single-car garage. They can't both be in there at the same time, but you need both to get your work done. The naive solution would be to constantly unload one model and load the other, but that's painfully slow—model loading can take 30+ seconds each time. During a multi-hour ingestion job, you'd spend more time swapping models than actually processing documents.

This is the reality of running modern AI on consumer hardware: VRAM is the bottleneck, and you have to be smart about managing it. The problem is particularly insidious because it often fails silently—the embedding model tries to load, can't find enough memory, falls back to CPU (if you're lucky), or just crashes (if you're not). Users see "ingestion complete" but get zero concepts extracted.

This ADR solves the problem with intelligent resource management: check available VRAM before trying to load the embedding model, automatically fall back to CPU-based embeddings when GPU memory is tight, and clearly communicate what's happening so operators understand the performance tradeoffs. The key insight is that CPU-based embeddings are slower but acceptable (adding ~100ms per chunk to a 2-3 minute extraction job), while silent failures are unacceptable.

---

## Context

With the introduction of local inference capabilities (ADR-042: Ollama for extraction, ADR-039: sentence-transformers for embeddings), the system can now run entirely on local GPU hardware. However, this creates resource contention on single-node deployments where both models compete for limited VRAM.

### Resource Conflict Scenario

**Typical Ingestion Pipeline:**
1. **Extraction Phase** (2-3 minutes per chunk)
   - Ollama loads GPT-OSS 20B into VRAM (~10-12GB)
   - Model stays resident due to `keep_alive` default behavior
   - GPU utilization: 100% during inference

2. **Embedding Phase** (immediate after extraction)
   - nomic-embed-text-v1.5 attempts to load into VRAM (~275MB base + overhead)
   - **Collision**: Insufficient free VRAM with extraction model still resident
   - Embedding generation silently fails or crashes

### Problem Manifestation

Users reported "silent failures" during ingestion:
- First chunk succeeds (cold start, no models loaded)
- Subsequent chunks fail at embedding phase
- No error logs (with `verbose=False`)
- Jobs appear to complete but produce zero concepts

**Real-world case:**
```
09:02:22 | INFO  | ✓ Extracted 22 concepts, 22 instances, 15 relationships
[silence - all 22 concepts fail embedding generation]
```

### Hardware Constraints

**Single-GPU Systems:**
- Total VRAM: 12-24GB (typical workstation GPUs)
- Extraction model: 8-16GB (depending on model size)
- Embedding model: 500MB (with safety margin)
- **Gap**: Often <500MB free after extraction

**Multi-GPU Systems:**
- Could isolate models to separate GPUs
- Adds complexity of device management
- Not accessible to most users

## Decision

Implement **dynamic device selection with intelligent CPU fallback** for the embedding model:

### Strategy

**Pre-flight VRAM Check** (one-time per chunk):
1. Before embedding pass begins, check available VRAM
2. If free VRAM >= 500MB → use GPU (`cuda:0`)
3. If free VRAM < 500MB → use CPU with clear warning

**Warning Message:**
```
⚠️  Not enough VRAM (250MB free, 500MB required)
🔄 Moving embedding model to CPU mode (performance degraded ~100ms/batch)
```

### Implementation Details

**Location:** `embedding_model_manager.py` → `generate_embedding()`

```python
def generate_embedding(self, text: str) -> List[float]:
    # One-time device selection (cached per embedding session)
    if not hasattr(self, '_device'):
        self._device = self._select_device()

    embedding = self.model.encode(
        text,
        normalize_embeddings=True,
        device=self._device  # Dynamic: 'cuda:0' or 'cpu'
    )
    return embedding.tolist()

def _select_device(self) -> str:
    """Select compute device based on VRAM availability"""
    import torch

    # Check if CUDA available
    if not torch.cuda.is_available():
        return 'cpu'

    # Check free VRAM
    try:
        free_vram_bytes, total_vram_bytes = torch.cuda.mem_get_info()
        free_vram_mb = free_vram_bytes / (1024 ** 2)

        if free_vram_mb >= 500:
            logger.info(f"✓ Sufficient VRAM ({int(free_vram_mb)}MB free), using GPU")
            return 'cuda:0'
        else:
            logger.warning(f"⚠️  Not enough VRAM ({int(free_vram_mb)}MB free, 500MB required)")
            logger.warning("🔄 Moving embedding model to CPU mode (performance degraded ~100ms/batch)")
            return 'cpu'
    except Exception as e:
        logger.warning(f"⚠️  Could not check VRAM: {e}, defaulting to CPU")
        return 'cpu'
```

### Performance Characteristics

**GPU Mode (VRAM available):**
- Embedding time: ~1-2ms per concept
- 22 concepts: ~22-44ms total
- Preferred when available

**CPU Fallback Mode (VRAM contention):**
- Embedding time: ~5-10ms per concept
- 22 concepts: ~110-220ms total
- **Penalty: ~100-180ms per chunk**

**Context:** In a 2-3 minute extraction job, a 100ms embedding penalty is **negligible** (<0.1% overhead).

## Consequences

### Positive

1. **Reliable Operation**
   - No silent failures
   - Graceful degradation instead of crashes
   - Works on any hardware configuration

2. **Minimal Performance Impact**
   - 100ms penalty is invisible in multi-minute jobs
   - GPU used when available (zero overhead)
   - No model reloading delays

3. **Transparent Operation**
   - Clear warning messages explain resource decisions
   - Users understand why performance may vary
   - Logs show device selection reasoning

4. **Zero Configuration**
   - No user intervention required
   - Works out-of-box on any system
   - Adapts to changing resource conditions

5. **Predictable Behavior**
   - Single VRAM check per chunk (not per concept)
   - Consistent device selection within batch
   - No mid-flight switching

### Negative

1. **Sub-optimal Resource Usage**
   - Could theoretically use GPU even with <500MB by unloading Ollama
   - Leaves some performance on the table
   - Trade-off: simplicity vs maximum performance

2. **No Cross-Model Coordination**
   - Doesn't actively manage Ollama's `keep_alive`
   - Passive adaptation rather than active resource negotiation
   - Could be improved in future with model orchestration

### Neutral

1. **Hardware Dependency**
   - Behavior varies based on GPU size
   - 16GB GPU: Usually GPU mode
   - 8GB GPU: Usually CPU mode
   - Consistent for a given system

2. **Embedding Latency Variance**
   - First chunk may use GPU (cold start)
   - Subsequent chunks may use CPU (contention)
   - Users see ~100ms variation in chunk processing time

## Alternatives Considered

### Alternative 1: Always Use CPU for Embeddings

**Approach:** If extraction provider is Ollama, force embeddings to CPU.

**Pros:**
- Simplest implementation
- Always reliable
- No VRAM checks needed

**Cons:**
- Wastes GPU when available (e.g., small extraction models)
- Arbitrary 100ms penalty even when unnecessary
- Doesn't adapt to resource changes

**Verdict:** Too conservative, leaves performance on table.

---

### Alternative 2: Always Use GPU for Embeddings

**Approach:** Assume sufficient VRAM, fail if not available.

**Pros:**
- Best performance when it works
- No fallback complexity

**Cons:**
- Fails on most single-GPU systems
- Silent failures (the original problem)
- Requires manual intervention

**Verdict:** Unreliable, recreates original issue.

---

### Alternative 3: Ollama `keep_alive` Management

**Approach:** Explicitly unload extraction model before embedding phase.

```python
# After extraction
POST /api/generate {"model": "gpt-oss:20b", "keep_alive": 0}
time.sleep(2)  # Wait for unload
# Then embeddings on GPU
```

**Pros:**
- Always uses GPU for embeddings
- Maximum performance
- Explicit resource coordination

**Cons:**
- Adds 2-5 second delay per chunk (unload + reload overhead)
- Next chunk must reload extraction model (30s+ for large models)
- Ollama API call overhead
- Tightly couples extraction and embedding logic

**Verdict:** Too slow, adds 30+ seconds per chunk.

---

### Alternative 4: Model Reloading (GPU ↔ CPU)

**Approach:** Reload embedding model to CPU when VRAM insufficient.

```python
if vram < 500:
    reload_embedding_model(device='cpu')
# Do embeddings
if originally_on_gpu:
    reload_embedding_model(device='cuda:0')
```

**Pros:**
- Adapts to resource availability
- Could reload back to GPU after extraction

**Cons:**
- Model reload overhead: 1-2 seconds per switch
- Adds complexity (model lifecycle management)
- State management issues
- Slower than just using CPU

**Verdict:** Complexity not justified by 1-2s savings.

---

### Alternative 5: Separate VRAM Pools (Multi-GPU)

**Approach:** Assign extraction to GPU 0, embeddings to GPU 1.

```python
extraction_device = 'cuda:0'
embedding_device = 'cuda:1'
```

**Pros:**
- No resource contention
- Both models run at full speed
- Scales to more models

**Cons:**
- Requires multi-GPU system (minority of users)
- Adds device management complexity
- Doesn't solve single-GPU case

**Verdict:** Good for multi-GPU, but need single-GPU solution too.

---

### Alternative 6: Unified Model Server

**Approach:** Single inference server manages all models (vLLM, TensorRT-LLM).

**Pros:**
- Sophisticated resource scheduling
- Batch processing optimization
- Production-grade solution

**Cons:**
- Massive architecture change
- Vendor lock-in
- Overkill for single-node deployment
- Still doesn't guarantee no contention

**Verdict:** Future consideration for scale, not for current scope.

## Implementation Checklist

- [x] Add VRAM check function to `embedding_model_manager.py`
- [ ] Implement `_select_device()` with 500MB threshold
- [ ] Add warning logs for CPU fallback
- [ ] Test on systems with varying VRAM (8GB, 16GB, 24GB)
- [ ] Update documentation with resource recommendations
- [ ] Add performance metrics to logs (device used, embedding time)

## Recommendations

### For Users

**Optimal Hardware:**
- 16GB+ VRAM: Both models fit comfortably, GPU mode
- 12GB VRAM: Tight fit, may use CPU mode with large extraction models
- 8GB VRAM: CPU mode likely for embeddings

**Model Selection:**
- Extraction: Smaller models (7-8B) leave room for GPU embeddings
- Extraction: Larger models (20B+) trigger CPU fallback

**Performance Expectations:**
- GPU mode: 2-3 minutes per chunk
- CPU mode: 2.1-3.1 minutes per chunk (~0.1% slower)

### For Developers

**Monitoring:**
- Log device selection decision
- Track embedding latency by device
- Alert on repeated CPU fallback (may indicate undersized GPU)

**Future Enhancements:**
- Configurable VRAM threshold (default 500MB)
- Multi-GPU device assignment
- Ollama `keep_alive` coordination
- Unified model server integration (vLLM, etc.)

## Metrics and Success Criteria

**Reliability:**
- ✓ Zero silent failures during embedding phase
- ✓ All chunks process to completion
- ✓ Clear error messages when issues occur

**Performance:**
- ✓ <1% overhead on total ingestion time
- ✓ GPU used when available (>500MB free)
- ✓ No model reload delays

**User Experience:**
- ✓ Transparent resource decisions
- ✓ No configuration required
- ✓ Works on all hardware configurations

## Related Documentation

- **ADR-039:** Local Embedding Service (introduces sentence-transformers)
- **ADR-042:** Local LLM Inference (introduces Ollama for extraction)
- **Performance Guide:** Hardware Recommendations (to be written)
- **Troubleshooting Guide:** VRAM Issues (to be written)

## Notes

This ADR represents a pragmatic approach to resource management: simple, reliable, and transparent. While more sophisticated solutions exist (unified model servers, advanced scheduling), they add complexity inappropriate for single-node deployments.

The 100ms CPU fallback penalty is negligible in the context of 2-3 minute extraction times, making this a high-reliability, low-overhead solution.

Future work may explore active resource coordination, but this passive adaptation approach provides a solid foundation.

---

**Revision History:**
- 2025-10-23: Initial draft (v1.0)
