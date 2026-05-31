"""
Materialized-derivation freshness contract (ADR-207).

The platform maintains several *materialized derivations* of the graph — caches
of a graph computation that must track the graph as it mutates: the catalog
index, the grounding/polarity cache tiers, and saved artifacts. Each one answers
the same four questions — what version was I built at? what is the version now?
am I stale? what do I do when I am? — and historically each answered them
ad-hoc, against different (and sometimes unsound) version signals.

This module is the one place those answers live:

- `read_committed_epoch(cur)` — THE canonical freshness clock (ADR-207 D1): the
  committed-prefix watermark over the ADR-203 epoch event log. Every derivation
  resolves freshness against this and nothing else. Never use
  `kg_api.get_graph_epoch()` (the graph_change_counter) for a freshness
  decision — it is a non-injective count checksum (ADR-203) and can read
  false-FRESH; it is a one-directional dirty-hint only.

- `Budget` — a derivation's declared staleness tolerance. Default is strict
  (must be at the current version). A derivation opts into bounded staleness
  explicitly.

- `CollectionDerivation` / `InstanceDerivation` — the two contract shapes. A
  collection derivation has ONE stamp for the whole thing and reconciles by
  rebuilding/invalidating the lot (catalog index, a grounding cache tier). An
  instance derivation is per-row: each item carries its own stamp and reconciles
  independently (artifacts). Forcing both behind one interface was an ISP/LSP
  leak (ADR-207 D3), hence two shapes over a shared base.

- the registry — derivations register their class so a conformance test can
  assert every one implements the contract (CI catches a new derivation that
  forgets on-read detection), and an operator surface can enumerate them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Type

__all__ = [
    "read_committed_epoch",
    "SubCounter",
    "SUBCOUNTERS",
    "subcounters",
    "Budget",
    "FreshnessContract",
    "CollectionDerivation",
    "InstanceDerivation",
    "register_derivation",
    "registered_derivations",
]


def read_committed_epoch(cur) -> int:
    """Read the canonical freshness clock: kg_api.get_committed_epoch().

    ADR-207 D1: the committed-prefix watermark over the ADR-203 epoch sequence —
    monotonic, gap-tolerant, and out-of-order-completion safe. This is the ONLY
    sanctioned freshness signal; `cur` is any open cursor (RealDict or plain).
    """
    cur.execute("SELECT kg_api.get_committed_epoch()")
    row = cur.fetchone()
    if row is None:
        return 0
    val = list(row.values())[0] if isinstance(row, dict) else row[0]
    return int(val) if val is not None else 0


# ----------------------------------------------------------------- sub-counters

@dataclass(frozen=True)
class SubCounter:
    """A monotonic counter subordinate to the universal tick (ADR-207 D1, step 4).

    The committed-epoch watermark (`read_committed_epoch`) is the ONE clock for
    graph-topology freshness. A sub-counter is a narrower monotonic signal that
    lives *under* it, of one of two kinds:

    - a **co-advancing mirror** (`coadvances_with_tick=True`): moves in lockstep
      with the tick, for a layer that needs its own invalidation channel.
      `graph_accel.generation` is the only one — `AGEClient.record_mutation`
      advances the tick AND calls `graph.invalidate()` from one place, so the two
      move together *by construction* (pinned by the co-advance test). It is not a
      second clock; it exists because the in-memory accelerator (ADR-201) needs a
      `pg_notify`-backed signal the SQL watermark cannot deliver to API processes.

    - an **independent narrower scope** (`coadvances_with_tick=False`): advances
      only when its own, narrower source-of-truth changes. A derivation whose
      input is narrower than the whole graph tracks this *instead of* the tick —
      the polarity axis is derived from vocabulary embeddings, so it keys on
      `vocabulary_embedding_generation_counter` (which changes far more rarely than
      the graph); keying it on the tick would force needless axis recompute.

    Declaring them makes the hierarchy a code-backed fact, not just prose: there
    is exactly one universal tick, and every other counter is enumerated here as
    subordinate to it, each with its relationship stated.
    """

    #: SQL/identifier name of the counter.
    name: str
    #: What it invalidates / what it is the freshness signal for.
    scope: str
    #: True iff it advances in lockstep with the universal tick (every
    #: record_mutation co-advances it); False for independent narrower clocks.
    coadvances_with_tick: bool
    #: The wiring that advances it (what keeps it monotonic).
    advanced_by: str


#: Every monotonic counter subordinate to the universal tick (ADR-207 step 4).
#: The universal tick itself (the `event_id` watermark, read via
#: `read_committed_epoch`) is deliberately NOT listed — it is the clock these are
#: subordinate to, not a peer.
SUBCOUNTERS: List["SubCounter"] = [
    SubCounter(
        name="graph_accel.generation",
        scope="in-memory grounding/polarity accelerator (ADR-201, migration 051)",
        coadvances_with_tick=True,
        advanced_by="AGEClient.record_mutation → graph.invalidate() (+ pg_notify)",
    ),
    SubCounter(
        name="vocabulary_change_counter",
        scope="vocabulary (relationship-type) membership",
        coadvances_with_tick=False,
        advanced_by="vocabulary add/remove",
    ),
    SubCounter(
        name="vocabulary_embedding_generation_counter",
        scope="vocabulary embedding regeneration (the polarity axis keys on this)",
        coadvances_with_tick=False,
        advanced_by="vocabulary embedding regeneration (migration 069)",
    ),
]


def subcounters() -> List["SubCounter"]:
    """All declared sub-counters subordinate to the universal tick (ADR-207 step 4)."""
    return list(SUBCOUNTERS)


@dataclass(frozen=True)
class Budget:
    """A derivation's declared staleness tolerance (ADR-207 D2).

    `versions` is how many clock-versions behind the derivation may serve before
    it must reconcile. The default (0) is strict: the derivation must reflect the
    current committed watermark. A wall-clock axis (stale_ok_ms) is reserved for
    later — it needs per-derivation build timestamps and is not yet enforced.
    """

    versions: int = 0

    @classmethod
    def strict(cls) -> "Budget":
        """Zero tolerance — the derivation must be at the current version."""
        return cls(versions=0)

    def tolerates(self, stamp: int, current: int) -> bool:
        """True if a derivation built at `stamp` is fresh enough against `current`.

        On the monotonic watermark a stamp can never exceed `current`, so strict
        (versions=0) is exactly `stamp == current`; a positive budget permits
        being that many versions behind.
        """
        return (current - stamp) <= self.versions


class FreshnessContract(ABC):
    """Shared base for every materialized derivation (ADR-207 D3).

    Subclasses do not inherit this directly — they implement one of the two
    shapes below. The base pins what is common: a registry `name`, a declared
    staleness `budget`, and resolution against the one canonical clock.
    """

    #: Stable registry key, also the operator-facing label.
    name: str = ""

    #: Declared staleness tolerance; strict by default.
    budget: Budget = Budget.strict()

    @abstractmethod
    def current_version(self) -> int:
        """The monotonic version this derivation tracks, read now.

        Graph-topology derivations return `read_committed_epoch(cur)` — the
        shared helper keeps the canonical-clock SQL in one place so no
        graph-derived surface drifts onto a different signal. A derivation whose
        source-of-truth is a narrower scope returns *that* monotonic sub-counter
        instead (e.g. the polarity axis is derived from vocabulary embeddings, so
        it tracks `vocabulary_embedding_generation_counter`, not the graph tick).
        Either way it must be monotonic and advance when the source changes."""
        raise NotImplementedError


class CollectionDerivation(FreshnessContract):
    """A whole-derivation materialized view: one stamp for the entire thing,
    reconcile rebuilds/invalidates the lot (catalog index, a grounding tier)."""

    @abstractmethod
    def version_stamp(self) -> Optional[int]:
        """The clock value the derivation was last built at, or None if never
        built (which reads as stale)."""
        raise NotImplementedError

    def is_fresh(self) -> bool:
        """Deferred, on-read freshness, honoring the declared budget. Never a
        warm-path short-circuit that skips reading current_version() — that is
        the #422 defect the contract forbids."""
        stamp = self.version_stamp()
        if stamp is None:
            return False
        return self.budget.tolerates(stamp, self.current_version())

    @abstractmethod
    def reconcile(self) -> None:
        """Make the derivation reflect current_version() (rebuild or invalidate).
        Idempotent: a no-op when already fresh."""
        raise NotImplementedError


