#!/usr/bin/env python3
"""
Visual Embedding Model Comparison

Compares three visual embedding models on the same image set:
1. CLIP (local) - sentence-transformers: clip-ViT-B-32 (512-dim)
2. OpenAI CLIP API - OpenAI embeddings API (varies by model)
3. Nomic Vision (local) - nomic-ai/nomic-embed-vision-v1.5 (768-dim)

Usage:
    python compare_embeddings.py /path/to/images/

Requirements:
    - OpenAI API key in /home/aaron/Projects/ai/data/images/.env
    - sentence-transformers, transformers, torch, openai, PIL
"""

import argparse
import base64
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not found.")
    print("Install with: pip install openai")
    sys.exit(1)

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

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv library not found.")
    print("Install with: pip install python-dotenv")
    sys.exit(1)

try:
    import torch
except ImportError:
    print("Error: torch library not found.")
    print("Install with: pip install torch")
    sys.exit(1)


def load_api_key(env_path: Path) -> str:
    """Load OpenAI API key from .env file."""
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    load_dotenv(env_path)
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print(f"Error: OPENAI_API_KEY not found in {env_path}")
        sys.exit(1)

    return api_key


def load_images(image_dir: Path) -> List[Tuple[Path, Image.Image]]:
    """Load all images from directory."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    images = []
    for img_path in sorted(image_dir.iterdir()):
        if img_path.suffix.lower() in image_extensions:
            try:
                img = Image.open(img_path).convert('RGB')
                images.append((img_path, img))
            except Exception as e:
                print(f"  Warning: Could not load {img_path.name}: {e}")

    return images


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def find_top_similar(embeddings: Dict[str, np.ndarray], top_n: int = 3) -> Dict[str, List[Tuple[str, float]]]:
    """Find top N most similar images for each image."""
    results = {}

    for img1, emb1 in embeddings.items():
        similarities = []
        for img2, emb2 in embeddings.items():
            if img1 != img2:
                sim = cosine_similarity(emb1, emb2)
                similarities.append((img2, float(sim)))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        results[img1] = similarities[:top_n]

    return results


def generate_clip_local_embeddings(images: List[Tuple[Path, Image.Image]]) -> Tuple[Dict[str, np.ndarray], float, int]:
    """Generate embeddings using local CLIP model (sentence-transformers)."""
    print("\n" + "=" * 80)
    print("MODEL 1: CLIP (Local - sentence-transformers)")
    print("=" * 80)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")
    print("Model: clip-ViT-B-32")

    try:
        start_time = time.time()

        print("Loading model...")
        model = SentenceTransformer('clip-ViT-B-32', device=device)

        print("Generating embeddings...")
        embeddings = {}
        for img_path, img in images:
            embedding = model.encode(img)
            embeddings[img_path.name] = embedding
            print(f"  ✓ {img_path.name} (dim={len(embedding)})")

        elapsed = time.time() - start_time
        dim = len(next(iter(embeddings.values())))

        print(f"\nCompleted in {elapsed:.2f}s")
        return embeddings, elapsed, dim

    except Exception as e:
        print(f"Error: {e}")
        return {}, 0.0, 0


def generate_openai_clip_embeddings(images: List[Tuple[Path, Image.Image]], api_key: str) -> Tuple[Dict[str, np.ndarray], float, int]:
    """Generate embeddings using OpenAI CLIP API."""
    print("\n" + "=" * 80)
    print("MODEL 2: OpenAI CLIP (API)")
    print("=" * 80)

    print("Model: openai/clip-vit-base-patch32")

    try:
        start_time = time.time()

        client = OpenAI(api_key=api_key)

        print("Generating embeddings...")
        embeddings = {}

        for img_path, img in images:
            # Convert image to base64
            import io
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Call OpenAI embeddings API with image
            response = client.embeddings.create(
                model="openai/clip-vit-base-patch32",
                input=f"data:image/png;base64,{img_base64}"
            )

            embedding = np.array(response.data[0].embedding)
            embeddings[img_path.name] = embedding
            print(f"  ✓ {img_path.name} (dim={len(embedding)})")

        elapsed = time.time() - start_time
        dim = len(next(iter(embeddings.values())))

        print(f"\nCompleted in {elapsed:.2f}s")
        return embeddings, elapsed, dim

    except Exception as e:
        print(f"Error: {e}")
        print("Note: OpenAI embeddings API may not support image inputs directly")
        print("Falling back to text-based approach (not ideal for visual comparison)")

        # Fallback: Use GPT-4o Vision to generate text descriptions, then embed
        try:
            start_time = time.time()
            client = OpenAI(api_key=api_key)

            print("\nFallback: Using GPT-4o Vision → text embeddings")
            embeddings = {}

            for img_path, img in images:
                # Convert to base64
                import io
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                # Get visual description
                vision_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe this image in detail (2-3 sentences). Focus on visual content, colors, objects, scene."},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                            ]
                        }
                    ],
                    max_tokens=100
                )
                description = vision_response.choices[0].message.content

                # Embed the description
                embed_response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=description
                )

                embedding = np.array(embed_response.data[0].embedding)
                embeddings[img_path.name] = embedding
                print(f"  ✓ {img_path.name} (dim={len(embedding)}) via description")

            elapsed = time.time() - start_time
            dim = len(next(iter(embeddings.values())))

            print(f"\nCompleted in {elapsed:.2f}s")
            print("Note: This uses text descriptions, not pure visual embeddings")
            return embeddings, elapsed, dim

        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return {}, 0.0, 0


def generate_nomic_vision_embeddings(images: List[Tuple[Path, Image.Image]]) -> Tuple[Dict[str, np.ndarray], float, int]:
    """Generate embeddings using Nomic Vision model (transformers)."""
    print("\n" + "=" * 80)
    print("MODEL 3: Nomic Vision (Local - transformers)")
    print("=" * 80)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")
    print("Model: nomic-ai/nomic-embed-vision-v1.5")

    try:
        from transformers import AutoModel, AutoProcessor

        start_time = time.time()

        print("Loading model...")
        model = AutoModel.from_pretrained(
            'nomic-ai/nomic-embed-vision-v1.5',
            trust_remote_code=True
        ).to(device)
        processor = AutoProcessor.from_pretrained(
            'nomic-ai/nomic-embed-vision-v1.5',
            trust_remote_code=True
        )

        print("Generating embeddings...")
        embeddings = {}

        for img_path, img in images:
            inputs = processor(images=img, return_tensors='pt').to(device)
            with torch.no_grad():
                outputs = model(**inputs)
                # Use CLS token (first token) as embedding
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()

            embeddings[img_path.name] = embedding
            print(f"  ✓ {img_path.name} (dim={len(embedding)})")

        elapsed = time.time() - start_time
        dim = len(next(iter(embeddings.values())))

        print(f"\nCompleted in {elapsed:.2f}s")
        return embeddings, elapsed, dim

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {}, 0.0, 0


def print_comparison_results(
    model_name: str,
    embeddings: Dict[str, np.ndarray],
    dim: int,
    elapsed: float
):
    """Print similarity results for one model."""
    if not embeddings:
        print(f"\n{model_name}: FAILED")
        return

    print(f"\n{model_name} ({dim}-dim, {elapsed:.2f}s)")
    print("=" * 80)

    top_similar = find_top_similar(embeddings, top_n=3)

    for img, similar in sorted(top_similar.items()):
        print(f"\n{img}:")
        for i, (other, sim) in enumerate(similar, 1):
            # Color code by similarity
            if sim > 0.9:
                color = '\033[92m'  # Green (very similar)
            elif sim > 0.7:
                color = '\033[93m'  # Yellow (moderately similar)
            else:
                color = '\033[91m'  # Red (not very similar)

            print(f"  {i}. {color}{other:<35} ({sim:.3f})\033[0m")


def analyze_clustering_quality(embeddings: Dict[str, np.ndarray]) -> Dict[str, float]:
    """Analyze clustering quality metrics."""
    if not embeddings:
        return {}

    top_similar = find_top_similar(embeddings, top_n=3)

    # Calculate average top-3 similarity
    avg_top3_sim = np.mean([
        np.mean([sim for _, sim in similar])
        for similar in top_similar.values()
    ])

    # Calculate similarity variance (higher = better separation)
    all_sims = []
    for img1, emb1 in embeddings.items():
        for img2, emb2 in embeddings.items():
            if img1 != img2:
                sim = cosine_similarity(emb1, emb2)
                all_sims.append(sim)

    sim_variance = np.var(all_sims)
    sim_std = np.std(all_sims)
    sim_range = max(all_sims) - min(all_sims)

    return {
        'avg_top3_similarity': avg_top3_sim,
        'similarity_variance': sim_variance,
        'similarity_std': sim_std,
        'similarity_range': sim_range
    }


def print_summary(results: Dict[str, Dict]):
    """Print comprehensive summary comparing all models."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE SUMMARY")
    print("=" * 80)

    # Performance comparison
    print("\n1. PERFORMANCE COMPARISON")
    print("-" * 80)
    print(f"{'Model':<30} {'Time':<15} {'Dimensions':<15} {'Status'}")
    print("-" * 80)

    for model_name, data in results.items():
        if data['embeddings']:
            status = "✓ SUCCESS"
            time_str = f"{data['elapsed']:.2f}s"
            dim_str = str(data['dim'])
        else:
            status = "✗ FAILED"
            time_str = "N/A"
            dim_str = "N/A"

        print(f"{model_name:<30} {time_str:<15} {dim_str:<15} {status}")

    # Clustering quality
    print("\n2. CLUSTERING QUALITY")
    print("-" * 80)
    print(f"{'Model':<30} {'Avg Top-3 Sim':<20} {'Variance':<15} {'Range'}")
    print("-" * 80)

    for model_name, data in results.items():
        if data['embeddings']:
            metrics = data['metrics']
            avg_sim = metrics['avg_top3_similarity']
            variance = metrics['similarity_variance']
            sim_range = metrics['similarity_range']

            print(f"{model_name:<30} {avg_sim:<20.3f} {variance:<15.4f} {sim_range:.3f}")

    # Recommendations
    print("\n3. RECOMMENDATIONS FOR ADR-057")
    print("-" * 80)

    successful_models = {
        name: data for name, data in results.items()
        if data['embeddings']
    }

    if not successful_models:
        print("No models succeeded. Cannot provide recommendations.")
        return

    # Find fastest
    fastest = min(successful_models.items(), key=lambda x: x[1]['elapsed'])
    print(f"\nFastest: {fastest[0]} ({fastest[1]['elapsed']:.2f}s)")

    # Find best clustering (highest avg top-3 similarity)
    best_clustering = max(
        successful_models.items(),
        key=lambda x: x[1]['metrics']['avg_top3_similarity']
    )
    print(f"Best clustering: {best_clustering[0]} (avg top-3 sim: {best_clustering[1]['metrics']['avg_top3_similarity']:.3f})")

    # Find best separation (highest variance)
    best_separation = max(
        successful_models.items(),
        key=lambda x: x[1]['metrics']['similarity_variance']
    )
    print(f"Best separation: {best_separation[0]} (variance: {best_separation[1]['metrics']['similarity_variance']:.4f})")

    # Cost-effectiveness
    print("\nCost-effectiveness:")
    for model_name, data in successful_models.items():
        if 'OpenAI' in model_name or 'API' in model_name:
            print(f"  {model_name}: $$$ (API costs per image)")
        else:
            print(f"  {model_name}: $ (local inference, one-time model download)")

    # Overall recommendation
    print("\n4. OVERALL RECOMMENDATION")
    print("-" * 80)

    local_models = {
        name: data for name, data in successful_models.items()
        if 'API' not in name and 'OpenAI' not in name
    }

    if local_models:
        # Recommend best local model
        best_local = max(
            local_models.items(),
            key=lambda x: x[1]['metrics']['avg_top3_similarity']
        )

        print(f"\nRecommended: {best_local[0]}")
        print(f"  - Best balance of quality and cost")
        print(f"  - No API costs")
        print(f"  - Clustering quality: {best_local[1]['metrics']['avg_top3_similarity']:.3f}")
        print(f"  - Speed: {best_local[1]['elapsed']:.2f}s for {len(best_local[1]['embeddings'])} images")
        print(f"  - Dimensions: {best_local[1]['dim']}")

        print("\nIntegration notes:")
        print("  - Use for visual context injection in ADR-057")
        print("  - Similarity threshold: 0.6-0.7 for finding related images")
        print("  - Ontology boosting: +0.1 for same-domain images")
        print("  - GPU acceleration available (CPU fallback supported)")
    else:
        print("\nNo local models succeeded. API-based model recommended:")
        best_api = max(
            successful_models.items(),
            key=lambda x: x[1]['metrics']['avg_top3_similarity']
        )
        print(f"  {best_api[0]}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare visual embedding models on image set",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare all models on image directory
  python compare_embeddings.py /path/to/images/

  # Use custom .env location
  python compare_embeddings.py /path/to/images/ --env /path/to/.env

Models tested:
  1. CLIP (local) - sentence-transformers: clip-ViT-B-32 (512-dim)
  2. OpenAI CLIP API - OpenAI embeddings API
  3. Nomic Vision (local) - nomic-ai/nomic-embed-vision-v1.5 (768-dim)

Output:
  - Similarity rankings for each model
  - Performance metrics (speed, dimensions)
  - Clustering quality analysis
  - Recommendation for ADR-057
        """
    )

    parser.add_argument(
        'image_dir',
        type=Path,
        help='Directory containing images to analyze'
    )

    parser.add_argument(
        '--env',
        type=Path,
        default=Path('/home/aaron/Projects/ai/data/images/.env'),
        help='Path to .env file with OPENAI_API_KEY (default: /home/aaron/Projects/ai/data/images/.env)'
    )

    args = parser.parse_args()

    # Validate directory
    if not args.image_dir.exists():
        print(f"Error: Directory not found: {args.image_dir}")
        sys.exit(1)

    if not args.image_dir.is_dir():
        print(f"Error: Not a directory: {args.image_dir}")
        sys.exit(1)

    print("=" * 80)
    print("VISUAL EMBEDDING MODEL COMPARISON")
    print("=" * 80)
    print(f"\nImage directory: {args.image_dir}")
    print()

    # Load API key
    print("Loading OpenAI API key...")
    api_key = load_api_key(args.env)

    # Load images
    print("\nLoading images...")
    images = load_images(args.image_dir)

    if len(images) < 2:
        print(f"Error: Need at least 2 images, found {len(images)}")
        sys.exit(1)

    print(f"Loaded {len(images)} images:")
    for img_path, _ in images:
        print(f"  - {img_path.name}")

    # Run all models
    results = {}

    # Model 1: CLIP (local)
    embeddings1, elapsed1, dim1 = generate_clip_local_embeddings(images)
    results['CLIP (Local)'] = {
        'embeddings': embeddings1,
        'elapsed': elapsed1,
        'dim': dim1,
        'metrics': analyze_clustering_quality(embeddings1)
    }
    print_comparison_results('CLIP (Local)', embeddings1, dim1, elapsed1)

    # Model 2: OpenAI CLIP API
    embeddings2, elapsed2, dim2 = generate_openai_clip_embeddings(images, api_key)
    results['OpenAI CLIP API'] = {
        'embeddings': embeddings2,
        'elapsed': elapsed2,
        'dim': dim2,
        'metrics': analyze_clustering_quality(embeddings2)
    }
    print_comparison_results('OpenAI CLIP API', embeddings2, dim2, elapsed2)

    # Model 3: Nomic Vision (local)
    embeddings3, elapsed3, dim3 = generate_nomic_vision_embeddings(images)
    results['Nomic Vision (Local)'] = {
        'embeddings': embeddings3,
        'elapsed': elapsed3,
        'dim': dim3,
        'metrics': analyze_clustering_quality(embeddings3)
    }
    print_comparison_results('Nomic Vision (Local)', embeddings3, dim3, elapsed3)

    # Print comprehensive summary
    print_summary(results)


if __name__ == '__main__':
    main()
