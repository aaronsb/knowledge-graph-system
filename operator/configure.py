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
        self.postgres_password = os.environ["POSTGRES_PASSWORD"]

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
                        "UPDATE kg_auth.users SET password_hash = %s WHERE username = %s",
                        (password_hash, username)
                    )
                    print(f"✅ Updated password for user: {username}")
                else:
                    cur.execute(
                        """INSERT INTO kg_auth.users (username, password_hash, primary_role, disabled)
                           VALUES (%s, %s, 'admin', false)
                           RETURNING id""",
                        (username, password_hash)
                    )
                    user_id = cur.fetchone()[0]
                    print(f"✅ Created admin user: {username} (id={user_id})")

                    # Add user to admins group (group_id=2, per ADR-082)
                    cur.execute(
                        """INSERT INTO kg_auth.user_groups (user_id, group_id, added_by)
                           VALUES (%s, 2, 1)
                           ON CONFLICT (user_id, group_id) DO NOTHING""",
                        (user_id,)
                    )
                    print(f"   Added to admins group")

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
        max_tokens = getattr(args, 'max_tokens', None)

        if not provider:
            print("❌ Provider required (openai, anthropic, ollama, or openrouter)")
            return False

        # Default models
        if not model:
            models = {
                "openai": "gpt-4o",
                "anthropic": "claude-sonnet-4-20250514",
                "ollama": "mistral:7b-instruct",
                "openrouter": "openai/gpt-4o",
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

                # Validate model exists in catalog (ADR-800) — warn but don't block
                try:
                    cur.execute(
                        """SELECT id, enabled FROM kg_api.provider_model_catalog
                           WHERE provider = %s AND model_id = %s AND category = 'extraction'""",
                        (provider, model),
                    )
                    catalog_row = cur.fetchone()
                    if catalog_row is None:
                        print(f"⚠️  Model '{model}' not in catalog for {provider}. Run: models refresh {provider}")
                    elif not catalog_row['enabled']:
                        print(f"⚠️  Model '{model}' is in catalog but not enabled. Run: models enable {catalog_row['id']}")
                except Exception:
                    # Table may not exist yet (migrations pending)
                    conn.rollback()

                # Insert/update configuration
                cur.execute(
                    """INSERT INTO kg_api.ai_extraction_config
                       (provider, model_name, supports_vision, supports_json_mode, max_tokens, active)
                       VALUES (%s, %s, true, true, %s, true)
                       ON CONFLICT (active) WHERE active = true
                       DO UPDATE SET
                         provider = EXCLUDED.provider,
                         model_name = EXCLUDED.model_name,
                         max_tokens = COALESCE(EXCLUDED.max_tokens, kg_api.ai_extraction_config.max_tokens),
                         updated_at = NOW()""",
                    (provider, model, max_tokens)
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
        """Configure embedding provider by activating a pre-configured profile"""
        profile_id = getattr(args, 'profile_id', None)
        provider_name = getattr(args, 'provider', None)

        # If no profile_id or provider specified, list available profiles
        if profile_id is None and provider_name is None:
            return self.list_embedding_profiles()

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Get the requested profile - by ID or by provider name
                if provider_name:
                    cur.execute(
                        """SELECT id, text_provider AS provider, text_model_name AS model_name,
                                  text_dimensions AS embedding_dimensions, text_precision AS precision, device
                           FROM kg_api.embedding_profile WHERE text_provider = %s LIMIT 1""",
                        (provider_name,)
                    )
                else:
                    cur.execute(
                        """SELECT id, text_provider AS provider, text_model_name AS model_name,
                                  text_dimensions AS embedding_dimensions, text_precision AS precision, device
                           FROM kg_api.embedding_profile WHERE id = %s""",
                        (profile_id,)
                    )
                profile = cur.fetchone()

                if not profile:
                    print(f"❌ Profile ID {profile_id} not found")
                    print("Run without arguments to list available profiles")
                    return False

                # Show current active profile
                cur.execute("SELECT id, text_provider AS provider, text_model_name AS model_name FROM kg_api.embedding_profile WHERE active = true")
                current = cur.fetchone()
                if current:
                    print(f"📝 Current: [{current['id']}] {current['provider']} / {current['model_name']}")

                # Deactivate all profiles
                cur.execute("UPDATE kg_api.embedding_profile SET active = false")

                # Activate selected profile (use profile['id'] from query, not profile_id arg)
                cur.execute("UPDATE kg_api.embedding_profile SET active = true WHERE id = %s", (profile['id'],))

                conn.commit()

                device_info = f" ({profile['device']})" if profile['device'] else ""
                print(f"✅ Activated: [{profile['id']}] {profile['provider']} / {profile['model_name']} ({profile['embedding_dimensions']} dims, {profile['precision']}){device_info}")
                return True

        except Exception as e:
            print(f"❌ Failed to configure embedding: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def list_embedding_profiles(self):
        """List available embedding profiles"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, text_provider AS provider, text_model_name AS model_name,
                              text_dimensions AS embedding_dimensions, text_precision AS precision,
                              device, active
                       FROM kg_api.embedding_profile ORDER BY id"""
                )
                profiles = cur.fetchall()

                if not profiles:
                    print("❌ No embedding profiles found")
                    return False

                print("📋 Available Embedding Profiles:")
                print()
                for profile in profiles:
                    status = "✓ ACTIVE" if profile['active'] else " "
                    device_info = f" ({profile['device']})" if profile['device'] else ""
                    print(f"  [{profile['id']}] {status:10} {profile['provider']:8} - {profile['model_name']}")
                    print(f"       {profile['embedding_dimensions']} dims, {profile['precision']}{device_info}")
                    print()

                print("To activate a profile:")
                print("  docker exec kg-operator python /workspace/operator/configure.py embedding <profile_id>")
                print()
                print("Example:")
                print("  docker exec kg-operator python /workspace/operator/configure.py embedding 2")
                return True

        except Exception as e:
            print(f"❌ Failed to list profiles: {e}")
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

        # Import required modules
        try:
            from api.app.lib.encrypted_keys import EncryptedKeyStore
            from api.app.lib.age_client import AGEClient
            from api.app.lib.ai_providers import OpenAIProvider, AnthropicProvider, OpenRouterProvider
        except ImportError as e:
            print(f"❌ Cannot import required modules: {e}")
            print("   Make sure PYTHONPATH includes api directory")
            return False

        # Validate the API key before storing
        print(f"🔍 Validating {provider} API key...")
        try:
            if provider.lower() == "openai":
                validator = OpenAIProvider(api_key=key)
            elif provider.lower() == "anthropic":
                validator = AnthropicProvider(api_key=key)
            elif provider.lower() == "openrouter":
                validator = OpenRouterProvider(api_key=key)
            else:
                print(f"⚠️  Warning: Validation not implemented for provider '{provider}'")
                print("   Key will be stored without validation.")
                validator = None

            if validator:
                if not validator.validate_api_key():
                    print(f"❌ API key validation failed for {provider}")
                    print("   The key was rejected by the provider's API.")
                    print("   Please check:")
                    print("     1. Key is correct (no extra spaces or characters)")
                    print("     2. Key has not been revoked")
                    print("     3. Account is active and in good standing")
                    return False
                print(f"✅ API key validated successfully")

        except ImportError as e:
            print(f"❌ Failed to import provider module: {e}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"❌ API key validation failed: {e}")
            print("   Error details:")
            import traceback
            traceback.print_exc()
            return False

        # Store the validated key
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

    def cmd_models(self, args):
        """Manage provider model catalog (ADR-800)."""
        action = getattr(args, 'action', None)

        if not action:
            print("❌ Action required: list, refresh, enable, disable, default, price")
            return False

        conn = self.get_connection()
        try:
            if action == 'list':
                provider = getattr(args, 'provider_name', None)
                use_tsv = getattr(args, 'tsv', False)
                category_filter = getattr(args, 'category', None)
                limit = getattr(args, 'limit', 0) or 0

                with conn.cursor() as cur:
                    conditions = []
                    params = []
                    if provider:
                        conditions.append("provider = %s")
                        params.append(provider)
                    if category_filter:
                        conditions.append("category = %s")
                        params.append(category_filter)

                    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                    limit_clause = f"LIMIT {int(limit)}" if limit > 0 else ""
                    cur.execute(
                        f"""SELECT id, provider, model_id, display_name, category,
                                   enabled, is_default,
                                   price_prompt_per_m, price_completion_per_m,
                                   fetched_at
                            FROM kg_api.provider_model_catalog
                            {where}
                            ORDER BY provider, sort_order, model_id
                            {limit_clause}""",
                        params,
                    )
                    rows = cur.fetchall()

                if not rows:
                    if not use_tsv:
                        print("📭 No models in catalog." + (" Try: models refresh <provider>" if provider else ""))
                    return True

                if use_tsv:
                    # Machine-parseable: ID\tmodel_id\tdisplay_name\tprice_prompt\tprice_completion
                    for row in rows:
                        prompt_p = f"{float(row['price_prompt_per_m']):.4f}" if row['price_prompt_per_m'] is not None else ""
                        comp_p = f"{float(row['price_completion_per_m']):.4f}" if row['price_completion_per_m'] is not None else ""
                        print(f"{row['id']}\t{row['model_id']}\t{row['display_name'] or row['model_id']}\t{prompt_p}\t{comp_p}")
                    return True

                current_provider = None
                for row in rows:
                    if row['provider'] != current_provider:
                        current_provider = row['provider']
                        print(f"\n📦 {current_provider.upper()}")
                        print(f"   {'ID':>4}  {'Model':<40} {'Category':<12} {'Enabled':<8} {'Default':<8} {'Prompt/1M':>10} {'Comp/1M':>10}")
                        print(f"   {'─'*4}  {'─'*40} {'─'*12} {'─'*8} {'─'*8} {'─'*10} {'─'*10}")

                    enabled_mark = "✅" if row['enabled'] else "  "
                    default_mark = "⭐" if row['is_default'] else "  "
                    prompt_price = f"${float(row['price_prompt_per_m']):.4f}" if row['price_prompt_per_m'] is not None else "—"
                    comp_price = f"${float(row['price_completion_per_m']):.4f}" if row['price_completion_per_m'] is not None else "—"

                    print(f"   {row['id']:>4}  {row['model_id']:<40} {row['category']:<12} {enabled_mark:<8} {default_mark:<8} {prompt_price:>10} {comp_price:>10}")

                print()
                return True

            elif action == 'refresh':
                provider = getattr(args, 'provider_name', None)
                if not provider:
                    print("❌ Provider required: openai, anthropic, ollama, openrouter")
                    return False

                print(f"🔄 Fetching model catalog from {provider}...")
                try:
                    from api.app.lib.ai_providers import get_provider
                    from api.app.lib.model_catalog import upsert_catalog_entries

                    prov = get_provider(provider)
                    entries = prov.fetch_model_catalog()

                    if not entries:
                        print(f"⚠️  No models returned from {provider}")
                        return False

                    count = upsert_catalog_entries(conn, entries)
                    print(f"✅ Refreshed {count} models from {provider}")
                    return True

                except Exception as e:
                    print(f"❌ Failed to refresh catalog: {e}")
                    return False

            elif action == 'enable':
                # Catalog ID is the 2nd positional arg (argparse maps it to provider_name)
                model_id_str = getattr(args, 'provider_name', None) or getattr(args, 'model_id', None)
                if not model_id_str:
                    print("❌ Model catalog ID required")
                    return False

                from api.app.lib.model_catalog import set_model_enabled
                if set_model_enabled(conn, int(model_id_str), True):
                    print(f"✅ Enabled model #{model_id_str}")
                    return True
                print(f"❌ Model #{model_id_str} not found")
                return False

            elif action == 'disable':
                model_id_str = getattr(args, 'provider_name', None) or getattr(args, 'model_id', None)
                if not model_id_str:
                    print("❌ Model catalog ID required")
                    return False

                from api.app.lib.model_catalog import set_model_enabled
                if set_model_enabled(conn, int(model_id_str), False):
                    print(f"✅ Disabled model #{model_id_str}")
                    return True
                print(f"❌ Model #{model_id_str} not found")
                return False

            elif action == 'default':
                model_id_str = getattr(args, 'provider_name', None) or getattr(args, 'model_id', None)
                if not model_id_str:
                    print("❌ Model catalog ID required")
                    return False

                from api.app.lib.model_catalog import set_model_default
                if set_model_default(conn, int(model_id_str)):
                    print(f"✅ Set model #{model_id_str} as default")
                    return True
                print(f"❌ Model #{model_id_str} not found")
                return False

            elif action == 'price':
                model_id_str = getattr(args, 'provider_name', None) or getattr(args, 'model_id', None)
                prompt_cost = getattr(args, 'prompt', None)
                comp_cost = getattr(args, 'completion', None)

                if not model_id_str:
                    print("❌ Model catalog ID required")
                    return False
                if prompt_cost is None and comp_cost is None:
                    print("❌ Specify --prompt and/or --completion price per 1M tokens")
                    return False

                from api.app.lib.model_catalog import update_model_pricing
                if update_model_pricing(
                    conn, int(model_id_str),
                    price_prompt_per_m=float(prompt_cost) if prompt_cost else None,
                    price_completion_per_m=float(comp_cost) if comp_cost else None,
                ):
                    print(f"✅ Updated pricing for model #{model_id_str}")
                    return True
                print(f"❌ Model #{model_id_str} not found")
                return False

            else:
                print(f"❌ Unknown action: {action}")
                return False

        except Exception as e:
            print(f"❌ Models command failed: {e}")
            return False
        finally:
            conn.close()

    def cmd_status(self, args):
        """Show current configuration status"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                print("📊 Platform Configuration Status")
                print()

                # Admin users
                cur.execute("SELECT COUNT(*) as count FROM kg_auth.users WHERE primary_role = 'admin'")
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
                cur.execute("SELECT text_provider AS provider, text_model_name AS model_name, text_dimensions AS embedding_dimensions FROM kg_api.embedding_profile WHERE active = true")
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


    def cmd_oauth(self, args):
        """Configure OAuth clients"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                if args.list:
                    # List all OAuth clients
                    cur.execute("""
                        SELECT client_id, client_name, client_type, redirect_uris
                        FROM kg_auth.oauth_clients
                        ORDER BY client_id
                    """)
                    clients = cur.fetchall()
                    print("\n📋 OAuth Clients:")
                    print("-" * 60)
                    for client in clients:
                        print(f"  {client['client_id']} ({client['client_type']})")
                        print(f"    Name: {client['client_name']}")
                        if client['redirect_uris']:
                            print(f"    Redirect URIs: {', '.join(client['redirect_uris'])}")
                        print()
                    return True

                if not args.client_id:
                    print("❌ Client ID required (use --list to see all clients)")
                    return False

                if args.redirect_uri:
                    # Update redirect URIs for a client
                    # Parse comma-separated URIs
                    uris = [u.strip() for u in args.redirect_uri.split(',')]
                    cur.execute("""
                        UPDATE kg_auth.oauth_clients
                        SET redirect_uris = %s
                        WHERE client_id = %s
                        RETURNING client_id
                    """, (uris, args.client_id))

                    if cur.fetchone():
                        conn.commit()
                        print(f"✅ Updated redirect URIs for {args.client_id}")
                        print(f"   URIs: {', '.join(uris)}")
                        return True
                    else:
                        print(f"❌ Client not found: {args.client_id}")
                        return False

                # Show client details
                cur.execute("""
                    SELECT client_id, client_name, client_type, redirect_uris, scopes
                    FROM kg_auth.oauth_clients
                    WHERE client_id = %s
                """, (args.client_id,))
                client = cur.fetchone()
                if client:
                    print(f"\n📋 OAuth Client: {client['client_id']}")
                    print(f"   Name: {client['client_name']}")
                    print(f"   Type: {client['client_type']}")
                    print(f"   Redirect URIs: {', '.join(client['redirect_uris'] or [])}")
                    print(f"   Scopes: {', '.join(client['scopes'] or [])}")
                    return True
                else:
                    print(f"❌ Client not found: {args.client_id}")
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
    ai_parser.add_argument('provider', nargs='?', help='Provider: openai, anthropic, ollama, openrouter')
    ai_parser.add_argument('--model', help='Model name (optional, uses default)')
    ai_parser.add_argument('--max-tokens', type=int, help='Max completion tokens for extraction (default: 16384)')

    # embedding
    embed_parser = subparsers.add_parser('embedding', help='List or activate embedding profile')
    embed_parser.add_argument('profile_id', nargs='?', type=int, help='Profile ID to activate (omit to list profiles)')
    embed_parser.add_argument('--provider', help='Select profile by provider name (local, openai)')

    # api-key
    key_parser = subparsers.add_parser('api-key', help='Store encrypted API key')
    key_parser.add_argument('provider', nargs='?', help='Provider name')
    key_parser.add_argument('--key', help='API key (will prompt if not provided)')

    # models (ADR-800)
    models_parser = subparsers.add_parser('models', help='Manage provider model catalog')
    models_parser.add_argument('action', nargs='?', help='list, refresh, enable, disable, default, price')
    models_parser.add_argument('provider_name', nargs='?', help='Provider name (for list/refresh)')
    models_parser.add_argument('model_id', nargs='?', help='Catalog ID (for enable/disable/default/price)')
    models_parser.add_argument('--prompt', type=float, help='Prompt price per 1M tokens (for price)')
    models_parser.add_argument('--completion', type=float, help='Completion price per 1M tokens (for price)')
    models_parser.add_argument('--tsv', action='store_true', help='Output in TSV format (for scripting)')
    models_parser.add_argument('--category', default='extraction', help='Filter by category (default: extraction)')
    models_parser.add_argument('--limit', type=int, default=0, help='Limit number of results (0=unlimited)')

    # status
    subparsers.add_parser('status', help='Show configuration status')

    # oauth
    oauth_parser = subparsers.add_parser('oauth', help='Configure OAuth clients')
    oauth_parser.add_argument('client_id', nargs='?', help='Client ID (kg-web, kg-cli, kg-mcp)')
    oauth_parser.add_argument('--list', action='store_true', help='List all OAuth clients')
    oauth_parser.add_argument('--redirect-uri', help='Set redirect URI(s), comma-separated')

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
        'models': config.cmd_models,
        'status': config.cmd_status,
        'oauth': config.cmd_oauth,
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
