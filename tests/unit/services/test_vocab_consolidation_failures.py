"""
Unit tests for how AITL vocabulary consolidation handles failed LLM
evaluations (#592).

A run of consecutive failures means the provider is down or the key is bad,
so consolidation stops instead of calling the LLM once per remaining pair.
A success in between resets the count.

The manager is built without __init__; vocabulary analysis and the LLM call
are stubbed. No database, no network.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from api.app.lib.pruning_strategies import MergeDecision
from api.app.services.vocabulary_manager import (
    MAX_CONSECUTIVE_EVAL_FAILURES,
    VocabularyManager,
)


FAILED = MergeDecision(should_merge=False, reasoning="provider down", failed=True)
REJECTED = MergeDecision(should_merge=False, reasoning="inverses")


def _manager(pair_count: int) -> VocabularyManager:
    """A manager whose analysis always offers `pair_count` distinct pairs."""
    manager = object.__new__(VocabularyManager)
    manager.ai_provider = MagicMock()
    manager.db = MagicMock()
    score = SimpleNamespace(edge_count=1, epistemic_status=None)
    pairs = [
        (SimpleNamespace(type1=f"A{i}", type2=f"B{i}", similarity=0.9), score, score, 1.0)
        for i in range(pair_count)
    ]
    manager.analyze_vocabulary = AsyncMock(return_value=SimpleNamespace(synonym_candidates=[]))
    manager.prioritize_merge_candidates = MagicMock(return_value=pairs)
    manager._get_vocabulary_size = AsyncMock(return_value=1000)
    return manager


def _run(manager: VocabularyManager, decisions, dry_run: bool):
    evaluate = AsyncMock(side_effect=list(decisions))
    with patch("api.app.lib.pruning_strategies.llm_evaluate_merge", evaluate):
        results = asyncio.run(
            manager.aitl_consolidate_vocabulary(target_size=10, dry_run=dry_run)
        )
    return results, evaluate.await_count


def test_live_run_stops_after_consecutive_failures():
    results, calls = _run(_manager(20), [FAILED] * 20, dry_run=False)

    assert calls == MAX_CONSECUTIVE_EVAL_FAILURES
    assert len(results["failed"]) == MAX_CONSECUTIVE_EVAL_FAILURES


def test_dry_run_stops_after_consecutive_failures():
    results, calls = _run(_manager(10), [FAILED] * 10, dry_run=True)

    assert calls == MAX_CONSECUTIVE_EVAL_FAILURES
    assert len(results["failed"]) == MAX_CONSECUTIVE_EVAL_FAILURES


def test_a_decision_between_failures_resets_the_count():
    below = MAX_CONSECUTIVE_EVAL_FAILURES - 1
    decisions = [FAILED] * below + [REJECTED] + [FAILED] * below + [REJECTED]

    results, calls = _run(_manager(len(decisions)), decisions, dry_run=False)

    assert calls == len(decisions)
    assert len(results["failed"]) == 2 * below
    assert len(results["rejected"]) == 2
