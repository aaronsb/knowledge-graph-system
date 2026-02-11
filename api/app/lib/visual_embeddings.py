"""
Visual Embedding generation — profile-driven.

Reads image embedding configuration from the active embedding profile
(kg_api.embedding_profile table, migration 055).

For non-multimodal profiles: uses image_* fields.
For multimodal profiles: uses text_* fields (same model handles both).

Supports loaders:
- transformers: AutoModel + AutoProcessor (Nomic Vision, SigLIP)
- sentence-transformers: SentenceTransformer (less common for vision)
- api: external API (no local model)
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
    Generate visual embeddings using the active profile's image model.

    Uses transformers library with CLS token pooling.
    Supports GPU acceleration with automatic CPU fallback.
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-vision-v1.5",
        device: Optional[str] = None,
        loader: str = "transformers",
        model_revision: Optional[str] = None,
        trust_remote_code: bool = True,
        dimensions: Optional[int] = None
    ):
        """
        Initialize visual embedding generator.

        Args:
            model_name: Hugging Face model name
            device: Device to use ('mps', 'cuda', 'cpu', or None for auto-detect)
            loader: How to load the model ('transformers', 'sentence-transformers', 'api')
            model_revision: HuggingFace commit hash / version tag
            trust_remote_code: Whether to trust remote code
            dimensions: Expected embedding dimensions (for validation)
        """
        from .device_selector import get_best_device, log_device_selection

        self.model_name = model_name
        self.loader = loader
        self.model_revision = model_revision
        self.trust_remote_code = trust_remote_code
        self._expected_dimensions = dimensions
        self.model = None
        self.processor = None
        self._dimensions = dimensions

        # Auto-detect device if not specified
        if device is None:
            device = get_best_device()
        self.device = device

        log_device_selection(model_name)

        if loader == 'api':
            logger.info(f"Visual embedding loader=api for {model_name}, no local model to load")
            return

        self._load_model()

    def _load_model(self):
        """Load the vision model based on loader type."""
        if self.loader == 'transformers':
            self._load_transformers()
        elif self.loader == 'sentence-transformers':
            self._load_sentence_transformers()
        else:
            raise RuntimeError(f"Unknown visual embedding loader: {self.loader}")

    def _load_transformers(self):
        """Load model via transformers AutoModel + AutoProcessor."""
        from transformers import AutoModel, AutoProcessor

        load_kwargs = {
            "trust_remote_code": self.trust_remote_code,
        }
        if self.model_revision:
            load_kwargs["revision"] = self.model_revision

        try:
            # Try loading from local cache first
            try:
                if self.device in ('cuda', 'mps'):
                    self.model = AutoModel.from_pretrained(
                        self.model_name,
                        device_map="auto",
                        local_files_only=True,
                        **load_kwargs
                    )
                else:
                    self.model = AutoModel.from_pretrained(
                        self.model_name,
                        low_cpu_mem_usage=False,
                        local_files_only=True,
                        **load_kwargs
                    )

                processor_kwargs = {"trust_remote_code": self.trust_remote_code, "use_fast": True}
                if self.model_revision:
                    processor_kwargs["revision"] = self.model_revision
                self.processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    **processor_kwargs
                )
                logger.info(f"  Loaded vision model from cache")

            except (OSError, ValueError):
                logger.warning(f"  Vision model not in cache, downloading...")

                if self.device in ('cuda', 'mps'):
                    self.model = AutoModel.from_pretrained(
                        self.model_name,
                        device_map="auto",
                        **load_kwargs
                    )
                else:
                    self.model = AutoModel.from_pretrained(
                        self.model_name,
                        low_cpu_mem_usage=False,
                        **load_kwargs
                    )

                processor_kwargs = {"trust_remote_code": self.trust_remote_code, "use_fast": True}
                if self.model_revision:
                    processor_kwargs["revision"] = self.model_revision
                self.processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    **processor_kwargs
                )
                logger.info(f"  Downloaded and cached vision model")

            self.model.eval()
            logger.info(
                f"Vision model loaded: {self.model_name} on {self.device}"
            )

        except Exception as e:
            logger.error(f"Failed to load vision model: {e}")
            raise

    def _load_sentence_transformers(self):
        """Load model via sentence-transformers (less common for vision)."""
        from sentence_transformers import SentenceTransformer

        load_kwargs = {
            "trust_remote_code": self.trust_remote_code,
            "device": self.device,
        }
        if self.model_revision:
            load_kwargs["revision"] = self.model_revision

        try:
            try:
                self.model = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                    **load_kwargs
                )
            except (OSError, ValueError):
                self.model = SentenceTransformer(
                    self.model_name,
                    **load_kwargs
                )

            self._dimensions = self.model.get_sentence_embedding_dimension()
            logger.info(f"Vision model loaded (sentence-transformers): {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to load vision model: {e}")
            raise

    def generate_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate embedding for an image.

        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)

        Returns:
            numpy array with normalized embedding
        """
        import torch

        try:
            image = Image.open(BytesIO(image_bytes)).convert('RGB')

            if self.loader == 'transformers':
                inputs = self.processor(images=image, return_tensors='pt').to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    # CLS token (first token) as embedding
                    embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()

                # L2 normalize
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                return embedding

            elif self.loader == 'sentence-transformers':
                # sentence-transformers can encode images directly
                embedding = self.model.encode(image, normalize_embeddings=True, show_progress_bar=False)
                return embedding

            else:
                raise ValueError(f"Cannot generate embedding with loader={self.loader}")

        except Exception as e:
            logger.error(f"Failed to generate visual embedding: {e}")
            raise ValueError(f"Failed to process image: {e}")

    def generate_embeddings_batch(self, images: List[bytes]) -> np.ndarray:
        """
        Generate embeddings for multiple images in batch.

        Args:
            images: List of raw image bytes

        Returns:
            numpy array of shape (n_images, dims) with normalized embeddings
        """
        import torch

        try:
            pil_images = [
                Image.open(BytesIO(img_bytes)).convert('RGB')
                for img_bytes in images
            ]

            if self.loader == 'transformers':
                inputs = self.processor(images=pil_images, return_tensors='pt').to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()

                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / np.maximum(norms, 1e-10)
                return embeddings

            elif self.loader == 'sentence-transformers':
                embeddings = self.model.encode(pil_images, normalize_embeddings=True, show_progress_bar=False)
                return embeddings

            else:
                raise ValueError(f"Cannot batch embed with loader={self.loader}")

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise ValueError(f"Failed to process images: {e}")

    def get_embedding_dimension(self) -> int:
        """Get the dimension of generated embeddings."""
        if self._dimensions:
            return self._dimensions
        if self._expected_dimensions:
            return self._expected_dimensions
        return 768  # Fallback for known models

    def get_model_name(self) -> str:
        """Get the model name"""
        return self.model_name

    def get_device(self) -> str:
        """Get the device being used"""
        return self.device

    def check_vram_availability(self) -> dict:
        """Check VRAM availability for resource management."""
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
                vram_free = torch.cuda.mem_get_info()[0] / 1024**2
                vram_total = torch.cuda.mem_get_info()[1] / 1024**2
                return {
                    'device': 'cuda',
                    'vram_available_mb': int(vram_free),
                    'vram_total_mb': int(vram_total),
                    'can_run_on_gpu': vram_free > 500
                }
        except Exception as e:
            logger.warning(f"Failed to check VRAM: {e}")

        return {
            'device': self.device,
            'vram_available_mb': 0,
            'vram_total_mb': 0,
            'can_run_on_gpu': False
        }


