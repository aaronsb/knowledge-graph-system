"""
Job analysis service for pre-ingestion cost estimation.

Provides fast analysis of ingestion jobs without making LLM calls:
- File statistics (size, word count)
- Estimated chunk count
- Token usage estimates
- Cost estimates for extraction and embeddings
- Warnings about large files, checkpoints, etc.

Based on cost logic from src/ingest/ingest_chunked.py but implemented
as standalone service to avoid coupling with POC code.
"""

import os
from typing import Dict, List, Optional
from pathlib import Path


class CostEstimator:
    """Calculate token costs based on model and environment configuration."""

    # Model pricing environment variable mappings
    EXTRACTION_MODEL_COSTS = {
        "gpt-4o": "TOKEN_COST_GPT4O",
        "gpt-4o-mini": "TOKEN_COST_GPT4O_MINI",
        "o1-preview": "TOKEN_COST_O1_PREVIEW",
        "o1-mini": "TOKEN_COST_O1_MINI",
        "claude-sonnet-4-20250514": "TOKEN_COST_CLAUDE_SONNET_4",
    }

    EMBEDDING_MODEL_COSTS = {
        "text-embedding-3-small": "TOKEN_COST_EMBEDDING_SMALL",
        "text-embedding-3-large": "TOKEN_COST_EMBEDDING_LARGE",
    }

    # Default costs per 1M tokens (USD)
    DEFAULT_EXTRACTION_COST = 6.25  # GPT-4o average
    DEFAULT_EMBEDDING_COST = 0.02   # text-embedding-3-small

    @classmethod
    def get_extraction_cost_per_million(cls, model: str) -> float:
        """Get extraction cost per 1M tokens from environment or default."""
        cost_var = cls.EXTRACTION_MODEL_COSTS.get(model, "TOKEN_COST_GPT4O")
        return float(os.getenv(cost_var, cls.DEFAULT_EXTRACTION_COST))

    @classmethod
    def get_embedding_cost_per_million(cls, model: str) -> float:
        """Get embedding cost per 1M tokens from environment or default."""
        cost_var = cls.EMBEDDING_MODEL_COSTS.get(model, "TOKEN_COST_EMBEDDING_SMALL")
        return float(os.getenv(cost_var, cls.DEFAULT_EMBEDDING_COST))

    @classmethod
    def calculate_extraction_cost(cls, tokens: int, model: str) -> float:
        """Calculate extraction cost for given token count and model."""
        if tokens == 0:
            return 0.0
        cost_per_million = cls.get_extraction_cost_per_million(model)
        return (tokens / 1_000_000) * cost_per_million

    @classmethod
    def calculate_embedding_cost(cls, tokens: int, model: str) -> float:
        """Calculate embedding cost for given token count and model."""
        if tokens == 0:
            return 0.0
        cost_per_million = cls.get_embedding_cost_per_million(model)
        return (tokens / 1_000_000) * cost_per_million


