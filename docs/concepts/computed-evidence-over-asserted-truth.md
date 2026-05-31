# Computed Evidence over Asserted Truth

*An engineering-philosophy note on why this system models knowledge the way it does — and why one common feature (bi-temporal "valid time") is deliberately absent.*

## The one-line inversion

Most knowledge systems **assert truth** and then maintain it. This system **computes evidence** and never asserts. That single inversion explains most of what makes it different — including a few things that look, at first glance, like missing features.

A conventional knowledge graph stores facts: *"X is true."* When a contradicting fact arrives, it has to decide — usually the new one wins, the old one is retired. The graph is always a snapshot of the current best-known truth.

This system stores no truths. A concept carries a **grounding score** — a continuous measurement computed from the balance of supporting versus contradicting evidence. A claim backed by forty-seven sources with twelve contradictions scores differently from one with a single unchallenged mention. When sources disagree, both sides stay. Nothing is retired for being "wrong"; its standing simply reflects the evidence pulling on it.

## Why there is no "valid time"

The clearest place this shows up is temporal modeling.

Bi-temporal systems (Zep/Graphiti is the well-known one) track two clocks: *transaction time* — when the system learned a fact — and *valid time* — when the fact was true in the world. The second clock is the interesting one, and it is exactly what this system refuses.

Valid time only means something if a fact **has** a truth value that holds over a real-world interval and can later become false. That is a correspondence theory of truth baked into the schema: the graph is supposed to mirror reality and track when reality changed. The operational tell is how such a system resolves a contradiction — it stamps the old fact with a `valid_to`, declaring *when it stopped being true*. Contradiction is settled by **supersession**.

This system keeps the *transaction-time* clock — that is precisely what the **ingestion epoch** is (`created_at_epoch`, `last_seen_epoch`): when evidence first arrived and when it was last reinforced. But it has no valid-time clock, and can't have one, because to write `valid_to` you must first assert that the claim *was* true — you must pick a winner. That is the one move the epistemic model is built to never make.

So the narrower temporal axis is not a gap. It is the same decision, viewed from a different angle: **we do not encode truth, so we cannot encode when truth changed.** What we can encode — and do — is when evidence accrued.

## Decisions are views, not writes

The deeper principle underneath both points is **non-destructiveness**.

A bi-temporal store, by expiring superseded facts, bakes a decision *into storage*. If the decision was wrong — a bad invalidation, a premature supersession — the losing evidence is gone, and the mistake compounds silently. You cannot recompute your way out of data you deleted.

This system treats every judgment as a **derived view**, not a stored fact. Grounding is computed, not written. Contradictions are preserved, not resolved. Ontologies are *annealed* — continuously reorganized by a background worker — rather than fixed at ingest. Because the evidence is never thrown away, any judgment can be **recomputed** when the data grows, the methods improve, or the compute gets cheaper. The graph is an accumulating substrate of evidence; the "answers" are functions over it that you can re-run.

This is also why the system keeps the original image beside its prose description, why it preserves both sides of a disagreement, and why "don't reset the graph" is a working principle rather than a slogan: the messy, contradictory, accumulated state *is* the asset.

## The bitter lesson, and the training wheels

Rich Sutton's "bitter lesson" is that general methods which scale with computation beat methods that bake in human knowledge — every time, eventually, by a large margin. Hand-built domain structure gives satisfying early wins and then plateaus.

Bi-temporal truth-maintenance is, in this light, a human-knowledge layer: someone has to decide what is true and when it stopped being true, and keep those intervals correct as the world contradicts itself. That is the kind of structure the bitter lesson comes for.

This system's bet is the other direction: **bake in no decisions; compute over accumulated evidence.** But honesty requires naming where it isn't there yet. There are hand-tuned constants today — a merge threshold, grounding weights, a closed vocabulary of annealing actions. Those are **training wheels**, not the philosophy. They exist to get the system *working* before it can be trusted to find its own settings. The direction of travel is to let computation take them over.

And there is already first evidence that it can. Left to run on its own, the **annealing worker reorganized raw extracted concepts into coherent emergent ontologies** — splitting and naming themes nobody specified, without a human drawing the schema. That is a small, concrete instance of the scaffolding coming off: the structure emerged from computation over evidence, not from a designer's ontology. The hand-tuned numbers are the wheels; the annealing graph is the first ride without them.

The loop is built to close further. Annealing already governs its promotion, demotion, split, and merge thresholds with **tunable pressure curves** rather than fixed cutoffs (ADR-200; the Bezier "ecological pressure" mechanism). And every annealing decision is recorded against the epoch event log (ADR-203), so the pool of decisions **deepens with each epoch**. The active frontier is to feed that accumulating decision history *back* into the curves — letting the system's own track record, not a designer's initial guess, set how aggressively it reorganizes. That is the training wheels loosening one notch at a time: a constant becomes a function of what the graph has learned about itself. The accumulated epoch signal is the teacher; the curves are what it adjusts.

## The honest limits

This is a stance, not a victory lap. Three things to keep clear-eyed about:

- **It is not pure computation yet.** The measurement apparatus — how grounding is scored, how concepts merge, what relationship types exist — is still human-designed. The bitter lesson applies to *those* too. The defensible claim is only that the human knowledge has moved **up a level**: we design the apparatus that measures evidence, not the truths themselves. That is a better place to stand, because the apparatus is general and the truths are brittle — but it is not the asymptote.
- **Scaling computation scales bias.** "Massively compute it" is only the right side of the bitter lesson if the thing being computed is a *general* objective. A brittle, hand-tuned grounding function, run at scale, just industrializes its own bias. The non-destructiveness is the insurance: because the evidence is preserved, a better objective can be swapped in and the answers re-derived. A system that expired its losing evidence has no such recourse.
- **Some questions genuinely want valid time.** "Who was CEO in 2013?" is cleanly answered by validity intervals. This system answers it differently — the dates live in content and relationships, and grounding reflects evidence — which is the right primitive for *measuring how well-supported a claim is* and the wrong one for *maintaining a single current truth*. Different question. We chose the first deliberately.

## Why it matters

The payoff is conviviality (in Illich's sense): a tool that shows its work. A system that asserts truth asks you to trust its resolution. A system that computes evidence hands you the evidence — the supporting sources, the contradicting ones, the grounding score, the provenance — and lets you judge. It does not numb your judgment by replacing it; it equips it.

"There is no truth, only computed evidence" is not relativism. It is the opposite: a refusal to launder a model's confident guess into a stored fact. Keep all the evidence, compute the standing, preserve the disagreement, and let the structure emerge. The rest is engineering toward the day the training wheels come off.

---

*Related: the conviviality framing of the project (README, Background); the annealing/self-organizing ontology design (ADR-200) and its tunable pressure curves (issue #249); the grounding and epistemic-ledger mechanisms (ADR-206); the epoch event log (ADR-203) and the accumulating-signal feedback work intended to tune the annealing curves (issues #386, #387); the modality-embedding stance that prose — not a joint vector space — is the cross-modal bridge (ADR-803).*
