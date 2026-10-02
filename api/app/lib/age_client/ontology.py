"""
Ontology mixin for node CRUD and lifecycle management.

Ontology nodes (ADR-200) are first-class graph entities that organize
Source nodes via :SCOPED_BY edges. This mixin handles the foundational
operations: creation, retrieval, deletion, renaming, and lifecycle
state transitions (active/pinned/frozen).

Also includes the legacy source-level rename (pre-ADR-200) for
backward compatibility.
"""

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Iterator, Tuple

from psycopg2 import errors as psycopg2_errors

logger = logging.getLogger(__name__)


def concept_in_ontology(concept_var: str = "c", ontology: str = "$ontology") -> str:
    """Cypher predicate: the concept belongs to the named ontology.

    Two membership models coexist. Extraction-created concepts belong through
    their sources, (Concept)-[:APPEARS]->(Source)-[:SCOPED_BY]->(Ontology), and
    carry no ontology property. API- and batch-created concepts carry an
    `ontology` property. Filtering on either alone silently drops the other.

    Args:
        concept_var: Cypher variable bound to the concept.
        ontology: A Cypher expression for the name: a parameter ("$ontology")
            or an already-escaped quoted literal.
    """
    return (
        f"({concept_var}.ontology = {ontology} OR "
        f"EXISTS(({concept_var})-[:APPEARS]->(:Source)-[:SCOPED_BY]->(:Ontology {{name: {ontology}}})))"
    )


class OntologyLockTimeout(Exception):
    """The per-name ontology create lock was not acquired in time (#597).

    Raised by OntologyMixin.ontology_create_lock() when another session holds
    the lock past ONTOLOGY_CREATE_LOCK_TIMEOUT_MS.  @verified ded70046d
    """


