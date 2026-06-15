"""
kg-backup/2 import path — :class:`DataImporter` (clone/merge writer) + epoch primitives.

Writes a kg-backup/2 object into Apache AGE under clone / merge / restamp
semantics (ADR-102 §2) plus the P5 / P5-faithful epoch machinery. Split out of
the former monolithic ``api/lib/serialization.py`` (ADR-102 P6d).
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

from api.app.lib.age_client import AGEClient

from ..console import Console
from .format import KgBackupV2Reader


def _execute_with_age_retry(client, query, params=None, *, fetch_one=False, max_retries=5):
    """Execute a Cypher statement with AGE's first-use + MVCC retry backoff.

    Apache AGE lazily creates the backing table the first time a label/edge-type
    is used; concurrent worker threads racing that creation surface as
    ``relation "..." already exists``. Concurrent MERGEs on the same node/edge
    surface as ``Entity failed to be updated`` (MVCC). Both are transient — retry
    with linear backoff. Lifted from the legacy importer so the single kg-backup/2
    clone writer shares the same proven path (ADR-102 P3).
    """
    import time
    import re
    for attempt in range(max_retries + 1):
        try:
            return client._execute_cypher(query, params=params, fetch_one=fetch_one)
        except Exception as e:
            es = str(e)
            # Only genuinely transient AGE conditions are retried: first-use label
            # table creation racing across threads, and MVCC write conflicts. A
            # malformed SET is deterministic and must surface, not be masked.
            transient = (
                "already exists" in es
                or "Entity failed to be updated" in es
            )
            if transient and attempt < max_retries:
                m = re.search(r'relation "(\w+)" already exists', es)
                if m:
                    Console.info(f"  Initializing AGE label: {m.group(1)}")
                time.sleep(0.1 * (attempt + 1))
                continue
            raise


def _progress(progress_callback, stage, current, total, every=10):
    """Emit console + job progress for an import stage every ``every`` items."""
    if total and (current % every == 0 or current == total):
        Console.progress(current, total, stage.capitalize())
        if progress_callback:
            progress_callback(stage, current, total, (current / total) * 100)


def _run_parallel(items, fn, max_workers):
    """Submit ``fn(item)`` for every item to a thread pool; raise the first error."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fn, it) for it in items]
        for future in as_completed(futures):
            future.result()


