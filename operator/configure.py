#!/usr/bin/env python3
"""
Operator Configuration Tool
Pure database configuration - no .env file editing
"""

import os
import sys
import argparse
import getpass
import psycopg2
from psycopg2.extras import RealDictCursor

# Add api to path for imports
sys.path.insert(0, '/workspace')  # When running in container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class OperatorConfig:
    """Database configuration manager for kg-operator"""

    def __init__(self):
        # Connection from environment
        self.postgres_host = os.getenv("POSTGRES_HOST", "kg-postgres-dev")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "knowledge_graph")
        self.postgres_user = os.getenv("POSTGRES_USER", "admin")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "password")

    def get_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
                user=self.postgres_user,
                password=self.postgres_password,
                cursor_factory=RealDictCursor
            )
        except psycopg2.OperationalError as e:
            print(f"❌ Cannot connect to PostgreSQL at {self.postgres_host}:{self.postgres_port}")
            print(f"   Error: {e}")
            print()
            print("Make sure:")
            print("  1. PostgreSQL container is running (docker ps)")
            print("  2. POSTGRES_HOST environment variable is correct")
            print("  3. .env file has correct POSTGRES_PASSWORD")
            sys.exit(1)

    def cmd_admin(self, args):
        """Configure admin user"""
        username = args.username or "admin"
        password = args.password

        if not password:
            password = getpass.getpass(f"Enter password for {username}: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("❌ Passwords do not match")
                return False

        # Hash password with bcrypt
        try:
            import bcrypt
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except ImportError:
            print("❌ bcrypt not installed (run: pip install bcrypt)")
            return False

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT username FROM kg_auth.users WHERE username = %s", (username,))
                exists = cur.fetchone()

                if exists:
                    cur.execute(
                        "UPDATE kg_auth.users SET password_hash = %s, updated_at = NOW() WHERE username = %s",
                        (password_hash, username)
                    )
                    print(f"✅ Updated password for user: {username}")
                else:
                    cur.execute(
                        """INSERT INTO kg_auth.users (username, password_hash, is_superuser, is_active)
                           VALUES (%s, %s, true, true)""",
                        (username, password_hash)
                    )
                    print(f"✅ Created admin user: {username}")

                conn.commit()
                return True

        except Exception as e:
            print(f"❌ Failed to configure admin: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def cmd_ai_provider(self, args):
        """Configure AI extraction provider"""
        provider = args.provider
        model = args.model

        if not provider:
            print("❌ Provider required (openai, anthropic, or ollama)")
            return False

        # Default models
        if not model:
            models = {
                "openai": "gpt-4o",
                "anthropic": "claude-sonnet-4-20250514",
                "ollama": "mistral:7b-instruct"
            }
            model = models.get(provider)
            if not model:
                print(f"❌ Unknown provider: {provider}")
                return False

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Check current config
                cur.execute("SELECT provider, model_name FROM kg_api.ai_extraction_config WHERE active = true")
                current = cur.fetchone()

                if current:
                    print(f"📝 Current: {current['provider']} / {current['model_name']}")

                # Insert/update configuration
                cur.execute(
                    """INSERT INTO kg_api.ai_extraction_config
                       (provider, model_name, supports_vision, supports_json_mode, active)
                       VALUES (%s, %s, true, true, true)
                       ON CONFLICT (active) WHERE active = true
                       DO UPDATE SET
                         provider = EXCLUDED.provider,
                         model_name = EXCLUDED.model_name,
                         updated_at = NOW()""",
                    (provider, model)
                )
                conn.commit()
                print(f"✅ Configured AI extraction: {provider} / {model}")
                return True

        except Exception as e:
            print(f"❌ Failed to configure AI provider: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def cmd_embedding(self, args):
        """Configure embedding provider"""
        provider = args.provider
        model = args.model

        if not provider:
            print("❌ Provider required (openai or local)")
            return False

        # Default models and dimensions
        config_map = {
            "openai": {
                "model": "text-embedding-3-small",
                "dims": 1536
            },
            "local": {
                "model": "nomic-ai/nomic-embed-text-v1.5",
                "dims": 768
            }
        }

        if provider not in config_map:
            print(f"❌ Unknown provider: {provider} (use 'openai' or 'local')")
            return False

        cfg = config_map[provider]
        model = model or cfg["model"]
        dims = cfg["dims"]

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Check current config
                cur.execute("SELECT provider, model_name FROM kg_api.embedding_config WHERE active = true")
                current = cur.fetchone()

                if current:
                    print(f"📝 Current: {current['provider']} / {current['model_name']}")

                # Insert configuration
                cur.execute(
                    """INSERT INTO kg_api.embedding_config
                       (provider, model_name, embedding_dimensions, active)
                       VALUES (%s, %s, %s, true)
                       ON CONFLICT (active) WHERE active = true
                       DO UPDATE SET
                         provider = EXCLUDED.provider,
                         model_name = EXCLUDED.model_name,
                         embedding_dimensions = EXCLUDED.embedding_dimensions,
                         updated_at = NOW()""",
                    (provider, model, dims)
                )
                conn.commit()
                print(f"✅ Configured embedding: {provider} / {model} ({dims} dims)")
                return True

        except Exception as e:
            print(f"❌ Failed to configure embedding: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def cmd_api_key(self, args):
        """Store encrypted API key"""
        provider = args.provider
        key = args.key

        if not provider:
            print("❌ Provider required (openai, anthropic, etc.)")
            return False

        if not key:
            key = getpass.getpass(f"Enter API key for {provider}: ")

        # Import encryption (from api module)
        try:
            from api.api.lib.encrypted_keys import EncryptedKeyStore
            from api.api.lib.age_client import AGEClient
        except ImportError as e:
            print(f"❌ Cannot import encryption modules: {e}")
            print("   Make sure PYTHONPATH includes api directory")
            return False

        try:
            client = AGEClient()
            conn = client.pool.getconn()
            try:
                key_store = EncryptedKeyStore(conn)
                key_store.store_key(provider, key)
                print(f"✅ Stored encrypted API key for: {provider}")
                return True
            finally:
                client.pool.putconn(conn)
        except Exception as e:
            print(f"❌ Failed to store API key: {e}")
            return False

    def cmd_status(self, args):
        """Show current configuration status"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                print("📊 Platform Configuration Status")
                print()

                # Admin users
                cur.execute("SELECT COUNT(*) as count FROM kg_auth.users WHERE is_superuser = true")
                admin_count = cur.fetchone()['count']
                print(f"Admin users: {admin_count}")

                # AI extraction provider
                cur.execute("SELECT provider, model_name FROM kg_api.ai_extraction_config WHERE active = true")
                extraction = cur.fetchone()
                if extraction:
                    print(f"AI Extraction: {extraction['provider']} / {extraction['model_name']}")
                else:
                    print("AI Extraction: Not configured")

                # Embedding provider
                cur.execute("SELECT provider, model_name, embedding_dimensions FROM kg_api.embedding_config WHERE active = true")
                embedding = cur.fetchone()
                if embedding:
                    print(f"Embedding: {embedding['provider']} / {embedding['model_name']} ({embedding['embedding_dimensions']} dims)")
                else:
                    print("Embedding: Not configured")

                # API keys (just count, don't show keys)
                cur.execute("SELECT provider FROM kg_api.system_api_keys ORDER BY provider")
                keys = cur.fetchall()
                if keys:
                    providers = [k['provider'] for k in keys]
                    print(f"API Keys: {', '.join(providers)}")
                else:
                    print("API Keys: None configured")

                return True

        except Exception as e:
            print(f"❌ Failed to get status: {e}")
            return False
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="kg-operator configuration tool")
    subparsers = parser.add_subparsers(dest='command', help='Configuration command')

    # admin
    admin_parser = subparsers.add_parser('admin', help='Configure admin user')
    admin_parser.add_argument('--username', default='admin', help='Admin username')
    admin_parser.add_argument('--password', help='Admin password (will prompt if not provided)')

    # ai-provider
    ai_parser = subparsers.add_parser('ai-provider', help='Configure AI extraction provider')
    ai_parser.add_argument('provider', nargs='?', help='Provider: openai, anthropic, ollama')
    ai_parser.add_argument('--model', help='Model name (optional, uses default)')

    # embedding
    embed_parser = subparsers.add_parser('embedding', help='Configure embedding provider')
    embed_parser.add_argument('provider', nargs='?', help='Provider: openai, local')
    embed_parser.add_argument('--model', help='Model name (optional, uses default)')

    # api-key
    key_parser = subparsers.add_parser('api-key', help='Store encrypted API key')
    key_parser.add_argument('provider', nargs='?', help='Provider name')
    key_parser.add_argument('--key', help='API key (will prompt if not provided)')

    # status
    subparsers.add_parser('status', help='Show configuration status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = OperatorConfig()

    # Route to command handler
    handlers = {
        'admin': config.cmd_admin,
        'ai-provider': config.cmd_ai_provider,
        'embedding': config.cmd_embedding,
        'api-key': config.cmd_api_key,
        'status': config.cmd_status,
    }

    handler = handlers.get(args.command)
    if handler:
        success = handler(args)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