# Global instance
_embedding_generator: Optional[VisualEmbeddingGenerator] = None


def _get_image_config_from_profile(config: dict) -> dict:
    """
    Extract image model configuration from an embedding profile.

    For multimodal profiles, uses text_* fields.
    For non-multimodal profiles, uses image_* fields.
    """
    if config.get('multimodal'):
        return {
            'model_name': config['text_model_name'],
            'loader': config.get('text_loader', 'transformers'),
            'revision': config.get('text_revision'),
            'trust_remote_code': config.get('text_trust_remote_code', False),
            'dimensions': config.get('text_dimensions'),
            'device': config.get('device'),
        }
    elif config.get('image_model_name'):
        return {
            'model_name': config['image_model_name'],
            'loader': config.get('image_loader', 'transformers'),
            'revision': config.get('image_revision'),
            'trust_remote_code': config.get('image_trust_remote_code', True),
            'dimensions': config.get('image_dimensions'),
            'device': config.get('device'),
        }
    else:
        # Text-only profile — no image model
        return None


async def init_visual_embedding_generator() -> Optional[VisualEmbeddingGenerator]:
    """
    Initialize the global visual embedding generator at startup.

    Reads from the active embedding profile's image configuration.
    For text-only profiles, returns None (no image embedding support).

    Returns:
        VisualEmbeddingGenerator instance if image model configured, None otherwise.
    """
    global _embedding_generator
    import asyncio
    from .embedding_config import load_active_embedding_config

    config = await asyncio.to_thread(load_active_embedding_config)

    if config is None:
        logger.info("No embedding profile — visual embeddings disabled")
        return None

    image_config = _get_image_config_from_profile(config)

    if image_config is None:
        logger.info("Text-only profile — visual embeddings disabled")
        return None

    if image_config['loader'] == 'api':
        logger.info(f"Image loader=api for {image_config['model_name']}, no local model to load")
        return None

    logger.info(f"Initializing visual embedding generator: {image_config['model_name']}")

    try:
        _embedding_generator = VisualEmbeddingGenerator(
            model_name=image_config['model_name'],
            device=image_config.get('device'),
            loader=image_config['loader'],
            model_revision=image_config.get('revision'),
            trust_remote_code=image_config.get('trust_remote_code', True),
            dimensions=image_config.get('dimensions'),
        )
        logger.info(f"Visual embedding generator initialized: {image_config['model_name']}")
        return _embedding_generator

    except Exception as e:
        logger.error(f"Failed to initialize visual embedding generator: {e}")
        raise


