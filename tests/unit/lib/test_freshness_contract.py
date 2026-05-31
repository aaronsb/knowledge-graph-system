"""
Conformance tests for the ADR-207 materialized-derivation freshness contract.

These pin the contract itself (no DB): every registered derivation implements a
contract shape and declares a budget; the shared clock helper resolves against
the committed-epoch watermark and never the graph_change_counter; and the
default on-read detection honors the staleness budget (the #422-forbidding
behavior). Importing the derivation modules is what triggers their
@register_derivation, so the registry reflects what actually ships.
"""

from unittest.mock import MagicMock

import pytest

from api.app.lib.freshness import (
    Budget,
    CollectionDerivation,
    FreshnessContract,
    InstanceDerivation,
    read_committed_epoch,
    register_derivation,
    registered_derivations,
)

# Importing these registers the shipped derivations (the @register_derivation
# decorator runs on import), so the registry reflects what actually ships.
from api.app.lib.catalog_facade import CatalogFacade
from api.app.lib.age_client.grounding import (
    GroundingCacheDerivation,
    PolarityAxisDerivation,
)
from api.app.services.confidence_analyzer import ConfidenceCacheDerivation


# --------------------------------------------------------------------- registry

def test_registry_includes_the_catalog_reference_implementation():
    """CatalogFacade registers itself as the reference derivation."""
    assert CatalogFacade in registered_derivations()


def test_registry_includes_both_grounding_tiers_separately():
    """The grounding cluster registers as two derivations on two clocks (D3)."""
    registered = registered_derivations()
    assert GroundingCacheDerivation in registered
    assert PolarityAxisDerivation in registered


def test_registry_includes_the_confidence_cache():
    """The confidence cache registers as its own derivation."""
    assert ConfidenceCacheDerivation in registered_derivations()


def test_every_registered_derivation_conforms():
    """Each registered derivation is one of the two contract shapes and declares
    a non-empty registry name plus a Budget. This is the CI gate: a new
    derivation that forgets the contract fails here, not in production."""
    derivations = registered_derivations()
    assert derivations, "no derivations registered — import wiring is broken"
    for cls in derivations:
        assert issubclass(cls, (CollectionDerivation, InstanceDerivation)), (
            f"{cls.__name__} must implement a contract shape"
        )
        assert isinstance(cls.name, str) and cls.name, (
            f"{cls.__name__} must declare a non-empty registry name"
        )
        assert isinstance(cls.budget, Budget), (
            f"{cls.__name__} must declare a Budget"
        )


# ----------------------------------------------------------------- canonical clock

def test_read_committed_epoch_uses_the_watermark_not_the_counter():
    """The one sanctioned freshness signal is get_committed_epoch(); the
    non-injective graph_change_counter must never back a freshness decision."""
    cur = MagicMock()
    cur.fetchone.return_value = (5,)

    result = read_committed_epoch(cur)

    assert result == 5
    sql = cur.execute.call_args[0][0]
    assert "get_committed_epoch" in sql
    assert "get_graph_epoch" not in sql


def test_read_committed_epoch_handles_dict_and_empty_rows():
    """Works for RealDictCursor (dict) and degrades to 0 on no row / null."""
    dict_cur = MagicMock()
    dict_cur.fetchone.return_value = {"get_committed_epoch": 7}
    assert read_committed_epoch(dict_cur) == 7

    empty_cur = MagicMock()
    empty_cur.fetchone.return_value = None
    assert read_committed_epoch(empty_cur) == 0


# ------------------------------------------------------------------------- budget

def test_budget_strict_is_exact_match():
    b = Budget.strict()
    assert b.versions == 0
    assert b.tolerates(stamp=5, current=5) is True
    assert b.tolerates(stamp=4, current=5) is False


def test_budget_tolerant_permits_lag_within_bound():
    b = Budget(versions=2)
    assert b.tolerates(stamp=3, current=5) is True   # 2 behind, within budget
    assert b.tolerates(stamp=2, current=5) is False  # 3 behind, exceeds budget


# --------------------------------------------------- default on-read detection

class _StubCollection(CollectionDerivation):
    """Minimal CollectionDerivation to exercise the inherited is_fresh()."""

    name = "stub_collection"

    def __init__(self, stamp, current, budget=Budget.strict()):
        self._stamp = stamp
        self._current = current
        self.budget = budget

    def version_stamp(self):
        return self._stamp

    def current_version(self):
        return self._current

    def reconcile(self):  # pragma: no cover - not exercised here
        pass


def test_is_fresh_true_only_when_within_budget():
    assert _StubCollection(stamp=5, current=5).is_fresh() is True
    assert _StubCollection(stamp=4, current=5).is_fresh() is False
    assert _StubCollection(stamp=3, current=5, budget=Budget(versions=2)).is_fresh() is True


def test_is_fresh_treats_never_built_as_stale():
    """A None stamp (never built) is stale — forces an initial build."""
    assert _StubCollection(stamp=None, current=5).is_fresh() is False


def test_is_fresh_reads_current_version_every_call():
    """Deferred on-read detection must re-read current_version each call — no
    warm-path short-circuit that skips the compare (the #422 defect)."""
    d = _StubCollection(stamp=5, current=5)
    d.current_version = MagicMock(return_value=5)
    d.is_fresh()
    d.is_fresh()
    assert d.current_version.call_count == 2


# --------------------------------------------------------------- contract typing

def test_contract_shapes_share_the_base():
    assert issubclass(CollectionDerivation, FreshnessContract)
    assert issubclass(InstanceDerivation, FreshnessContract)


def test_abstract_methods_block_incomplete_implementations():
    """A derivation missing a contract method cannot be instantiated."""
    class _Incomplete(CollectionDerivation):
        name = "incomplete"
        # missing version_stamp / current_version / reconcile

    with pytest.raises(TypeError):
        _Incomplete()
