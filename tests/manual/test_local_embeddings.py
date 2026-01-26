#!/usr/bin/env python3
"""
Quick test script for local embedding generation.

Tests the LocalEmbeddingProvider to ensure embeddings are generated correctly.
"""

import sys
sys.path.insert(0, '/home/aaron/Projects/ai/knowledge-graph-system')

from api.app.lib.embedding_model_manager import get_embedding_model_manager
import numpy as np

print("=" * 80)
print("Testing Local Embedding Generation")
print("=" * 80)
print()

# Initialize the model manager
print("Initializing embedding model manager...")
try:
    from api.app.lib.embedding_model_manager import EmbeddingModelManager

    # Create and load model manager (same as API startup)
    manager = EmbeddingModelManager(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        precision="float16"
    )
    manager.load_model()

    print(f"✅ Model loaded: {manager.get_model_name()}")
    print(f"   Dimensions: {manager.get_dimensions()}")
    print(f"   Precision: {manager.precision}")
    print()
except Exception as e:
    print(f"❌ Error loading model: {e}")
    sys.exit(1)

# Test embedding generation
test_texts = [
    "The quick brown fox jumps over the lazy dog",
    "Machine learning models require large amounts of training data",
    "PostgreSQL is a powerful open-source relational database"
]

print("Generating embeddings for test texts...")
print()

embeddings = []
for i, text in enumerate(test_texts, 1):
    print(f"  {i}. \"{text[:50]}...\"" if len(text) > 50 else f"  {i}. \"{text}\"")

    embedding = manager.generate_embedding(text)
    embeddings.append(embedding)

    # Verify embedding properties
    embedding_array = np.array(embedding)
    print(f"     • Shape: {embedding_array.shape}")
    print(f"     • Dtype: {embedding_array.dtype}")
    print(f"     • Norm: {np.linalg.norm(embedding_array):.4f} (should be ~1.0 if normalized)")
    print(f"     • First 5 values: {embedding_array[:5]}")
    print()

# Test cosine similarity
print("Testing similarity calculations...")
print()

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Compare embeddings
sim_1_2 = cosine_similarity(embeddings[0], embeddings[1])
sim_1_3 = cosine_similarity(embeddings[0], embeddings[2])
sim_2_3 = cosine_similarity(embeddings[1], embeddings[2])

print(f"  Similarity (text 1 vs text 2): {sim_1_2:.4f}")
print(f"  Similarity (text 1 vs text 3): {sim_1_3:.4f}")
print(f"  Similarity (text 2 vs text 3): {sim_2_3:.4f}")
print()

# Test self-similarity (should be 1.0)
self_sim = cosine_similarity(embeddings[0], embeddings[0])
print(f"  Self-similarity (text 1 vs text 1): {self_sim:.4f} (should be 1.0000)")
print()

print("=" * 80)
print("✅ Local embedding generation test complete!")
print("=" * 80)
