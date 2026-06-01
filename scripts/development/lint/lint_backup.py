#!/usr/bin/env python3
"""
Offline backup-object validator for the ``kg-backup/2`` format.

Validates a portable backup object (per ``docs/reference/BACKUP_OBJECT_SPEC.md``)
WITHOUT touching the running platform: no database, no Garage, no AGEClient, no
network, no docker. It is pure file/dict parsing.

It accepts either a raw JSON backup object or a ``.tar.gz`` archive (in which
case ``manifest.json`` is extracted from the archive and validated as the
backup object).

Design for reuse (ADR-102 Track D): the core is a pure function
``validate_backup(obj: dict) -> ValidationResult`` with no I/O. The P3/P6 pytest
suites and a future live API endpoint import that directly. The CLI is a thin
wrapper that reads a path, calls the core, prints issues, and exits non-zero if
any ERROR was found (CI convention, matching the sibling lint tools).

Checks implemented (see ``CHECK_CODES`` for the stable code registry):
  - HEADER presence / well-formedness and format_version family negotiation (§7)
  - kg-backup/2 required header fields (§3.1)
  - legacy kg-backup/1 flat shape detection (notice, then best-effort) (§7)
  - embedding-profile identity string {provider}:{model}@{dims} (§3.2)
  - dictionary index resolution: profile / rel-type / content_type / kind / actor (§4)
  - cascading embedding-profile resolution record→ontology→backup (§4.1)
  - internal referential integrity: rel from/to, instance concept/source (§5)
  - learned_id edge property references an existing source_id (§5.4.1)
  - epoch fields per mode (faithful graph_epochs vs simple) (§5.6, §5.3)
  - duplicate concept_id / source_id / instance_id (§5)
  - excluded derived products absent (projections / artifacts) (§6)

Usage:
    python3 scripts/development/lint/lint_backup.py <path-to-backup.json>
    python3 scripts/development/lint/lint_backup.py <path-to-archive.tar.gz>
    python3 scripts/development/lint/lint_backup.py --selftest

@verified cffa180b
"""

import argparse
import io
import json
import re
import sys
import tarfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The format family this validator natively understands.
KNOWN_FAMILY = "kg-backup"
#: Major version this validator natively understands (exact-match accept, §7).
NATIVE_MAJOR = 2

#: Header fields required for a well-formed kg-backup/2 object (spec §3.1).
REQUIRED_HEADER_FIELDS = [
    "format_version",
    "source",
    "exported_at",
    "schema_version",
    "embedding_profiles",
    "default_embedding_profile",
    "relationship_vocabulary",
    "epoch_kinds",
    "actors",
    "content_types",
    "ontologies",
]

#: Bulk keys that MUST NOT appear — derived products are regenerated post-restore (§6).
EXCLUDED_BULK_KEYS = ["projections", "artifacts", "scores", "grounding", "catalog"]

#: Embedding-profile identity: {provider}:{model}@{dims}  (§3.2).
IDENTITY_RE = re.compile(r"^[^:@\s]+:[^@\s]+@\d+$")