class DataImporter:
    """Import a kg-backup/2 object into the graph (ADR-102 P3).

    Single-path: consumes the one backup model via :class:`KgBackupV2Reader`. The
    clone writer (:meth:`_import_kg_backup_v2`) preserves app-assigned ids 1:1, which
    is correct for an empty target. Adjacent-mode ID remapping and the merge modes
    (idempotent / adjacent / integration) are added in P4.
    """

    _INSTANCE_Q = """
        MATCH (s:Source {source_id: $source_id})
        MERGE (i:Instance {instance_id: $instance_id})
        SET i.quote = $quote,
            i.created_at_event_id = $created_at_event_id
        MERGE (i)-[:FROM_SOURCE]->(s)
    """

    # Reconstruct the M:N EVIDENCED_BY edge and the derived APPEARS edge by joining
    # the concept to the instance's already-created source (ADR-102 §5.3.1).
    _EVIDENCE_Q = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (i:Instance {instance_id: $instance_id})-[:FROM_SOURCE]->(s:Source)
        MERGE (c)-[:EVIDENCED_BY]->(i)
        MERGE (c)-[:APPEARS]->(s)
    """

    @staticmethod
    def validate_backup(backup_data: Dict[str, Any]) -> bool:
        """Validate that ``backup_data`` is a readable kg-backup object.

        Constructs a :class:`KgBackupV2Reader`, which negotiates the format and
        refuses anything that is not ``kg-backup/<=2``. Raises ``ValueError`` on
        failure; returns ``True`` when readable. The thorough field-level oracle
        lives in the offline validator (``scripts/development/lint/lint_backup.py``).
        """
        KgBackupV2Reader(backup_data)
        return True

    @staticmethod
    def import_backup(client: AGEClient, backup_data: Dict[str, Any],
                      overwrite_existing: bool = False,
                      progress_callback: Optional[callable] = None,
                      max_workers: int = 2,
                      epoch_restamp: Optional[Dict[str, int]] = None,
                      event_id_map: Optional[Dict[int, int]] = None) -> Dict[str, int]:
        """Import a kg-backup/2 object — the single backup model's front-door.

        Args:
            client: AGEClient instance
            backup_data: Parsed kg-backup/2 object (``{header, bulk}``)
            overwrite_existing: If True, update existing nodes; if False, preserve them
            progress_callback: Optional callback(stage, current, total, percent)
            max_workers: Parallel workers for instances/evidence/relationships
            epoch_restamp: ADR-102 P5 epoch-simple restamp. When provided,
                ``{"event_id": int, "concept_epoch": int}`` overrides the carried
                per-record epoch stamps so every restored node points at LOCAL
                clocks: instances' ``created_at_event_id`` → the one restore
                ``event_id`` (a real ``graph_epochs`` row in this target — carried
                ids would dangle), and concepts' ``created_at_epoch`` /
                ``last_seen_epoch`` → the target's current ``concept_epoch``
                (a separate counter; carrying a foreign value future-dates concept
                vitality). When None the carried stamps are preserved verbatim
                (faithful — used by checkpoint rollback and P5-faithful replay).
            event_id_map: ADR-102 P5-faithful replay. When provided, each
                instance's carried ``created_at_event_id`` is remapped through this
                ``{old_event_id: new_event_id}`` table (the freshly-minted local
                epoch ids from the faithful replay). Mutually exclusive with
                ``epoch_restamp`` (simple collapses to one id; faithful preserves
                the per-event structure). Concepts are NOT remapped here — faithful
                carries their original epochs and the worker sets the counter.

        Returns:
            Stats: vocabulary_imported, concepts_created, sources_created,
            instances_created, relationships_created.
        """
        reader = KgBackupV2Reader(backup_data)
        return DataImporter._import_kg_backup_v2(
            client, reader,
            overwrite_existing=overwrite_existing,
            progress_callback=progress_callback,
            max_workers=max_workers,
            epoch_restamp=epoch_restamp,
            event_id_map=event_id_map,
        )

    @staticmethod
    def _import_kg_backup_v2(client: AGEClient, reader: "KgBackupV2Reader", *,
                             overwrite_existing: bool = False,
                             progress_callback: Optional[callable] = None,
                             max_workers: int = 2,
                             epoch_restamp: Optional[Dict[str, int]] = None,
                             event_id_map: Optional[Dict[int, int]] = None) -> Dict[str, int]:
        """Clone-path writer: import normalized records, preserving ids 1:1.

        Order matters: vocabulary (before relationships, ADR-603) → concepts →
        sources → instances (+FROM_SOURCE) → evidence (EVIDENCED_BY + derived
        APPEARS) → relationships. Clone preserves ids, so edge ``learned_id`` needs
        no remap here (that is P4 adjacent mode).

        ``epoch_restamp`` (P5 epoch-simple) / ``event_id_map`` (P5-faithful) control
        instance epoch stamping — see ``import_backup`` for the contract.
        """
        restamp_event_id = epoch_restamp.get("event_id") if epoch_restamp else None
        restamp_concept_epoch = epoch_restamp.get("concept_epoch") if epoch_restamp else None
        stats = {
            "vocabulary_imported": 0,
            "concepts_created": 0,
            "sources_created": 0,
            "ontologies_created": 0,
            "documents_created": 0,
            "instances_created": 0,
            "relationships_created": 0,
        }

        vocab = reader.vocabulary()
        if vocab:
            Console.info("Importing vocabulary...")
            DataImporter._import_vocabulary(client, vocab, progress_callback)
            stats["vocabulary_imported"] = len(vocab)

        concepts = list(reader.concepts())
        Console.info("Importing concepts...")
        DataImporter._import_concepts(client, concepts, overwrite_existing, progress_callback,
                                      restamp_epoch=restamp_concept_epoch)
        stats["concepts_created"] = len(concepts)

        sources = list(reader.sources())
        Console.info("Importing sources...")
        DataImporter._import_sources(client, sources, progress_callback)
        stats["sources_created"] = len(sources)

        # Ontologies after concepts + sources: SCOPED_BY needs sources, ANCHORED_BY
        # needs concepts (both already imported above). Absent in pre-stream backups.
        ontologies = list(reader.ontologies())
        if ontologies:
            Console.info(f"Importing {len(ontologies)} ontologies (+SCOPED_BY/ANCHORED_BY)...")
            stats["ontologies_created"] = DataImporter._import_ontologies(
                client, ontologies, reader.scoped_by(), reader.anchored_by(), progress_callback
            )

        # DocumentMeta after sources: HAS_SOURCE needs the Source nodes (imported
        # above). Authoritative restore of the catalog document tier (issue #505).
        # Absent in pre-stream backups → falls back to the restore-worker's
        # Garage-hashed reconstruction.
        documents = list(reader.documents())
        if documents:
            Console.info(f"Importing {len(documents)} documents (+HAS_SOURCE)...")
            stats["documents_created"] = DataImporter._import_documents(
                client, documents, reader.has_source(), progress_callback
            )

        instances = list(reader.instances())
        Console.info("Importing instances...")
        DataImporter._import_instances(client, instances, progress_callback, max_workers,
                                       restamp_event_id=restamp_event_id,
                                       event_id_map=event_id_map)
        stats["instances_created"] = len(instances)

        evidence_map = reader.evidence_by_instance()
        pairs = [(cid, iid) for iid, cids in evidence_map.items() for cid in cids]
        if pairs:
            Console.info(f"Reconstructing {len(pairs)} evidence links (EVIDENCED_BY + APPEARS)...")
            DataImporter._import_evidence(client, pairs, max_workers)

        rels = list(reader.relationships())
        Console.info("Importing relationships...")
        stats["relationships_created"] = DataImporter._import_relationships(
            client, rels, progress_callback, max_workers
        )

        return stats

    @staticmethod
    def _import_vocabulary(client: AGEClient, vocabulary: List[Dict[str, Any]],
                           progress_callback: Optional[callable] = None) -> None:
        """Import relationship vocabulary: SQL rows + :VocabType graph nodes.

        Ported from the original importer (ADR-603 / ADR-606): upserts
        kg_api.relationship_vocabulary, then MERGEs the :VocabType / :VocabCategory
        nodes. Shared by the single import path.
        """
        total_vocab = len(vocabulary)
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for i, entry in enumerate(vocabulary):
                    current = i + 1
                    Console.progress(current, total_vocab, "Vocabulary")
                    if progress_callback and current % 10 == 0:
                        progress_callback("vocabulary", current, total_vocab,
                                          (current / total_vocab) * 100)

                    synonyms_array = entry.get('synonyms') if entry.get('synonyms') else None
                    embedding_json = json.dumps(entry.get('embedding')) if entry.get('embedding') else None

                    cur.execute("""
                        INSERT INTO kg_api.relationship_vocabulary
                            (relationship_type, description, category, added_by, added_at,
                             usage_count, is_active, is_builtin, synonyms, deprecation_reason,
                             embedding_model, embedding_generated_at, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (relationship_type) DO UPDATE SET
                            description = EXCLUDED.description,
                            category = EXCLUDED.category,
                            added_by = EXCLUDED.added_by,
                            added_at = EXCLUDED.added_at,
                            usage_count = EXCLUDED.usage_count,
                            is_active = EXCLUDED.is_active,
                            is_builtin = EXCLUDED.is_builtin,
                            synonyms = EXCLUDED.synonyms,
                            deprecation_reason = EXCLUDED.deprecation_reason,
                            embedding_model = EXCLUDED.embedding_model,
                            embedding_generated_at = EXCLUDED.embedding_generated_at,
                            embedding = EXCLUDED.embedding
                    """, (
                        entry.get('relationship_type'),
                        entry.get('description'),
                        entry.get('category'),
                        entry.get('added_by'),
                        entry.get('added_at'),
                        entry.get('usage_count', 0),
                        entry.get('is_active', True),
                        entry.get('is_builtin', False),
                        synonyms_array,
                        entry.get('deprecation_reason'),
                        entry.get('embedding_model'),
                        entry.get('embedding_generated_at'),
                        embedding_json
                    ))
            conn.commit()
        finally:
            client.pool.putconn(conn)

        # Create :VocabType graph nodes (ADR-606) after the SQL import.
        Console.info("  Creating vocabulary graph nodes...")
        for i, entry in enumerate(vocabulary):
            relationship_type = entry.get('relationship_type')
            try:
                vocab_query = """
                    MERGE (v:VocabType {name: $name})
                    SET v.description = $description,
                        v.is_builtin = $is_builtin,
                        v.is_active = $is_active,
                        v.added_by = $added_by,
                        v.usage_count = $usage_count,
                        v.direction_semantics = $direction_semantics
                    WITH v
                    MERGE (c:VocabCategory {name: $category})
                    MERGE (v)-[:IN_CATEGORY]->(c)
                    RETURN v.name as name
                """
                params = {
                    "name": relationship_type,
                    "category": entry.get('category', 'unknown'),
                    "description": entry.get('description', ''),
                    "is_builtin": 't' if entry.get('is_builtin', False) else 'f',
                    "is_active": 't' if entry.get('is_active', True) else 'f',
                    "added_by": entry.get('added_by', 'system'),
                    "usage_count": entry.get('usage_count', 0),
                    "direction_semantics": entry.get('direction_semantics'),
                }
                client._execute_cypher(vocab_query, params)
                if (i + 1) % 10 == 0:
                    Console.progress(i + 1, total_vocab, "Graph nodes")
            except Exception as e:
                # SQL data is already imported — log but don't fail the restore.
                Console.warning(f"  Failed to create graph node for '{relationship_type}': {e}")

        if progress_callback and total_vocab > 0:
            progress_callback("vocabulary", total_vocab, total_vocab, 100.0)

    @staticmethod
    def _import_concepts(client: AGEClient, concepts: List[Dict[str, Any]],
                         overwrite_existing: bool, progress_callback,
                         restamp_epoch: Optional[int] = None) -> None:
        """MERGE concepts, carrying the ADR-102 §3 epoch stamps.

        ``restamp_epoch`` (ADR-102 P5 epoch-simple): when set, override the carried
        ``created_at_epoch`` / ``last_seen_epoch`` with this target-local concept
        epoch (a value in the ``document_ingestion_counter`` space). Carried foreign
        values future-date concept vitality, so a restore into any non-pristine
        target restamps to "now".
        """
        total = len(concepts)
        if overwrite_existing:
            query = """
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.label = $label,
                    c.search_terms = $search_terms,
                    c.embedding = $embedding,
                    c.created_at_epoch = $created_at_epoch,
                    c.last_seen_epoch = $last_seen_epoch
            """
        else:
            # Preserve an existing concept's properties (AGE has no ON CREATE SET).
            query = """
                OPTIONAL MATCH (existing:Concept {concept_id: $concept_id})
                WITH existing
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.label = CASE WHEN existing IS NULL THEN $label ELSE c.label END,
                    c.search_terms = CASE WHEN existing IS NULL THEN $search_terms ELSE c.search_terms END,
                    c.embedding = CASE WHEN existing IS NULL THEN $embedding ELSE c.embedding END,
                    c.created_at_epoch = CASE WHEN existing IS NULL THEN $created_at_epoch ELSE c.created_at_epoch END,
                    c.last_seen_epoch = CASE WHEN existing IS NULL THEN $last_seen_epoch ELSE c.last_seen_epoch END
            """
        for i, c in enumerate(concepts):
            params = {
                "concept_id": c["concept_id"],
                "label": c.get("label"),
                "search_terms": c.get("search_terms", []),
                "embedding": c.get("embedding", []),
                "created_at_epoch": c.get("created_at_epoch"),
                "last_seen_epoch": c.get("last_seen_epoch"),
            }
            if restamp_epoch is not None:
                params["created_at_epoch"] = restamp_epoch
                params["last_seen_epoch"] = restamp_epoch
            _execute_with_age_retry(client, query, params)
            _progress(progress_callback, "concepts", i + 1, total)

    @staticmethod
    def _import_sources(client: AGEClient, sources: List[Dict[str, Any]],
                        progress_callback) -> None:
        """MERGE sources, including optional Garage/media keys when present (ADR-307)."""
        total = len(sources)
        for i, s in enumerate(sources):
            query = """
                MERGE (s:Source {source_id: $source_id})
                SET s.document = $document,
                    s.file_path = $file_path,
                    s.paragraph = $paragraph,
                    s.full_text = $full_text
            """
            params = {
                "source_id": s["source_id"],
                "document": s.get("document"),
                "file_path": s.get("file_path"),
                "paragraph": s.get("paragraph"),
                "full_text": s.get("full_text"),
            }
            if s.get("garage_key"):
                query = query.rstrip() + ",\n                    s.garage_key = $garage_key"
                params["garage_key"] = s["garage_key"]
            if s.get("content_type"):
                query = query.rstrip() + ",\n                    s.content_type = $content_type"
                params["content_type"] = s["content_type"]
            if s.get("storage_key"):
                query = query.rstrip() + ",\n                    s.storage_key = $storage_key"
                params["storage_key"] = s["storage_key"]
            _execute_with_age_retry(client, query, params)
            _progress(progress_callback, "sources", i + 1, total, every=1)

    @staticmethod
    def _import_ontologies(client: AGEClient,
                           ontologies: List[Dict[str, Any]],
                           scoped_by: List[Dict[str, Any]],
                           anchored_by: List[Dict[str, Any]],
                           progress_callback) -> int:
        """MERGE :Ontology nodes and their SCOPED_BY / ANCHORED_BY edges.

        Clone-faithful and idempotent (MERGE + SET), so re-running a restore
        re-converges. Nodes are written first so the edge MERGEs can match both
        endpoints; an edge whose other endpoint (source/concept) is absent simply
        matches nothing and is skipped — no dangling edge is created.

        Identity is keyed on ``name``, NOT ``ontology_id`` — ``name`` is the
        natural key the rest of the system uses (``ensure_ontology_exists`` /
        ``get_ontology_node`` / both edge MATCHes key on it, and the SCOPED_BY /
        ANCHORED_BY edges below cite ontologies by name). MERGE-on-name keeps a
        single node per name across merge modes (where ``ontology_id`` is carried
        verbatim and could otherwise collide-by-id or, when null, collapse every
        id-less ontology into one node); ``ontology_id`` is restored as a property.

        Returns the number of ontology nodes written.
        """
        total = len(ontologies)
        node_query = """
            MERGE (o:Ontology {name: $name})
            SET o.ontology_id = $ontology_id,
                o.description = $description,
                o.embedding = $embedding,
                o.search_terms = $search_terms,
                o.lifecycle_state = $lifecycle_state,
                o.creation_epoch = $creation_epoch,
                o.created_by = $created_by
        """
        for i, o in enumerate(ontologies):
            params = {
                "ontology_id": o.get("ontology_id"),
                "name": o.get("name"),
                "description": o.get("description", ""),
                "embedding": o.get("embedding", []),
                "search_terms": o.get("search_terms", []),
                "lifecycle_state": o.get("lifecycle_state", "active"),
                "creation_epoch": o.get("creation_epoch"),
                "created_by": o.get("created_by"),
            }
            _execute_with_age_retry(client, node_query, params)
            _progress(progress_callback, "ontologies", i + 1, total, every=1)

        # SCOPED_BY: (Source)-[:SCOPED_BY]->(Ontology), keyed by ontology name.
        scoped_query = """
            MATCH (s:Source {source_id: $source_id}), (o:Ontology {name: $ontology})
            MERGE (s)-[:SCOPED_BY]->(o)
        """
        for edge in scoped_by:
            _execute_with_age_retry(client, scoped_query, {
                "source_id": edge.get("source_id"),
                "ontology": edge.get("ontology"),
            })

        # ANCHORED_BY: (Ontology)-[:ANCHORED_BY]->(Concept), founding-concept provenance.
        anchored_query = """
            MATCH (o:Ontology {name: $ontology}), (c:Concept {concept_id: $concept_id})
            MERGE (o)-[:ANCHORED_BY]->(c)
        """
        for edge in anchored_by:
            _execute_with_age_retry(client, anchored_query, {
                "ontology": edge.get("ontology"),
                "concept_id": edge.get("concept_id"),
            })

        return total

    # DocumentMeta properties carried in the backup, besides the document_id MERGE
    # key. Only non-None values are SET so a restore never wipes a field that the
    # backup happens not to carry (mirrors create_document_meta's build).
    _DOCUMENT_PROPS = (
        "content_hash", "ontology", "filename", "garage_key", "content_type",
        "source_count", "ingested_at", "ingested_by", "job_id", "file_path",
        "source_type", "hostname", "storage_key",
    )

    @staticmethod
    def _import_documents(client: AGEClient,
                          documents: List[Dict[str, Any]],
                          has_source: List[Dict[str, Any]],
                          progress_callback) -> int:
        """MERGE :DocumentMeta nodes and their HAS_SOURCE edges (issue #505).

        Authoritative restore of the catalog document tier. Idempotent and keyed on
        the canonical ``document_id`` (the full ``sha256:``-prefixed digest), carried
        **verbatim** from the backup — never recomputed. MERGE-on-``document_id``
        means restoring the same backup twice, or restoring a document already
        present in the target, converges to a single node (robustness requirement #1:
        no duplicate DocumentMeta). ``content_hash``/``garage_key`` are likewise
        carried verbatim, so byte-identical content keeps its deterministic Garage
        key and re-ingest dedup still short-circuits (requirement #2).

        Nodes are written first so the HAS_SOURCE MERGEs can match both endpoints;
        an edge whose Source endpoint is absent matches nothing and is skipped (no
        dangling edge). Returns the number of DocumentMeta nodes written.
        """
        total = len(documents)
        for i, d in enumerate(documents):
            document_id = d.get("document_id")
            if not document_id:
                continue
            # Build SET only from carried, non-None props (don't wipe on restore).
            set_props = {k: d[k] for k in DataImporter._DOCUMENT_PROPS
                         if d.get(k) is not None}
            set_clause = ", ".join(f"d.{k} = ${k}" for k in set_props)
            node_query = "MERGE (d:DocumentMeta {document_id: $document_id})"
            if set_clause:
                node_query += f" SET {set_clause}"
            _execute_with_age_retry(client, node_query, {"document_id": document_id, **set_props})
            _progress(progress_callback, "documents", i + 1, total, every=1)

        # HAS_SOURCE: (DocumentMeta)-[:HAS_SOURCE]->(Source), keyed on document_id.
        has_source_query = """
            MATCH (d:DocumentMeta {document_id: $document_id}), (s:Source {source_id: $source_id})
            MERGE (d)-[:HAS_SOURCE]->(s)
        """
        for edge in has_source:
            _execute_with_age_retry(client, has_source_query, {
                "document_id": edge.get("document_id"),
                "source_id": edge.get("source_id"),
            })

        return total

    @staticmethod
    def _import_instances(client: AGEClient, instances: List[Dict[str, Any]],
                          progress_callback, max_workers: int,
                          restamp_event_id: Optional[int] = None,
                          event_id_map: Optional[Dict[int, int]] = None) -> None:
        """MERGE instances and their FROM_SOURCE edges in parallel.

        Instance ``created_at_event_id`` resolution (mutually exclusive):
        - ``event_id_map`` (P5-faithful): remap the carried id through the
          {old: new} faithful-replay table (``.get(old, old)`` — an unmapped or
          null carried id passes through).
        - ``restamp_event_id`` (P5 epoch-simple): override every instance with this
          one restore event id (carried ids would dangle — the simple path does not
          replay ``graph_epochs``).
        - neither: carry verbatim (checkpoint rollback).

        Faithful safety: a carried id absent from ``event_id_map`` (an instance
        referencing an event the backup did not carry) is stamped NULL rather than
        passed through — a passed-through foreign id would dangle against the target's
        fresh epoch sequence (reads unpredictably); NULL reads stale, which is safe.
        """
        total = len(instances)
        lock = threading.Lock()
        done = {"n": 0}
        unmapped = {"n": 0}

        def _event_id(inst):
            carried = inst.get("created_at_event_id")
            if event_id_map is not None:
                if carried is None:
                    return None
                mapped = event_id_map.get(carried)
                if mapped is None:
                    unmapped["n"] += 1  # tracked under `lock` in work()
                    return None
                return mapped
            if restamp_event_id is not None:
                return restamp_event_id
            return carried

        def work(inst):
            with lock:
                eid = _event_id(inst)
            params = {
                "instance_id": inst["instance_id"],
                "quote": inst.get("quote", ""),
                "source_id": inst["source_id"],
                "created_at_event_id": eid,
            }
            _execute_with_age_retry(client, DataImporter._INSTANCE_Q, params)
            with lock:
                done["n"] += 1
                _progress(progress_callback, "instances", done["n"], total)

        _run_parallel(instances, work, max_workers)
        if unmapped["n"]:
            Console.warning(
                f"  {unmapped['n']} instance(s) referenced an event_id not in the "
                f"backup's graph_epochs — left unstamped (faithful replay)."
            )

    @staticmethod
    def _import_evidence(client: AGEClient, pairs: List, max_workers: int) -> None:
        """Reconstruct EVIDENCED_BY + derived APPEARS edges from the evidence stream."""
        total = len(pairs)
        lock = threading.Lock()
        done = {"n": 0}

        def work(pair):
            concept_id, instance_id = pair
            _execute_with_age_retry(
                client, DataImporter._EVIDENCE_Q,
                {"concept_id": concept_id, "instance_id": instance_id},
            )
            with lock:
                done["n"] += 1
                if done["n"] % 50 == 0 or done["n"] == total:
                    Console.progress(done["n"], total, "Evidence")

        _run_parallel(pairs, work, max_workers)

    @staticmethod
    def _import_relationships(client: AGEClient, rels: List[Dict[str, Any]],
                              progress_callback, max_workers: int) -> int:
        """MERGE concept-concept relationships in parallel; return created count."""
        total = len(rels)
        lock = threading.Lock()
        done = {"n": 0, "created": 0}

        def work(rel):
            created = DataImporter._merge_relationship(client, rel)
            with lock:
                done["n"] += 1
                done["created"] += created
                _progress(progress_callback, "relationships", done["n"], total)

        _run_parallel(rels, work, max_workers)
        return done["created"]

    # Edge-property keys are simple identifiers (e.g. learned_id, confidence). AGE
    # rejects a whole-map parameter (`SET r = $props` → "SET clause expects a map"),
    # so each property is set individually with a scalar param — mirroring how the
    # ingestion path writes edge properties.
    _PROP_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    @staticmethod
    def _merge_relationship(client: AGEClient, rel: Dict[str, Any]) -> int:
        """MERGE a single concept relationship (dynamic edge label). Returns 1 if created/matched.

        The edge label is interpolated into the Cypher text (AGE has no parameterized
        edge labels), so a backup — an untrusted-input boundary in adjacent mode — must
        not inject through ``type``. Labels are identifiers; reject anything else.
        """
        rel_type = rel["type"]  # de-interned label string
        if not isinstance(rel_type, str) or not DataImporter._PROP_KEY.match(rel_type):
            Console.warning(f"  Skipping relationship with unsafe edge type: {rel_type!r}")
            return 0
        query = f"""
            OPTIONAL MATCH (c1:Concept {{concept_id: $from_id}})
            OPTIONAL MATCH (c2:Concept {{concept_id: $to_id}})
            WITH c1, c2
            WHERE c1 IS NOT NULL AND c2 IS NOT NULL
            MERGE (c1)-[r:{rel_type}]->(c2)
        """
        params = {"from_id": rel["from"], "to_id": rel["to"]}

        set_items = []
        for idx, (key, value) in enumerate((rel.get("properties") or {}).items()):
            if not DataImporter._PROP_KEY.match(str(key)):
                Console.warning(f"  Skipping edge property with unsafe key: {key!r}")
                continue
            pkey = f"p_{idx}"
            set_items.append(f"r.{key} = ${pkey}")
            params[pkey] = value
        if set_items:
            query += "                SET " + ", ".join(set_items) + "\n"
        query += "                RETURN count(r) as created"

        result = _execute_with_age_retry(client, query, params, fetch_one=True)
        if result and int(str(result.get("created", 0))) > 0:
            return 1
        return 0

    # ------------------------------------------------------------------
    # P5-faithful epoch replay (ADR-102) — clone-only. The worker gates this
    # to an empty target + idempotent mode and orchestrates the order:
    #   _ensure_epoch_kinds -> _replay_graph_epochs(in_progress) -> import(map)
    #   -> _resolve_replayed_epochs(completed) -> _set_ingestion_counter.
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_epoch_kinds(client: AGEClient, reader: "KgBackupV2Reader") -> None:
        """Upsert the backup's epoch kinds into kg_api.graph_epoch_kinds.

        Faithful replay inserts graph_epochs rows whose ``kind`` is FK-constrained
        (migration 064) to this lookup, so any carried kind not already present must
        exist first. ON CONFLICT DO NOTHING preserves the target's own definition
        for kinds that already exist.
        """
        kinds = reader.header.get("epoch_kinds", [])
        if not kinds:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for k in kinds:
                    name = k.get("kind") if isinstance(k, dict) else k
                    if not name:
                        continue
                    # Log-only kinds (present in the epoch log but not the lookup
                    # export) arrive as bare {"kind": k} with no flag — default them
                    # to forensic (semantic_wallclock=False), the conservative choice.
                    wallclock = bool(k.get("semantic_wallclock", False)) if isinstance(k, dict) else False
                    desc = (k.get("description") if isinstance(k, dict) else None) or ""
                    cur.execute(
                        "INSERT INTO kg_api.graph_epoch_kinds (kind, semantic_wallclock, description) "
                        "VALUES (%s, %s, %s) ON CONFLICT (kind) DO NOTHING",
                        (name, wallclock, desc),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)

    @staticmethod
    def _replay_graph_epochs(client: AGEClient, reader: "KgBackupV2Reader",
                             status: str = "in_progress",
                             owner_job_id: Optional[str] = None) -> Dict[int, int]:
        """Replay carried graph_epochs as NEW local events (P5-faithful).

        Inserts each carried event in original-id order, letting BIGSERIAL mint a
        fresh local event_id while carrying occurred_at/kind/actor/counter_after/
        metadata — so the replayed history's structure (count, order, node→event
        groupings, wallclock) is faithful even though the ids are new (new ids never
        collide; no sequence surgery). Returns {old_event_id: new_event_id} for
        remapping Instance.created_at_event_id.

        Inserted with ``status`` (default 'in_progress') so the committed watermark
        sits below the lowest new id and the graph reads STALE during the import;
        the worker resolves them to 'completed' once the import lands.

        ``owner_job_id`` (issue #485): stamp the LOCAL restore job into each row's
        metadata under ``job_id`` so the orphaned-epoch reconciliation sweep can tell
        a still-running restore's in_progress rows from a crashed one's. The backup's
        original ``job_id`` (a foreign id) is preserved under ``source_job_id``.
        """
        old_to_new: Dict[int, int] = {}
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for ep in reader.graph_epochs():
                    old_id = ep.get("event_id")
                    metadata = dict(ep.get("metadata") or {})
                    if owner_job_id is not None:
                        # Reserve metadata.job_id for the LOCAL owning job (the sweep
                        # invariant); keep the backup's original under source_job_id.
                        if "job_id" in metadata:
                            metadata["source_job_id"] = metadata["job_id"]
                        metadata["job_id"] = owner_job_id
                    # counter_after is carried verbatim — it snapshots the SOURCE
                    # graph's graph_change_counter, a foreign counter space. It is
                    # display-only (epoch_facade timeline), never drives the watermark
                    # or vitality, so carrying it is honest for a faithful replay.
                    cur.execute(
                        "INSERT INTO kg_api.graph_epochs "
                        "(occurred_at, kind, actor, counter_after, metadata, status) "
                        "VALUES (%s::timestamptz, %s, %s, %s, %s::jsonb, %s) RETURNING event_id",
                        (
                            ep.get("occurred_at"),
                            ep.get("kind"),
                            ep.get("actor"),
                            ep.get("counter_after"),
                            json.dumps(metadata),
                            status,
                        ),
                    )
                    new_id = cur.fetchone()[0]
                    if old_id is not None:
                        old_to_new[old_id] = new_id
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)
        return old_to_new

    @staticmethod
    def _resolve_replayed_epochs(client: AGEClient, new_event_ids: List[int],
                                 status: str = "completed") -> None:
        """Resolve replayed epoch rows to a terminal status (P5-faithful).

        Called after the import lands ('completed') or fails ('failed'). Both count
        toward the committed watermark (migration 076); completing advances the
        freshness clock to the max replayed id, failing keeps the graph stale.
        """
        if not new_event_ids:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE kg_api.graph_epochs SET status = %s WHERE event_id = ANY(%s)",
                    (status, list(new_event_ids)),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)

    @staticmethod
    def _set_ingestion_counter(client: AGEClient, value: int) -> None:
        """Advance document_ingestion_counter to at least ``value`` (P5-faithful).

        Faithful carries concepts' original created_at/last_seen epochs; the counter
        must be >= the max carried epoch or restored concepts read as 'from the
        future' against a lower counter (the P5 hazard) and future ingestion would
        reissue colliding epoch numbers. GREATEST keeps it monotonic.
        """
        if value is None:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE graph_metrics SET counter = GREATEST(counter, %s), updated_at = NOW() "
                    "WHERE metric_name = 'document_ingestion_counter'",
                    (value,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)
