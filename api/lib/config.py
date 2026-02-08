"""
Configuration management - Environment variables and application settings

Centralizes configuration loading from .env files and environment variables.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Application configuration from environment variables"""

    _loaded = False

    @classmethod
    def load(cls):
        """Load environment variables from .env file"""
        if not cls._loaded:
            # Find .env file (look in project root)
            project_root = Path(__file__).parent.parent.parent
            env_file = project_root / '.env'

            if env_file.exists():
                load_dotenv(env_file)
            cls._loaded = True

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value"""
        Config.load()
        return os.getenv(key, default)

    @staticmethod
    def require(key: str) -> str:
        """Get required configuration value, raise if missing"""
        Config.load()
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    # Neo4j Configuration (Legacy - for migration compatibility)
    @staticmethod
    def neo4j_uri() -> str:
        return Config.get("NEO4J_URI", "bolt://localhost:7687")

    @staticmethod
    def neo4j_user() -> str:
        return Config.get("NEO4J_USER", "neo4j")

    @staticmethod
    def neo4j_password() -> str:
        return Config.get("NEO4J_PASSWORD", "password")

    # PostgreSQL / Apache AGE Configuration
    @staticmethod
    def postgres_host() -> str:
        return Config.get("POSTGRES_HOST", "localhost")

    @staticmethod
    def postgres_port() -> int:
        return int(Config.get("POSTGRES_PORT", "5432"))

    @staticmethod
    def postgres_db() -> str:
        return Config.get("POSTGRES_DB", "knowledge_graph")

    @staticmethod
    def postgres_user() -> str:
        return Config.get("POSTGRES_USER", "admin")

    @staticmethod
    def postgres_password() -> str:
        return Config.require("POSTGRES_PASSWORD")

    # OpenAI Configuration
    @staticmethod
    def openai_api_key() -> Optional[str]:
        return Config.get("OPENAI_API_KEY")

    @staticmethod
    def openai_embedding_model() -> str:
        return Config.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Anthropic Configuration
    @staticmethod
    def anthropic_api_key() -> Optional[str]:
        return Config.get("ANTHROPIC_API_KEY")

    # AI Provider
    @staticmethod
    def ai_provider() -> str:
        return Config.get("AI_PROVIDER", "openai")

    @staticmethod
    def validate_ai_config():
        """Validate that required AI configuration is present"""
        provider = Config.ai_provider()

        if provider == "openai":
            if not Config.openai_api_key():
                raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        elif provider == "anthropic":
            if not Config.anthropic_api_key():
                raise ValueError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic")
            # Anthropic doesn't provide embeddings, so OpenAI key is still needed
            if not Config.openai_api_key():
                raise ValueError("OPENAI_API_KEY is required for embeddings (Anthropic doesn't provide embeddings)")
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {provider}. Must be 'openai' or 'anthropic'")