#: Stable issue-code registry. Each entry: code -> short human description.
CHECK_CODES = {
    # structure / header
    "E_NOT_OBJECT": "Backup object is not a JSON object.",
    "E_NO_HEADER": "Missing 'header' region.",
    "E_NO_FORMAT_VERSION": "header.format_version missing.",
    "E_FORMAT_VERSION_SHAPE": "format_version is not '{family}/{major}'.",
    "E_UNKNOWN_FAMILY": "Unknown format family (refuse).",
    "E_HIGHER_MAJOR": "Higher major version than supported (refuse).",
    "E_MISSING_HEADER_FIELD": "Required kg-backup/2 header field missing.",
    "E_NO_BULK": "Missing 'bulk' region.",
    "N_LEGACY_FORMAT": "Legacy kg-backup/1 flat format (best-effort validation).",
    # embedding profiles
    "E_PROFILE_IDENTITY": "embedding profile identity not '{provider}:{model}@{dims}'.",
    "E_DEFAULT_PROFILE_RANGE": "default_embedding_profile index out of range.",
    "E_ONTOLOGY_PROFILE_RANGE": "ontology default_embedding_profile index out of range.",
    # dictionary index resolution
    "E_CONCEPT_PROFILE_RANGE": "concept.embedding_profile index out of range.",
    "E_REL_TYPE_RANGE": "relationship.type index out of range.",
    "E_CONTENT_TYPE_RANGE": "source.content_type index out of range.",
    "E_EPOCH_KIND_RANGE": "graph_epoch.kind index out of range.",
    "E_EPOCH_ACTOR_RANGE": "graph_epoch.actor index out of range.",
    # cascading default
    "E_NO_PROFILE_CASCADE": "concept resolves to no embedding-profile (cascade failed).",
    # referential integrity
    "E_REL_FROM_MISSING": "relationship.from concept_id not in concepts[].",
    "E_REL_TO_MISSING": "relationship.to concept_id not in concepts[].",
    "E_INSTANCE_CONCEPT_MISSING": "instance.concept_id not in concepts[] (legacy kg-backup/1 only).",
    "E_INSTANCE_SOURCE_MISSING": "instance.source_id not in sources[].",
    "E_EVIDENCE_CONCEPT_MISSING": "evidence.concept_id not in concepts[].",
    "E_EVIDENCE_INSTANCE_MISSING": "evidence.instance_id not in instances[].",
    "E_LEARNED_ID_MISSING": "edge properties.learned_id not an existing source_id.",
    # epochs
    "E_EVENT_ID_UNRESOLVED": "instance.created_at_event_id not in graph_epochs[].",
    "W_CONCEPT_NO_EPOCH": "faithful mode: concept missing created_at_epoch/last_seen_epoch.",
    # duplicates
    "E_DUP_CONCEPT_ID": "duplicate concept_id.",
    "E_DUP_SOURCE_ID": "duplicate source_id.",
    "E_DUP_INSTANCE_ID": "duplicate instance_id.",
    # exclusions
    "E_DERIVED_PRESENT": "derived product present in bulk (must be excluded).",
}


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

ERROR = "ERROR"
WARNING = "WARNING"
NOTICE = "NOTICE"


@dataclass
class Issue:
    """A single structured validation finding.

    Attributes:
        severity: one of ``ERROR`` / ``WARNING`` / ``NOTICE``.
        code: a stable identifier from ``CHECK_CODES`` (machine-matchable).
        message: human-readable description of the specific finding.
        location: JSON-path-ish locator (e.g. ``bulk.relationships[3].from``).

    @verified cffa180b
    """

    severity: str
    code: str
    message: str
    location: str = ""

    def __str__(self) -> str:
        loc = f" at {self.location}" if self.location else ""
        return f"[{self.severity}] {self.code}: {self.message}{loc}"


@dataclass
class ValidationResult:
    """Aggregate result of validating one backup object.

    Holds the ordered list of :class:`Issue` findings. ``ok`` is True when no
    ``ERROR``-severity issue is present (NOTICE/WARNING do not fail validation).

    @verified cffa180b
    """

    issues: List[Issue] = field(default_factory=list)
    format_version: Optional[str] = None

    def add(self, severity: str, code: str, message: str, location: str = "") -> None:
        """Append a structured issue.  @verified cffa180b"""
        self.issues.append(Issue(severity, code, message, location))

    @property
    def errors(self) -> List[Issue]:
        """Issues with ERROR severity.  @verified cffa180b"""
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self) -> List[Issue]:
        """Issues with WARNING severity.  @verified cffa180b"""
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def ok(self) -> bool:
        """True when no ERROR-severity issue is present.  @verified cffa180b"""
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Core validation (pure: dict in, ValidationResult out)
# ---------------------------------------------------------------------------

def _is_int_index(value: Any) -> bool:
    """True when value is a usable list index (int, not bool).  @verified cffa180b"""
    return isinstance(value, int) and not isinstance(value, bool)


