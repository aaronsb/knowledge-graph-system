"""
Vocabulary mixin for relationship type management.

Manages the vocabulary of relationship types used between concepts.
Each relationship type has a canonical name, category, description,
embedding vector, and active/inactive status.

Key operations:
- Configuration: vocabulary size, config values, edge type listing
- Sync: discover edge types in graph not yet in vocabulary (ADR-077)
- CRUD: add, update, merge relationship types (ADR-047)
- Categories: distribution of types across semantic categories
- Embeddings: store/retrieve embedding vectors for relationship types
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from psycopg2 import extras
from api.app.constants import RELATIONSHIP_TYPE_TO_CATEGORY

logger = logging.getLogger(__name__)


class VocabularyMixin:
    """Relationship type vocabulary: config, CRUD, sync, merge, and embeddings."""

    def get_vocabulary_size(self) -> int:
        """
        Get count of active relationship types in vocabulary.

        Returns:
            Count of active (non-deprecated) relationship types

        Example:
            >>> client = AGEClient()
            >>> size = client.get_vocabulary_size()
            >>> print(f"Vocabulary size: {size}")

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
        """
        try:
            query = """
            MATCH (v:VocabType)
            WHERE v.is_active = 't'
            RETURN count(v) as total
            """
            result = self._execute_cypher(query, fetch_one=True)
            if result and 'total' in result:
                return int(str(result['total']))
            return 0
        except Exception as e:
            logger.error(f"Failed to get vocabulary size from graph: {e}")
            return 0

    def get_vocab_config(self, key: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        Get vocabulary configuration value from database.

        Reads from kg_api.vocabulary_config table using helper function
        created in migration 017.

        Args:
            key: Configuration key (e.g., 'vocab_min', 'vocab_emergency')
            fallback: Value to return if key not found

        Returns:
            Configuration value as string, or fallback if not found

        Example:
            >>> client = AGEClient()
            >>> emergency = client.get_vocab_config('vocab_emergency', '200')
            >>> print(f"Emergency threshold: {emergency}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kg_api.get_vocab_config(%s, %s)",
                    (key, fallback)
                )
                result = cur.fetchone()
                if result and result[0] is not None:
                    return result[0]
                return fallback
        except Exception as e:
            logger.error(f"Failed to get vocab config '{key}' from database: {e}")
            return fallback
        finally:
            self.pool.putconn(conn)

    def get_all_edge_types(self, include_inactive: bool = False) -> List[str]:
        """
        Get list of all relationship types in vocabulary.

        Args:
            include_inactive: Include deprecated types (default: False)

        Returns:
            List of relationship type names

        Example:
            >>> client = AGEClient()
            >>> types = client.get_all_edge_types()
            >>> print(f"Active types: {len(types)}")

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
        """
        try:
            if include_inactive:
                query = """
                MATCH (v:VocabType)
                RETURN v.name as name
                ORDER BY v.name
                """
            else:
                query = """
                MATCH (v:VocabType)
                WHERE v.is_active = 't'
                RETURN v.name as name
                ORDER BY v.name
                """

            results = self._execute_cypher(query)
            return [str(row['name']) for row in results]
        except Exception as e:
            logger.error(f"Failed to get edge types from graph: {e}")
            return []

    def sync_missing_edge_types(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync edge types from graph edges to vocabulary (ADR-077).

        Scans all unique relationship types used in the graph and ensures each
        has a corresponding entry in the vocabulary table and VocabType node.
        This fixes the gap where predefined types from constants.py are used
        during ingestion but never registered in the vocabulary.

        Args:
            dry_run: If True, only report missing types without creating them

        Returns:
            Dict with:
                - missing: List of types in graph but not vocabulary
                - synced: List of types that were synced (if not dry_run)
                - failed: List of types that failed to sync
                - system_types: List of system types (skipped)
                - total_graph_types: Count of unique types in graph

        Example:
            >>> result = client.sync_missing_edge_types(dry_run=True)
            >>> print(f"Missing: {len(result['missing'])}")
            >>> # If satisfied, run without dry_run
            >>> result = client.sync_missing_edge_types(dry_run=False)
        """
        from api.app.constants import RELATIONSHIP_TYPE_TO_CATEGORY

        # System relationship types - internal use only, not user-facing vocabulary
        SYSTEM_TYPES = {
            'APPEARS', 'EVIDENCED_BY', 'FROM_SOURCE', 'IN_CATEGORY',
            'SCOPED_BY', 'LOAD', 'SET',  # LOAD/SET may appear from SQL parsing artifacts
        }

        try:
            # Step 1: Get all unique edge types from the graph
            graph_types_query = """
                MATCH ()-[r]->()
                RETURN DISTINCT type(r) AS rel_type
            """
            graph_results = self._execute_cypher(graph_types_query)
            graph_types = set()
            for row in graph_results:
                rel_type = str(row['rel_type']).strip('"')
                if rel_type and rel_type.isupper():  # Only valid uppercase types
                    graph_types.add(rel_type)

            # Step 2: Get all types in vocabulary (VocabType nodes)
            vocab_types = set(self.get_all_edge_types(include_inactive=True))

            # Step 3: Find missing types
            missing_types = graph_types - vocab_types - SYSTEM_TYPES
            system_types_found = graph_types & SYSTEM_TYPES

            result = {
                'missing': sorted(list(missing_types)),
                'synced': [],
                'failed': [],
                'system_types': sorted(list(system_types_found)),
                'total_graph_types': len(graph_types),
                'total_vocab_types': len(vocab_types),
                'dry_run': dry_run
            }

            if dry_run:
                logger.info(f"Dry run: Found {len(missing_types)} missing types")
                return result

            # Step 4: Add missing types to vocabulary
            for rel_type in sorted(missing_types):
                try:
                    # Get category from constants.py if defined
                    category = RELATIONSHIP_TYPE_TO_CATEGORY.get(rel_type, 'llm_generated')
                    is_builtin = rel_type in RELATIONSHIP_TYPE_TO_CATEGORY

                    # Use add_edge_type which handles both SQL table and VocabType node
                    success = self.add_edge_type(
                        relationship_type=rel_type,
                        category=category,
                        description=f"Auto-synced from graph edges",
                        added_by="vocabulary_sync",
                        is_builtin=is_builtin
                    )

                    if success:
                        result['synced'].append(rel_type)
                        logger.info(f"✓ Synced '{rel_type}' → {category}")
                    else:
                        # add_edge_type returns False if type already exists
                        result['synced'].append(rel_type)
                        logger.debug(f"Type '{rel_type}' already exists (race condition)")

                except Exception as e:
                    logger.error(f"✗ Failed to sync '{rel_type}': {e}")
                    result['failed'].append({'type': rel_type, 'error': str(e)})

            return result

        except Exception as e:
            logger.error(f"Failed to sync missing edge types: {e}")
            raise

    def get_edge_type_info(self, relationship_type: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a relationship type.

        Args:
            relationship_type: Relationship type name

        Returns:
            Dict with type details, or None if not found

        Example:
            >>> info = client.get_edge_type_info("IMPLIES")
            >>> print(f"Category: {info['category']}, Builtin: {info['is_builtin']}")

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
            Some metadata fields (description, added_by, etc.) not yet in graph
        """
        try:
            # Query VocabType node and category via relationship (Phase 3.3)
            query = """
            MATCH (v:VocabType {name: $type_name})
            OPTIONAL MATCH (v)-[:IN_CATEGORY]->(c:VocabCategory)
            RETURN v.name as relationship_type,
                   v.is_active as is_active,
                   v.is_builtin as is_builtin,
                   v.usage_count as usage_count,
                   v.direction_semantics as direction_semantics,
                   c.name as category
            """
            result = self._execute_cypher(query, {"type_name": relationship_type}, fetch_one=True)

            if not result:
                return None

            # Build info dict from graph data
            # Note: AGE stores PostgreSQL booleans as strings 't'/'f'
            # Handle missing/None values gracefully for usage_count
            usage_count_val = result.get('usage_count', 0)
            usage_count = 0 if usage_count_val is None else int(str(usage_count_val))

            info = {
                'relationship_type': str(result['relationship_type']),
                'is_active': str(result.get('is_active', 't')) == 't',
                'is_builtin': str(result.get('is_builtin', 'f')) == 't',
                'usage_count': usage_count,
                'category': str(result['category']) if result.get('category') else None,
                'direction_semantics': str(result['direction_semantics']) if result.get('direction_semantics') else None,  # ADR-049
                # Fields not yet migrated to graph (Phase 3.3)
                'description': None,
                'added_by': None,
                'added_at': None,
                'synonyms': None,
                'deprecation_reason': None,
                'embedding_model': None,
                'embedding_generated_at': None,
            }

            # Fetch ADR-047 category scoring fields from SQL (not yet in graph)
            try:
                conn = self.pool.getconn()
                try:
                    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                        cur.execute("""
                            SELECT category_source, category_confidence,
                                   category_scores, category_ambiguous
                            FROM kg_api.relationship_vocabulary
                            WHERE relationship_type = %s
                        """, (relationship_type,))
                        sql_result = cur.fetchone()
                        if sql_result:
                            info['category_source'] = sql_result.get('category_source')
                            info['category_confidence'] = sql_result.get('category_confidence')
                            info['category_scores'] = sql_result.get('category_scores')
                            info['category_ambiguous'] = sql_result.get('category_ambiguous')
                finally:
                    self.pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Failed to fetch category scoring fields for {relationship_type}: {e}")
                info['category_source'] = None
                info['category_confidence'] = None
                info['category_scores'] = None
                info['category_ambiguous'] = None

            # ⚠️ CRITICAL: Real-time edge counting required (ADR-044)
            # This MUST count actual edges - do NOT return cached/stale usage_count!
            # Grounding calculations depend on current edge state. See ADR-044 section on caching.
            try:
                count_query = f"""
                MATCH ()-[r:{relationship_type}]->()
                RETURN count(r) as edge_count
                """
                edge_result = self._execute_cypher(count_query, fetch_one=True)
                if edge_result:
                    info['edge_count'] = int(str(edge_result.get('edge_count', 0)))
                else:
                    info['edge_count'] = 0
            except Exception as e:
                logger.warning(f"Failed to count edges for {relationship_type}: {e}")
                info['edge_count'] = 0

            return info

        except Exception as e:
            logger.error(f"Failed to get edge type info from graph: {e}")
            return None

    def add_edge_type(
        self,
        relationship_type: str,
        category: str,
        description: Optional[str] = None,
        added_by: str = "system",
        is_builtin: bool = False,
        direction_semantics: Optional[str] = None,
        ai_provider = None,
        auto_categorize: bool = True
    ) -> bool:
        """
        Add a new relationship type to vocabulary with automatic embedding generation.

        Creates both:
        1. Row in kg_api.relationship_vocabulary table
        2. :VocabType node in the graph (ADR-048 Phase 3.2)

        ADR-047: If category is "llm_generated" and auto_categorize is True, will compute
        proper semantic category after generating embedding using probabilistic categorization.

        ADR-049: LLM determines direction_semantics based on frame of reference when creating
        new relationship types. Direction can be updated on first use if NULL.

        Args:
            relationship_type: Relationship type name (e.g., "AUTHORED_BY")
            category: Semantic category (or "llm_generated" for auto-categorization)
            description: Optional description
            added_by: Who added the type (username or "system")
            is_builtin: Whether this is a protected builtin type
            direction_semantics: Direction ("outward", "inward", "bidirectional", or None for LLM to decide)
            ai_provider: Optional AI provider for embedding generation (auto-generation if provided)
            auto_categorize: If True and category="llm_generated", compute proper category (ADR-047)

        Returns:
            True if added successfully, False if already exists

        Example:
            >>> success = client.add_edge_type("AUTHORED_BY", "llm_generated",
            ...                                 "LLM-generated relationship type",
            ...                                 "llm_extractor",
            ...                                 direction_semantics="outward",
            ...                                 ai_provider=provider,
            ...                                 auto_categorize=True)
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Add to vocabulary table (ADR-049: include direction_semantics)
                cur.execute("""
                    INSERT INTO kg_api.relationship_vocabulary
                        (relationship_type, description, category, added_by, is_builtin, is_active, direction_semantics)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (relationship_type) DO NOTHING
                    RETURNING relationship_type
                """, (relationship_type, description, category, added_by, is_builtin, direction_semantics))
                result = cur.fetchone()
                was_added = result is not None

                # Generate and store embedding if AI provider available and type was just added
                embedding_json = None
                model = None
                if was_added and ai_provider is not None:
                    try:
                        # Convert edge type to descriptive text (same logic as SynonymDetector)
                        descriptive_text = f"relationship: {relationship_type.lower().replace('_', ' ')}"

                        # Generate embedding
                        embedding_response = ai_provider.generate_embedding(descriptive_text)
                        embedding = embedding_response["embedding"]
                        model = embedding_response.get("model", "text-embedding-ada-002")

                        # Store embedding in table
                        embedding_json = json.dumps(embedding)
                        cur.execute("""
                            UPDATE kg_api.relationship_vocabulary
                            SET embedding = %s::jsonb,
                                embedding_model = %s,
                                embedding_generated_at = NOW()
                            WHERE relationship_type = %s
                        """, (embedding_json, model, relationship_type))

                        logger.debug(f"Generated embedding for vocabulary type '{relationship_type}' ({len(embedding)} dims)")

                        # ADR-047: Auto-categorize LLM-generated types
                        if auto_categorize and category == "llm_generated":
                            try:
                                import asyncio
                                from api.app.lib.vocabulary_categorizer import VocabularyCategorizer

                                # Create categorizer and compute category
                                categorizer = VocabularyCategorizer(self, ai_provider)

                                # Run async categorization in sync context
                                try:
                                    loop = asyncio.get_event_loop()
                                except RuntimeError:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                assignment = loop.run_until_complete(
                                    categorizer.assign_category(
                                        relationship_type,
                                        store=False,
                                        embedding=embedding  # Pass freshly-generated embedding
                                    )
                                )

                                # Update category in database
                                category = assignment.category
                                cur.execute("""
                                    UPDATE kg_api.relationship_vocabulary
                                    SET category = %s,
                                        category_source = 'computed',
                                        category_confidence = %s,
                                        category_scores = %s::jsonb,
                                        category_ambiguous = %s
                                    WHERE relationship_type = %s
                                """, (
                                    category,
                                    assignment.confidence,
                                    json.dumps(assignment.scores),
                                    assignment.ambiguous,
                                    relationship_type
                                ))

                                logger.info(
                                    f"  🎯 Auto-categorized '{relationship_type}' → {category} "
                                    f"(confidence: {assignment.confidence:.0%})"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to auto-categorize '{relationship_type}': {e}")
                                # Keep category as "llm_generated" if categorization fails

                    except Exception as e:
                        # Don't fail the entire operation if embedding generation fails
                        logger.warning(f"Failed to generate embedding for '{relationship_type}': {e}")

                # Create :VocabType node in graph (ADR-048 Phase 3.3 + ADR-049)
                # Creates both node and :IN_CATEGORY relationship
                if was_added:
                    try:
                        # Use MERGE to be idempotent (in case of partial failures)
                        # Phase 3.3: Create :IN_CATEGORY relationship to :VocabCategory node
                        # ADR-049: Add direction_semantics property
                        vocab_query = """
                            MERGE (v:VocabType {name: $name})
                            SET v.description = $description,
                                v.is_builtin = $is_builtin,
                                v.is_active = 't',
                                v.added_by = $added_by,
                                v.usage_count = 0,
                                v.direction_semantics = $direction_semantics
                            WITH v
                            MERGE (c:VocabCategory {name: $category})
                            MERGE (v)-[:IN_CATEGORY]->(c)
                            RETURN v.name as name
                        """
                        params = {
                            "name": relationship_type,
                            "category": category,
                            "description": description or "",
                            "is_builtin": 't' if is_builtin else 'f',
                            "added_by": added_by,
                            "direction_semantics": direction_semantics
                        }
                        self._execute_cypher(vocab_query, params)
                        direction_info = f", direction={direction_semantics}" if direction_semantics else ""
                        logger.debug(f"Created :VocabType node with :IN_CATEGORY->{category}{direction_info} for '{relationship_type}'")
                    except Exception as e:
                        logger.warning(f"Failed to create :VocabType node for '{relationship_type}': {e}")
                        # Don't fail the entire operation - table row was created successfully

                return was_added
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def update_edge_type(
        self,
        relationship_type: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        deprecation_reason: Optional[str] = None
    ) -> bool:
        """
        Update relationship type properties.

        Args:
            relationship_type: Type to update
            description: New description (optional)
            category: New category (optional)
            is_active: Active status (optional)
            deprecation_reason: Reason for deprecation (optional)

        Returns:
            True if updated successfully

        Example:
            >>> client.update_edge_type("OLD_TYPE", is_active=False, 
            ...                          deprecation_reason="Merged into NEW_TYPE")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Build dynamic UPDATE
                updates = []
                params = []
                
                if description is not None:
                    updates.append("description = %s")
                    params.append(description)
                
                if category is not None:
                    updates.append("category = %s")
                    params.append(category)
                
                if is_active is not None:
                    updates.append("is_active = %s")
                    params.append(is_active)
                
                if deprecation_reason is not None:
                    updates.append("deprecation_reason = %s")
                    params.append(deprecation_reason)
                
                if not updates:
                    return False
                
                params.append(relationship_type)
                
                cur.execute(f"""
                    UPDATE kg_api.relationship_vocabulary
                    SET {', '.join(updates)}
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, params)
                result = cur.fetchone()
                return result is not None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def merge_edge_types(
        self,
        deprecated_type: str,
        target_type: str,
        performed_by: str = "system"
    ) -> Dict[str, int]:
        """
        Merge one relationship type into another.

        This updates all edges using deprecated_type to use target_type instead,
        marks deprecated_type as inactive, and records the change in history.

        Args:
            deprecated_type: Type to deprecate and merge
            target_type: Type to preserve
            performed_by: Who performed the merge

        Returns:
            Dict with counts: {"edges_updated": N, "vocab_updated": 1}

        Example:
            >>> result = client.merge_edge_types("VERIFIES", "VALIDATES", "admin")
            >>> print(f"Updated {result['edges_updated']} edges")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # First, update all edges in the graph from deprecated_type to target_type
                # Note: AGE doesn't support dynamic relationship types in parameterized queries
                # We must use string interpolation for relationship types
                try:
                    # Delete existing edges of deprecated type and recreate with target type
                    # This is a two-step process since AGE doesn't support SET on relationship labels
                    merge_query = f"""
                    MATCH (c1)-[r:{deprecated_type}]->(c2)
                    CREATE (c1)-[new_r:{target_type}]->(c2)
                    SET new_r = properties(r)
                    DELETE r
                    RETURN count(new_r) as edges_updated
                    """

                    result = self._execute_cypher(merge_query, fetch_one=True)
                    edges_updated = int(str(result.get('edges_updated', 0))) if result else 0

                    logger.info(f"Merged {edges_updated} edges from {deprecated_type} to {target_type}")
                except Exception as e:
                    logger.error(f"Failed to update graph edges during merge: {e}")
                    # Continue with vocabulary update even if graph update fails
                    edges_updated = 0

                # Mark deprecated type as inactive in vocabulary
                cur.execute("""
                    UPDATE kg_api.relationship_vocabulary
                    SET is_active = FALSE,
                        deprecation_reason = %s
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, (f"Merged into {target_type}", deprecated_type))

                vocab_updated = 1 if cur.fetchone() else 0

                # Record in history
                cur.execute("""
                    INSERT INTO kg_api.vocabulary_history
                        (relationship_type, action, performed_by, target_type, reason)
                    VALUES (%s, 'merged', %s, %s, %s)
                """, (deprecated_type, performed_by, target_type, f"Merged into {target_type}"))

                return {
                    "edges_updated": edges_updated,
                    "vocab_updated": vocab_updated
                }
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_category_distribution(self) -> Dict[str, int]:
        """
        Get count of types per category.

        Returns:
            Dict mapping category name -> count

        Example:
            >>> distribution = client.get_category_distribution()
            >>> for category, count in distribution.items():
            ...     print(f"{category}: {count}")

        Note:
            ADR-048 Phase 3.3: Queries :IN_CATEGORY relationships to :VocabCategory nodes
        """
        try:
            # Phase 3.3: Query via :IN_CATEGORY relationships
            query = """
            MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
            WHERE v.is_active = 't'
            WITH c.name as category, count(v) as type_count
            RETURN category, type_count
            ORDER BY type_count DESC
            """
            results = self._execute_cypher(query)
            return {str(row['category']): int(str(row['type_count'])) for row in results}
        except Exception as e:
            logger.error(f"Failed to get category distribution from graph: {e}")
            return {}

    def store_embedding(
        self,
        relationship_type: str,
        embedding: List[float],
        model: str = "text-embedding-ada-002"
    ) -> bool:
        """
        Store embedding vector for relationship type.

        Args:
            relationship_type: Type to store embedding for
            embedding: Embedding vector
            model: Model used to generate embedding

        Returns:
            True if stored successfully

        Example:
            >>> embedding = [0.123, 0.456, ...]  # 1536 dimensions
            >>> client.store_embedding("VALIDATES", embedding)
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Store as JSONB array
                import json
                embedding_json = json.dumps(embedding)
                
                cur.execute("""
                    UPDATE kg_api.relationship_vocabulary
                    SET embedding = %s::jsonb,
                        embedding_model = %s,
                        embedding_generated_at = NOW()
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, (embedding_json, model, relationship_type))
                result = cur.fetchone()
                return result is not None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_embedding(self, relationship_type: str) -> Optional[List[float]]:
        """
        Get stored embedding for relationship type.

        Args:
            relationship_type: Type to get embedding for

        Returns:
            Embedding vector as list of floats, or None if not found

        Example:
            >>> embedding = client.get_embedding("VALIDATES")
            >>> if embedding:
            ...     print(f"Embedding dimension: {len(embedding)}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type = %s
                """, (relationship_type,))
                result = cur.fetchone()
                if result and result[0]:
                    import json
                    return json.loads(result[0])
                return None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_vocabulary_embedding(self, relationship_type: str) -> Optional[Dict[str, Any]]:
        """
        Get embedding with metadata for vocabulary type from database.

        Args:
            relationship_type: The edge type to get embedding for

        Returns:
            Dict with 'embedding' (list of floats) and 'embedding_model' (str),
            or None if not found or no embedding

        Example:
            >>> client = AGEClient()
            >>> data = client.get_vocabulary_embedding("VALIDATES")
            >>> if data:
            ...     print(f"Embedding dimensions: {len(data['embedding'])}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding, embedding_model
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type = %s
                      AND embedding IS NOT NULL
                """, (relationship_type,))
                result = cur.fetchone()

                if result and result[0]:
                    return {
                        'embedding': result[0],  # Already a Python list from JSONB
                        'embedding_model': result[1]
                    }
                return None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def update_vocabulary_embedding(
        self,
        relationship_type: str,
        embedding: List[float],
        embedding_model: str
    ) -> bool:
        """
        Update embedding for a vocabulary type in database.

        Wrapper around store_embedding() for consistency with get_vocabulary_embedding().

        Args:
            relationship_type: The edge type to update
            embedding: Embedding vector as list of floats
            embedding_model: Name of the model used (e.g., "text-embedding-ada-002")

        Returns:
            True if updated, False if type not found

        Example:
            >>> client = AGEClient()
            >>> success = client.update_vocabulary_embedding(
            ...     "VALIDATES",
            ...     embedding_vector,
            ...     "text-embedding-ada-002"
            ... )
        """
        return self.store_embedding(relationship_type, embedding, embedding_model)