def get_visual_embedding_generator(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    force_reload: bool = False
) -> VisualEmbeddingGenerator:
    """
    Get or create global visual embedding generator instance.

    If no instance exists and no model_name given, reads from active profile.

    Args:
        model_name: Explicit model name override
        device: Device override
        force_reload: Force reload the model

    Returns:
        VisualEmbeddingGenerator instance
    """
    global _embedding_generator

    # Return cached instance if compatible
    if _embedding_generator is not None and not force_reload:
        if (model_name is None or _embedding_generator.get_model_name() == model_name) and \
           (device is None or _embedding_generator.get_device() == device):
            return _embedding_generator

    # If explicit model_name, use it directly
    if model_name:
        _embedding_generator = VisualEmbeddingGenerator(
            model_name=model_name,
            device=device
        )
        return _embedding_generator

    # Otherwise, read from active profile
    from .embedding_config import load_active_embedding_config
    config = load_active_embedding_config()

    if config:
        image_config = _get_image_config_from_profile(config)
        if image_config and image_config['loader'] != 'api':
            _embedding_generator = VisualEmbeddingGenerator(
                model_name=image_config['model_name'],
                device=image_config.get('device') or device,
                loader=image_config['loader'],
                model_revision=image_config.get('revision'),
                trust_remote_code=image_config.get('trust_remote_code', True),
                dimensions=image_config.get('dimensions'),
            )
            return _embedding_generator

    # Fallback: use default model name from env or hardcoded default
    fallback_model = os.getenv("IMAGE_EMBEDDING_MODEL", "nomic-ai/nomic-embed-vision-v1.5")
    logger.info(f"Creating visual embedding generator with fallback: {fallback_model}")
    _embedding_generator = VisualEmbeddingGenerator(
        model_name=fallback_model,
        device=device
    )
    return _embedding_generator


def generate_visual_embedding(image_bytes: bytes) -> List[float]:
    """
    Convenience function to generate single visual embedding.

    Args:
        image_bytes: Raw image bytes

    Returns:
        List of floats (normalized embedding)
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
        List of embeddings (each a list of floats)
    """
    generator = get_visual_embedding_generator()
    embeddings = generator.generate_embeddings_batch(images)
    return embeddings.tolist()


def check_visual_embedding_health() -> dict:
    """
    Health check for visual embedding system.

    Returns:
        Dict with status, model, device, and error info.
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
        dim = len(embedding)

        vram_info = generator.check_vram_availability()

        return {
            'status': 'healthy',
            'model': generator.get_model_name(),
            'device': generator.get_device(),
            'embedding_dimension': dim,
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