class OntologyMixin:
    """Ontology node CRUD and lifecycle state management."""

    def rename_ontology(
        self,
        old_name: str,
        new_name: str
    ) -> Dict[str, int]:
        """
        Rename an ontology by updating all Source nodes' document property.

        Ontologies are logical groupings defined by the 'document' property on Source nodes.
        This method updates all Source nodes from old_name to new_name.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            Dictionary with count: {"sources_updated": N}

        Raises:
            ValueError: If old ontology doesn't exist or new ontology already exists
            Exception: If rename operation fails
        """
        # Check if old ontology exists
        check_old = """
        MATCH (s:Source {document: $old_name})
        RETURN count(s) as source_count
        """

        try:
            old_result = self._execute_cypher(
                check_old,
                params={"old_name": old_name},
                fetch_one=True
            )
            old_count = int(str(old_result.get("source_count", 0)))

            if old_count == 0:
                raise ValueError(f"Ontology '{old_name}' does not exist")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check old ontology existence: {e}")

        # Check if new ontology already exists
        check_new = """
        MATCH (s:Source {document: $new_name})
        RETURN count(s) as source_count
        """

        try:
            new_result = self._execute_cypher(
                check_new,
                params={"new_name": new_name},
                fetch_one=True
            )
            new_count = int(str(new_result.get("source_count", 0)))

            if new_count > 0:
                raise ValueError(f"Ontology '{new_name}' already exists")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check new ontology existence: {e}")

        # Rename ontology by updating all Source nodes
        rename_query = """
        MATCH (s:Source {document: $old_name})
        SET s.document = $new_name
        RETURN count(s) as updated_count
        """

        try:
            result = self._execute_cypher(
                rename_query,
                params={
                    "old_name": old_name,
                    "new_name": new_name
                },
                fetch_one=True
            )

            updated_count = int(str(result.get("updated_count", 0)))

            return {"sources_updated": updated_count}
        except Exception as e:
            raise Exception(f"Failed to rename ontology: {e}")

    # =========================================================================
    # Ontology Node Methods (ADR-200)
    # =========================================================================
    # Ontology nodes are first-class graph entities in the same embedding space
    # as concepts. They represent knowledge domains that organize Source nodes
    # via :SCOPED_BY edges. The s.document string on Source nodes is preserved
    # as a denormalized cache — :SCOPED_BY is the source of truth for new code.

    def create_ontology_node(
        self,
        ontology_id: str,
        name: str,
        description: str = "",
        embedding: Optional[List[float]] = None,
        search_terms: Optional[List[str]] = None,
        lifecycle_state: str = "active",
        creation_epoch: int = 0,
        created_by: Optional[str] = None,
        conn=None
    ) -> Dict[str, Any]:
        """
        Create an Ontology node in the graph.

        Args:
            ontology_id: Unique identifier (ont_<uuid>)
            name: Ontology name (matches s.document on Source nodes)
            description: What this knowledge domain covers
            embedding: 1536-dim vector in the same space as concepts
            search_terms: Alternative names for similarity matching
            lifecycle_state: 'active' | 'pinned' | 'frozen'
            creation_epoch: Global epoch when created
            created_by: Username of the creating user (ADR-200 Phase 2)
            conn: Optional caller-held connection (see _execute_cypher)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (o:Ontology {
            ontology_id: $ontology_id,
            name: $name,
            description: $description,
            embedding: $embedding,
            search_terms: $search_terms,
            lifecycle_state: $lifecycle_state,
            creation_epoch: $creation_epoch,
            created_by: $created_by
        })
        RETURN o
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "ontology_id": ontology_id,
                    "name": name,
                    "description": description,
                    "embedding": embedding,
                    "search_terms": search_terms if search_terms else [],
                    "lifecycle_state": lifecycle_state,
                    "creation_epoch": creation_epoch,
                    "created_by": created_by
                },
                fetch_one=True,
                conn=conn
            )
            if results:
                agtype_result = results.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Ontology node {name}: {e}")

    def get_ontology_node(self, name: str, conn=None) -> Optional[Dict[str, Any]]:
        """
        Get an Ontology node by name.

        Args:
            name: Ontology name
            conn: Optional caller-held connection (see _execute_cypher)

        Returns:
            Dictionary with node properties, or None if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True,
                conn=conn
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except Exception as e:
            logger.error(f"Failed to get Ontology node {name}: {e}")
            return None

    def list_ontology_nodes(self) -> List[Dict[str, Any]]:
        """
        List all Ontology nodes in the graph.

        Returns:
            List of dictionaries with ontology node properties
        """
        query = """
        MATCH (o:Ontology)
        RETURN o
        ORDER BY o.name
        """

        try:
            results = self._execute_cypher(query)
            ontologies = []
            for row in results:
                agtype_result = row.get('o')
                parsed = self._parse_agtype(agtype_result)
                if isinstance(parsed, dict) and 'properties' in parsed:
                    ontologies.append(parsed['properties'])
            return ontologies
        except Exception as e:
            logger.error(f"Failed to list Ontology nodes: {e}")
            return []

    def delete_ontology_node(self, name: str) -> bool:
        """
        Delete an Ontology node and its edges (SCOPED_BY, etc).

        Does not delete Source nodes — they retain their s.document property.
        Only removes the :Ontology node and edges connected to it.

        Args:
            name: Ontology name

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        DETACH DELETE o
        RETURN count(*) as deleted
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True
            )
            deleted = int(str(result.get("deleted", 0))) if result else 0
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to delete Ontology node {name}: {e}")
            return False

    def rename_ontology_node(self, old_name: str, new_name: str) -> bool:
        """
        Rename an Ontology node (updates the name property).

        This is called alongside rename_ontology() which updates s.document
        on Source nodes. Both must be kept in sync.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            True if renamed, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $old_name})
        SET o.name = $new_name
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"old_name": old_name, "new_name": new_name},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to rename Ontology node {old_name} -> {new_name}: {e}")
            return False

    def create_scoped_by_edge(self, source_id: str, ontology_name: str) -> bool:
        """
        Create a :SCOPED_BY edge from a Source to an Ontology node.

        Uses MERGE for idempotency — safe to call multiple times.

        Args:
            source_id: Source node identifier
            ontology_name: Ontology node name

        Returns:
            True if edge exists (created or already present)
        """
        query = """
        MATCH (s:Source {source_id: $source_id})
        MATCH (o:Ontology {name: $ontology_name})
        MERGE (s)-[:SCOPED_BY]->(o)
        RETURN s.source_id as source_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "source_id": source_id,
                    "ontology_name": ontology_name
                },
                fetch_one=True
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Failed to create SCOPED_BY edge {source_id} -> {ontology_name}: {e}")
            return False

    # Advisory-lock namespace for ontology creation (two-key form: namespace,
    # hashtext(name)). Keeps the lock space separate from other advisory locks.
    _ONTOLOGY_CREATE_LOCK_NS = 200

    # How long a caller waits for the per-name create lock before giving up.
    # Bounds the time a stalled holder can pin waiters (and their pooled
    # connections) instead of letting them block indefinitely (#597).
    ONTOLOGY_CREATE_LOCK_TIMEOUT_MS = 10_000

    @contextmanager
    def ontology_create_lock(self, name: str) -> Iterator[Any]:
        """
        Hold the per-name ontology creation lock for the duration of the block.

        Apache AGE has no uniqueness constraints, so every check-then-CREATE
        of an :Ontology node must run under this lock or two callers can both
        see "missing" and both CREATE (#588, #597). Yields a dedicated pooled
        connection that holds a session-level PostgreSQL advisory lock keyed
        on (namespace, hashtext(name)); the re-check and CREATE must run on
        that connection and be committed before the block exits so the next
        waiter's re-check sees the node.

        The wait is bounded by ``SET LOCAL lock_timeout`` (scoped to the
        acquiring transaction, so it never leaks to the pool or to the
        statements run under the lock). A session lock is used rather than an
        xact lock because _execute_cypher may roll back on AGE label races,
        which would drop an xact lock. A connection that might still hold the
        lock is closed rather than returned to the pool.
        @verified ded70046d

        Args:
            name: Ontology name to serialize creation on

        Yields:
            The psycopg2 connection holding the lock

        Raises:
            OntologyLockTimeout: If the lock is not acquired within
                ONTOLOGY_CREATE_LOCK_TIMEOUT_MS
        """
        conn = self.pool.getconn()
        discard_conn = True
        try:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SET LOCAL lock_timeout = %s",
                        (f"{self.ONTOLOGY_CREATE_LOCK_TIMEOUT_MS}ms",),
                    )
                    cur.execute(
                        "SELECT pg_advisory_lock(%s, hashtext(%s))",
                        (self._ONTOLOGY_CREATE_LOCK_NS, name),
                    )
                conn.commit()
            except psycopg2_errors.LockNotAvailable as e:
                # Nothing was acquired; the connection is still discarded
                # (discard_conn stays True) since its transaction aborted.
                raise OntologyLockTimeout(
                    f"Timed out after {self.ONTOLOGY_CREATE_LOCK_TIMEOUT_MS}ms "
                    f"waiting for the create lock on ontology '{name}'"
                ) from e
            try:
                yield conn
            finally:
                try:
                    conn.rollback()
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT pg_advisory_unlock(%s, hashtext(%s))",
                            (self._ONTOLOGY_CREATE_LOCK_NS, name),
                        )
                    conn.commit()
                    discard_conn = False
                except Exception as e:
                    logger.warning(f"Failed to release ontology create lock for {name}: {e}")
        finally:
            self.pool.putconn(conn, close=discard_conn)

    def create_ontology_if_absent(
        self,
        name: str,
        description: str = "",
        embedding: Optional[List[float]] = None,
        lifecycle_state: str = "active",
        creation_epoch: Optional[int] = None,
        created_by: Optional[str] = None,
        ontology_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Atomically create an Ontology node unless one with that name exists.

        The single locked check-then-CREATE path every caller that creates
        :Ontology nodes should use (ingestion, POST /ontology, annealing
        CLEAVE/MERGE/primordial pool). The existence check is repeated under
        ontology_create_lock() and the CREATE is committed before the lock is
        released, so concurrent callers for one name yield one node. Callers
        decide what "already existed" means for them (reuse it, 409, fail).
        @verified ded70046d

        Args:
            name: Ontology name
            description: Description for a newly created node
            embedding: Optional embedding for a newly created node
            lifecycle_state: Lifecycle state for a newly created node
            creation_epoch: Epoch to stamp; None reads the current
                document_ingestion_counter under the lock (0 if unavailable)
            created_by: Username or worker that created the node
            ontology_id: Identifier for a new node; defaults to ont_<uuid4>

        Returns:
            (node, created): the existing or new node's properties, and True
            only if this call created it

        Raises:
            OntologyLockTimeout: If the create lock could not be acquired
            Exception: If the CREATE fails (the lock is still released)
        """
        with self.ontology_create_lock(name) as conn:
            existing = self.get_ontology_node(name, conn=conn)
            if existing:
                return existing, False

            if creation_epoch is None:
                creation_epoch = 0
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT counter FROM graph_metrics WHERE metric_name = 'document_ingestion_counter'"
                        )
                        row = cur.fetchone()
                        if row:
                            creation_epoch = row[0] or 0
                except Exception:
                    conn.rollback()  # Default to 0 if metrics unavailable

            created = self.create_ontology_node(
                ontology_id=ontology_id or f"ont_{uuid.uuid4()}",
                name=name,
                description=description,
                embedding=embedding,
                lifecycle_state=lifecycle_state,
                creation_epoch=creation_epoch,
                created_by=created_by,
                conn=conn,
            )
            # Commit before the lock is released so the next waiter's
            # re-check sees the node.
            conn.commit()
            return created, True

    def ensure_ontology_exists(self, name: str, description: str = "", created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create an Ontology node. Used by ingestion pipeline to ensure
        the target ontology exists before creating Source nodes.

        Checks without the lock first (the common case is that the node
        exists), then falls back to create_ontology_if_absent(), which
        re-checks and creates under the per-name advisory lock (#588).
        @verified ded70046d

        Args:
            name: Ontology name
            description: Optional description for new ontologies
            created_by: Username of the creating user (ADR-200 Phase 2)

        Returns:
            Dictionary with ontology node properties

        Raises:
            OntologyLockTimeout: If the create lock could not be acquired
        """
        # Fast path: no lock needed when the node already exists.
        existing = self.get_ontology_node(name)
        if existing:
            return existing

        node, _created = self.create_ontology_if_absent(
            name, description=description, created_by=created_by
        )
        return node

    def update_ontology_lifecycle(
        self,
        name: str,
        new_state: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update the lifecycle_state of an Ontology node.

        Args:
            name: Ontology name
            new_state: Target state ('active', 'pinned', or 'frozen')

        Returns:
            Dictionary with updated node properties, or None if not found

        Raises:
            ValueError: If new_state is not a valid lifecycle state
        """
        valid_states = {"active", "pinned", "frozen"}
        if new_state not in valid_states:
            raise ValueError(f"Invalid lifecycle state '{new_state}'. Must be one of: {valid_states}")

        query = """
        MATCH (o:Ontology {name: $name})
        SET o.lifecycle_state = $new_state
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "new_state": new_state},
                fetch_one=True
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update Ontology lifecycle for {name}: {e}")
            return None

    def is_ontology_frozen(self, name: str) -> bool:
        """
        Check if an ontology is in the 'frozen' lifecycle state.

        Returns False for nonexistent ontologies (they have no protection).

        Args:
            name: Ontology name

        Returns:
            True if the ontology exists and is frozen, False otherwise
        """
        node = self.get_ontology_node(name)
        if node is None:
            return False
        return node.get("lifecycle_state") == "frozen"

    def update_ontology_embedding(
        self,
        name: str,
        embedding: List[float]
    ) -> bool:
        """
        Update the embedding on an existing Ontology node.

        Args:
            name: Ontology name
            embedding: 1536-dim vector

        Returns:
            True if updated, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.embedding = $embedding
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "embedding": embedding},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to update Ontology embedding for {name}: {e}")
            return False