class ChunkEstimator:
    """Estimate chunk count and token usage for documents."""

    @staticmethod
    def estimate_chunks(
        word_count: int,
        target_words: int = 1000,
        min_words: int = 800,
        max_words: int = 1500
    ) -> int:
        """
        Estimate number of chunks for a document.

        Uses target_words as average chunk size with some padding
        to account for overlap and boundary adjustments.
        """
        if word_count == 0:
            return 0

        # Use target_words as base estimate
        # Add 10% padding for overlap and boundaries
        avg_chunk_size = target_words * 0.9
        return max(1, int(word_count / avg_chunk_size))

    @staticmethod
    def estimate_extraction_tokens(
        word_count: int,
        estimated_chunks: int
    ) -> Dict[str, int]:
        """
        Estimate token usage for concept extraction.

        Returns:
            {"tokens_low": int, "tokens_high": int}
        """
        if word_count == 0:
            return {"tokens_low": 0, "tokens_high": 0}

        # Token estimation (words * ~0.5 tokens/word for English)
        # Add system prompt overhead (~500 tokens per chunk)
        base_tokens = int(word_count * 0.5)
        prompt_overhead = estimated_chunks * 500

        # Low estimate: base + overhead
        tokens_low = base_tokens + prompt_overhead

        # High estimate: 1.6x base (dense text) + overhead
        tokens_high = int(base_tokens * 1.6) + prompt_overhead

        return {
            "tokens_low": tokens_low,
            "tokens_high": tokens_high
        }

    @staticmethod
    def estimate_embedding_tokens(
        estimated_chunks: int,
        concepts_per_chunk_low: int = 5,
        concepts_per_chunk_high: int = 8,
        avg_concept_tokens: int = 8
    ) -> Dict[str, int]:
        """
        Estimate token usage for embeddings.

        Returns:
            {"concepts_low": int, "concepts_high": int,
             "tokens_low": int, "tokens_high": int}
        """
        if estimated_chunks == 0:
            return {
                "concepts_low": 0,
                "concepts_high": 0,
                "tokens_low": 0,
                "tokens_high": 0
            }

        # Estimate number of concepts
        concepts_low = estimated_chunks * concepts_per_chunk_low
        concepts_high = estimated_chunks * concepts_per_chunk_high

        # Estimate tokens (each concept ~8 tokens average)
        tokens_low = concepts_low * avg_concept_tokens
        tokens_high = concepts_high * avg_concept_tokens

        return {
            "concepts_low": concepts_low,
            "concepts_high": concepts_high,
            "tokens_low": tokens_low,
            "tokens_high": tokens_high
        }