def validate_backup(obj: Dict[str, Any]) -> ValidationResult:
    """Validate a kg-backup object offline and return structured findings.

    Pure function: takes the already-parsed backup object (a ``dict``) and
    returns a :class:`ValidationResult`. Performs NO I/O — no file, network,
    database, or container access. Safe to call from pytest or an API handler.

    Negotiation (§7) gates the depth of validation:
      - ``kg-backup/2`` (exact major): full header + bulk validation.
      - ``kg-backup/1`` (legacy flat): emits ``N_LEGACY_FORMAT`` notice and
        validates the applicable subset (duplicates, basic referential links).
      - higher major / unknown family: emits ERROR and stops (refuse, §7).

    Args:
        obj: the parsed backup object.

    Returns:
        ValidationResult with ``.issues`` and ``.ok``.

    @verified cffa180b
    """
    result = ValidationResult()

    if not isinstance(obj, dict):
        result.add(ERROR, "E_NOT_OBJECT", "Backup object is not a JSON object.", "$")
        return result

    # ---- Legacy detection (§7 case 2): flat version/type/data, no header ----
    if "header" not in obj and "version" in obj and "data" in obj:
        result.format_version = str(obj.get("version"))
        result.add(
            NOTICE,
            "N_LEGACY_FORMAT",
            f"Legacy kg-backup/1 flat format detected (version={obj.get('version')!r}, "
            f"type={obj.get('type')!r}); validating applicable subset only.",
            "$",
        )
        _validate_legacy(obj, result)
        return result

    # ---- HEADER presence ----
    header = obj.get("header")
    if not isinstance(header, dict):
        result.add(ERROR, "E_NO_HEADER", "Missing or non-object 'header' region.", "$.header")
        return result

    # ---- format_version negotiation (§7) ----
    fmt = header.get("format_version")
    result.format_version = fmt if isinstance(fmt, str) else None
    if not isinstance(fmt, str) or not fmt:
        result.add(ERROR, "E_NO_FORMAT_VERSION", "header.format_version missing or empty.",
                   "$.header.format_version")
        return result

    if "/" not in fmt:
        result.add(ERROR, "E_FORMAT_VERSION_SHAPE",
                   f"format_version {fmt!r} is not '{{family}}/{{major}}'.",
                   "$.header.format_version")
        return result

    family, _, major_str = fmt.partition("/")
    if family != KNOWN_FAMILY:
        result.add(ERROR, "E_UNKNOWN_FAMILY",
                   f"Unknown format family {family!r}; refuse.",
                   "$.header.format_version")
        return result

    try:
        major = int(major_str)
    except ValueError:
        result.add(ERROR, "E_FORMAT_VERSION_SHAPE",
                   f"format_version major {major_str!r} is not an integer.",
                   "$.header.format_version")
        return result

    if major > NATIVE_MAJOR:
        result.add(ERROR, "E_HIGHER_MAJOR",
                   f"format_version {fmt!r} is a higher major than supported "
                   f"({KNOWN_FAMILY}/{NATIVE_MAJOR}); refuse (spec §7).",
                   "$.header.format_version")
        return result

    if major < NATIVE_MAJOR:
        # Known family, lower major embedded under a header — treat as legacy notice.
        result.add(NOTICE, "N_LEGACY_FORMAT",
                   f"Lower-major {fmt!r}; validating applicable subset.",
                   "$.header.format_version")

    # ---- kg-backup/2 full validation ----
    _validate_header(header, result)
    _validate_bulk(obj, header, result)
    return result