class InstanceDerivation(FreshnessContract):
    """A per-row materialized view: each item carries its own stamp and
    reconciles independently from its stored parameters (artifacts)."""

    @abstractmethod
    def version_stamp(self, item_id) -> Optional[int]:
        """The clock value `item_id` was built at, or None if absent."""
        raise NotImplementedError

    def is_fresh(self, item_id) -> bool:
        """Deferred, on-read freshness for one item, honoring the budget."""
        stamp = self.version_stamp(item_id)
        if stamp is None:
            return False
        return self.budget.tolerates(stamp, self.current_version())

    @abstractmethod
    def reconcile(self, item_id) -> None:
        """Regenerate one item so it reflects current_version()."""
        raise NotImplementedError


# --------------------------------------------------------------------- registry

_DERIVATION_CLASSES: List[Type[FreshnessContract]] = []


def register_derivation(cls: Type[FreshnessContract]) -> Type[FreshnessContract]:
    """Register a derivation class (usable as a class decorator).

    Registration buys the conformance test (every registered derivation must
    implement a contract shape) and the operator surface (enumerate derivations,
    show freshness, trigger reconcile)."""
    if cls not in _DERIVATION_CLASSES:
        _DERIVATION_CLASSES.append(cls)
    return cls


def registered_derivations() -> List[Type[FreshnessContract]]:
    """All registered derivation classes (for conformance tests / operator UI)."""
    return list(_DERIVATION_CLASSES)
