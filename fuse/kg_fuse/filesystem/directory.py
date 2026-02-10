"""
DirectoryMixin — Directory listing, lookup, and semantic search.

Handles readdir, lookup, opendir/releasedir, all _list_* methods,
_refresh_dir, and _execute_search.
"""

import errno
import logging
import os
from typing import Optional

import pyfuse3

from ..models import InodeEntry
from .ingestion import _is_image_file

log = logging.getLogger(__name__)


class DirectoryMixin:
    """Directory listing, lookup, and semantic search."""

    async def lookup(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Look up a directory entry by name."""
        name_str = name.decode("utf-8")
        log.debug(f"lookup: parent={parent_inode}, name={name_str}")

        # Check existing inodes first
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode and entry.name == name_str:
                return await self.getattr(inode, ctx)

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Root level: "ontology" (fixed) + global user queries
        if parent_entry.entry_type == "root":
            if name_str == "ontology":
                return await self.getattr(self.ONTOLOGY_ROOT_INODE, ctx)

            # Check if it's a global user query
            if self.query_store.is_query_dir(None, name_str):
                inode = self._get_or_create_query_inode(None, name_str, parent_inode)
                return await self.getattr(inode, ctx)

        # ontology_root: list actual ontologies
        elif parent_entry.entry_type == "ontology_root":
            entries = await self._list_ontologies()
            for inode, ont_name in entries:
                if ont_name == name_str:
                    return await self.getattr(inode, ctx)

        # Inside ontology: "documents" (fixed) + "ingest" (drop box) + user queries
        elif parent_entry.entry_type == "ontology":
            ontology = parent_entry.ontology

            if name_str == "documents":
                inode = self._get_or_create_documents_dir_inode(ontology, parent_inode)
                return await self.getattr(inode, ctx)

            if name_str == "ingest":
                inode = self._get_or_create_ingest_dir_inode(ontology, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a query directory
            if self.query_store.is_query_dir(ontology, name_str):
                inode = self._get_or_create_query_inode(ontology, name_str, parent_inode)
                return await self.getattr(inode, ctx)

        # documents_dir: list actual document files
        elif parent_entry.entry_type == "documents_dir":
            ontology = parent_entry.ontology
            entries = await self._list_documents(parent_inode, ontology)
            for inode, doc_name in entries:
                if doc_name == name_str:
                    return await self.getattr(inode, ctx)

        # ingest_dir: job status files (or active ingestion_file inodes)
        elif parent_entry.entry_type == "ingest_dir":
            # Check active ingestion file inodes first (files being written)
            for inode, entry in self._inodes.items():
                if entry.parent == parent_inode and entry.name == name_str:
                    return await self.getattr(inode, ctx)
            # Then check job status files
            entries = self._list_ingest_contents(parent_inode, parent_entry.ontology)
            for inode, job_name in entries:
                if job_name == name_str:
                    return await self.getattr(inode, ctx)

        # Query directory: .meta + images + concepts + nested queries
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology  # Can be None for global queries
            parent_path = parent_entry.query_path

            # Check for .meta directory
            if name_str == ".meta":
                inode = self._get_or_create_meta_dir_inode(ontology, parent_path, parent_inode)
                return await self.getattr(inode, ctx)

            # Check for images directory
            if name_str == "images":
                inode = self._image_handler.get_or_create_images_dir_inode(ontology, parent_path, parent_inode)
                return await self.getattr(inode, ctx)

            nested_path = f"{parent_path}/{name_str}" if parent_path else name_str

            # Check if it's a nested query directory
            if self.query_store.is_query_dir(ontology, nested_path):
                inode = self._get_or_create_query_inode(ontology, nested_path, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a concept file (fetch results if needed)
            entries = await self._list_query_results(parent_inode, ontology, parent_path)
            for inode, file_name in entries:
                if file_name == name_str:
                    return await self.getattr(inode, ctx)

        # images directory: list image evidence files
        elif parent_entry.entry_type == "images_dir":
            entries = await self._image_handler.list_query_images(
                parent_inode, parent_entry.ontology, parent_entry.query_path,
                cache=self._cache
            )
            for inode, file_name in entries:
                if file_name == name_str:
                    return await self.getattr(inode, ctx)

        # .meta directory: list virtual config files
        elif parent_entry.entry_type == "meta_dir":
            ontology = parent_entry.ontology
            query_path = parent_entry.query_path

            if name_str in self.META_FILES:
                inode = self._get_or_create_meta_file_inode(name_str, ontology, query_path, parent_inode)
                return await self.getattr(inode, ctx)

        # Not found
        raise pyfuse3.FUSEError(errno.ENOENT)

    async def opendir(self, inode: int, ctx: pyfuse3.RequestContext) -> int:
        """Open a directory, return file handle."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)
        if not self._is_dir_type(self._inodes[inode].entry_type):
            raise pyfuse3.FUSEError(errno.ENOTDIR)

        return inode  # Use inode as file handle

    async def releasedir(self, fh: int) -> None:
        """Release (close) a directory handle. No-op — we use inodes as handles."""
        pass

    async def readdir(self, fh: int, start_id: int, token: pyfuse3.ReaddirToken) -> None:
        """Read directory contents with stale-while-revalidate.

        If the epoch changed and we have cached directory listings, serves
        stale data immediately and spawns a background refresh. The kernel
        is notified via invalidate_inode when fresh data arrives.
        """
        log.debug(f"readdir: fh={fh}, start_id={start_id}")

        # Check graph epoch (does not invalidate — stale data survives)
        await self._cache.check_epoch()

        entry = self._inodes.get(fh)
        if not entry:
            return

        entries = []

        if entry.entry_type == "root":
            entries = await self._list_root_contents(fh)

        elif entry.entry_type == "ontology_root":
            entries = await self._list_ontologies()

        elif entry.entry_type == "ontology":
            entries = await self._list_ontology_contents(fh, entry.ontology)

        elif entry.entry_type == "documents_dir":
            entries = await self._list_documents(fh, entry.ontology)

        elif entry.entry_type == "ingest_dir":
            entries = self._list_ingest_contents(fh, entry.ontology)

        elif entry.entry_type == "query":
            meta_inode = self._get_or_create_meta_dir_inode(entry.ontology, entry.query_path, fh)
            entries.append((meta_inode, ".meta"))
            results = await self._list_query_results(fh, entry.ontology, entry.query_path)
            entries.extend(results)

        elif entry.entry_type == "images_dir":
            entries = await self._image_handler.list_query_images(
                fh, entry.ontology, entry.query_path,
                cache=self._cache
            )

        elif entry.entry_type == "meta_dir":
            for meta_key in self.META_FILES:
                inode = self._get_or_create_meta_file_inode(meta_key, entry.ontology, entry.query_path, fh)
                entries.append((inode, meta_key))

        # Spawn background refresh if directory listing is stale
        if (self._cache.get_dir(fh) is not None
                and not self._cache.is_dir_fresh(fh)):
            self._cache.spawn_dir_refresh(fh, lambda: self._refresh_dir(fh, entry))

        # Emit entries starting from start_id
        for idx, (inode, name) in enumerate(entries):
            if idx < start_id:
                continue
            attr = await self.getattr(inode, None)
            if not pyfuse3.readdir_reply(token, name.encode("utf-8"), attr, idx + 1):
                break

    async def _refresh_dir(self, fh: int, entry: InodeEntry) -> list[tuple[int, str]]:
        """Fetch fresh directory listing for background refresh.

        Invalidates the stale cache entry first so the _list_* methods
        re-fetch from the API instead of returning stale data.
        """
        self._cache.invalidate_dir(fh)

        if entry.entry_type == "root":
            return await self._list_root_contents(fh)
        elif entry.entry_type == "ontology_root":
            return await self._list_ontologies()
        elif entry.entry_type == "ontology":
            return await self._list_ontology_contents(fh, entry.ontology)
        elif entry.entry_type == "documents_dir":
            return await self._list_documents(fh, entry.ontology)
        elif entry.entry_type == "ingest_dir":
            return self._list_ingest_contents(fh, entry.ontology)
        elif entry.entry_type == "query":
            entries = []
            meta_inode = self._get_or_create_meta_dir_inode(entry.ontology, entry.query_path, fh)
            entries.append((meta_inode, ".meta"))
            results = await self._list_query_results(fh, entry.ontology, entry.query_path)
            entries.extend(results)
            return entries
        elif entry.entry_type == "images_dir":
            return await self._image_handler.list_query_images(
                fh, entry.ontology, entry.query_path,
                cache=self._cache
            )
        return []

    async def _list_root_contents(self, parent_inode: int) -> list[tuple[int, str]]:
        """List root directory contents: ontology/ + global user queries."""
        entries = []

        # Fixed: the "ontology" directory
        entries.append((self.ONTOLOGY_ROOT_INODE, "ontology"))

        # Global user queries (ontology=None)
        global_queries = self.query_store.list_queries_under(None, "")
        for query_name in global_queries:
            inode = self._get_or_create_query_inode(None, query_name, parent_inode)
            entries.append((inode, query_name))

        return entries

    async def _list_ontologies(self) -> list[tuple[int, str]]:
        """List ontologies as directories under /ontology/."""
        cache_key = self.ONTOLOGY_ROOT_INODE
        cached = self._cache.get_dir(cache_key)
        if cached is not None:
            return cached

        try:
            data = await self._api.get("/ontology/")
            ontologies = data.get("ontologies", [])

            entries = []
            seen_names = set()
            for ont in ontologies:
                name = ont.get("ontology", "unknown")
                seen_names.add(name)
                # Allocate inode for this ontology
                inode = self._get_or_create_ontology_inode(name)
                entries.append((inode, name))

            # Add pending ontologies (created with mkdir but no documents yet)
            for pending_name in self._pending_ontologies:
                if pending_name not in seen_names:
                    inode = self._get_or_create_ontology_inode(pending_name)
                    entries.append((inode, pending_name))

            # Prune stale ontology inodes (deleted out-of-band via CLI/curl/web)
            all_valid = seen_names | self._pending_ontologies
            stale_inodes = [
                inode for inode, entry in self._inodes.items()
                if entry.entry_type == "ontology" and entry.ontology not in all_valid
            ]
            for inode in stale_inodes:
                # Cascade: remove all child inodes for this ontology
                children = [i for i, e in self._inodes.items()
                            if e.ontology == self._inodes[inode].ontology
                            and e.entry_type != "ontology_root"]
                for child in children:
                    del self._inodes[child]
                    self._free_inode(child)
                log.info(f"Pruned stale ontology inode: {self._inodes[inode].name}")

            self._cache.put_dir(cache_key, entries)
            return entries

        except Exception as e:
            log.error(f"Failed to list ontologies: {e}")
            return []

    async def _list_ontology_contents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List contents of an ontology directory: documents/ + ingest/ + user queries."""
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Virtual .ontology — ontology statistics
        info_inode = self._get_or_create_info_inode(".ontology", parent_inode, ontology)
        entries.append((info_inode, ".ontology"))

        # Fixed: the "documents" directory (read-only view of ingested content)
        docs_inode = self._get_or_create_documents_dir_inode(ontology, parent_inode)
        entries.append((docs_inode, "documents"))

        # Fixed: the "ingest" drop box (write-only for new content)
        ingest_inode = self._get_or_create_ingest_dir_inode(ontology, parent_inode)
        entries.append((ingest_inode, "ingest"))

        # Add user-created query directories
        query_dirs = self.query_store.list_queries_under(ontology, "")
        for query_name in query_dirs:
            inode = self._get_or_create_query_inode(ontology, query_name, parent_inode)
            entries.append((inode, query_name))

        self._cache.put_dir(parent_inode, entries)
        return entries

    async def _list_documents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List document files inside an ontology's documents/ directory.

        Also includes virtual job files ({filename}.ingesting) for jobs tracked locally.
        Uses lazy polling: jobs are only polled when their .job file is read.
        """
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Virtual .documents — document listing with count
        info_inode = self._get_or_create_info_inode(".documents", parent_inode, ontology)
        entries.append((info_inode, ".documents"))

        # Get documents from API
        try:
            data = await self._api.get("/documents", params={"ontology": ontology, "limit": 100})
            documents = data.get("documents", [])

            for doc in documents:
                filename = doc.get("filename", doc.get("document_id", "unknown"))
                document_id = doc.get("document_id")
                content_type = doc.get("content_type", "document")

                if content_type == "image":
                    # Image: two entries — raw image bytes + companion .md
                    img_inode = self._image_handler.get_or_create_image_document_inode(
                        filename, parent_inode, ontology, document_id
                    )
                    entries.append((img_inode, filename))

                    prose_name = f"{filename}.md"
                    prose_inode = self._image_handler.get_or_create_image_prose_inode(
                        prose_name, parent_inode, ontology, document_id
                    )
                    entries.append((prose_inode, prose_name))
                else:
                    # Text document: single entry (unchanged)
                    inode = self._get_or_create_document_inode(
                        filename, parent_inode, ontology, document_id
                    )
                    entries.append((inode, filename))

        except Exception as e:
            log.error(f"Failed to list documents for {ontology}: {e}")

        self._cache.put_dir(parent_inode, entries)
        return entries

    def _list_ingest_contents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List contents of the ingest/ drop box: active ingestion job status files.

        No API call — job tracker is local. Files appear as .ingesting
        while the job is running and disappear when complete.

        Always includes a .ingest so the directory is never empty on first
        read — Dolphin/KIO grays out paste on empty FUSE directories.
        """
        entries = []

        # Virtual .ingest — drop-box instructions + Dolphin workaround.
        # Dolphin/KIO grays out paste on empty FUSE directories.
        info_inode = self._get_or_create_info_inode(".ingest", parent_inode, ontology)
        entries.append((info_inode, ".ingest"))

        for job in self._job_tracker.get_jobs_for_ontology(ontology):
            virtual_name = self.jobs_config.format_job_filename(job.filename)
            inode = self._get_or_create_job_inode(
                virtual_name, parent_inode, ontology, job.job_id
            )
            entries.append((inode, virtual_name))

            # For image jobs, also show companion .md as ingesting
            if _is_image_file(job.filename):
                md_virtual_name = self.jobs_config.format_job_filename(f"{job.filename}.md")
                md_inode = self._get_or_create_job_inode(
                    md_virtual_name, parent_inode, ontology, job.job_id
                )
                entries.append((md_inode, md_virtual_name))

        return entries

    async def _list_query_results(self, parent_inode: int, ontology: Optional[str], query_path: str) -> list[tuple[int, str]]:
        """Execute semantic search and list results + child queries + symlinks."""
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Get the query chain for nested resolution
        queries = self.query_store.get_query_chain(ontology, query_path)
        if not queries:
            log.warning(f"No query found for {ontology}/{query_path}")
            return entries

        leaf_query = queries[-1]

        # Execute semantic search with AND intersection for nested queries
        try:
            # For global queries with symlinks, search those specific ontologies
            # Otherwise search the scoped ontology (or all if global without symlinks)
            symlinked_ontologies = leaf_query.symlinks if ontology is None else []

            # Collect all query terms from hierarchy for AND intersection
            query_terms = [q.query_text for q in queries]

            results = await self._execute_search(
                ontology,
                query_terms,  # Pass list for AND intersection
                leaf_query.threshold,
                leaf_query.limit,
                symlinked_ontologies,
                exclude_terms=leaf_query.exclude,
                union_terms=leaf_query.union
            )

            for concept in results:
                concept_id = concept.get("concept_id", "unknown")
                concept_name = concept.get("label", concept_id)
                # Sanitize name for filename
                safe_name = self._sanitize_filename(concept_name)
                filename = f"{safe_name}.concept.md"

                inode = self._get_or_create_concept_inode(
                    filename, parent_inode, ontology, query_path, concept_id
                )
                entries.append((inode, filename))

        except Exception as e:
            log.error(f"Failed to execute search for {ontology}/{query_path}: {e}")

        # Always include images/ directory (lazy-loaded on readdir)
        images_dir_inode = self._image_handler.get_or_create_images_dir_inode(ontology, query_path, parent_inode)
        entries.append((images_dir_inode, "images"))

        # Add child query directories
        child_queries = self.query_store.list_queries_under(ontology, query_path)
        for child_name in child_queries:
            child_path = f"{query_path}/{child_name}"
            inode = self._get_or_create_query_inode(ontology, child_path, parent_inode)
            entries.append((inode, child_name))

        # Add symlinks (for global queries only)
        if ontology is None:
            for linked_ont in leaf_query.symlinks:
                target = f"../ontology/{linked_ont}"
                inode = self._get_or_create_symlink_inode(linked_ont, linked_ont, query_path, target, parent_inode)
                entries.append((inode, linked_ont))

        self._cache.put_dir(parent_inode, entries)
        return entries

    async def _execute_search(
        self,
        ontology: Optional[str],
        query_terms: list[str],
        threshold: float,
        limit: int = 50,
        symlinked_ontologies: list[str] = None,
        exclude_terms: list[str] = None,
        union_terms: list[str] = None
    ) -> list[dict]:
        """Execute semantic search via API with full filtering model.

        Args:
            ontology: Single ontology to search (None for global)
            query_terms: List of search terms (AND intersection if multiple)
            threshold: Minimum similarity score
            limit: Maximum results
            symlinked_ontologies: For global queries, list of ontologies to search
            exclude_terms: Terms to exclude from results (semantic NOT)
            union_terms: Additional terms to include (semantic OR)
        """
        exclude_terms = exclude_terms or []
        union_terms = union_terms or []

        try:
            async def search_single_term(term: str, ontologies: list[str] = None, fetch_limit: int = None) -> list[dict]:
                """Search for a single term, optionally across multiple ontologies."""
                body = {
                    "query": term,
                    "min_similarity": threshold,
                    "limit": fetch_limit or limit * 2,  # Fetch more for intersection/filtering
                }

                if ontology is not None:
                    # Scoped query - search single ontology
                    body["ontology"] = ontology
                    result = await self._api.post("/query/search", json=body)
                    return result.get("results", [])
                elif ontologies:
                    # Global query with symlinks - search specific ontologies
                    all_results = []
                    for ont in ontologies:
                        body["ontology"] = ont
                        result = await self._api.post("/query/search", json=body)
                        all_results.extend(result.get("results", []))
                    return all_results
                else:
                    # Global query without symlinks - search all
                    result = await self._api.post("/query/search", json=body)
                    return result.get("results", [])

            # Step 1: Get base results from query terms (AND intersection)
            concept_data = {}  # concept_id -> full result dict

            if len(query_terms) == 1:
                # Single term: simple search
                results = await search_single_term(query_terms[0], symlinked_ontologies)
                for r in results:
                    cid = r.get("concept_id")
                    if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                        concept_data[cid] = r
                base_ids = set(concept_data.keys())
            else:
                # Multiple terms: AND intersection
                result_sets = []
                for term in query_terms:
                    results = await search_single_term(term, symlinked_ontologies)
                    concept_ids = set()
                    for r in results:
                        cid = r.get("concept_id")
                        concept_ids.add(cid)
                        if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                            concept_data[cid] = r
                    result_sets.append(concept_ids)

                if not result_sets:
                    base_ids = set()
                else:
                    base_ids = result_sets[0]
                    for rs in result_sets[1:]:
                        base_ids = base_ids & rs

            # Step 2: Add union terms (semantic OR - expand results)
            if union_terms:
                for term in union_terms:
                    results = await search_single_term(term, symlinked_ontologies, fetch_limit=limit)
                    for r in results:
                        cid = r.get("concept_id")
                        base_ids.add(cid)  # Add to result set
                        if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                            concept_data[cid] = r

            # Step 3: Apply exclude terms (semantic NOT - filter results)
            if exclude_terms:
                exclude_ids = set()
                for term in exclude_terms:
                    results = await search_single_term(term, symlinked_ontologies, fetch_limit=limit * 2)
                    for r in results:
                        exclude_ids.add(r.get("concept_id"))
                # Remove excluded concepts
                base_ids = base_ids - exclude_ids

            # Step 4: Build final results, sorted by similarity
            matched = [concept_data[cid] for cid in base_ids if cid in concept_data]
            matched.sort(key=lambda x: x.get("score", 0), reverse=True)
            return matched[:limit]

        except Exception as e:
            log.error(f"Search failed: {e}")
            return []