def _validate_header(header: Dict[str, Any], result: ValidationResult) -> None:
    """Validate required header fields and embedding-profile identities (§3).

    @verified cffa180b
    """
    for fieldname in REQUIRED_HEADER_FIELDS:
        if fieldname not in header:
            result.add(ERROR, "E_MISSING_HEADER_FIELD",
                       f"Required header field {fieldname!r} missing.",
                       f"$.header.{fieldname}")

    profiles = header.get("embedding_profiles")
    if isinstance(profiles, list):
        for i, prof in enumerate(profiles):
            identity = prof.get("identity") if isinstance(prof, dict) else None
            if not isinstance(identity, str) or not IDENTITY_RE.match(identity):
                result.add(ERROR, "E_PROFILE_IDENTITY",
                           f"embedding profile identity {identity!r} is not "
                           f"'{{provider}}:{{model}}@{{dims}}'.",
                           f"$.header.embedding_profiles[{i}].identity")

    n_profiles = len(profiles) if isinstance(profiles, list) else 0

    # default_embedding_profile index in range
    default_idx = header.get("default_embedding_profile")
    if _is_int_index(default_idx) and not (0 <= default_idx < n_profiles):
        result.add(ERROR, "E_DEFAULT_PROFILE_RANGE",
                   f"default_embedding_profile={default_idx} out of range "
                   f"[0,{n_profiles}).",
                   "$.header.default_embedding_profile")

    # ontology default indices in range
    ontologies = header.get("ontologies")
    if isinstance(ontologies, list):
        for i, ont in enumerate(ontologies):
            if not isinstance(ont, dict):
                continue
            idx = ont.get("default_embedding_profile")
            if _is_int_index(idx) and not (0 <= idx < n_profiles):
                result.add(ERROR, "E_ONTOLOGY_PROFILE_RANGE",
                           f"ontology {ont.get('name')!r} default_embedding_profile="
                           f"{idx} out of range [0,{n_profiles}).",
                           f"$.header.ontologies[{i}].default_embedding_profile")


def _resolve_concept_profile(
    concept: Dict[str, Any],
    backup_default: Any,
) -> Optional[int]:
    """Resolve a concept's effective embedding-profile index via the cascade (§4.1).

    Concepts use the 2-tier cascade — record override -> backup default — with
    NO ontology tier. A concept is cross-ontology by design (it associates with
    ontologies only via APPEARS->Source{document} and may span several), so it has
    no single home ontology to inherit from (BACKUP_OBJECT_SPEC §4.1, ADR-102 P2
    decision). The ontology tier is reserved for ontology-scoped records (sources).

    Returns the first present integer index, or ``None`` if neither tier yields one.

    @verified cffa180b
    """
    # 1. record override
    if _is_int_index(concept.get("embedding_profile")):
        return concept["embedding_profile"]
    # 2. backup default
    if _is_int_index(backup_default):
        return backup_default
    return None


