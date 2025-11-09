"""
Visual Embedding generation using Nomic Embed Vision v1.5.

Research Findings (ADR-057, Nov 2025):
- Nomic Vision v1.5: 0.847 average top-3 similarity (27% better than CLIP)
- 768-dimensional embeddings (same space as Nomic Text)
- Excellent clustering quality for similar images
- Local inference via transformers library (not Ollama)
- Uses CLS token pooling strategy

See docs/research/vision-testing/ for comprehensive validation.

Architecture Decision (ADR-043):
- GPU acceleration when available (~1-2ms per image)
- CPU fallback when VRAM insufficient (<500MB free)
- Resource management to avoid VRAM contention
"""

import os
import logging
from typing import List, Optional
import numpy as np
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class VisualEmbeddingGenerator:
    """
    Generate visual embeddings using Nomic Embed Vision v1.5.

    Uses transformers library with CLS token pooling for 768-dim embeddings.
    Supports GPU acceleration with automatic CPU fallback.
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-vision-v1.5",
        device: Optional[str] = None
    ):
        """
        Initialize visual embedding generator.

        Args:
            model_name: Hugging Face model name (default: nomic-ai/nomic-embed-vision-v1.5)
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
        """
        from transformers import AutoModel, AutoProcessor
        import torch

        self.model_name = model_name

        # Auto-detect device if not specified
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device

        logger.info(f"Loading Nomic Vision model on {self.device}: {model_name}")

        try:
            # Load model and processor
            # Use device_map instead of .to() to handle meta tensors properly
            if self.device == 'cuda':
                self.model = AutoModel.from_pretrained(
                    model_name,
                    trust_remote_code=True,
                    device_map="auto"
                )
            else:
                # For CPU, use low_cpu_mem_usage to avoid meta tensor issues
                self.model = AutoModel.from_pretrained(
                    model_name,
                    trust_remote_code=True,
                    low_cpu_mem_usage=False
                )

            self.processor = AutoProcessor.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_fast=True
            )

            # Set model to eval mode
            self.model.eval()

            logger.info(
                f"Nomic Vision model loaded successfully on {self.device}. "
                f"Embedding dimension: 768"
            )

        except Exception as e:
            logger.error(f"Failed to load Nomic Vision model: {e}")
            raise

    def generate_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate 768-dimensional embedding for an image.

        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)

        Returns:
            numpy array of shape (768,) with normalized embedding

        Raises:
            ValueError: If image cannot be processed
        """
        import torch

        try:
            # Load image
            image = Image.open(BytesIO(image_bytes)).convert('RGB')

            # Process image
            inputs = self.processor(images=image, return_tensors='pt').to(self.device)

            # Generate embedding (CLS token pooling)
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use CLS token (first token) as embedding
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()

            # Normalize embedding (L2 normalization for cosine similarity)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate visual embedding: {e}")
            raise ValueError(f"Failed to process image: {e}")

    def generate_embeddings_batch(self, images: List[bytes]) -> np.ndarray:
        """
        Generate embeddings for multiple images in batch.

        Args:
            images: List of raw image bytes

        Returns:
            numpy array of shape (n_images, 768) with normalized embeddings

        Note: Batch processing is more efficient for multiple images.
        """
        import torch

        try:
            # Load all images
            pil_images = []
            for img_bytes in images:
                img = Image.open(BytesIO(img_bytes)).convert('RGB')
                pil_images.append(img)

            # Process batch
            inputs = self.processor(images=pil_images, return_tensors='pt').to(self.device)

            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use CLS token (first token) for each image
                embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()

            # Normalize each embedding
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.maximum(norms, 1e-10)  # Avoid division by zero

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise ValueError(f"Failed to process images: {e}")

    def get_embedding_dimension(self) -> int:
        """Get the dimension of generated embeddings (always 768 for Nomic Vision)"""
        return 768

    def get_model_name(self) -> str:
        """Get the model name"""
        return self.model_name

    def get_device(self) -> str:
        """Get the device being used (cuda or cpu)"""
        return self.device

    def check_vram_availability(self) -> dict:
        """
        Check VRAM availability for resource management (ADR-043).

        Returns:
            Dict with:
            - 'device': Current device
            - 'vram_available_mb': VRAM available in MB (0 if CPU)
            - 'vram_total_mb': Total VRAM in MB (0 if CPU)
            - 'can_run_on_gpu': Whether GPU has sufficient VRAM
        """
        import torch

        if self.device == 'cpu':
            return {
                'device': 'cpu',
                'vram_available_mb': 0,
                'vram_total_mb': 0,
                'can_run_on_gpu': False
            }

        try:
            if torch.cuda.is_available():
                vram_free = torch.cuda.mem_get_info()[0] / 1024**2  # Convert to MB
                vram_total = torch.cuda.mem_get_info()[1] / 1024**2
                can_run = vram_free > 500  # Need > 500MB free (ADR-043)

                return {
                    'device': 'cuda',
                    'vram_available_mb': int(vram_free),
                    'vram_total_mb': int(vram_total),
                    'can_run_on_gpu': can_run
                }
        except Exception as e:
            logger.warning(f"Failed to check VRAM: {e}")

        return {
            'device': self.device,
            'vram_available_mb': 0,
            'vram_total_mb': 0,
            'can_run_on_gpu': False
        }


