# Understanding: Vocabulary Lifecycle & Grounded LLM Decisions

Working reference for why the vocabulary management system works the way it does.
Written collaboratively (human + Claude) on 2026-02-08 during product readiness work.

## The Problem

As documents are ingested, the LLM invents relationship types organically —
IMPLIES, SUPPORTS, HISTORICALLY_PRECEDED, etc. Over time the vocabulary sprawls:
near-duplicates appear, some types accumulate zero edges, others become
structurally irrelevant. Something needs to govern this lifecycle.

## The Key Insight

The system already computes objective mathematical scores for every relationship
type: grounding strength, similarity to other types, edge counts, traversal
frequency, bridge importance, polarity positioning, epistemic status. These
numbers describe reality.

A human reviewing vocabulary decisions would look at these same numbers and
compute a function: "low value, no bridges, similar to another type → merge."
If the human ignored the numbers and went with gut feeling, they'd be
inconsistent, biased, and worse than the math.

An LLM, given the same numbers as context, computes the same function — but
also brings reasoning that a pure threshold cannot: "these types look
numerically similar but capture different semantic intent." This is the same
external reasoning a human would bring, and a capable LLM does it at
comparable quality.

**Therefore: math grounds the LLM, the LLM reasons over the math, and the
combination is more consistent than a human in the loop.**

The human's role is bringing external information *into* the graph (new
documents, new knowledge domains), not reviewing vocabulary hygiene decisions
that the system can make objectively.

## The Design: Math → LLM → Execute

1. **Score**: Mathematical evaluation of each relationship type (value score,
   edge count, bridge count, similarity to other types, traversal patterns)
2. **Present**: Format the scores as structured context in a prompt that asks
   the LLM to reason about the decision (merge? deprecate? prune? skip?)
3. **Decide**: The LLM reads real numbers and applies judgment. The grounding
   prevents drift — the LLM can't hallucinate that a zero-edge type is
   important when the math says otherwise
4. **Execute**: Carry out the decision against the database

The three-tier review model (automatic / AI / human) still exists but the
tiers mean:
- **Automatic**: Pure math, no ambiguity (zero-edge type → prune)
- **AI (LLM-grounded)**: Math + reasoning for moderate cases
- **Human**: Optional audit/override, not the primary path

## Current State of the Code

The scoring and recommendation engine works. The prompts in
`pruning_strategies.py` are correctly structured — they present the math and
ask for a decision. What's broken:

- The LLM is never called. Heuristic thresholds stand in as a degenerate
  case (strip out reasoning, just threshold on the numbers)
- `_execute_prune()` and `_execute_deprecate()` return success without
  touching the database. The pipeline breaks at the last mile.
- The heuristic results are mislabeled as `ReviewLevel.AI` with
  `"ai_decision"` metadata, which is dishonest

## What Needs to Happen

1. Wire `_ai_review_merge_candidate()` and `_ai_review_low_value()` to an
   actual LLM call (the prompts are already written). Keep heuristic as
   fallback when no reasoning provider is configured.
2. Implement `_execute_prune()` — the SQL is sketched in the TODOs
3. Implement `_execute_deprecate()` — same
4. Fix review level labels: heuristic fallback should be labeled honestly
5. `get_pending_reviews()` and `approve_action()` work but lack persistence —
   lower priority since the primary path is automated

## After It Works

If the system behaves as expected with GPT-4o as the reasoning LLM, fold this
understanding into the actual codebase:
- Docstrings on the vocabulary manager and pruning strategies (more important
  than standalone docs — agents and humans read these first)
- Consider an ADR if the grounded-LLM-decision pattern generalizes to other
  subsystems (e.g., ontology annealing uses similar logic)