def _validate_bulk(
    obj: Dict[str, Any], header: Dict[str, Any], result: ValidationResult
) -> None:
    """Validate the bulk region: indices, integrity, epochs, dups, exclusions (§4-6).

    @verified cffa180b
    """
    bulk = obj.get("bulk")
    if not isinstance(bulk, dict):
        result.add(ERROR, "E_NO_BULK", "Missing or non-object 'bulk' region.", "$.bulk")
        return

    # ---- §6 exclusions: derived products must be absent ----
    for key in EXCLUDED_BULK_KEYS:
        if key in bulk:
            result.add(ERROR, "E_DERIVED_PRESENT",
                       f"Derived product {key!r} present in bulk; must be regenerated "
                       f"post-restore, never serialized (spec §6).",
                       f"$.bulk.{key}")

    concepts = bulk.get("concepts") or []
    sources = bulk.get("sources") or []
    instances = bulk.get("instances") or []
    relationships = bulk.get("relationships") or []
    graph_epochs = bulk.get("graph_epochs")  # None => simple mode

    n_profiles = len(header.get("embedding_profiles") or [])
    n_rel_types = len(header.get("relationship_vocabulary") or [])
    n_content_types = len(header.get("content_types") or [])
    n_kinds = len(header.get("epoch_kinds") or [])
    n_actors = len(header.get("actors") or [])
    backup_default = header.get("default_embedding_profile")

    faithful = isinstance(graph_epochs, list)

    # ---- concepts: ids, dup, profile index, cascade, epoch fields ----
    concept_ids = set()
    for i, c in enumerate(concepts):
        if not isinstance(c, dict):
            continue
        cid = c.get("concept_id")
        if cid is not None:
            if cid in concept_ids:
                result.add(ERROR, "E_DUP_CONCEPT_ID",
                           f"duplicate concept_id {cid!r}.",
                           f"$.bulk.concepts[{i}].concept_id")
            concept_ids.add(cid)

        # record-level profile override in range
        prof_ref = c.get("embedding_profile")
        if _is_int_index(prof_ref) and not (0 <= prof_ref < n_profiles):
            result.add(ERROR, "E_CONCEPT_PROFILE_RANGE",
                       f"concept.embedding_profile={prof_ref} out of range "
                       f"[0,{n_profiles}).",
                       f"$.bulk.concepts[{i}].embedding_profile")

        # cascade resolves to a valid profile (concepts: record → backup, no ontology tier)
        resolved = _resolve_concept_profile(c, backup_default)
        if resolved is None:
            result.add(ERROR, "E_NO_PROFILE_CASCADE",
                       f"concept {cid!r} resolves to no embedding-profile via "
                       f"record→ontology→backup cascade (spec §4.1).",
                       f"$.bulk.concepts[{i}]")

        # faithful mode: concepts should carry epoch stamps
        if faithful:
            if c.get("created_at_epoch") is None or c.get("last_seen_epoch") is None:
                result.add(WARNING, "W_CONCEPT_NO_EPOCH",
                           f"faithful mode: concept {cid!r} missing created_at_epoch/"
                           f"last_seen_epoch (spec §5.1).",
                           f"$.bulk.concepts[{i}]")

    # ---- sources: ids, dup, content_type index ----
    source_ids = set()
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            continue
        sid = s.get("source_id")
        if sid is not None:
            if sid in source_ids:
                result.add(ERROR, "E_DUP_SOURCE_ID",
                           f"duplicate source_id {sid!r}.",
                           f"$.bulk.sources[{i}].source_id")
            source_ids.add(sid)

        ct = s.get("content_type")
        if _is_int_index(ct) and not (0 <= ct < n_content_types):
            result.add(ERROR, "E_CONTENT_TYPE_RANGE",
                       f"source.content_type={ct} out of range [0,{n_content_types}).",
                       f"$.bulk.sources[{i}].content_type")

    # ---- relationships: type index, from/to integrity, learned_id ----
    for i, r in enumerate(relationships):
        if not isinstance(r, dict):
            continue
        rtype = r.get("type")
        if _is_int_index(rtype) and not (0 <= rtype < n_rel_types):
            result.add(ERROR, "E_REL_TYPE_RANGE",
                       f"relationship.type={rtype} out of range [0,{n_rel_types}).",
                       f"$.bulk.relationships[{i}].type")

        frm = r.get("from")
        if frm is not None and frm not in concept_ids:
            result.add(ERROR, "E_REL_FROM_MISSING",
                       f"relationship.from {frm!r} not present in concepts[].",
                       f"$.bulk.relationships[{i}].from")
        to = r.get("to")
        if to is not None and to not in concept_ids:
            result.add(ERROR, "E_REL_TO_MISSING",
                       f"relationship.to {to!r} not present in concepts[].",
                       f"$.bulk.relationships[{i}].to")

        # §5.4.1 learned_id is a source_id by another name
        props = r.get("properties")
        if isinstance(props, dict) and "learned_id" in props:
            learned = props["learned_id"]
            if learned is not None and learned not in source_ids:
                result.add(ERROR, "E_LEARNED_ID_MISSING",
                           f"edge properties.learned_id {learned!r} does not reference "
                           f"an existing source_id (spec §5.4.1).",
                           f"$.bulk.relationships[{i}].properties.learned_id")

    # ---- instances: UNIQUE per instance_id (normalized — no concept_id; the
    #      Concept->Instance M:N links live in the separate evidence stream) ----
    event_ids = set()
    if faithful:
        for ep in graph_epochs:
            if isinstance(ep, dict) and "event_id" in ep:
                event_ids.add(ep["event_id"])

    instance_ids = set()
    for i, inst in enumerate(instances):
        if not isinstance(inst, dict):
            continue
        iid = inst.get("instance_id")
        if iid is not None:
            if iid in instance_ids:
                result.add(ERROR, "E_DUP_INSTANCE_ID",
                           f"duplicate instance_id {iid!r}.",
                           f"$.bulk.instances[{i}].instance_id")
            instance_ids.add(iid)

        sid = inst.get("source_id")
        if sid is not None and sid not in source_ids:
            result.add(ERROR, "E_INSTANCE_SOURCE_MISSING",
                       f"instance.source_id {sid!r} not present in sources[].",
                       f"$.bulk.instances[{i}].source_id")

        # epoch event-id resolution only enforced in faithful mode (§5.3)
        if faithful:
            ev = inst.get("created_at_event_id")
            if ev is not None and ev not in event_ids:
                result.add(ERROR, "E_EVENT_ID_UNRESOLVED",
                           f"instance.created_at_event_id={ev} does not resolve to a "
                           f"graph_epochs[].event_id (spec §5.3).",
                           f"$.bulk.instances[{i}].created_at_event_id")

    # ---- evidence: Concept->Instance links resolve to existing ids (§5.3.1) ----
    for i, ev in enumerate(bulk.get("evidence") or []):
        if not isinstance(ev, dict):
            continue
        cid = ev.get("concept_id")
        if cid is not None and cid not in concept_ids:
            result.add(ERROR, "E_EVIDENCE_CONCEPT_MISSING",
                       f"evidence.concept_id {cid!r} not present in concepts[].",
                       f"$.bulk.evidence[{i}].concept_id")
        iid = ev.get("instance_id")
        if iid is not None and iid not in instance_ids:
            result.add(ERROR, "E_EVIDENCE_INSTANCE_MISSING",
                       f"evidence.instance_id {iid!r} not present in instances[].",
                       f"$.bulk.evidence[{i}].instance_id")

    # ---- graph_epochs: kind/actor index resolution (§5.6) ----
    if faithful:
        for i, ep in enumerate(graph_epochs):
            if not isinstance(ep, dict):
                continue
            kind = ep.get("kind")
            if _is_int_index(kind) and not (0 <= kind < n_kinds):
                result.add(ERROR, "E_EPOCH_KIND_RANGE",
                           f"graph_epoch.kind={kind} out of range [0,{n_kinds}).",
                           f"$.bulk.graph_epochs[{i}].kind")
            actor = ep.get("actor")
            if _is_int_index(actor) and not (0 <= actor < n_actors):
                result.add(ERROR, "E_EPOCH_ACTOR_RANGE",
                           f"graph_epoch.actor={actor} out of range [0,{n_actors}).",
                           f"$.bulk.graph_epochs[{i}].actor")