# Global instance (lazy loaded)
_embedding_generator: Optional[VisualEmbeddingGenerator] = None


def get_visual_embedding_generator(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    force_reload: bool = False
) -> VisualEmbeddingGenerator:
    """
    Get or create global visual embedding generator instance.

    Args:
        model_name: Hugging Face model name (default from env or nomic-ai/nomic-embed-vision-v1.5)
        device: Device to use ('cuda', 'cpu', or None for auto-detect)
        force_reload: Force reload the model (useful for testing)

    Returns:
        VisualEmbeddingGenerator instance

    Examples:
        # Use default (Nomic Vision v1.5 on auto-detected device)
        generator = get_visual_embedding_generator()

        # Force CPU
        generator = get_visual_embedding_generator(device='cpu')

        # Force GPU
        generator = get_visual_embedding_generator(device='cuda')
    """
    global _embedding_generator

    # Use environment variable or default
    if model_name is None:
        model_name = os.getenv(
            "IMAGE_EMBEDDING_MODEL",
            "nomic-ai/nomic-embed-vision-v1.5"
        )

    # Return cached instance if compatible
    if _embedding_generator is not None and not force_reload:
        if (_embedding_generator.get_model_name() == model_name and
            (device is None or _embedding_generator.get_device() == device)):
            return _embedding_generator

    # Create new instance
    logger.info(f"Creating new visual embedding generator: {model_name}")
    _embedding_generator = VisualEmbeddingGenerator(
        model_name=model_name,
        device=device
    )

    return _embedding_generator


def generate_visual_embedding(image_bytes: bytes) -> List[float]:
    """
    Convenience function to generate single visual embedding.

    Args:
        image_bytes: Raw image bytes

    Returns:
        List of 768 floats (normalized embedding)

    Examples:
        # Generate embedding for an image
        with open('diagram.jpg', 'rb') as f:
            embedding = generate_visual_embedding(f.read())

        # embedding is 768-dimensional
        assert len(embedding) == 768
    """
    generator = get_visual_embedding_generator()
    embedding = generator.generate_embedding(image_bytes)
    return embedding.tolist()


def generate_visual_embeddings_batch(images: List[bytes]) -> List[List[float]]:
    """
    Convenience function to generate multiple visual embeddings.

    Args:
        images: List of raw image bytes

    Returns:
        List of embeddings (each 768 floats)

    Examples:
        # Generate embeddings for multiple images
        image_files = ['img1.jpg', 'img2.jpg', 'img3.jpg']
        images = [open(f, 'rb').read() for f in image_files]
        embeddings = generate_visual_embeddings_batch(images)

        # embeddings[i] is 768-dimensional
        assert all(len(emb) == 768 for emb in embeddings)
    """
    generator = get_visual_embedding_generator()
    embeddings = generator.generate_embeddings_batch(images)
    return embeddings.tolist()


def check_visual_embedding_health() -> dict:
    """
    Health check for visual embedding system.

    Returns:
        Dict with:
        - 'status': 'healthy' or 'unhealthy'
        - 'model': Model name
        - 'device': Current device
        - 'vram_info': VRAM status (if GPU)
        - 'error': Error message (if unhealthy)

    Examples:
        # Check if visual embeddings are working
        health = check_visual_embedding_health()
        if health['status'] == 'healthy':
            print(f"Visual embeddings ready on {health['device']}")
    """
    try:
        generator = get_visual_embedding_generator()

        # Test with tiny 1x1 black pixel PNG
        test_image = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        embedding = generator.generate_embedding(test_image)

        # Verify embedding
        if len(embedding) != 768:
            raise ValueError(f"Expected 768-dim embedding, got {len(embedding)}")

        # Check VRAM
        vram_info = generator.check_vram_availability()

        return {
            'status': 'healthy',
            'model': generator.get_model_name(),
            'device': generator.get_device(),
            'embedding_dimension': 768,
            'vram_info': vram_info
        }

    except Exception as e:
        logger.error(f"Visual embedding health check failed: {e}")
        return {
            'status': 'unhealthy',
            'model': 'unknown',
            'device': 'unknown',
            'error': str(e)
        }