class FileAnalyzer:
    """Analyze files for ingestion cost estimation."""

    @staticmethod
    def get_file_stats(file_path: str) -> Dict:
        """
        Get file statistics.

        Returns:
            {
                "filename": str,
                "size_bytes": int,
                "size_human": str,
                "word_count": int
            }
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file size
        size_bytes = path.stat().st_size

        # Human-readable size
        if size_bytes < 1024:
            size_human = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_human = f"{size_bytes / 1024:.1f} KB"
        else:
            size_human = f"{size_bytes / (1024 * 1024):.1f} MB"

        # Count words
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            word_count = len(content.split())
        except Exception as e:
            raise ValueError(f"Failed to read file: {e}")

        return {
            "filename": path.name,
            "size_bytes": size_bytes,
            "size_human": size_human,
            "word_count": word_count
        }

    @staticmethod
    def generate_warnings(
        file_stats: Dict,
        estimated_chunks: int,
        file_path: str
    ) -> List[str]:
        """Generate warnings about potential issues."""
        warnings = []

        # Large file warning
        if file_stats["size_bytes"] > 1_000_000:  # > 1 MB
            # Estimate processing time (rough: 2-5 seconds per chunk)
            time_low = (estimated_chunks * 2) / 60  # minutes
            time_high = (estimated_chunks * 5) / 60
            warnings.append(
                f"Large file - estimated processing time: {time_low:.0f}-{time_high:.0f} minutes"
            )

        # Check for existing checkpoint
        filename = Path(file_path).stem
        checkpoint_path = Path(f"data/checkpoints/{filename}_checkpoint.json")
        if checkpoint_path.exists():
            warnings.append(f"Existing checkpoint found: {checkpoint_path.name}")
        else:
            warnings.append("No existing checkpoint found")

        # Very small file warning
        if file_stats["word_count"] < 100:
            warnings.append("Very small file - may produce minimal concepts")

        return warnings


class JobAnalyzer:
    """
    Analyze ingestion jobs for cost estimation and pre-validation.

    Provides fast analysis without making LLM calls:
    - File statistics
    - Chunk count estimation
    - Token usage estimates
    - Cost estimates
    - Warnings about large files, existing checkpoints, etc.
    """

    def __init__(self):
        self.cost_estimator = CostEstimator()
        self.chunk_estimator = ChunkEstimator()
        self.file_analyzer = FileAnalyzer()

    def analyze_ingestion_job(self, job_data: Dict) -> Dict:
        """
        Analyze an ingestion job and return estimates.

        Args:
            job_data: Job data dict containing:
                - file_path: Path to file to ingest
                - ontology: Ontology name (optional, for warnings)
                - target_words: Target words per chunk (default: 1000)
                - min_words: Min words per chunk (default: 800)
                - max_words: Max words per chunk (default: 1500)
                - extraction_model: Model for extraction (default: from env)
                - embedding_model: Model for embeddings (default: from env)

        Returns:
            Analysis dict matching ADR-014 spec:
            {
                "file_stats": {...},
                "cost_estimate": {...},
                "config": {...},
                "warnings": [...],
                "analyzed_at": "ISO timestamp"
            }
        """
        from datetime import datetime

        # Extract parameters
        file_path = job_data.get("file_path")
        if not file_path:
            raise ValueError("file_path is required in job_data")

        target_words = job_data.get("target_words", 1000)
        min_words = job_data.get("min_words", 800)
        max_words = job_data.get("max_words", 1500)

        # Get models from job_data or environment
        extraction_model = job_data.get("extraction_model") or os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o")
        embedding_model = job_data.get("embedding_model") or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        # Analyze file
        file_stats = self.file_analyzer.get_file_stats(file_path)

        # Estimate chunks
        estimated_chunks = self.chunk_estimator.estimate_chunks(
            word_count=file_stats["word_count"],
            target_words=target_words,
            min_words=min_words,
            max_words=max_words
        )

        file_stats["estimated_chunks"] = estimated_chunks

        # Estimate extraction tokens and costs
        extraction_tokens = self.chunk_estimator.estimate_extraction_tokens(
            word_count=file_stats["word_count"],
            estimated_chunks=estimated_chunks
        )

        extraction_cost_low = self.cost_estimator.calculate_extraction_cost(
            tokens=extraction_tokens["tokens_low"],
            model=extraction_model
        )
        extraction_cost_high = self.cost_estimator.calculate_extraction_cost(
            tokens=extraction_tokens["tokens_high"],
            model=extraction_model
        )

        # Estimate embedding tokens and costs
        embedding_estimates = self.chunk_estimator.estimate_embedding_tokens(
            estimated_chunks=estimated_chunks
        )

        embedding_cost_low = self.cost_estimator.calculate_embedding_cost(
            tokens=embedding_estimates["tokens_low"],
            model=embedding_model
        )
        embedding_cost_high = self.cost_estimator.calculate_embedding_cost(
            tokens=embedding_estimates["tokens_high"],
            model=embedding_model
        )

        # Total costs
        total_cost_low = extraction_cost_low + embedding_cost_low
        total_cost_high = extraction_cost_high + embedding_cost_high

        # Generate warnings
        warnings = self.file_analyzer.generate_warnings(
            file_stats=file_stats,
            estimated_chunks=estimated_chunks,
            file_path=file_path
        )

        # Build analysis response
        analysis = {
            "file_stats": file_stats,
            "cost_estimate": {
                "extraction": {
                    "model": extraction_model,
                    "tokens_low": extraction_tokens["tokens_low"],
                    "tokens_high": extraction_tokens["tokens_high"],
                    "cost_low": round(extraction_cost_low, 2),
                    "cost_high": round(extraction_cost_high, 2),
                    "currency": "USD"
                },
                "embeddings": {
                    "model": embedding_model,
                    "concepts_low": embedding_estimates["concepts_low"],
                    "concepts_high": embedding_estimates["concepts_high"],
                    "tokens_low": embedding_estimates["tokens_low"],
                    "tokens_high": embedding_estimates["tokens_high"],
                    "cost_low": round(embedding_cost_low, 2),
                    "cost_high": round(embedding_cost_high, 2),
                    "currency": "USD"
                },
                "total": {
                    "cost_low": round(total_cost_low, 2),
                    "cost_high": round(total_cost_high, 2),
                    "currency": "USD"
                }
            },
            "config": {
                "target_words": target_words,
                "min_words": min_words,
                "max_words": max_words,
                "overlap_words": job_data.get("overlap_words", 200),
                "checkpoint_interval": job_data.get("checkpoint_interval", 5)
            },
            "warnings": warnings,
            "analyzed_at": datetime.now().isoformat()
        }

        return analysis