def _validate_legacy(obj: Dict[str, Any], result: ValidationResult) -> None:
    """Best-effort validation of a legacy kg-backup/1 flat object (§7 case 2).

    Legacy has flat ``version``/``type``/``data`` with inline strings and no
    header/epoch fields. Only duplicate-id and basic referential checks apply.

    @verified cffa180b
    """
    data = obj.get("data")
    if not isinstance(data, dict):
        return
    concepts = data.get("concepts") or []
    sources = data.get("sources") or []
    instances = data.get("instances") or []
    relationships = data.get("relationships") or []

    concept_ids = set()
    for i, c in enumerate(concepts):
        if not isinstance(c, dict):
            continue
        cid = c.get("concept_id")
        if cid is not None:
            if cid in concept_ids:
                result.add(ERROR, "E_DUP_CONCEPT_ID", f"duplicate concept_id {cid!r}.",
                           f"$.data.concepts[{i}].concept_id")
            concept_ids.add(cid)

    source_ids = set()
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            continue
        sid = s.get("source_id")
        if sid is not None:
            if sid in source_ids:
                result.add(ERROR, "E_DUP_SOURCE_ID", f"duplicate source_id {sid!r}.",
                           f"$.data.sources[{i}].source_id")
            source_ids.add(sid)

    instance_ids = set()
    for i, inst in enumerate(instances):
        if not isinstance(inst, dict):
            continue
        iid = inst.get("instance_id")
        if iid is not None:
            if iid in instance_ids:
                result.add(ERROR, "E_DUP_INSTANCE_ID", f"duplicate instance_id {iid!r}.",
                           f"$.data.instances[{i}].instance_id")
            instance_ids.add(iid)
        cid = inst.get("concept_id")
        if cid is not None and cid not in concept_ids:
            result.add(ERROR, "E_INSTANCE_CONCEPT_MISSING",
                       f"instance.concept_id {cid!r} not present in concepts[].",
                       f"$.data.instances[{i}].concept_id")
        sid = inst.get("source_id")
        if sid is not None and sid not in source_ids:
            result.add(ERROR, "E_INSTANCE_SOURCE_MISSING",
                       f"instance.source_id {sid!r} not present in sources[].",
                       f"$.data.instances[{i}].source_id")

    for i, r in enumerate(relationships):
        if not isinstance(r, dict):
            continue
        frm = r.get("from")
        if frm is not None and frm not in concept_ids:
            result.add(ERROR, "E_REL_FROM_MISSING",
                       f"relationship.from {frm!r} not present in concepts[].",
                       f"$.data.relationships[{i}].from")
        to = r.get("to")
        if to is not None and to not in concept_ids:
            result.add(ERROR, "E_REL_TO_MISSING",
                       f"relationship.to {to!r} not present in concepts[].",
                       f"$.data.relationships[{i}].to")


