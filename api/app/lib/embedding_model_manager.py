"""
Embedding Model Manager - Singleton pattern for local embedding models.

Manages heavy sentence-transformers and transformers models that should be loaded
once at startup and reused across all requests.

Supports multiple loaders (ADR-039 + migration 055):
- sentence-transformers: SentenceTransformer (nomic, bge, etc.)
- transformers: AutoModel + AutoTokenizer (SigLIP text, custom models)
- api: No local model needed (OpenAI, etc.)

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

    Loads heavy models once and reuses them across all requests.
    Dispatches loading and inference based on the loader type.
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        precision: str = "float16",
        device: str = None,
        loader: str = "sentence-transformers",
        model_revision: Optional[str] = None,
        trust_remote_code: bool = False
    ):
        """
        Initialize embedding model manager.

        Args:
            model_name: HuggingFace model identifier
            precision: Embedding precision ('float16' or 'float32')
            device: Device to use ('cpu', 'cuda', 'mps') - if None, auto-detect
            loader: How to load the model: 'sentence-transformers', 'transformers', or 'api'
            model_revision: HuggingFace commit hash / version tag
            trust_remote_code: Whether to trust remote code in HuggingFace models
        """
        self.model_name = model_name
        self.precision = precision
        self.configured_device = device
        self.loader = loader
        self.model_revision = model_revision
        self.trust_remote_code = trust_remote_code
        self.model = None
        self.tokenizer = None  # Used by transformers loader
        self.dimensions = None

    def load_model(self):
        """
        Load the embedding model into memory.

        Dispatches to the appropriate loader:
        - sentence-transformers: SentenceTransformer
        - transformers: AutoModel + AutoTokenizer
        - api: no-op (external API handles inference)
        """
        if self.model is not None:
            logger.warning(f"Model {self.model_name} already loaded, skipping")
            return

        if self.loader == 'api':
            logger.info(f"Loader=api for {self.model_name}, no local model to load")
            return

        # Determine device
        from .device_selector import get_best_device, log_device_selection

        if self.configured_device and self.configured_device != "auto":
            device = self.configured_device
        else:
            device = get_best_device()
        log_device_selection(self.model_name)

        logger.info(f"Loading embedding model: {self.model_name}")
        logger.info(f"  Loader: {self.loader}")
        logger.info(f"  Precision: {self.precision}")
        logger.info(f"  Device: {device}")
        if self.model_revision:
            logger.info(f"  Revision: {self.model_revision}")

        self._device = device

        if self.loader == 'sentence-transformers':
            self._load_sentence_transformers(device)
        elif self.loader == 'transformers':
            self._load_transformers(device)
        else:
            raise RuntimeError(f"Unknown loader: {self.loader}")

    def _load_sentence_transformers(self, device: str):
        """Load model via sentence-transformers library."""
        try:
            from sentence_transformers import SentenceTransformer

            load_kwargs = {
                "trust_remote_code": self.trust_remote_code,
                "device": device,
            }
            if self.model_revision:
                load_kwargs["revision"] = self.model_revision

            # Try local cache first
            try:
                self.model = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                    **load_kwargs
                )
                logger.info("  Loaded from local cache")
            except (OSError, ValueError):
                logger.warning("  Model not in cache, downloading...")
                self.model = SentenceTransformer(
                    self.model_name,
                    **load_kwargs
                )
                logger.info("  Downloaded and cached")

            self.dimensions = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded: {self.model_name} ({self.dimensions} dims, {device})")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embedding model {self.model_name}: {e}")

    def _resolve_text_model_class(self):
        """Resolve the correct model class for text embedding.

        Multimodal models (SigLIP, CLIP) need their text-tower subclass
        rather than AutoModel, which loads the full vision+text model and
        requires pixel_values in forward().
        """
        from transformers import AutoConfig, AutoModel

        config = AutoConfig.from_pretrained(
            self.model_name,
            trust_remote_code=self.trust_remote_code,
            revision=self.model_revision,
        )
        model_type = getattr(config, 'model_type', '')

        # Map multimodal model types to their text-tower classes
        text_tower_map = {
            'siglip': 'SiglipTextModel',
            'clip': 'CLIPTextModel',
        }

        if model_type in text_tower_map:
            import transformers
            cls_name = text_tower_map[model_type]
            cls = getattr(transformers, cls_name, None)
            if cls:
                logger.info(f"  Multimodal model ({model_type}) — loading text tower: {cls_name}")
                return cls
            logger.warning(f"  {cls_name} not found in transformers, falling back to AutoModel")

        return AutoModel

    def _load_transformers(self, device: str):
        """Load model via transformers AutoModel + AutoTokenizer."""
        try:
            from transformers import AutoTokenizer
            import torch

            load_kwargs = {
                "trust_remote_code": self.trust_remote_code,
            }
            if self.model_revision:
                load_kwargs["revision"] = self.model_revision

            model_cls = self._resolve_text_model_class()

            # Try local cache first
            try:
                self.model = model_cls.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    **load_kwargs
                )
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    trust_remote_code=self.trust_remote_code,
                )
                logger.info("  Loaded from local cache")
            except (OSError, ValueError):
                logger.warning("  Model not in cache, downloading...")
                self.model = model_cls.from_pretrained(
                    self.model_name,
                    **load_kwargs
                )
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    trust_remote_code=self.trust_remote_code,
                )
                logger.info("  Downloaded and cached")

            # Move to device
            if device in ('cuda', 'mps'):
                self.model = self.model.to(device)
            self.model.eval()

            # Detect dimensions via a dummy forward pass
            dummy_input = self.tokenizer("hello", return_tensors="pt", padding=True, truncation=True)
            if device in ('cuda', 'mps'):
                dummy_input = {k: v.to(device) for k, v in dummy_input.items()}
            with torch.no_grad():
                outputs = self.model(**dummy_input)
                embedding = self._extract_text_embedding(outputs)
                self.dimensions = embedding.shape[-1]

            logger.info(f"Embedding model loaded: {self.model_name} ({self.dimensions} dims, {device})")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embedding model {self.model_name}: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using the loaded model.

        Dispatches based on loader type:
        - sentence-transformers: model.encode()
        - transformers: tokenize -> forward -> CLS pool -> normalize
        """
        if self.model is None:
            raise RuntimeError(
                "Embedding model not loaded. Call load_model() first."
            )

        if self.loader == 'sentence-transformers':
            return self._embed_sentence_transformers(text)
        elif self.loader == 'transformers':
            return self._embed_transformers(text)
        else:
            raise RuntimeError(f"Cannot generate embedding with loader={self.loader}")

    def _extract_text_embedding(self, outputs):
        """Extract embedding from model outputs, handling different architectures.

        Tries in order: pooler_output, last_hidden_state CLS token, text_embeds.
        Works for BERT-family, SigLIP, and other transformer variants.
        """
        # Log available output keys for debugging new architectures
        if hasattr(outputs, 'keys'):
            logger.debug(f"Model output keys: {list(outputs.keys())}")
        # pooler_output: BERT, SigLIP text tower
        if hasattr(outputs, 'pooler_output') and outputs.pooler_output is not None:
            return outputs.pooler_output.squeeze()
        # last_hidden_state CLS: generic fallback
        if hasattr(outputs, 'last_hidden_state') and outputs.last_hidden_state is not None:
            return outputs.last_hidden_state[:, 0, :].squeeze()
        # text_embeds: CLIP-family
        if hasattr(outputs, 'text_embeds') and outputs.text_embeds is not None:
            return outputs.text_embeds.squeeze()
        # Report what we actually got
        available = {k for k in (outputs.keys() if hasattr(outputs, 'keys') else [])
                     if getattr(outputs, k, None) is not None}
        raise RuntimeError(
            f"Cannot extract text embedding — non-None output keys: {available}"
        )

    def _embed_sentence_transformers(self, text: str) -> List[float]:
        """Generate embedding via sentence-transformers encode()."""
        try:
            embedding = self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)
            if self.precision == "float16":
                embedding = embedding.astype(np.float16)
            return embedding.tolist()
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")

    def _embed_transformers(self, text: str) -> List[float]:
        """Generate embedding via transformers tokenize -> forward -> CLS pool -> normalize."""
        import torch

        try:
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            device = getattr(self, '_device', 'cpu')
            if device in ('cuda', 'mps'):
                inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                embedding = self._extract_text_embedding(outputs).cpu().numpy()

            # L2 normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            if self.precision == "float16":
                embedding = embedding.astype(np.float16)

            return embedding.tolist()
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")

    def get_dimensions(self) -> int:
        """Get embedding dimensions for this model."""
        if self.dimensions is None:
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

    Loads configuration from database (kg_api.embedding_profile table).
    Only loads if text_provider='local' is configured. For API providers, returns None.

    Returns:
        EmbeddingModelManager instance if local provider configured, None otherwise
    """
    global _model_manager

    from .embedding_config import load_active_embedding_config

    config = await asyncio.to_thread(load_active_embedding_config)

    if config is None:
        logger.info("No embedding profile in database")
        return None

    provider = config.get('text_provider', config.get('provider'))
    if provider != 'local':
        logger.info(f"Embedding provider: {provider} (no local model needed)")
        return None

    model_name = config.get('text_model_name', config.get('model_name'))
    if not model_name:
        logger.error("Local embedding provider configured but no model_name specified")
        return None

    precision = config.get('text_precision', config.get('precision', 'float16'))
    device = config.get('device', 'cpu')
    loader = config.get('text_loader', 'sentence-transformers')
    revision = config.get('text_revision')
    trust_remote_code = config.get('text_trust_remote_code', False)

    logger.info(f"Embedding provider: local")
    logger.info(f"  Model: {model_name}")
    logger.info(f"  Loader: {loader}")
    logger.info(f"  Precision: {precision}")
    logger.info(f"  Device: {device}")
    if revision:
        logger.info(f"  Revision: {revision}")

    try:
        _model_manager = EmbeddingModelManager(
            model_name=model_name,
            precision=precision,
            device=device,
            loader=loader,
            model_revision=revision,
            trust_remote_code=trust_remote_code
        )
        _model_manager.load_model()

        # Verify dimensions match config
        actual_dims = _model_manager.get_dimensions()
        expected_dims = config.get('text_dimensions', config.get('embedding_dimensions'))
        if expected_dims and actual_dims != expected_dims:
            logger.warning(f"Dimension mismatch: model has {actual_dims} dims, config specifies {expected_dims}")

        logger.info(f"Local embedding model manager initialized")
        return _model_manager

    except Exception as e:
        logger.error(f"Failed to initialize embedding model manager: {e}")
        raise


def get_embedding_model_manager() -> EmbeddingModelManager:
    """
    Get the global embedding model manager instance.

    Raises:
        RuntimeError: If manager not initialized
    """
    global _model_manager

    if _model_manager is None:
        raise RuntimeError(
            "Embedding model manager not initialized. "
            "Call init_embedding_model_manager() at startup."
        )

    return _model_manager


async def reload_embedding_model_manager() -> Optional[EmbeddingModelManager]:
    """
    Hot reload embedding model manager with new configuration from database.

    Implements zero-downtime configuration updates:
    1. Load new config from database
    2. Create and load new model in parallel (old model still serves)
    3. Atomic swap to new model
    4. Old model garbage collected
    """
    global _model_manager

    logger.info("Hot reloading embedding model manager...")

    from .embedding_config import load_active_embedding_config

    config = await asyncio.to_thread(load_active_embedding_config)

    if config is None:
        logger.warning("No embedding profile in database after reload attempt")
        return _model_manager

    provider = config.get('text_provider', config.get('provider'))

    # If switching to non-local provider, unload model
    if provider != 'local':
        _model_manager = None
        logger.info(f"Switched to {provider} embeddings (local model unloaded)")
        return None

    model_name = config.get('text_model_name', config.get('model_name'))
    if not model_name:
        raise RuntimeError("Local embedding provider configured but no model_name specified")

    precision = config.get('text_precision', config.get('precision', 'float16'))
    device = config.get('device', 'cpu')
    loader = config.get('text_loader', 'sentence-transformers')
    revision = config.get('text_revision')
    trust_remote_code = config.get('text_trust_remote_code', False)

    logger.info(f"Loading new model: {model_name} (loader={loader})")

    try:
        new_manager = EmbeddingModelManager(
            model_name=model_name,
            precision=precision,
            device=device,
            loader=loader,
            model_revision=revision,
            trust_remote_code=trust_remote_code
        )
        new_manager.load_model()

        # Verify dimensions
        actual_dims = new_manager.get_dimensions()
        expected_dims = config.get('text_dimensions', config.get('embedding_dimensions'))
        if expected_dims and actual_dims != expected_dims:
            logger.warning(f"Dimension mismatch: model has {actual_dims} dims, config specifies {expected_dims}")

        # Atomic swap
        old_manager = _model_manager
        _model_manager = new_manager

        if old_manager:
            logger.info(f"Hot reload complete: {old_manager.get_model_name()} -> {model_name}")
        else:
            logger.info(f"Model loaded: {model_name}")

        return _model_manager

    except Exception as e:
        logger.error(f"Hot reload failed: {e}")
        raise RuntimeError(f"Failed to reload embedding model: {e}")
