#!/usr/bin/env python3
"""
Test script for device detection and cross-platform compatibility.

Tests:
1. Device selector module (MPS/CUDA/CPU detection)
2. Embedding model compatibility with detected device
3. Vision model compatibility with detected device

Usage:
    python scripts/development/test/test_device_detection.py

    # Or from within operator container:
    docker exec kg-operator python /workspace/scripts/development/test/test_device_detection.py
"""

import sys
import os

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))

def test_device_detection():
    """Test basic device detection"""
    print("=" * 60)
    print("Testing Device Detection")
    print("=" * 60)

    try:
        from api.lib.device_selector import get_best_device, get_device_info, check_device_health

        # Test basic detection
        print("\n1. Basic Device Detection:")
        device = get_best_device()
        print(f"   Detected device: {device}")

        # Test device info
        print("\n2. Detailed Device Info:")
        info = get_device_info()
        for key, value in info.items():
            print(f"   {key}: {value}")

        # Test health check
        print("\n3. Device Health Check:")
        health = check_device_health()
        print(f"   Status: {health['status']}")
        if health['warnings']:
            print("   Warnings:")
            for warning in health['warnings']:
                print(f"     - {warning}")

        # Test CPU override
        print("\n4. Testing CPU Override:")
        cpu_device = get_best_device(prefer_cpu=True)
        print(f"   Device with prefer_cpu=True: {cpu_device}")
        assert cpu_device == "cpu", "CPU override failed"

        print("\n✅ Device detection tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Device detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_text_embedding_compatibility():
    """Test text embedding model compatibility with detected device"""
    print("\n" + "=" * 60)
    print("Testing Text Embedding Compatibility")
    print("=" * 60)

    try:
        from api.lib.device_selector import get_best_device
        from sentence_transformers import SentenceTransformer

        device = get_best_device()
        print(f"\n1. Detected device: {device}")

        print("\n2. Loading small test model (all-MiniLM-L6-v2, ~80MB)...")
        print("   This may take 10-20 seconds if not cached...")

        # Use a small model for quick testing
        model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2',
            device=device
        )

        print(f"   ✓ Model loaded on {device}")

        print("\n3. Testing embedding generation...")
        test_text = "This is a test sentence."
        embedding = model.encode(test_text, show_progress_bar=False)

        print(f"   ✓ Generated embedding: {len(embedding)} dimensions")
        print(f"   Sample values: {embedding[:5]}")

        print("\n✅ Text embedding compatibility tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Text embedding compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vision_embedding_compatibility():
    """Test vision embedding model compatibility with detected device"""
    print("\n" + "=" * 60)
    print("Testing Vision Embedding Compatibility")
    print("=" * 60)

    try:
        from api.lib.device_selector import get_best_device
        from PIL import Image
        import numpy as np

        device = get_best_device()
        print(f"\n1. Detected device: {device}")

        print("\n2. Creating test image (32x32 RGB)...")
        # Create a small test image
        test_image = Image.new('RGB', (32, 32), color='red')

        print("\n3. Testing vision model loading...")
        print("   Note: This test requires transformers and torch installed")

        from transformers import AutoModel, AutoProcessor

        # Use a small vision model for testing (CLIP is ~350MB)
        model_name = "openai/clip-vit-base-patch32"

        print(f"   Loading {model_name}...")
        print("   This may take 30-60 seconds if not cached...")

        if device in ('cuda', 'mps'):
            model = AutoModel.from_pretrained(model_name, device_map="auto")
        else:
            model = AutoModel.from_pretrained(model_name, low_cpu_mem_usage=False)

        processor = AutoProcessor.from_pretrained(model_name)

        print(f"   ✓ Model loaded on {device}")

        print("\n4. Testing image processing...")
        inputs = processor(images=test_image, return_tensors='pt')
        if device != 'cpu':
            inputs = {k: v.to(device) for k, v in inputs.items()}

        import torch
        with torch.no_grad():
            outputs = model.vision_model(**inputs)

        print(f"   ✓ Image processed successfully")
        print(f"   Output shape: {outputs.last_hidden_state.shape}")

        print("\n✅ Vision embedding compatibility tests passed!")
        return True

    except ImportError as e:
        print(f"\n⚠️  Skipping vision test - dependencies not available: {e}")
        return True  # Don't fail if transformers not installed
    except Exception as e:
        print(f"\n❌ Vision embedding compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Device Detection Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Device detection
    results.append(("Device Detection", test_device_detection()))

    # Test 2: Text embeddings (requires sentence-transformers)
    try:
        import sentence_transformers
        results.append(("Text Embedding Compatibility", test_text_embedding_compatibility()))
    except ImportError:
        print("\n⚠️  Skipping text embedding test - sentence-transformers not installed")

    # Test 3: Vision embeddings (optional)
    try:
        import transformers
        results.append(("Vision Embedding Compatibility", test_vision_embedding_compatibility()))
    except ImportError:
        print("\n⚠️  Skipping vision embedding test - transformers not installed")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
