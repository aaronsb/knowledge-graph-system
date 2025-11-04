#!/usr/bin/env python3
"""
Nomic Vision Embedding Similarity Tester

Test Nomic Embed Vision v2.0's ability to identify visually similar images.
This validates the visual context injection component of ADR-057.

Usage:
    python test_nomic_similarity.py /path/to/images/
    python test_nomic_similarity.py /path/to/images/ --show-matrix

Requirements:
    - sentence-transformers (pip install sentence-transformers)
    - torch, PIL, numpy
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: sentence-transformers library not found.")
    print("Install with: pip install sentence-transformers")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library not found.")
    print("Install with: pip install Pillow")
    sys.exit(1)


def load_images(image_dir: Path) -> List[Tuple[Path, Image.Image]]:
    """Load all images from directory."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    images = []
    for img_path in sorted(image_dir.iterdir()):
        if img_path.suffix.lower() in image_extensions:
            try:
                img = Image.open(img_path).convert('RGB')
                images.append((img_path, img))
                print(f"  Loaded: {img_path.name} ({img.size})")
            except Exception as e:
                print(f"  Warning: Could not load {img_path.name}: {e}")

    return images


def generate_embeddings(images: List[Tuple[Path, Image.Image]], model_name: str = "nomic-ai/nomic-embed-vision-v1.5") -> Dict[str, np.ndarray]:
    """Generate embeddings for all images using Nomic Embed Vision or CLIP."""
    print(f"\nLoading vision model: {model_name}")
    print("(This may take a minute on first run...)")

    # Auto-detect CUDA or use CPU
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda':
        print(f"Using device: {device} (GPU available)")
    else:
        print(f"Using device: {device} (no GPU available)")

    # Try Nomic Vision with transformers library
    if 'nomic' in model_name.lower():
        try:
            from transformers import AutoModel, AutoProcessor

            print("Loading Nomic Vision with transformers library...")
            model = AutoModel.from_pretrained(model_name, trust_remote_code=True).to(device)
            processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

            print("Model loaded. Generating embeddings...")

            embeddings = {}
            for img_path, img in images:
                # Process and embed
                inputs = processor(images=img, return_tensors='pt').to(device)
                with torch.no_grad():
                    outputs = model(**inputs)
                    # Use CLS token (first token) as embedding
                    embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()

                embeddings[img_path.name] = embedding
                print(f"  Embedded: {img_path.name} (dim={len(embedding)})")

            return embeddings

        except Exception as e:
            print(f"\nWarning: Could not load Nomic Vision with transformers")
            print(f"Error: {e}")
            print("\nFalling back to CLIP...")

    # Fall back to sentence-transformers (CLIP, etc.)
    try:
        model = SentenceTransformer(model_name, device=device)
    except Exception as e:
        print(f"Could not load {model_name}: {e}")
        print("Falling back to CLIP (clip-ViT-B-32)...")
        model = SentenceTransformer('clip-ViT-B-32', device=device)

    print("Model loaded. Generating embeddings...")

    embeddings = {}
    for img_path, img in images:
        # Generate embedding
        embedding = model.encode(img)
        embeddings[img_path.name] = embedding
        print(f"  Embedded: {img_path.name} (dim={len(embedding)})")

    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def compute_similarity_matrix(embeddings: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
    """Compute pairwise cosine similarities between all embeddings."""
    image_names = sorted(embeddings.keys())

    similarity_matrix = {}
    for img1 in image_names:
        similarity_matrix[img1] = {}
        for img2 in image_names:
            if img1 == img2:
                similarity_matrix[img1][img2] = 1.0  # Self-similarity
            else:
                sim = cosine_similarity(embeddings[img1], embeddings[img2])
                similarity_matrix[img1][img2] = float(sim)

    return similarity_matrix


def find_most_similar(similarity_matrix: Dict[str, Dict[str, float]], top_n: int = 3) -> Dict[str, List[Tuple[str, float]]]:
    """Find top N most similar images for each image."""
    most_similar = {}

    for img, similarities in similarity_matrix.items():
        # Sort by similarity (excluding self)
        sorted_sims = sorted(
            [(other, sim) for other, sim in similarities.items() if other != img],
            key=lambda x: x[1],
            reverse=True
        )
        most_similar[img] = sorted_sims[:top_n]

    return most_similar


def print_similarity_matrix(similarity_matrix: Dict[str, Dict[str, float]]):
    """Print full similarity matrix as table."""
    image_names = sorted(similarity_matrix.keys())

    # Header
    print("\nSimilarity Matrix:")
    print("=" * 100)
    print(f"{'Image':<30}", end="")
    for img in image_names:
        print(f"{img[:12]:>12}", end=" ")
    print()
    print("-" * 100)

    # Rows
    for img1 in image_names:
        print(f"{img1:<30}", end="")
        for img2 in image_names:
            sim = similarity_matrix[img1][img2]
            if img1 == img2:
                print(f"{'1.000':>12}", end=" ")
            else:
                print(f"{sim:>12.3f}", end=" ")
        print()


def print_most_similar(most_similar: Dict[str, List[Tuple[str, float]]]):
    """Print most similar images for each image."""
    print("\nMost Similar Images:")
    print("=" * 80)

    for img, similar in most_similar.items():
        print(f"\n{img}:")
        for i, (other, sim) in enumerate(similar, 1):
            # Color code by similarity
            if sim > 0.9:
                color = '\033[92m'  # Green (very similar)
            elif sim > 0.7:
                color = '\033[93m'  # Yellow (moderately similar)
            else:
                color = '\033[91m'  # Red (not very similar)

            print(f"  {i}. {color}{other:<30} (similarity: {sim:.3f})\033[0m")


def main():
    parser = argparse.ArgumentParser(
        description="Test Nomic Vision embedding similarity on images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test similarity on images in directory
  python test_nomic_similarity.py /path/to/images/

  # Show full similarity matrix
  python test_nomic_similarity.py /path/to/images/ --show-matrix

  # Use custom model
  python test_nomic_similarity.py /path/to/images/ --model clip-ViT-B-32

Expected behavior:
  - Visually similar images should have high similarity (>0.7)
  - Different images should have lower similarity (<0.5)
  - This validates visual context injection for ADR-057

Test setup:
  1. Create directory with mix of similar and different images
  2. Run this script to compute similarities
  3. Verify that similar images cluster together
        """
    )

    parser.add_argument(
        'image_dir',
        type=Path,
        help='Directory containing test images'
    )

    parser.add_argument(
        '--show-matrix',
        action='store_true',
        help='Show full similarity matrix (useful for small sets)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='nomic-ai/nomic-embed-vision-v1.5',
        help='Vision model to use (default: nomic-ai/nomic-embed-vision-v1.5)'
    )

    parser.add_argument(
        '--top-n',
        type=int,
        default=3,
        help='Number of most similar images to show per image (default: 3)'
    )

    args = parser.parse_args()

    # Validate directory
    if not args.image_dir.exists():
        print(f"Error: Directory not found: {args.image_dir}")
        sys.exit(1)

    if not args.image_dir.is_dir():
        print(f"Error: Not a directory: {args.image_dir}")
        sys.exit(1)

    print(f"Testing visual similarity in: {args.image_dir}")
    print()

    # Load images
    print("Loading images...")
    images = load_images(args.image_dir)

    if len(images) < 2:
        print(f"Error: Need at least 2 images, found {len(images)}")
        sys.exit(1)

    print(f"\nLoaded {len(images)} images")

    # Generate embeddings
    embeddings = generate_embeddings(images, model_name=args.model)

    # Compute similarities
    print("\nComputing pairwise similarities...")
    similarity_matrix = compute_similarity_matrix(embeddings)

    # Find most similar
    most_similar = find_most_similar(similarity_matrix, top_n=args.top_n)

    # Display results
    print_most_similar(most_similar)

    if args.show_matrix:
        print_similarity_matrix(similarity_matrix)

    print()
    print("=" * 80)
    print("Interpretation:")
    print("  >0.9: Very similar (same content, slight variations)")
    print("  0.7-0.9: Moderately similar (related content or style)")
    print("  0.5-0.7: Somewhat similar (same domain or type)")
    print("  <0.5: Different (unrelated content)")
    print()
    print("For ADR-057 visual context injection:")
    print("  - Threshold of 0.6-0.7 recommended for finding related images")
    print("  - Ontology boosting (+0.1) will favor same-domain results")


if __name__ == '__main__':
    main()
