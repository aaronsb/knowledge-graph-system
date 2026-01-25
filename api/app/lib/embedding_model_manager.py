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
import asyncio
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

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5", precision: str = "float16", device: str = None):
        """
        Initialize embedding model manager.

        Args:
            model_name: HuggingFace model identifier
            precision: Embedding precision ('float16' or 'float32')
            device: Device to use ('cpu', 'cuda', 'mps') - if None, auto-detect
        """
        self.model_name = model_name
        self.precision = precision
        self.configured_device = device  # Device from config (may be None for auto)
        self.model = None
        self.dimensions = None

    def load_model(self):
        """
        Load the sentence-transformers model into memory.

        This is called once at startup. Model loading takes 1-2 seconds
        and allocates 300MB-1.3GB RAM depending on model size.

        Uses local cache-first strategy to avoid HuggingFace network checks on every startup.
        Falls back to downloading if model not cached.

        Device selection:
        - Automatically detects MPS (Apple Silicon), CUDA (NVIDIA), or CPU
        - MPS: Apple M1/M2/M3 and other ARM platforms with Metal support
        - CUDA: NVIDIA GPUs on Linux/Windows
        - CPU: Fallback when no GPU available
        """
        if self.model is not None:
            logger.warning(f"Model {self.model_name} already loaded, skipping")
            return

        # Determine device to use
        from .device_selector import get_best_device, log_device_selection

        if self.configured_device and self.configured_device != "auto":
            # Use device from config (respects user's choice to force CPU)
            device = self.configured_device
            logger.info(f"📍 Using configured device: {device}")
        else:
            # Auto-detect best available device
            device = get_best_device()
        log_device_selection(self.model_name)

        logger.info(f"📥 Loading embedding model: {self.model_name}")
        logger.info(f"   Precision: {self.precision}")
        logger.info(f"   Device: {device}")
        logger.info(f"   This may take 1-2 seconds...")

        try:
            from sentence_transformers import SentenceTransformer

            # TODO: Pin specific model version/revision for consistency and reproducibility
            # Example: self.model_name = "nomic-ai/nomic-embed-text-v1.5@abc123"

            # Try loading from local cache first (fast, no network)
            # If not cached, download ONCE to persistent volume
            # trust_remote_code=True required for models like nomic-embed-text that have custom code
            try:
                logger.info(f"   Attempting to load from local cache...")
                self.model = SentenceTransformer(
                    self.model_name,
                    trust_remote_code=True,
                    device=device,  # Use detected device (mps/cuda/cpu)
                    local_files_only=True  # Try cache first
                )
                logger.info(f"   ✓ Loaded from local cache")

            except (OSError, ValueError) as cache_error:
                # Model not in cache - download to persistent volume (one-time operation)
                logger.warning(f"   Model not in cache, downloading from HuggingFace...")
                logger.warning(f"   This is a one-time download (~200-500MB)")
                logger.warning(f"   Model will be cached in persistent volume for future startups")

                self.model = SentenceTransformer(
                    self.model_name,
                    trust_remote_code=True,
                    device=device  # Use detected device (mps/cuda/cpu)
                    # local_files_only=False (default) - will download
                )
                logger.info(f"   ✓ Downloaded and cached to persistent volume")

            self.dimensions = self.model.get_sentence_embedding_dimension()

            logger.info(f"✅ Embedding model loaded: {self.model_name}")
            logger.info(f"   Dimensions: {self.dimensions}")
            logger.info(f"   Device: {device}")
            logger.info(f"   Max sequence length: {self.model.max_seq_length}")

        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            logger.error(f"   This indicates a network or configuration issue")
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
            embedding = self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)

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


