# FUSE Driver API Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from FUSE driver source code docstrings.
> Last updated: 2026-02-09

---

## Modules

- [`api_client`](#api-client) - HTTP API client for the Knowledge Graph.
- [`cli`](#cli) - Subcommand implementations for kg-fuse CLI.
- [`config`](#config) - Configuration management for kg-fuse.
- [`daemon`](#daemon) - Daemon lifecycle management for kg-fuse.
- [`epoch_cache`](#epoch-cache) - Epoch-gated cache for FUSE filesystem.
- [`filesystem`](#filesystem) - Knowledge Graph FUSE Filesystem Operations
- [`formatters`](#formatters) - Formatters for rendering documents and concepts as markdown.
- [`image_handler`](#image-handler) - Image handling for the FUSE filesystem.
- [`job_tracker`](#job-tracker) - Job tracking for FUSE ingestion visibility.
- [`main`](#main) - Knowledge Graph FUSE Driver
- [`models`](#models) - Data models for the FUSE filesystem.
- [`query_store`](#query-store) - Query Store - Client-side persistence for user-created query directories.
- [`safety`](#safety) - Safety fences for kg-fuse.

---

## api_client

HTTP API client for the Knowledge Graph.

### class `KnowledgeGraphClient`

Async HTTP client for the Knowledge Graph API with OAuth support.

#### `KnowledgeGraphClient.__init__(api_url: str, client_id: str, client_secret: str)`

#### `async get(path: str, params: Optional[dict])`

Make authenticated GET request to API.

#### `async post(path: str, json: dict, data: dict, files: dict)`

Make authenticated POST request to API.

#### `async get_bytes(path: str, params: Optional[dict], timeout: float)`

Make authenticated GET request returning raw bytes.

Used for fetching binary content like images from the API.
Uses a longer default timeout since binary transfers can be large.

#### `async get_epoch()`

Fetch the current graph epoch (change counter).

Returns the graph_change_counter value, which changes when
the graph is modified. Used for cache invalidation.

Returns:
    Integer epoch value, or -1 on error (forces cache invalidation).

#### `async close()`

Close the HTTP client.

---

## cli

Subcommand implementations for kg-fuse CLI.

Commands: init, mount, unmount, status, config, repair, update.

### `cmd_status(args: Namespace)`

Show status of all configured mounts + system info.

### `cmd_init(args: Namespace)`

Interactive setup: detect auth, configure mount, offer autostart.

### `cmd_mount(args: Namespace)`

Mount one or all configured FUSE filesystems.

### `cmd_unmount(args: Namespace)`

Unmount one or all FUSE filesystems.

### `cmd_config(args: Namespace)`

Show current configuration with masked secrets.

### `cmd_repair(args: Namespace)`

Detect and fix orphaned mounts, stale PIDs, bad config.

### `cmd_update(args: Namespace)`

Self-update via pipx.

---

## config

Configuration management for kg-fuse.

Two-file config model:
  ~/.config/kg/config.json  — kg CLI owns (read-only for kg-fuse): auth, api_url
  ~/.config/kg/fuse.json    — kg-fuse owns (read/write): mounts, preferences

Credential resolution (highest → lowest):
  1. CLI flags (--client-id, --client-secret)
  2. fuse.json auth_client_id → lookup in config.json auth
  3. config.json auth section directly
  4. Error with guidance

### `get_kg_config_dir()`

Get kg config directory (~/.config/kg/).

### `get_kg_config_path()`

Get path to kg CLI's config.json (read-only for kg-fuse).

### `get_fuse_config_path()`

Get path to kg-fuse's own config file.

### `get_fuse_data_dir()`

Get XDG data directory for kg-fuse runtime state.

### `get_fuse_state_dir()`

Get XDG state directory for kg-fuse PID files.

### `get_mount_id(mountpoint: str)`

Stable short hash of mountpoint path for per-mount data dirs.

### `get_mount_data_dir(mountpoint: str)`

Get per-mount data directory for query store etc.

### `read_kg_config()`

Read kg CLI's config.json. Returns None if not found.

### `read_kg_credentials()`

Read OAuth credentials from kg CLI's config.json.

Returns (client_id, client_secret, api_url). Any may be None.

### `read_fuse_config()`

Read fuse.json. Returns None if not found.

### `write_fuse_config(data: dict)`

Atomic write to fuse.json with file locking.

Writes to a temp file, validates the roundtrip, then renames atomically.
The flock is held through the rename to prevent concurrent writers from
seeing a partially-written state. Enforces 600 permissions.

### `load_config(cli_client_id: Optional[str], cli_client_secret: Optional[str], cli_api_url: Optional[str])`

Load full FUSE config with credential resolution.

Priority:
  1. CLI flags
  2. fuse.json auth_client_id → config.json auth
  3. config.json auth directly
  4. Empty (caller should handle missing creds)

### `add_mount_to_config(mountpoint: str, mount_config: Optional[MountConfig])`

Add a mount to fuse.json. Creates the file if it doesn't exist.

### `remove_mount_from_config(mountpoint: str)`

Remove a mount from fuse.json. Returns True if found and removed.

### class `TagsConfig`

Tag generation settings for YAML frontmatter (Obsidian, Logseq, etc.)

### class `JobsConfig`

Job visibility settings for ingestion tracking.

#### `format_job_filename(filename: str)`

Format a job filename with .ingesting suffix and optional dot prefix.

### class `CacheConfig`

Cache invalidation settings for epoch-gated caching.

### class `MountConfig`

Configuration for a single FUSE mount point.

### class `FuseConfig`

Full kg-fuse configuration (from fuse.json + config.json).

---

## daemon

Daemon lifecycle management for kg-fuse.

Handles forking mount processes into background, PID tracking,
and clean shutdown via signal handling.

### `fork_mount(mountpoint: str, config: FuseConfig, run_fn: Callable)`

Fork a daemon process that runs a FUSE mount.

Args:
    mountpoint: Where to mount
    config: Full FUSE config (credentials, mount settings)
    run_fn: Function that performs the actual mount (blocks until unmount)

Returns:
    Daemon PID (in parent), never returns in child.

### `mount_status(mountpoint: str)`

Get status of a mount daemon.

Returns dict with keys: running, pid, orphaned.

---

## epoch_cache

Epoch-gated cache for FUSE filesystem.

Tracks the graph change counter (epoch) and invalidates caches when the
graph changes. Uses stale-while-revalidate: serves cached data immediately
and refreshes in the background via trio nursery.

Cache contract:
  - Epoch unchanged → cache valid, serve immediately
  - Epoch changed → cache stale, serve stale + background refresh
  - No cache → block on first fetch (unavoidable)

### class `EpochCache`

Graph-epoch-aware cache with stale-while-revalidate semantics.

Caches survive epoch changes so stale data can be served immediately
while background refreshes fetch fresh data. Per-entry epoch tracking
distinguishes fresh (fetched at current epoch) from stale (fetched at
a previous epoch).

#### `EpochCache.__init__(api: KnowledgeGraphClient, config: CacheConfig)`

#### `graph_epoch()`

#### `set_nursery(nursery: trio.Nursery)`

Set trio nursery for background tasks. Starts periodic sweep.

#### `async check_epoch()`

Check if graph epoch changed. Throttled to one API call per interval.

Does NOT invalidate caches — stale entries survive so callers can
serve them immediately while spawning background refreshes.
Per-entry epoch tracking lets callers distinguish fresh from stale.

Returns True if epoch changed.

#### `get_dir(inode: int)`

Get cached directory listing, or None if missing.

Returns cached data regardless of staleness — callers use
is_dir_fresh() to decide whether to spawn background refresh.
TTL only applies when epoch tracking hasn't initialized.

#### `is_dir_fresh(inode: int)`

Check if cached directory listing was fetched at current epoch.

#### `put_dir(inode: int, entries: list[tuple[int, str]])`

Cache a directory listing at the current epoch.

#### `invalidate_dir(inode: int)`

Invalidate a single directory's cache.

#### `get_content(inode: int)`

Get cached file content, or None if not cached.

#### `is_content_fresh(inode: int)`

Check if cached content was fetched at current epoch.

#### `put_content(inode: int, data: bytes)`

Cache file content at current epoch with LRU eviction.

#### `invalidate_content(inode: int)`

Invalidate a single file's cached content.

#### `is_refreshing(inode: int)`

#### `hydration_state(inode: int)`

Get hydration state for xattr reporting.

States: fresh (current epoch), stale (older epoch, awaiting refresh),
refreshing (background fetch in progress), pending (never cached).

#### `spawn_refresh(inode: int, fetch_fn: Callable[[], Awaitable[bytes]])`

Spawn a background content refresh if not already running.

Args:
    inode: The inode to refresh
    fetch_fn: Async callable that returns the new content bytes

#### `spawn_dir_refresh(inode: int, fetch_fn: Callable[[], Awaitable[list[tuple[int, str]]]])`

Spawn a background directory listing refresh.

#### `invalidate_all()`

Force-clear all caches. Used for explicit invalidation and unmount.

#### `clear()`

Full cleanup for unmount.

---

## filesystem

Knowledge Graph FUSE Filesystem Operations

Hierarchy:
- /                              - Mount root (ontology/ + user global queries)
- /ontology/                     - Fixed, system-managed ontology listing
- /ontology/{name}/              - Ontology directories (from graph)
- /ontology/{name}/documents/    - Source documents (read-only)
- /ontology/{name}/documents/{doc}.md  - Text document content
- /ontology/{name}/documents/{img}.png - Image: raw bytes from Garage S3
- /ontology/{name}/documents/{img}.png.md - Image companion: prose + link
- /ontology/{name}/{query}/      - User query scoped to ontology
- /{user-query}/                 - User global query (all ontologies)
- /{path}/*.concept.md           - Concept search results
- /{path}/images/                - Image evidence from query concepts
- /{query}/.meta/                - Query control plane (virtual)

Query Control Plane (.meta):
- .meta/limit      - Max results (default: 50)
- .meta/threshold  - Min similarity 0.0-1.0 (default: 0.7)
- .meta/exclude    - Terms to exclude (NOT)
- .meta/union      - Terms to broaden (OR)
- .meta/query.toml - Full query state (read-only)

Filtering Model:
- Hierarchy = AND (nesting narrows results)
- Symlinks = OR (add sources)
- .meta/exclude = NOT (removes matches)
- .meta/union = OR (adds matches)

### class `KnowledgeGraphFS`

FUSE filesystem backed by Knowledge Graph API.

#### `KnowledgeGraphFS.__init__(api_url: str, client_id: str, client_secret: str, tags_config: TagsConfig, jobs_config: JobsConfig, cache_config: CacheConfig, query_store: QueryStore)`

#### `async getattr(inode: int, ctx: pyfuse3.RequestContext)`

Get file/directory attributes.

#### `async lookup(parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext)`

Look up a directory entry by name.

#### `async opendir(inode: int, ctx: pyfuse3.RequestContext)`

Open a directory, return file handle.

#### `async mkdir(parent_inode: int, name: bytes, mode: int, ctx: pyfuse3.RequestContext)`

Create a query directory.

#### `async rmdir(parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext)`

Remove a query directory.

#### `async readdir(fh: int, start_id: int, token: pyfuse3.ReaddirToken)`

Read directory contents with stale-while-revalidate.

If the epoch changed and we have cached directory listings, serves
stale data immediately and spawns a background refresh. The kernel
is notified via invalidate_inode when fresh data arrives.

#### `set_nursery(nursery)`

Set the trio nursery for background tasks. Called by main.py.

#### `async open(inode: int, flags: int, ctx: pyfuse3.RequestContext)`

Open a file.

#### `async read(fh: int, off: int, size: int)`

Read file contents with stale-while-revalidate.

Cache flow:
1. Epoch unchanged + cached → serve fresh (zero API calls)
2. Epoch changed + cached → serve stale instantly, background refresh
3. No cache → block on first fetch (unavoidable)

Image bytes are handled by ImageHandler's immutable cache.

#### `async write(fh: int, off: int, buf: bytes)`

Write to a file (meta files and ingestion files are writable).

#### `async setattr(inode: int, attr: pyfuse3.EntryAttributes, fields: pyfuse3.SetattrFields, fh: int, ctx: pyfuse3.RequestContext)`

Set file attributes (needed for truncate on write).

#### `async symlink(parent_inode: int, name: bytes, target: bytes, ctx: pyfuse3.RequestContext)`

Create a symbolic link (for linking ontologies into queries).

#### `async readlink(inode: int, ctx: pyfuse3.RequestContext)`

Read the target of a symbolic link.

#### `async unlink(parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext)`

Remove a file or symlink.

#### `async create(parent_inode: int, name: bytes, mode: int, flags: int, ctx: pyfuse3.RequestContext)`

Create a file for ingestion (black hole - file gets ingested on release).

#### `async release(fh: int)`

Release (close) a file - triggers ingestion for ingestion files.

#### `async getxattr(inode: int, name: bytes, ctx: pyfuse3.RequestContext)`

Get extended attribute — exposes cache hydration state.

#### `async listxattrs(inode: int, ctx: pyfuse3.RequestContext)`

List available extended attributes.

#### `async destroy()`

Clean up resources on unmount.

---

## formatters

Formatters for rendering documents and concepts as markdown.

### `format_document(data: dict, concepts: list, tags_config: TagsConfig)`

Format document data as markdown with optional YAML frontmatter.

### `format_image_prose(data: dict, image_filename: str, tags_config: TagsConfig)`

Format image companion markdown with frontmatter, relative image link, and prose.

Args:
    data: Document content response from GET /documents/{id}/content
    image_filename: Original image filename (e.g., "diagram.png")
    tags_config: Tag configuration for optional concept tags

### `format_concept(data: dict, tags_config: TagsConfig)`

Format concept data as markdown with YAML frontmatter.

### `format_job(job_data: dict | None)`

Format ingestion job data as a TOML-like readable file.

Args:
    job_data: Job information from the API including job_id, status,
              ontology, filename, created_at, and progress info.
              Can be None if API returned no data.

Returns:
    Formatted string suitable for display in a virtual file.

### `render_meta_file(meta_key: str, query: Optional[Query], ontology: Optional[str])`

Render content for a .meta virtual file.

---

## image_handler

Image handling for the FUSE filesystem.

Encapsulates image-specific operations: reading image bytes and prose,
managing the immutable image cache, listing query image evidence,
creating image-related inodes, and routing image ingestion.

### class `ImageHandler`

Handles image-specific operations for the FUSE filesystem.

Owns the immutable image cache (100MB budget, no eviction needed
since images are content-addressed). Delegates inode allocation
back to the filesystem via the provided callable.

#### `ImageHandler.__init__(api: KnowledgeGraphClient, tags_config: TagsConfig, job_tracker: JobTracker, inodes: dict[int, InodeEntry], allocate_inode: Callable[[], int], sanitize_filename: Callable[[str], str])`

#### `get_or_create_image_document_inode(name: str, parent: int, ontology: str, document_id: str)`

Get or create inode for an image document file (raw bytes).

#### `get_or_create_image_prose_inode(name: str, parent: int, ontology: str, document_id: str)`

Get or create inode for an image companion markdown file.

#### `get_or_create_images_dir_inode(ontology: Optional[str], query_path: str, parent: int)`

Get or create inode for the images/ directory inside a query.

#### `get_or_create_image_evidence_inode(name: str, parent: int, ontology: Optional[str], query_path: str, source_id: str)`

Get or create inode for an image evidence file in query images/ dir.

#### `async read_image_bytes(entry: InodeEntry)`

Read raw image bytes from Garage via API.

#### `async read_image_prose(entry: InodeEntry)`

Read image companion markdown with frontmatter + prose.

#### `async read_image_evidence(entry: InodeEntry)`

Read raw image bytes for query image evidence.

#### `clear_cache()`

Clear the image cache (called on filesystem destroy).

#### `async list_query_images(parent_inode: int, ontology: Optional[str], query_path: str, cache)`

List image evidence files for query results.

Fetches concept details for each concept in the parent query to find
instances with image evidence. Deduplicates by source_id.

#### `async ingest_image(ontology: str, filename: str, content: bytes)`

Submit image to dedicated image ingestion API (ADR-057) and track the job.

---

## job_tracker

Job tracking for FUSE ingestion visibility.

Tracks ingestion jobs locally and provides lazy polling when job files are read.
Jobs are automatically cleaned up after completion is shown or after staleness timeout.

### class `TrackedJob`

State for a tracked ingestion job.

#### `is_stale()`

Check if job has been tracked too long (likely orphaned).

### class `JobTracker`

Tracks ingestion jobs for FUSE visibility.

Thread-safe job tracking with lazy polling and automatic cleanup.
Jobs are only fetched from the API when their virtual file is read.

#### `JobTracker.__init__()`

#### `track_job(job_id: str, ontology: str, filename: str)`

Start tracking a new ingestion job.

#### `get_jobs_for_ontology(ontology: str)`

Get all tracked jobs for an ontology.

Performs atomic cleanup of stale/removed jobs before returning.

#### `mark_job_status(job_id: str, status: str)`

Update job status after reading from API.

If status is terminal:
- First call: marks seen_complete=True (show final status)
- Second call: marks for removal (cleanup on next listing)

#### `mark_job_not_found(job_id: str)`

Mark a job for removal when API returns not found.

#### `get_job(job_id: str)`

Get a tracked job by ID.

#### `is_tracking(job_id: str)`

Check if a job is being tracked.

#### `clear()`

Clear all tracked jobs (for cleanup on unmount).

#### `job_count()`

Number of currently tracked jobs.

---

## main

Knowledge Graph FUSE Driver

Multi-command CLI for mounting and managing FUSE filesystems
backed by the knowledge graph API.

Usage:
    kg-fuse                          # Status + help
    kg-fuse init /mnt/knowledge      # Interactive setup
    kg-fuse mount                    # Mount all configured
    kg-fuse mount /mnt/knowledge     # Mount one
    kg-fuse unmount                  # Unmount all
    kg-fuse status                   # Same as bare kg-fuse
    kg-fuse config                   # Show configuration
    kg-fuse repair                   # Fix orphaned mounts
    kg-fuse update                   # Self-update via pipx

### `get_version()`

Get package version from installed metadata.

### `main()`

---

## models

Data models for the FUSE filesystem.

### `is_dir_type(entry_type: str)`

Check if entry type is a directory.

Non-directory types include: document, image_document, image_prose,
image_evidence, concept, meta_file, ingestion_file, symlink, job_file

### class `InodeEntry`

Metadata for an inode.

Entry types:
- root: Mount root (shows ontology/ + global user queries)
- ontology_root: The /ontology/ directory (lists ontologies)
- ontology: Individual ontology directory
- documents_dir: The documents/ directory inside an ontology
- document: Source document file
- image_document: Raw image bytes file (e.g., diagram.png)
- image_prose: Companion markdown for an image (e.g., diagram.png.md)
- image_evidence: Image file inside a query's images/ directory
- query: User-created query directory
- concept: Concept result file
- symlink: Symlink to ontology (for multi-ontology queries)
- meta_dir: The .meta/ control plane directory inside a query
- meta_file: Virtual file inside .meta/ (limit, threshold, exclude, union, query.toml)
- images_dir: The images/ directory inside a query (lazy-loaded image evidence)
- ingestion_file: Temporary file being written for ingestion

---

## query_store

Query Store - Client-side persistence for user-created query directories.

Query directories are created with mkdir and stored in TOML format.
Each directory name becomes a semantic search term.

### class `Query`

A user-created query directory definition with .meta control plane settings.

#### `to_dict()`

### class `QueryStore`

Manages user-created query directories with TOML persistence.

#### `QueryStore.__init__(data_path: Optional[Path])`

Initialize query store.

Args:
    data_path: Path to queries.toml file. If None, uses the legacy
               global path (~/.local/share/kg-fuse/queries.toml).
               Per-mount paths are preferred — pass
               get_mount_data_dir(mountpoint) / "queries.toml".

#### `add_query(ontology: Optional[str], path: str, query_text: Optional[str])`

Add a query (called on mkdir).

Args:
    ontology: The ontology name (None for global queries)
    path: Relative path (e.g., "leadership" or "leadership/communication")
    query_text: Custom query text (defaults to last path component)

Returns:
    The created Query

#### `remove_query(ontology: Optional[str], path: str)`

Remove a query and all children (called on rmdir).

Args:
    ontology: The ontology name (None for global queries)
    path: Relative path

#### `get_query(ontology: Optional[str], path: str)`

Get query definition by ontology and path.

#### `is_query_dir(ontology: Optional[str], path: str)`

Check if path is a user-created query directory.

#### `list_queries_under(ontology: Optional[str], path: str)`

List immediate child query directories under a path.

Args:
    ontology: The ontology name (None for global queries)
    path: Parent path (empty string for root)

Returns:
    List of child directory names (not full paths)

#### `get_query_chain(ontology: Optional[str], path: str)`

Get all queries in the path hierarchy (for nested query resolution).

Args:
    ontology: The ontology name (None for global queries)
    path: Full path (e.g., "leadership/communication")

Returns:
    List of Query objects from root to leaf

#### `update_limit(ontology: Optional[str], path: str, limit: int)`

Update the limit parameter for a query.

#### `update_threshold(ontology: Optional[str], path: str, threshold: float)`

Update the threshold parameter for a query.

#### `add_exclude(ontology: Optional[str], path: str, term: str)`

Add a term to the exclude list.

#### `add_union(ontology: Optional[str], path: str, term: str)`

Add a term to the union list.

#### `clear_exclude(ontology: Optional[str], path: str)`

Clear all exclude terms.

#### `clear_union(ontology: Optional[str], path: str)`

Clear all union terms.

#### `add_symlink(ontology: Optional[str], path: str, linked_ontology: str)`

Add a symlinked ontology to the query.

#### `remove_symlink(ontology: Optional[str], path: str, linked_ontology: str)`

Remove a symlinked ontology from the query.

#### `get_symlinks(ontology: Optional[str], path: str)`

Get list of symlinked ontologies for a query.

---

## safety

Safety fences for kg-fuse.

Mountpoint validation, PID verification, orphaned mount detection,
and RC file management with backup/restore.

### `validate_mountpoint(path: str)`

Validate a mountpoint path. Returns error message or None if OK.

### `ensure_mountpoint(path: str)`

Create mountpoint directory if needed. Returns error message or None.

### `get_pid_path(mountpoint: str)`

Get PID file path for a mountpoint.

### `write_pid(mountpoint: str, pid: int)`

Write PID file for a mount.

### `read_pid(mountpoint: str)`

Read PID from file. Returns None if missing or invalid.

### `clear_pid(mountpoint: str)`

Remove PID file for a mount.

### `is_kg_fuse_process(pid: int)`

Check if a PID belongs to a kg-fuse process via /proc/cmdline.

### `find_kg_fuse_processes()`

Scan /proc for running kg-fuse daemon processes owned by current user.

Only matches processes where 'kg-fuse' or 'kg_fuse' appears as the actual
command being run (argv[0] or argv[1]), not just in a path component.

Returns list of {"pid": int, "cmdline": str}.

### `is_process_alive(pid: int)`

Check if a process is running.

### `kill_mount_daemon(mountpoint: str)`

Kill the daemon for a mountpoint. Returns (success, message).

Verifies the PID is actually a kg-fuse process before sending SIGTERM.

### `find_mounted_fuse()`

Find all kg-fuse entries in /proc/mounts.

Returns list of {"mountpoint": str, "fstype": str}.

### `find_all_fuse_mounts()`

Find ALL FUSE mounts on the system (not just kg-fuse).

Returns list of {"source": str, "mountpoint": str, "fstype": str,
                 "is_ours": bool, "is_system": bool}.

### `is_mount_orphaned(mountpoint: str)`

Check if a FUSE mount is orphaned (transport endpoint not connected).

### `fusermount_unmount(mountpoint: str)`

Run fusermount -u to clean-unmount a FUSE mount. Returns (success, message).

### `detect_shell()`

Detect the user's shell and RC file.

Returns (shell_name, rc_path) or None if unrecognized.

### `add_to_rc(rc_path: Path, mount_command: str)`

Add kg-fuse mount line to shell RC file with backup.

Uses delimited blocks for clean removal. Backs up RC file first.

### `remove_from_rc(rc_path: Path)`

Remove kg-fuse block from shell RC file.

### `has_systemd()`

Check if systemd user services are available.

### `get_systemd_unit_path()`

Get path for kg-fuse systemd user unit file.

### `install_systemd_unit(kg_fuse_path: str)`

Install and enable systemd user service for kg-fuse.

### `uninstall_systemd_unit()`

Disable and remove systemd user service.

### `check_config_permissions(path: Path)`

Check if a config file has overly permissive permissions.

Returns warning message or None if OK.

### `fix_config_permissions(path: Path)`

Set config file to owner-only permissions (600).

Returns (success, message).

---
