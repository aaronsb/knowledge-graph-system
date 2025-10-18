"""
Embedding Model Manager - Singleton pattern for local embedding models.

Manages heavy sentence-transformers models that should be loaded once
at startup and reused across all requests.

Usage:
    # In main.py startup event
    await init_embedding_model_manager()

    # In LocalEmbeddingProvider
    manager = get_embedding_model_manager()
    embedding = manager.generate_embedding("some text")
"""

import os
import logging
from typing import Optional, List
import numpy as np

logger = logging.getLogger(__name__)

# Global singleton instance
_model_manager: Optional['EmbeddingModelManager'] = None


class EmbeddingModelManager:
    """
    Singleton manager for local embedding models.

    Loads heavy sentence-transformers models once and reuses them
    across all requests to avoid repeated model loading overhead.
    """

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5", precision: str = "float16"):
        """
        Initialize embedding model manager.

        Args:
            model_name: HuggingFace model identifier
            precision: Embedding precision ('float16' or 'float32')
        """
        self.model_name = model_name
        self.precision = precision
        self.model = None
        self.dimensions = None

    def load_model(self):
        """
        Load the sentence-transformers model into memory.

        This is called once at startup. Model loading takes 1-2 seconds
        and allocates 300MB-1.3GB RAM depending on model size.
        """
        if self.model is not None:
            logger.warning(f"Model {self.model_name} already loaded, skipping")
            return

        logger.info(f"📥 Loading embedding model: {self.model_name}")
        logger.info(f"   Precision: {self.precision}")
        logger.info(f"   This may take 1-2 seconds...")

        try:
            from sentence_transformers import SentenceTransformer

            # Load model (downloads if not cached)
            self.model = SentenceTransformer(self.model_name)
            self.dimensions = self.model.get_sentence_embedding_dimension()

            logger.info(f"✅ Embedding model loaded: {self.model_name}")
            logger.info(f"   Dimensions: {self.dimensions}")
            logger.info(f"   Max sequence length: {self.model.max_seq_length}")

        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embedding model {self.model_name}: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using the loaded model.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)

        Raises:
            RuntimeError: If model not loaded
        """
        if self.model is None:
            raise RuntimeError(
                "Embedding model not loaded. Call load_model() first or "
                "ensure init_embedding_model_manager() was called at startup."
            )

        try:
            # Generate embedding with normalization (for cosine similarity)
            embedding = self.model.encode(text, normalize_embeddings=True)

            # Apply precision conversion
            if self.precision == "float16":
                embedding = embedding.astype(np.float16)

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")

    def get_dimensions(self) -> int:
        """
        Get embedding dimensions for this model.

        Returns:
            Number of dimensions

        Raises:
            RuntimeError: If model not loaded
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        return self.dimensions

    def get_model_name(self) -> str:
        """Get the model name"""
        return self.model_name

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None


async def init_embedding_model_manager(
    model_name: Optional[str] = None,
    precision: Optional[str] = None
) -> Optional[EmbeddingModelManager]:
    """
    Initialize the global embedding model manager (called at startup).

    Only loads if EMBEDDING_PROVIDER=local is configured. For OpenAI,
    returns None (no local model needed).

    Args:
        model_name: Model to load (default: from EMBEDDING_MODEL env var)
        precision: Embedding precision (default: from EMBEDDING_PRECISION env var)

    Returns:
        EmbeddingModelManager instance if local provider configured, None otherwise
    """
    global _model_manager

    # Check if local embeddings are configured
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider != "local":
        logger.info(f"📍 Embedding provider: {embedding_provider} (no local model needed)")
        return None

    # Get configuration from environment
    model_name = model_name or os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
    precision = precision or os.getenv("EMBEDDING_PRECISION", "float16")

    logger.info(f"📍 Embedding provider: local")
    logger.info(f"   Initializing model manager...")

    try:
        # Create and load model manager
        _model_manager = EmbeddingModelManager(model_name=model_name, precision=precision)
        _model_manager.load_model()

        logger.info(f"✅ Local embedding model manager initialized")
        return _model_manager

    except Exception as e:
        logger.error(f"❌ Failed to initialize embedding model manager: {e}")
        logger.error(f"   Consider switching to EMBEDDING_PROVIDER=openai in .env")
        raise


def get_embedding_model_manager() -> EmbeddingModelManager:
    """
    Get the global embedding model manager instance.

    Returns:
        EmbeddingModelManager singleton

    Raises:
        RuntimeError: If manager not initialized (call init_embedding_model_manager first)
    """
    global _model_manager

    if _model_manager is None:
        raise RuntimeError(
            "Embedding model manager not initialized. "
            "This should be called at startup via init_embedding_model_manager()"
        )

    return _model_manager