async def init_embedding_model_manager() -> Optional[EmbeddingModelManager]:
    """
    Initialize the global embedding model manager (called at startup).

    Loads configuration from database (kg_api.embedding_config table).
    Only loads if provider='local' is configured. For OpenAI, returns None.

    Database-first configuration (ADR-039):
    - No environment variable fallback
    - Config must be in database
    - Use admin API to configure: POST /admin/embedding/config

    Returns:
        EmbeddingModelManager instance if local provider configured, None otherwise
    """
    global _model_manager

    # Load configuration from database (ADR-039: database-first, no .env fallback)
    from .embedding_config import load_active_embedding_config

    config = await asyncio.to_thread(load_active_embedding_config)

    if config is None:
        logger.info("⚠️  No embedding config in database")
        logger.info("   Use: POST /admin/embedding/config to configure")
        logger.info("   Defaulting to OpenAI embeddings via AI provider")
        return None

    if config['provider'] != 'local':
        logger.info(f"📍 Embedding provider: {config['provider']} (no local model needed)")
        return None

    # Extract local model configuration
    model_name = config.get('model_name')
    if not model_name:
        logger.error("❌ Local embedding provider configured but no model_name specified")
        logger.error("   Use: POST /admin/embedding/config with model_name parameter")
        return None

    precision = config.get('precision', 'float16')
    device = config.get('device', 'cpu')  # Default to CPU for safety

    logger.info(f"📍 Embedding provider: local")
    logger.info(f"   Model: {model_name}")
    logger.info(f"   Precision: {precision}")
    logger.info(f"   Device: {device}")
    logger.info(f"   Dimensions: {config.get('embedding_dimensions', 'auto-detect')}")
    logger.info(f"   Resource limits: {config.get('max_memory_mb')}MB RAM, {config.get('num_threads')} threads")
    logger.info(f"   Initializing model manager...")

    try:
        # Create and load model manager
        _model_manager = EmbeddingModelManager(model_name=model_name, precision=precision, device=device)
        _model_manager.load_model()

        # Verify dimensions match config (if specified)
        actual_dims = _model_manager.get_dimensions()
        expected_dims = config.get('embedding_dimensions')
        if expected_dims and actual_dims != expected_dims:
            logger.warning(f"⚠️  Dimension mismatch: model has {actual_dims} dims, config specifies {expected_dims}")
            logger.warning(f"   Consider updating config to match model dimensions")

        logger.info(f"✅ Local embedding model manager initialized")
        return _model_manager

    except Exception as e:
        logger.error(f"❌ Failed to initialize embedding model manager: {e}")
        logger.error(f"   Check model_name in database config or switch to provider='openai'")
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


async def reload_embedding_model_manager() -> Optional[EmbeddingModelManager]:
    """
    Hot reload embedding model manager with new configuration from database.

    This implements zero-downtime configuration updates:
    1. Load new config from database
    2. Create and load new model in parallel (old model still serves requests)
    3. Atomic swap to new model
    4. Old model garbage collected when no longer referenced

    For provider switches (local ↔ openai):
    - local → openai: New manager set to None, old model unloaded
    - openai → local: New model loaded, replaces None

    Returns:
        New EmbeddingModelManager instance if local provider, None for openai

    Raises:
        RuntimeError: If configuration invalid or model loading fails
    """
    global _model_manager

    logger.info("🔄 Hot reloading embedding model manager...")

    # Load new configuration from database
    from .embedding_config import load_active_embedding_config

    config = await asyncio.to_thread(load_active_embedding_config)

    if config is None:
        logger.warning("⚠️  No embedding config in database after reload attempt")
        logger.info("   Keeping existing configuration")
        return _model_manager

    provider = config['provider']
    logger.info(f"📍 New provider: {provider}")

    # If switching to non-local provider, unload model
    if provider != 'local':
        old_manager = _model_manager
        _model_manager = None
        logger.info(f"✅ Switched to {provider} embeddings (local model unloaded)")
        return None

    # Local provider - load or reload model
    model_name = config.get('model_name')
    if not model_name:
        raise RuntimeError(
            "Local embedding provider configured but no model_name specified. "
            "Update config via: POST /admin/embedding/config"
        )

    precision = config.get('precision', 'float16')
    device = config.get('device', 'cpu')  # Default to CPU for safety

    logger.info(f"📥 Loading new model: {model_name}")
    logger.info(f"   Precision: {precision}")
    logger.info(f"   Device: {device}")

    try:
        # Create new manager and load model (in parallel with old model serving requests)
        new_manager = EmbeddingModelManager(model_name=model_name, precision=precision, device=device)
        new_manager.load_model()

        # Verify dimensions
        actual_dims = new_manager.get_dimensions()
        expected_dims = config.get('embedding_dimensions')
        if expected_dims and actual_dims != expected_dims:
            logger.warning(f"⚠️  Dimension mismatch: model has {actual_dims} dims, config specifies {expected_dims}")

        # Atomic swap - old model will be garbage collected
        old_manager = _model_manager
        _model_manager = new_manager

        if old_manager:
            logger.info(f"✅ Hot reload complete: {old_manager.get_model_name()} → {model_name}")
        else:
            logger.info(f"✅ Model loaded: {model_name}")

        return _model_manager

    except Exception as e:
        logger.error(f"❌ Hot reload failed: {e}")
        logger.error(f"   Keeping existing model configuration")
        raise RuntimeError(f"Failed to reload embedding model: {e}")