# ---------------------------------------------------------------------------
# I/O boundary (CLI only — kept out of the pure core)
# ---------------------------------------------------------------------------

def load_backup_object(path: str) -> Dict[str, Any]:
    """Load a backup object from a JSON file or a .tar.gz archive.

    For a ``.tar.gz`` archive, the embedded ``manifest.json`` (the logical
    backup object) is extracted in-memory and parsed. This is the only I/O the
    module performs and it lives outside :func:`validate_backup`.

    Args:
        path: filesystem path to a ``.json`` or ``.tar.gz`` backup.

    Returns:
        The parsed backup object (dict).

    Raises:
        ValueError: archive has no manifest.json, or content is not a JSON object.

    @verified cffa180b
    """
    if path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as tar:
            member = None
            for name in ("manifest.json", "./manifest.json"):
                try:
                    member = tar.getmember(name)
                    break
                except KeyError:
                    continue
            if member is None:
                # fall back: any *manifest.json in the archive
                for m in tar.getmembers():
                    if m.name.endswith("manifest.json"):
                        member = m
                        break
            if member is None:
                raise ValueError(f"No manifest.json found in archive {path!r}.")
            fobj = tar.extractfile(member)
            if fobj is None:
                raise ValueError(f"Could not read {member.name!r} from {path!r}.")
            data = json.load(io.TextIOWrapper(fobj, encoding="utf-8"))
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Backup object in {path!r} is not a JSON object.")
    return data


def print_report(result: ValidationResult) -> None:
    """Print a human-readable report of a ValidationResult.  @verified cffa180b"""
    if not result.issues:
        print("OK: no issues found.")
        return

    for issue in result.issues:
        print(str(issue))

    n_err = len(result.errors)
    n_warn = len(result.warnings)
    n_notice = sum(1 for i in result.issues if i.severity == NOTICE)
    print()
    print(f"Summary: {n_err} error(s), {n_warn} warning(s), {n_notice} notice(s)"
          f"  [format_version={result.format_version}]")


# ---------------------------------------------------------------------------
# Inline self-test (optional; --selftest)
# ---------------------------------------------------------------------------

def _selftest() -> int:
    """Run a minimal valid/invalid self-test. Returns process exit code.

    @verified cffa180b
    """
    valid = {
        "header": {
            "format_version": "kg-backup/2",
            "source": {"platform": "kg", "version": "1.7.3"},
            "exported_at": "2026-06-01T00:00:00Z",
            "schema_version": 76,
            "embedding_profiles": [
                {"identity": "openai:text-embedding-3-small@1536"}
            ],
            "default_embedding_profile": 0,
            "relationship_vocabulary": [{"relationship_type": "IMPLIES"}],
            "epoch_kinds": [{"kind": "ingestion"}],
            "actors": ["system"],
            "content_types": ["text/plain"],
            "ontologies": [{"name": "Corpus", "default_embedding_profile": 0}],
        },
        "bulk": {
            "concepts": [{"concept_id": "c1", "label": "A"}],
            "sources": [{"source_id": "s1", "content_type": 0}],
            "instances": [{"instance_id": "i1", "source_id": "s1"}],
            "evidence": [{"concept_id": "c1", "instance_id": "i1"}],
            "relationships": [
                {"from": "c1", "to": "c1", "type": 0,
                 "properties": {"learned_id": "s1"}}
            ],
            "vocabulary": [],
        },
    }
    r1 = validate_backup(valid)
    assert r1.ok, f"valid sample should pass, got: {[str(i) for i in r1.issues]}"

    invalid = {
        "header": {
            "format_version": "kg-backup/2",
            "source": {}, "exported_at": "x", "schema_version": 1,
            "embedding_profiles": [{"identity": "bogus-identity"}],
            "default_embedding_profile": 9,  # out of range
            "relationship_vocabulary": [],
            "epoch_kinds": [], "actors": [], "content_types": [], "ontologies": [],
        },
        "bulk": {
            "concepts": [
                {"concept_id": "c1"}, {"concept_id": "c1"},  # dup
            ],
            "sources": [{"source_id": "s1", "content_type": 5}],  # out of range
            "instances": [{"instance_id": "i1", "source_id": "sX"}],  # source missing
            "evidence": [
                {"concept_id": "cX", "instance_id": "i1"},   # concept missing
                {"concept_id": "c1", "instance_id": "iX"},   # instance missing
            ],
            "relationships": [
                {"from": "cZ", "to": "c1", "type": 7,
                 "properties": {"learned_id": "sZ"}}
            ],
            "artifacts": [],  # excluded derived product
        },
    }
    r2 = validate_backup(invalid)
    assert not r2.ok, "invalid sample should fail"
    codes = {i.code for i in r2.issues}
    expected = {
        "E_PROFILE_IDENTITY", "E_DEFAULT_PROFILE_RANGE", "E_DUP_CONCEPT_ID",
        "E_CONTENT_TYPE_RANGE", "E_INSTANCE_SOURCE_MISSING",
        "E_EVIDENCE_CONCEPT_MISSING", "E_EVIDENCE_INSTANCE_MISSING",
        "E_REL_FROM_MISSING", "E_REL_TYPE_RANGE",
        "E_LEARNED_ID_MISSING", "E_DERIVED_PRESENT",
    }
    missing = expected - codes
    assert not missing, f"invalid sample missing expected codes: {missing}"

    # legacy detection
    legacy = {"version": "1.0", "type": "full", "data": {"concepts": [], "sources": [],
              "instances": [], "relationships": []}}
    r3 = validate_backup(legacy)
    assert any(i.code == "N_LEGACY_FORMAT" for i in r3.issues), "legacy notice expected"

    print("selftest: PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point: load a path, validate, print, return exit code.

    Exit code is 1 when any ERROR-severity issue is present (CI convention),
    else 0. ``--selftest`` runs the inline samples instead.

    @verified cffa180b
    """
    parser = argparse.ArgumentParser(
        description="Offline validator for kg-backup objects (no platform needed)."
    )
    parser.add_argument("path", nargs="?",
                        help="Path to a backup .json or .tar.gz archive.")
    parser.add_argument("--selftest", action="store_true",
                        help="Run the inline valid/invalid self-test and exit.")
    parser.add_argument("--json", action="store_true",
                        help="Emit issues as JSON instead of human text.")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.path:
        parser.error("a backup path is required (or use --selftest)")

    try:
        obj = load_backup_object(args.path)
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as e:
        print(f"Error: could not load {args.path!r}: {e}", file=sys.stderr)
        return 1

    result = validate_backup(obj)

    if args.json:
        print(json.dumps({
            "ok": result.ok,
            "format_version": result.format_version,
            "issues": [
                {"severity": i.severity, "code": i.code,
                 "message": i.message, "location": i.location}
                for i in result.issues
            ],
        }, indent=2))
    else:
        print_report(result)

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
