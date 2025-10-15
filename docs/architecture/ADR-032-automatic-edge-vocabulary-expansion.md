# ADR-032: Automatic Edge Vocabulary Expansion with Intelligent Pruning

**Status:** Proposed
**Date:** 2025-10-15
**Deciders:** System Architects
**Related:** ADR-022 (30-Type Taxonomy), ADR-025 (Dynamic Vocabulary), ADR-026 (Autonomous Curation)

## Context

The current system uses a static 30-type relationship vocabulary defined in `src/api/constants.py`. While ADR-025 and ADR-026 propose dynamic vocabulary management with manual curator approval, this creates a bottleneck during high-volume ingestion.

### Current Limitations

**Static Vocabulary (ADR-022):**
```python
RELATIONSHIP_TYPES = {
    'IMPLIES', 'SUPPORTS', 'CONTRADICTS', 'CAUSES', 'ENABLES',
    # ... 25 more fixed types
}
```

**Problems:**
1. **Ingestion Blocking:** Novel edge types from LLM extraction are rejected
2. **Lost Semantics:** Domain-specific relationships (e.g., `TRAINS_ON`, `OPTIMIZES` for ML) get mapped to generic types or skipped
3. **Manual Bottleneck:** Every new type requires code change and deployment
4. **No Self-Regulation:** Vocabulary can only grow, never shrink

**ADR-025 Proposed Flow (Not Implemented):**
```
LLM extracts "OPTIMIZES" → Skipped → Logged to skipped_relationships
→ Curator reviews → Curator approves → Type added → Backfill process
```

This works but doesn't scale for rapid iteration or domain-specific ontologies.

### Core Insight

**Vocabulary should behave like a self-regulating cache:**
- **Auto-expand** on first use (like cache miss → fetch)
- **Value-based retention** (frequently used types stay, unused types pruned)
- **Sliding window** (30-90 types, tunable)
- **Intelligent pruning** (AI or human decides what to remove when limit reached)

## Decision

Implement **automatic edge vocabulary expansion with three-tier intelligent pruning**.

### Architecture: Proactive Expansion + Reactive Pruning

#### 1. Auto-Expansion During Ingestion

```python
def upsert_relationship(from_id, to_id, rel_type, confidence):
    """
    Auto-expand vocabulary on first use.
    """
    # 1. Check if type exists in vocabulary
    canonical_type, category = normalize_relationship_type(rel_type)

    if canonical_type:
        # Known type or fuzzy match
        create_graph_edge(from_id, to_id, canonical_type, confidence)
        increment_usage_count(canonical_type)
    else:
        # Unknown type - AUTO-EXPAND VOCABULARY
        if is_valid_edge_type(rel_type):  # Basic validation
            # Add to vocabulary immediately
            add_to_vocabulary(
                relationship_type=rel_type,
                category=infer_category(rel_type),  # LLM-assisted
                description=f"Auto-added during ingestion",
                added_by="system:auto-expansion",
                is_builtin=False,
                is_active=True
            )

            # Create edge
            create_graph_edge(from_id, to_id, rel_type, confidence)

            # Log expansion
            log_vocabulary_expansion(rel_type, context={
                "from_concept": get_label(from_id),
                "to_concept": get_label(to_id),
                "job_id": current_job_id
            })

            # Check if pruning needed
            if get_active_vocabulary_size() > VOCAB_MAX:
                trigger_pruning_workflow()
        else:
            # Invalid type (e.g., profanity, malformed)
            log_rejected_type(rel_type, reason="validation_failed")
```

**Validation Rules:**
- Uppercase alphanumeric + underscores only
- Length: 3-50 characters
- Not in blacklist (profanity, reserved terms)
- Not reverse form (`_BY` suffix rejected)

##### Category Classification for New Edge Types

**Two-Tier Vocabulary Structure:**

```python
# High-level categories (8 protected groups from ADR-022)
RELATIONSHIP_CATEGORIES = {
    "logical_truth": ["IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO"],
    "causal": ["CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM"],
    "structural": ["PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF", "INSTANCE_OF"],
    "evidential": ["SUPPORTS", "REFUTES", "EXEMPLIFIES", "MEASURED_BY"],
    "similarity": ["SIMILAR_TO", "ANALOGOUS_TO", "CONTRASTS_WITH", "OPPOSITE_OF"],
    "temporal": ["PRECEDES", "CONCURRENT_WITH", "EVOLVES_INTO"],
    "functional": ["USED_FOR", "REQUIRES", "PRODUCES", "REGULATES"],
    "meta": ["DEFINED_AS", "CATEGORIZED_AS"],
}
```

**Category Assignment Algorithm:**

When a new edge type is auto-added, it must be classified into an existing category:

```python
def infer_category(new_edge_type):
    """
    Classify new edge type into existing category using semantic analysis.
    Only create new category if confidence is extremely low (<0.3) for ALL categories.
    """
    # Get embeddings for the new type
    new_embedding = generate_embedding(new_edge_type)

    # Calculate similarity to each category
    category_scores = {}
    for category, existing_types in RELATIONSHIP_CATEGORIES.items():
        # Average similarity to all types in this category
        similarities = []
        for existing_type in existing_types:
            existing_embedding = generate_embedding(existing_type)
            similarity = cosine_similarity(new_embedding, existing_embedding)
            similarities.append(similarity)

        category_scores[category] = {
            "avg_similarity": np.mean(similarities),
            "max_similarity": np.max(similarities),
            "confidence": np.mean(similarities)  # Use average for robustness
        }

    # Find best-fit category
    best_category = max(category_scores.items(), key=lambda x: x[1]["confidence"])
    best_confidence = best_category[1]["confidence"]

    # HIGH BAR: Only create new category if confidence < 0.3 for ALL categories
    if best_confidence < 0.3:
        # Extremely poor fit to all existing categories
        return propose_new_category(new_edge_type, category_scores)
    else:
        # Assign to best-fit category
        return best_category[0]
```

**New Category Creation (High Bar):**

```python
def propose_new_category(new_edge_type, category_scores):
    """
    Propose a new high-level category (requires curator approval).

    HIGH BAR: Only if confidence < 0.3 for ALL existing categories.
    """
    # Generate category name via LLM reasoning
    proposal = {
        "new_category_name": suggest_category_name(new_edge_type),
        "trigger_type": new_edge_type,
        "poor_fit_evidence": {
            cat: scores["confidence"]
            for cat, scores in category_scores.items()
        },
        "reasoning": generate_category_justification(new_edge_type, category_scores),
        "status": "awaiting_curator_approval"
    }

    # Log proposal
    store_category_proposal(proposal)

    # FALLBACK: Temporarily assign to closest category (even if poor fit)
    fallback_category = max(category_scores.items(), key=lambda x: x[1]["confidence"])[0]

    notify_curator_new_category_proposal(proposal)

    return fallback_category  # Use fallback until approved
```

**Example LLM Category Reasoning:**

```python
prompt = f"""
Analyze the relationship type "{new_edge_type}" and determine if it fits existing categories:

EXISTING CATEGORIES:
- logical_truth: Logical entailment, contradiction, equivalence
- causal: Cause-effect relationships, enablement
- structural: Part-whole, composition, hierarchies
- evidential: Evidence, support, examples
- similarity: Likeness, analogy, contrast
- temporal: Time-based sequences, evolution
- functional: Purpose, requirements, usage
- meta: Definitions, categorizations

CONFIDENCE SCORES:
{json.dumps(category_scores, indent=2)}

All scores < 0.3 suggest poor fit to existing categories.

Should we create a NEW category? If yes:
1. Suggest category name (e.g., "transformation", "attribution")
2. Explain semantic distinction from existing categories
3. Predict other edge types that would belong to this category

Return JSON:
{{
  "create_new_category": true|false,
  "suggested_name": "category_name",
  "semantic_distinction": "Why this doesn't fit existing categories",
  "predicted_members": ["OTHER_TYPE_1", "OTHER_TYPE_2"],
  "confidence": 0.0-1.0
}}
"""
```

**Category Lifecycle Management:**

Just like edge types, categories can be merged:

```python
def merge_categories(source_category, target_category):
    """
    Merge two high-level categories.
    Example: "transformation" + "temporal" → "temporal" (evolution is temporal)
    """
    # Move all edge types from source to target
    source_types = RELATIONSHIP_CATEGORIES[source_category]

    for edge_type in source_types:
        # Update edge type metadata
        update_edge_category(edge_type, target_category)

    # Update category registry
    RELATIONSHIP_CATEGORIES[target_category].extend(source_types)
    del RELATIONSHIP_CATEGORIES[source_category]

    # Audit trail
    log_category_merge(source_category, target_category, len(source_types))
```

**Category Protection Rules:**

```python
CATEGORY_PROTECTION = {
    "builtin_categories": [
        "logical_truth", "causal", "structural", "evidential",
        "similarity", "temporal", "functional", "meta"
    ],
    "min_categories": 8,   # Never drop below original 8
    "max_categories": 15,  # HIGH BAR: only 7 additional categories allowed
}

def can_add_category(proposed_name):
    """Check if new category creation is allowed."""
    current_count = len(RELATIONSHIP_CATEGORIES)

    if current_count >= CATEGORY_PROTECTION["max_categories"]:
        # At limit - must merge existing categories first
        return False, "Category limit reached (15/15). Merge existing categories first."

    return True, "Category creation allowed"
```

**Curator Workflow for Categories:**

```bash
# Review new category proposals
kg vocab categories review

# Output:
┌─────────────────────────────────────────────────────────────┐
│ Pending Category Proposal                                   │
├─────────────────────────────────────────────────────────────┤
│ Category: "transformation"                                  │
│ Triggered by: TRANSFORMS                                    │
│                                                             │
│ Poor Fit Evidence:                                          │
│   • temporal: 0.28 (closest, but not temporal sequence)    │
│   • causal: 0.22 (not pure cause-effect)                   │
│   • structural: 0.19 (not composition)                      │
│                                                             │
│ AI Reasoning:                                               │
│ "TRANSFORMS implies state change without implying cause or │
│ temporal sequence. Distinct from EVOLVES_INTO (temporal)   │
│ and CAUSES (causal). Predicted members: CONVERTS,          │
│ TRANSMUTES, MORPHS_INTO."                                   │
│                                                             │
│ [A]pprove | [R]eject | [M]erge into existing category     │
└─────────────────────────────────────────────────────────────┘

# Approve new category
kg vocab categories approve transformation

# Or merge into existing
kg vocab categories merge transformation --into temporal \
  --reason "Transformation is a form of temporal evolution"

# View category stats
kg vocab categories list

# Output:
┌────────────────┬───────────────┬─────────────────┐
│ Category       │ Edge Types    │ Total Edges     │
├────────────────┼───────────────┼─────────────────┤
│ causal         │ 5 builtin     │ 1,247 edges     │
│                │ 3 custom      │                 │
├────────────────┼───────────────┼─────────────────┤
│ structural     │ 5 builtin     │ 892 edges       │
│                │ 1 custom      │                 │
├────────────────┼───────────────┼─────────────────┤
│ transformation │ 0 builtin     │ 34 edges (NEW)  │
│                │ 3 custom      │                 │
└────────────────┴───────────────┴─────────────────┘
```

**Aggressiveness Curve for Categories:**

Categories also have a sliding window, but with tighter limits:

```python
CATEGORY_WINDOW = {
    'min': 8,    # Original 8 categories (protected)
    'max': 15,   # Maximum 15 categories
    'merge_threshold': 12,  # Start flagging merge opportunities
}

# When at 12+ categories, flag merge opportunities
if len(RELATIONSHIP_CATEGORIES) >= 12:
    merge_suggestions = detect_category_merge_opportunities()
    notify_curator_category_merge_suggestions(merge_suggestions)
```

#### 2. Sliding Window Parameters

```python
VOCABULARY_WINDOW = {
    'min': 30,              # Protected core (builtin types)
    'max': 90,              # Soft limit (trigger pruning)
    'hard_limit': 200,      # Emergency stop (block new types)
    'prune_batch_size': 5,  # Prune N types per trigger
}

# Tunable via API/config
def set_vocabulary_limits(min_types, max_types):
    """Adjust sliding window (requires curator/admin role)"""
    update_config('vocab_min', min_types)
    update_config('vocab_max', max_types)
```

**Window Behavior:**
- **Below min (30):** Never prune builtin types
- **Between min-max (30-90):** Stable operating range
- **Above max (90+):** Trigger pruning workflow
- **Above hard limit (200):** Block new types, force human intervention

#### 3. Aggressiveness Curve: Graduated Response System

**Problem:** Reactive pruning (wait until limit hit → prune) causes frequent optimization invocations and system instability.

**Solution:** Graduated aggressiveness curve using **Cubic Bezier interpolation** (same as CSS animations), configurable via control points.

##### Cubic Bezier Aggressiveness Curve

```python
class CubicBezier:
    """
    Cubic Bezier curve for smooth, tunable aggressiveness.
    Same math as CSS cubic-bezier(x1, y1, x2, y2).
    """
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2

    def bezier(self, t):
        """Calculate Bezier value at t (0.0 to 1.0)"""
        # Cubic Bezier formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        # Where P₀ = (0, 0), P₃ = (1, 1) are fixed endpoints
        cx = 3 * self.x1
        bx = 3 * (self.x2 - self.x1) - cx
        ax = 1 - cx - bx

        cy = 3 * self.y1
        by = 3 * (self.y2 - self.y1) - cy
        ay = 1 - cy - by

        return ((ay * t + by) * t + cy) * t

    def solve_x(self, x, epsilon=1e-6):
        """Find t value for given x using Newton-Raphson"""
        # Binary search for t where bezier_x(t) ≈ x
        t = x
        for _ in range(8):  # Newton iterations
            x_guess = ((((1 - 3 * self.x2 + 3 * self.x1) * t +
                         (3 * self.x2 - 6 * self.x1)) * t +
                        (3 * self.x1)) * t)

            if abs(x_guess - x) < epsilon:
                break

            # Derivative for Newton step
            dx = (3 * (1 - 3 * self.x2 + 3 * self.x1) * t * t +
                  2 * (3 * self.x2 - 6 * self.x1) * t +
                  (3 * self.x1))

            if abs(dx) < epsilon:
                break

            t -= (x_guess - x) / dx

        return t

    def get_y_for_x(self, x):
        """Get aggressiveness (y) for vocabulary position (x)"""
        if x <= 0:
            return 0
        if x >= 1:
            return 1
        t = self.solve_x(x)
        return self.bezier(t)


# Predefined curve profiles (like CSS ease functions)
AGGRESSIVENESS_CURVES = {
    "linear": CubicBezier(0.0, 0.0, 1.0, 1.0),           # Constant rate
    "ease": CubicBezier(0.25, 0.1, 0.25, 1.0),           # CSS ease (default)
    "ease-in": CubicBezier(0.42, 0.0, 1.0, 1.0),         # Slow start, fast end
    "ease-out": CubicBezier(0.0, 0.0, 0.58, 1.0),        # Fast start, slow end
    "ease-in-out": CubicBezier(0.42, 0.0, 0.58, 1.0),    # Smooth S-curve
    "aggressive": CubicBezier(0.1, 0.0, 0.9, 1.0),       # Sharp acceleration near limit
    "gentle": CubicBezier(0.5, 0.5, 0.5, 0.5),           # Very gradual
    "exponential": CubicBezier(0.7, 0.0, 0.84, 0.0),     # Explosive near limit
}

# Configuration (tunable via API)
AGGRESSIVENESS_PROFILE = os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")


def calculate_aggressiveness(current_size):
    """
    Calculate aggressiveness (0.0-1.0) using Bezier curve.

    Args:
        current_size: Current vocabulary size

    Returns:
        float: Aggressiveness value (0.0 = passive, 1.0 = emergency)
    """
    VOCAB_MIN = 30
    VOCAB_MAX = 90
    EMERGENCY = 200

    if current_size <= VOCAB_MIN:
        return 0.0  # Comfort zone

    if current_size >= EMERGENCY:
        return 1.0  # Hard limit

    # Normalize position: 0.0 (at min) → 1.0 (at max)
    position = (current_size - VOCAB_MIN) / (VOCAB_MAX - VOCAB_MIN)
    position = max(0.0, min(1.0, position))  # Clamp to [0, 1]

    # Apply Bezier curve
    curve = AGGRESSIVENESS_CURVES[AGGRESSIVENESS_PROFILE]
    aggressiveness = curve.get_y_for_x(position)

    # Boost aggressiveness if beyond soft limit
    if current_size > VOCAB_MAX:
        overage = (current_size - VOCAB_MAX) / (EMERGENCY - VOCAB_MAX)
        aggressiveness = aggressiveness + (1.0 - aggressiveness) * overage

    return aggressiveness


def calculate_optimization_strategy(current_size):
    """
    Determine pruning strategy based on vocabulary size and aggressiveness curve.
    Returns (action, aggressiveness, batch_size)
    """
    VOCAB_MAX = 90
    EMERGENCY = 200

    aggressiveness = calculate_aggressiveness(current_size)

    # Map aggressiveness to action zones
    if aggressiveness < 0.2:
        # 0-20%: Comfort zone, just monitor
        return ("monitor", aggressiveness, 0)

    elif aggressiveness < 0.5:
        # 20-50%: Watch zone, flag merge opportunities
        return ("watch", aggressiveness, 0)

    elif aggressiveness < 0.7:
        # 50-70%: Merge zone, prefer synonym merging
        batch_size = max(1, ceil(aggressiveness * 10))
        return ("merge", aggressiveness, batch_size)

    elif aggressiveness < 0.9:
        # 70-90%: Mixed zone, merge + prune
        batch_size = max(2, ceil(aggressiveness * 15))
        return ("mixed", aggressiveness, batch_size)

    elif current_size < EMERGENCY:
        # 90-100%: Emergency zone
        batch_size = max(5, current_size - VOCAB_MAX + 5)
        return ("emergency", aggressiveness, batch_size)

    else:
        # Hard limit reached
        return ("block", 1.0, 0)
```

**Curve Profiles Visualization:**

```
Aggressiveness (y)
1.0 ┤                                        ╭─────── exponential
    │                                    ╭───╯
0.9 ┤                                ╭───╯
    │                            ╭───╯
0.8 ┤                        ╭───╯     ╭──── aggressive
    │                    ╭───╯      ╭──╯
0.7 ┤                ╭───╯      ╭───╯
    │            ╭───╯      ╭───╯    ╭───── ease-in-out
0.6 ┤        ╭───╯      ╭───╯    ╭───╯
    │    ╭───╯      ╭───╯    ╭───╯
0.5 ┤╭───╯      ╭───╯    ╭───╯      ╭────── linear
    │╯      ╭───╯    ╭───╯      ╭───╯
0.4 ┤   ╭───╯    ╭───╯      ╭───╯
    │╭──╯    ╭───╯      ╭───╯
0.3 ┤╯   ╭───╯      ╭───╯         ╭──────── gentle
    │╭───╯      ╭───╯         ╭───╯
0.2 ┤╯      ╭───╯         ╭───╯
    │   ╭───╯         ╭───╯
0.1 ┤╭──╯         ╭───╯
    │╯        ╭───╯
0.0 ┼─────────┴────────────────────────────────────────
    30       45       60       75       90      (vocab size)
    min              comfort          max
```

**Configuration & Tuning:**

```bash
# List available profiles
kg vocab config profiles

# Output:
# Available aggressiveness profiles:
#   linear      - Constant rate increase
#   ease        - Balanced (CSS default)
#   ease-in     - Slow start, fast end
#   ease-out    - Fast start, slow end
#   ease-in-out - Smooth S-curve
#   aggressive  - Sharp near limit (RECOMMENDED)
#   gentle      - Very gradual
#   exponential - Explosive near limit

# Set profile
kg vocab config set aggressiveness aggressive

# View current curve
kg vocab config show aggressiveness

# Output:
# Current profile: aggressive
# Bezier control points: (0.1, 0.0, 0.9, 1.0)
#
# Behavior:
#   30-60: Very gradual (10-20% aggressive)
#   60-75: Moderate (20-40% aggressive)
#   75-85: Accelerating (40-70% aggressive)
#   85-90: Sharp rise (70-95% aggressive)
#   90+: Emergency (95-100% aggressive)

# Custom curve (advanced)
kg vocab config set aggressiveness-custom 0.2,0.1,0.8,0.95

# Test curve without applying
kg vocab simulate --profile gentle --vocab-range 30-95
```

**Curve Selection Guide:**

| Profile | Use Case | Behavior |
|---------|----------|----------|
| `aggressive` | **Production (default)** | Stay passive until 75, then accelerate sharply |
| `ease-in-out` | Balanced environments | Smooth S-curve, predictable |
| `gentle` | High-churn ontologies | Very gradual, minimizes disruption |
| `exponential` | Strict capacity limits | Explosive response near limit |
| `linear` | Testing/debugging | Constant rate, easy to predict |

**Strategy Zones:**

```
30        60        75        85  90                200
├─────────┼─────────┼─────────┼───┼─────────────────┤
│ COMFORT │  WATCH  │  MERGE  │ M │    EMERGENCY    │
│  (0%)   │ (10-30%)│ (30-60%)│I X│    (90-100%)    │
│         │         │         │ E │                 │
│ No      │ Detect  │ Prefer  │ D │ Aggressive      │
│ Action  │ Only    │ Merging │   │ Pruning         │
└─────────┴─────────┴─────────┴───┴─────────────────┘
                                │
                            Soft Limit
```

**Decision Logic: Merge vs Prune**

```python
def select_optimization_action(current_size, candidates):
    """
    Determine whether to merge or prune based on zone and available options.
    """
    action_type, aggressiveness, batch_size = calculate_optimization_strategy(current_size)

    if action_type == "monitor":
        # Just flag opportunities for curator review
        synonym_pairs = detect_synonym_opportunities()
        if synonym_pairs:
            log_merge_opportunities(synonym_pairs, action="flag_only")
        return None  # Don't act yet

    elif action_type == "merge":
        # PREFER merging (preserves edges, reduces vocabulary)
        synonym_pairs = detect_synonym_opportunities()

        if synonym_pairs:
            # Select top N pairs by aggressiveness
            pairs_to_merge = synonym_pairs[:batch_size]
            return {
                "action": "merge",
                "pairs": pairs_to_merge,
                "reason": f"Proactive merging in merge zone ({current_size}/{VOCAB_MAX})"
            }
        else:
            # No merge candidates, prune zero-edge types only
            zero_edge_types = [c for c in candidates if c.edge_count == 0]
            if zero_edge_types:
                return {
                    "action": "prune",
                    "types": zero_edge_types[:batch_size],
                    "reason": "No merge candidates, safe zero-edge pruning"
                }
            else:
                # Can't merge or prune safely - escalate
                return {"action": "escalate", "reason": "No safe optimization available"}

    elif action_type == "mixed":
        # Try both: merge high-similarity pairs AND prune zero-edge types
        synonym_pairs = detect_synonym_opportunities()
        zero_edge_types = [c for c in candidates if c.edge_count == 0]

        actions = []
        if synonym_pairs:
            actions.append({
                "action": "merge",
                "pairs": synonym_pairs[:max(2, batch_size // 2)]
            })
        if zero_edge_types:
            actions.append({
                "action": "prune",
                "types": zero_edge_types[:max(2, batch_size // 2)]
            })

        if actions:
            return {
                "action": "mixed",
                "sub_actions": actions,
                "reason": f"Mixed optimization in prune zone ({current_size}/{VOCAB_MAX})"
            }
        else:
            # Last resort: prune low-value types with edges
            return {
                "action": "prune",
                "types": candidates[:batch_size],
                "reason": "Emergency pruning: all safe options exhausted"
            }

    elif action_type == "emergency":
        # Aggressive: prune anything low-value, merge anything similar
        return {
            "action": "emergency_prune",
            "types": candidates[:batch_size],
            "reason": f"Emergency: vocabulary at {current_size}/{VOCAB_MAX}"
        }

    elif action_type == "block":
        # Hard stop
        raise VocabularyLimitExceeded(
            f"Hard limit reached ({current_size}/{EMERGENCY}). "
            f"Manual curator intervention required."
        )
```

**Merge vs Prune Decision Tree:**

```
┌─────────────────────────────────────────────┐
│ Need to reduce vocabulary by N types       │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Check synonyms │
         └────────┬───────┘
                  │
         ┌────────┴────────┐
         │                 │
    [Synonyms Found]  [No Synonyms]
         │                 │
         ▼                 ▼
  ┌──────────────┐   ┌──────────────┐
  │ MERGE pairs  │   │ Check zero-  │
  │ (preserves   │   │ edge types   │
  │  edges)      │   └──────┬───────┘
  └──────┬───────┘          │
         │            ┌─────┴──────┐
         │            │            │
         │       [Found]      [None Found]
         │            │            │
         │            ▼            ▼
         │     ┌──────────┐  ┌──────────┐
         │     │ PRUNE    │  │ PRUNE    │
         │     │ zero-edge│  │ low-value│
         │     │ (safe)   │  │ (lossy)  │
         │     └────┬─────┘  └────┬─────┘
         │          │             │
         └──────────┴─────────────┘
                    │
                    ▼
            ┌───────────────┐
            │ Batch actions │
            │ to reduce     │
            │ invocations   │
            └───────────────┘
```

**Batching Strategy:**

Instead of: "Hit 91 → prune 1 → hit 91 again → prune 1 → repeat"

Do this: "Hit 90 → prune/merge 5 → back to 85 → comfortable for longer"

```python
def execute_batched_optimization(current_size):
    """
    Batch optimizations to reduce invocation frequency.
    """
    if current_size <= VOCAB_MAX:
        return  # No action needed

    # Calculate how much to prune
    excess = current_size - VOCAB_MAX
    buffer = 5  # Create buffer to avoid immediate re-trigger

    target_reduction = excess + buffer  # Remove more than minimum

    # Get optimization strategy
    strategy = select_optimization_action(current_size, get_candidates())

    if strategy["action"] == "merge":
        # Merging: each pair removes 1 type from active vocabulary
        pairs_needed = target_reduction
        execute_merges(strategy["pairs"][:pairs_needed])

    elif strategy["action"] == "mixed":
        # Do both (more efficient)
        merges_completed = execute_merges(strategy["sub_actions"][0]["pairs"])
        remaining = target_reduction - merges_completed
        execute_prunes(strategy["sub_actions"][1]["types"][:remaining])

    elif strategy["action"] == "prune":
        execute_prunes(strategy["types"][:target_reduction])

    log_optimization(
        action=strategy["action"],
        types_removed=target_reduction,
        new_size=current_size - target_reduction,
        buffer_created=buffer
    )
```

**Benefits of Graduated Approach:**

1. **Reduced invocations:** Proactive + batched = fewer optimization runs
2. **Preference for merging:** Preserves graph data while reducing vocabulary
3. **Predictable behavior:** Clear rules for when/how to optimize
4. **Buffer zones:** Creating headroom prevents constant re-triggering
5. **Early warning:** Monitor zone gives visibility before action required

**Example Scenario:**

```
Vocabulary grows from 60 → 92 types over 1 week:

Without aggressiveness curve:
- Hit 91 → prune 1 type → back to 90
- Hit 91 → prune 1 type → back to 90
- Hit 91 → prune 1 type → back to 90
- Hit 92 → prune 2 types → back to 90
Total: 4 optimization invocations, 5 types pruned

With aggressiveness curve:
- 60-75: Monitor, no action (flagged 3 synonym pairs)
- 75: Merged 2 synonym pairs → back to 73
- 85: Mixed optimization (merge 2, prune 3) → back to 80
- 90: Emergency batch (prune 7) → back to 83
Total: 3 optimization invocations, 12 types removed
Result: More stable, fewer invocations, better buffer
```

#### 4. Three-Tier Pruning Modes

**Mode Selection:**
```python
VOCABULARY_PRUNING_MODE = os.getenv("VOCAB_PRUNING_MODE", "aitl")
# Options: "naive" | "hitl" | "aitl"

AITL_CONFIDENCE_THRESHOLD = 0.7  # Fallback to HITL if AI confidence < 0.7
AITL_REASONING_MODEL = "claude-3-5-sonnet-20241022"
```

##### Mode 1: Naive (Algorithmic)

Pure bottom-up pruning, no intelligence:

```python
def naive_prune():
    """
    Automatic pruning based purely on value scores.
    Use cases: Testing, CI/CD, low-stakes environments
    """
    candidates = get_custom_types_ordered_by_value()  # ASC

    prune_count = get_active_vocabulary_size() - VOCAB_MAX
    to_prune = candidates[:prune_count]

    for type_obj in to_prune:
        if type_obj.edge_count == 0:
            delete_type(type_obj.relationship_type)
        else:
            deprecate_type(type_obj.relationship_type,
                          reason="Naive pruning: low value score")

    log_pruning(mode="naive", pruned=to_prune)
```

##### Mode 2: HITL (Human-in-the-Loop) - DEFAULT

System recommends, human approves:

```python
def hitl_prune():
    """
    Generate recommendation, await curator approval.
    Use cases: Production, high-stakes decisions, learning preferences
    """
    candidates = get_custom_types_ordered_by_value()
    prune_count = get_active_vocabulary_size() - VOCAB_MAX

    # Generate recommendation
    recommendation = {
        "id": generate_recommendation_id(),
        "timestamp": now(),
        "trigger": "vocabulary_limit_exceeded",
        "current_state": {
            "active_types": get_active_vocabulary_size(),
            "max_limit": VOCAB_MAX,
            "prune_needed": prune_count
        },
        "suggested_actions": [
            {
                "action": "prune",
                "types": [c.relationship_type for c in candidates[:prune_count]],
                "rationale": [format_rationale(c) for c in candidates[:prune_count]]
            },
            {
                "action": "merge",
                "opportunities": detect_synonym_pairs(candidates),
                "impact_analysis": calculate_merge_impact()
            }
        ],
        "status": "awaiting_approval"
    }

    store_recommendation(recommendation)
    notify_curator(recommendation)

    # Block further auto-expansion until approved
    set_expansion_paused(True)
```

**Curator CLI Workflow:**
```bash
kg vocab review

# Output:
┌─────────────────────────────────────────────────────────────┐
│ Vocabulary Status: 92/90 types (OVER LIMIT)                │
├─────────────────────────────────────────────────────────────┤
│ RECOMMENDED ACTIONS:                                        │
│                                                             │
│ [1] PRUNE 2 low-value types:                               │
│     • CREATES (0 edges, never used)                        │
│     • FEEDS_INTO (3 edges, 0 traversals, score: 0.02)     │
│                                                             │
│ [2] MERGE 1 synonym pair:                                  │
│     • AUTHORED_BY → CREATED_BY (94% similar)               │
│                                                             │
│ Approve all? [Y/n] | Review individually? [i]             │
└─────────────────────────────────────────────────────────────┘

# One-click approval
kg vocab approve-all

# Or selective
kg vocab approve recommendation 1  # Just prune
kg vocab reject recommendation 2   # Keep synonyms separate
```

##### Mode 3: AITL (AI-in-the-Loop)

**Tactical decision layer with strategic human oversight:**

```python
class AITLVocabularyCurator:
    """
    AI makes tactical decisions, human provides strategic oversight.
    """

    def __init__(self):
        self.reasoning_model = get_provider(AITL_REASONING_MODEL)
        self.decision_history = []
        self.curator_corrections = self._load_learned_preferences()

    def make_pruning_decision(self, context):
        """
        AI analyzes context and makes decision with detailed reasoning.
        """
        # Build prompt with context
        prompt = self._build_reasoning_prompt(context)

        # Get AI decision
        response = self.reasoning_model.complete(
            prompt=prompt,
            response_format={"type": "json_object"}
        )

        decision = parse_decision(response)

        # Log with full justification
        self._log_decision(decision, context)

        # Check confidence threshold
        if decision["confidence"] < AITL_CONFIDENCE_THRESHOLD:
            # Fallback to HITL
            return self._escalate_to_human(decision, context)

        # Execute decision
        return self._execute_decision(decision)

    def _build_reasoning_prompt(self, context):
        """Build prompt with learned preferences."""
        return f"""
You are a knowledge graph vocabulary curator. Analyze this optimization scenario:

CURRENT STATE:
- Active types: {context['active_types']} (limit: {context['max_limit']})
- Recent ingestions: {context['recent_ingestions']}
- Domain: {context['domain']}

PRUNING CANDIDATES (by value score):
{json.dumps(context['candidates'], indent=2)}

MERGE OPPORTUNITIES:
{json.dumps(context['merge_opportunities'], indent=2)}

LEARNED CURATOR PREFERENCES:
{json.dumps(self.curator_corrections, indent=2)}

TASKS:
1. Decide: prune, merge, or reject (raise limit)
2. Select specific types/pairs
3. Analyze impact on graph connectivity
4. Assess future regret probability
5. Provide detailed reasoning

Return JSON:
{{
  "decision": "prune" | "merge" | "reject",
  "selected_actions": [
    {{"action": "prune", "type": "CREATES", "reasoning": "..."}}
  ],
  "confidence": 0.0-1.0,
  "reasoning": "Comprehensive explanation",
  "alternatives_considered": [...],
  "risk_assessment": {{
    "connectivity_impact": "zero|low|medium|high",
    "query_disruption": "none|minimal|moderate|severe",
    "future_regret_probability": 0.0-1.0
  }},
  "human_review_required": true|false
}}

IMPORTANT: Consider learned preferences. Never prune types that humans have previously protected.
"""

    def _log_decision(self, decision, context):
        """Store decision with full justification trail."""
        audit_entry = {
            "decision_id": generate_id(),
            "timestamp": now(),
            "mode": "aitl",
            "model": AITL_REASONING_MODEL,
            "trigger": context["trigger"],
            "context": context,
            "decision": decision,
            "human_review_required": decision.get("human_review_required", False)
        }

        store_audit(audit_entry)

        # Notify if flagged for review
        if decision.get("human_review_required"):
            notify_curator_review_required(audit_entry)

    def learn_from_feedback(self, decision_id, curator_feedback):
        """
        Human corrected AI decision - extract preference and update.
        """
        decision = get_decision(decision_id)

        # Infer preference rule
        preference = self._infer_preference(decision, curator_feedback)

        # Store for future decisions
        self.curator_corrections.append({
            "decision_id": decision_id,
            "original_decision": decision["decision"],
            "curator_action": curator_feedback["action"],
            "reasoning": curator_feedback["reason"],
            "extracted_rule": preference,
            "timestamp": now()
        })

        # Persist
        save_learned_preferences(self.curator_corrections)

    def _infer_preference(self, decision, feedback):
        """Extract reusable preference rule from correction."""
        if feedback["action"] == "reject_prune":
            # Human rejected pruning a type
            type_name = feedback["protected_type"]
            return {
                "rule": f"never_prune_{type_name}",
                "condition": {
                    "relationship_type": type_name,
                    "reason": feedback["reason"]
                }
            }
        elif feedback["action"] == "reject_merge":
            # Human wants to keep synonyms separate
            pair = feedback["synonym_pair"]
            return {
                "rule": f"keep_distinct_{pair[0]}_{pair[1]}",
                "condition": {
                    "types": pair,
                    "semantic_distinction": feedback["reason"]
                }
            }
        # ... more inference patterns
```

**Human Oversight Interface:**

```bash
# Review AI decisions
kg vocab decisions --since 7d

# Output:
┌──────────────────────────────────────────────────────────────┐
│ AI Vocabulary Decisions (Last 7 Days)                       │
├──────────────────────────────────────────────────────────────┤
│ 2025-10-15 14:32 [EXECUTED] PRUNED: CREATES, FEEDS_INTO    │
│   Confidence: 87% | Impact: 3 edges                         │
│   AI Reasoning: "Zero usage, no traversals, no future..."  │
│   ➜ [A]pprove | [R]eject & Teach | [D]etailed View         │
│                                                              │
│ 2025-10-14 03:15 [EXECUTED] MERGED: AUTHORED_BY → CREATED  │
│   Confidence: 91% | Impact: 27 edges                        │
│   AI Reasoning: "94% semantic similarity, stem match..."    │
│   ➜ [A]pprove | [R]eject & Teach | [D]etailed View         │
│                                                              │
│ 2025-10-13 19:45 [FLAGGED] AWAITING HUMAN REVIEW           │
│   Action: Prune OPTIMIZES                                   │
│   Confidence: 62% (below threshold)                         │
│   ➜ Human decision REQUIRED                                 │
└──────────────────────────────────────────────────────────────┘

# View detailed reasoning
kg vocab decision vocab_prune_20251015_1432 --explain

# Output:
Decision: vocab_prune_20251015_1432
Model: claude-3-5-sonnet-20241022
Confidence: 87%

DECISION: Prune CREATES and FEEDS_INTO

REASONING:
Pruned CREATES (0 edges, never matched during 15 recent ingestions)
and FEEDS_INTO (3 edges but 0 traversals in 30 days, effectively
orphaned). Rejected pruning OPTIMIZES despite borderline score because
it appears in ML-specific contexts and recent ingestions show increasing
usage (trend: +40% over 14 days).

GRAPH IMPACT ANALYSIS:
- Removing these 2 types affects 0% of active queries
- No orphaned concepts created
- Connectivity preserved

ALTERNATIVES CONSIDERED:
1. Merge AUTHORED_BY → CREATED_BY
   Rejected: Semantic analysis shows AUTHORED_BY used specifically
   for documentation (86% of instances) vs general object creation.
   Merger would lose domain specificity.

2. Raise max limit to 100
   Rejected: Trend analysis projects 105 types in 60 days, requiring
   another adjustment. Better to prune now.

RISK ASSESSMENT:
- Future regret probability: 15%
- Fallback available: Yes (types archived, can restore)

# Provide corrective feedback (teaches AI)
kg vocab decision vocab_prune_20251015_1432 --reject \
  --reason "FEEDS_INTO is critical for data pipeline ontology despite low current usage"

# AI learns and adds to preferences:
# - never_prune_FEEDS_INTO (when domain=data_pipeline)
```

#### 4. Value Scoring Algorithm

**Multi-factor scoring prevents catastrophic forgetting:**

```python
def calculate_value_score(rel_type):
    """
    Value = structural utility, not temporal recency.

    Factors:
    - Edge count: How many edges use this type
    - Traversal frequency: How often edges are queried
    - Bridge bonus: Connects low-activation to high-activation concepts
    - Trend: Recent usage growth
    """
    stats = get_relationship_stats(rel_type)

    edge_count = stats.usage_count
    avg_traversal = stats.avg_traversal_count or 0
    bridge_count = calculate_bridge_importance(rel_type)
    trend = calculate_usage_trend(rel_type, days=14)

    # Weighted formula
    value_score = (
        edge_count * 1.0 +                          # Base: edge existence
        (avg_traversal / 100.0) * 0.5 +             # Usage weight
        (bridge_count / 10.0) * 0.3 +               # Bridge preservation
        max(0, trend) * 0.2                         # Growth momentum
    )

    return value_score


def calculate_bridge_importance(rel_type):
    """
    Bridge bonus: low-activation nodes connecting to high-activation nodes.
    Prevents pruning critical pathways.
    """
    query = """
    SELECT COUNT(*) as bridge_count
    FROM kg_api.edge_usage_stats e
    JOIN kg_api.concept_access_stats c_from
        ON e.from_concept_id = c_from.concept_id
    JOIN kg_api.concept_access_stats c_to
        ON e.to_concept_id = c_to.concept_id
    WHERE e.relationship_type = %s
      AND c_from.access_count < 10      -- Low activation source
      AND c_to.access_count > 100       -- High activation destination
    """

    result = execute_query(query, [rel_type])
    return result['bridge_count']
```

**Key Insight:** A rarely-used type with high bridge count (e.g., `PRECEDES` connecting timeline concepts) scores higher than a frequently-used type with no bridge value.

#### 5. Protected Core Set

**30 builtin types are immune to automatic pruning:**

```python
def is_protected_type(rel_type):
    """Check if type is in protected core set."""
    return db.execute("""
        SELECT is_builtin
        FROM kg_api.relationship_vocabulary
        WHERE relationship_type = %s
    """, [rel_type])['is_builtin']


def prune_vocabulary(candidates):
    """Prune low-value types, respecting protections."""
    for candidate in candidates:
        if is_protected_type(candidate.relationship_type):
            log_warning(f"Skipped pruning protected type: {candidate.relationship_type}")
            continue

        if candidate.edge_count == 0:
            delete_type(candidate.relationship_type)
        else:
            deprecate_type(candidate.relationship_type)
```

**Protected types can be merged** (e.g., merge novel `OPTIMIZES` into builtin `IMPROVES`), but never deleted.

#### 6. Edge Compaction (Synonym Merging)

**When approaching max limit, merge synonyms instead of pruning:**

```python
def detect_synonym_opportunities():
    """
    Find high-similarity type pairs for merging.
    """
    active_types = get_active_custom_types()
    synonym_pairs = []

    for type_a in active_types:
        for type_b in active_types:
            if type_a >= type_b:
                continue

            # Semantic similarity via embeddings
            similarity = cosine_similarity(
                get_embedding(type_a),
                get_embedding(type_b)
            )

            if similarity > 0.90:
                synonym_pairs.append({
                    "pair": [type_a, type_b],
                    "similarity": similarity,
                    "merge_suggestion": suggest_canonical_form(type_a, type_b),
                    "edge_impact": count_edges(type_a) + count_edges(type_b)
                })

    return sorted(synonym_pairs, key=lambda x: x['edge_impact'], reverse=True)


def merge_relationship_types(source_type, target_type):
    """
    Merge source_type into target_type.
    Updates all edges in graph + vocabulary tables.
    """
    # 1. Update graph edges (Cypher)
    cypher_query = f"""
    MATCH ()-[r:{source_type}]->()
    SET r:{target_type}
    REMOVE r:{source_type}
    RETURN count(r) as updated_count
    """
    result = execute_graph_query(cypher_query)

    # 2. Update vocabulary table
    db.execute("""
        UPDATE kg_api.relationship_vocabulary
        SET synonyms = array_append(synonyms, %s),
            usage_count = usage_count + (
                SELECT usage_count
                FROM kg_api.relationship_vocabulary
                WHERE relationship_type = %s
            )
        WHERE relationship_type = %s
    """, [source_type, source_type, target_type])

    # 3. Deprecate source type
    db.execute("""
        UPDATE kg_api.relationship_vocabulary
        SET is_active = FALSE,
            deprecation_reason = %s
        WHERE relationship_type = %s
    """, [f"Merged into {target_type}", source_type])

    # 4. Audit trail
    log_vocabulary_merge(source_type, target_type, result['updated_count'])
```

#### 7. Deletion History & Rollback

**All pruning/merging operations are logged and reversible:**

```sql
-- Vocabulary history (track all changes)
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_history (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'added', 'deprecated', 'deleted', 'merged'
    performed_by VARCHAR(100),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot JSONB,  -- Full type metadata at time of change
    merge_target VARCHAR(100),  -- If merged, what was target
    affected_edges INTEGER,
    details JSONB
);

CREATE INDEX idx_vocab_history_type ON kg_api.vocabulary_history(relationship_type);
CREATE INDEX idx_vocab_history_action ON kg_api.vocabulary_history(action);
```

**Rollback support:**

```bash
# View deletion history
kg vocab history --deleted

# Output:
┌────────────────────────────────────────────────────────────┐
│ Deleted/Merged Relationship Types                         │
├────────────────────────────────────────────────────────────┤
│ 2025-10-15 14:32 CREATES                                  │
│   Action: Pruned (0 edges)                                │
│   Reason: Never used                                      │
│   ➜ [R]estore                                             │
│                                                            │
│ 2025-10-14 03:15 AUTHORED_BY → CREATED_BY                │
│   Action: Merged (27 edges updated)                       │
│   Reason: 94% semantic similarity                         │
│   ➜ [U]nmerge (revert)                                    │
└────────────────────────────────────────────────────────────┘

# Restore pruned type
kg vocab restore CREATES --reason "Needed for new documentation ontology"

# Unmerge (split edges back)
kg vocab unmerge AUTHORED_BY --from CREATED_BY
```

## Implementation Plan

### Phase 1: Auto-Expansion Infrastructure

1. **Modify `upsert_relationship()` in `age_client.py`:**
   - Add auto-expansion logic
   - Basic validation (format, blacklist)
   - Trigger pruning check

2. **Create `vocabulary_manager.py` service:**
   - `add_to_vocabulary()`
   - `get_active_vocabulary_size()`
   - `trigger_pruning_workflow()`

3. **Add configuration:**
   - `VOCAB_MIN`, `VOCAB_MAX`, `VOCAB_HARD_LIMIT`
   - `VOCAB_PRUNING_MODE` (naive|hitl|aitl)

4. **Update schema:**
   - Add `vocabulary_history` table
   - Add `pruning_recommendations` table

### Phase 2: Aggressiveness Curve + Naive Mode

1. **Implement aggressiveness curve:**
   - Zone calculations (comfort/watch/merge/prune/emergency)
   - Batching strategy
   - Merge vs prune decision logic

2. **Implement naive pruning:**
   - Value score calculation
   - Automatic prune on limit exceeded

3. **Add synonym detection:**
   - Embedding-based similarity
   - Merge suggestions in recommendations

### Phase 3: HITL Mode

1. **Implement HITL workflow:**
   - Recommendation generation with aggressiveness curve
   - Curator approval API endpoints
   - CLI commands (`kg vocab review`, `kg vocab approve-all`)

2. **Add monitoring:**
   - Zone transition alerts
   - Optimization invocation tracking
   - Buffer effectiveness metrics

### Phase 4: AITL Mode

1. **Build AITL curator:**
   - Reasoning prompt template
   - Decision logging
   - Confidence thresholds

2. **Implement learning loop:**
   - Curator feedback capture
   - Preference extraction
   - Preference persistence

3. **Add oversight interface:**
   - `kg vocab decisions` (view AI decisions)
   - `kg vocab decision {id} --explain` (detailed reasoning)
   - `kg vocab decision {id} --reject --reason` (teach AI)

### Phase 5: Rollback & Analytics

1. **Implement rollback:**
   - `kg vocab restore {type}`
   - `kg vocab unmerge {type}`

2. **Add analytics:**
   - `kg vocab analytics` (trends, value scores, zone history)
   - `kg vocab candidates` (pruning candidates)
   - Aggressiveness curve visualization

## API Endpoints

### Vocabulary Management

```
GET    /api/vocabulary/types              # List all types with stats
POST   /api/vocabulary/types              # Manually add type (curator)
PUT    /api/vocabulary/types/{type}       # Update metadata
DELETE /api/vocabulary/types/{type}       # Deprecate type
POST   /api/vocabulary/types/{type}/restore  # Restore pruned type

POST   /api/vocabulary/merge              # Merge two types
POST   /api/vocabulary/unmerge            # Revert merge
```

### Configuration

```
GET    /api/vocabulary/config             # Get tuning parameters
PUT    /api/vocabulary/config             # Update parameters (admin)
```

### HITL Workflow

```
GET    /api/vocabulary/recommendations    # Get pending recommendations
POST   /api/vocabulary/recommendations/{id}/approve
POST   /api/vocabulary/recommendations/{id}/reject
```

### AITL Workflow

```
GET    /api/vocabulary/decisions          # List AI decisions
GET    /api/vocabulary/decisions/{id}     # Detailed decision view
POST   /api/vocabulary/decisions/{id}/feedback  # Provide correction
```

### Analytics

```
GET    /api/vocabulary/history            # Change history
GET    /api/vocabulary/analytics          # Value scores, trends
GET    /api/vocabulary/candidates         # Pruning candidates
```

## Benefits

### 1. Self-Regulating System

- **No manual deployment** for new types
- **Automatic capacity management** (sliding window)
- **Data-driven decisions** (value scores, not guesswork)

### 2. Domain Adaptability

- **ML ontologies** get `TRAINS_ON`, `PREDICTS`, `OPTIMIZES`
- **Pipeline ontologies** get `FEEDS_INTO`, `TRANSFORMS`, `VALIDATES`
- **Semantic ontologies** get `SYMBOLIZES`, `REPRESENTS`, `EMBODIES`

Each domain naturally grows its vocabulary through ingestion.

### 3. Intelligent Oversight

- **Naive mode:** Fast, deterministic (CI/CD)
- **HITL mode:** Human control (production)
- **AITL mode:** Scalable + justifiable (high-volume)

### 4. Learning System

- **AI learns curator preferences** over time
- **Reduces false positives** (e.g., never prune temporal types)
- **Improves with usage** (self-optimizing)

### 5. Auditability

- **Full justification logs** for every decision
- **Rollback capability** for mistakes
- **Compliance-friendly** (who, what, when, why)

## Trade-offs

### Complexity

**Cost:** More complex than static vocabulary
**Mitigation:** Start with naive mode, graduate to HITL, enable AITL only when needed

### AI Decision Risk

**Cost:** AITL might make wrong pruning decisions
**Mitigation:**
- Confidence threshold (fallback to HITL if < 0.7)
- Protected core set (30 builtin types immune)
- Full audit trail + rollback
- Human oversight weekly

### Token Cost

**Cost:** AITL reasoning uses ~500-1000 tokens per decision
**Mitigation:**
- Only runs when limit exceeded (infrequent)
- Cost: ~$0.01 per decision with Claude Sonnet
- Can disable in cost-sensitive environments

### Synonym Detection Accuracy

**Cost:** Might merge non-synonyms (false positives)
**Mitigation:**
- High similarity threshold (0.90+)
- HITL/AITL approval required
- Easy unmerge via rollback

## Monitoring & Metrics

### Key Metrics

1. **Vocabulary Size Over Time**
   - Track active types (should stay 30-90)
   - Alert if exceeds hard limit

2. **Auto-Expansion Rate**
   - New types added per ingestion
   - Alert if > 5 types/job (possible LLM issue)

3. **Pruning Frequency**
   - How often pruning triggered
   - Target: < 1x per week

4. **AITL Decision Accuracy**
   - % of AI decisions approved by humans
   - Target: > 85%

5. **Value Score Distribution**
   - Histogram of type value scores
   - Identify low-value types proactively

### Alerts

- `vocab_size > hard_limit` → Block ingestion, require curator intervention
- `aitl_approval_rate < 70%` → AI making poor decisions, review preferences
- `auto_expansion_rate > 10/day` → Possible LLM extraction issue

## Security & Governance

### Access Control (RBAC)

- **Contributor:** Can ingest (triggers auto-expansion)
- **Curator:** Can approve pruning recommendations
- **Admin:** Can modify config, force operations

### Validation

- **Format validation:** Prevent malformed types
- **Blacklist:** Block profanity, reserved terms
- **Rate limiting:** Max 10 auto-expansions per ingestion job

### Audit Trail

Every operation logged to `vocabulary_audit` and `vocabulary_history` with:
- Who (user/system/ai)
- What (action + details)
- When (timestamp)
- Why (reasoning/context)

## Alternatives Considered

### 1. Manual Approval for Every Type (ADR-025)

**Rejected:** Doesn't scale for high-volume ingestion or domain-specific ontologies

### 2. Unlimited Vocabulary Growth

**Rejected:** Leads to vocabulary explosion, degraded LLM extraction quality

### 3. Time-Based Pruning

**Rejected:** Graph value is structural, not temporal. Old types can have high bridge importance.

### 4. No Pruning (Only Expansion)

**Rejected:** Eventually hits performance limits, confuses LLM with 200+ type options

### 5. Hardcoded If/Else Threshold Logic

**Rejected:** Multiple issues with maintainability and tuning

**Original Approach:**
```python
# Example of hardcoded threshold logic
def calculate_aggressiveness(vocab_size):
    if vocab_size < 60:
        return 0.0
    elif vocab_size < 70:
        return 0.2
    elif vocab_size < 80:
        return 0.5
    elif vocab_size < 90:
        return 0.8
    else:
        return 1.0
```

**Problems:**

1. **Hard to Debug:**
   - Which threshold is causing behavior X?
   - What happens at boundary conditions (vocab_size = 79 vs 80)?
   - Discontinuous jumps create unpredictable behavior

2. **Difficult to Tune:**
   - Want gentler curve? Rewrite all thresholds
   - Want sharper curve? Add more if/elif branches
   - Every tuning attempt requires code changes and deployment

3. **Not Visualizable:**
   - Can't graph the behavior easily
   - Hard to communicate to non-technical stakeholders
   - No way to preview changes before deploying

4. **Maintenance Burden:**
   - Each environment might need different thresholds
   - Testing requires multiple code paths
   - Adding new zones means rewriting logic

5. **Example Debugging Scenario:**
   ```python
   # Bug report: "System pruned aggressively at 78 types"
   # Developer has to trace through:
   if vocab_size < 60:  # Not here
       ...
   elif vocab_size < 70:  # Not here
       ...
   elif vocab_size < 80:  # AH! Here's the culprit
       return 0.5  # But why 0.5? Is that right for 78?
       # And what about 79? 77? Where's the sweet spot?
   ```

**Why Bezier is Better:**

```python
# Single line configuration
curve = AGGRESSIVENESS_CURVES["aggressive"]
aggressiveness = curve.get_y_for_x(position)

# Debugging: "What's aggressiveness at 78 types?"
# Answer: Plot curve, see exact value (e.g., 0.67)
# Visual, continuous, predictable

# Tuning: "Too aggressive at 78?"
# Change: VOCAB_AGGRESSIVENESS = "gentle"
# No code changes, no deployment
```

**Bezier Benefits:**
- ✅ Continuous function (smooth behavior, no jumps)
- ✅ Visually tunable (drag control points, see result)
- ✅ Configuration-based (no code changes)
- ✅ Familiar to developers (CSS animations use same math)
- ✅ Easy to debug (plot curve, see exact behavior)
- ✅ Environment-specific (dev vs prod can use different profiles)

**Trade-off:**
- More complex implementation (CubicBezier class)
- But: Implementation is one-time, benefits are ongoing
- And: Standard algorithm, well-tested, no surprises

## Success Criteria

### Phase 1 (Auto-Expansion)

- [ ] New types auto-added during ingestion
- [ ] No code deployment required for new types
- [ ] Vocabulary size tracked and alerts functional

### Phase 2 (HITL)

- [ ] Curator can approve/reject recommendations in < 2 minutes
- [ ] Pruning maintains vocabulary at 30-90 types
- [ ] Zero false positives (protected types never pruned)

### Phase 3 (AITL)

- [ ] AI decision approval rate > 85%
- [ ] AI learns from corrections (preferences applied)
- [ ] Detailed justification logs for compliance

### Phase 4 (Rollback)

- [ ] Can restore any pruned type
- [ ] Can unmerge any synonym pair
- [ ] Full change history queryable

## References

- **ADR-022:** 30-Type Semantically Sparse Taxonomy (current static system)
- **ADR-025:** Dynamic Relationship Vocabulary (skip-and-approve workflow)
- **ADR-026:** Autonomous Vocabulary Curation (LLM-assisted suggestions)
- **ADR-014:** Job Approval Workflow (HITL pattern)
- **ADR-021:** Live Man Switch (human oversight principles)

## Future Enhancements

### Phase 5: Advanced Learning

- Cross-ontology type analysis (find domain patterns)
- Predictive type suggestions (recommend types before ingestion)
- Automatic category inference via clustering

### Phase 6: Distributed Vocabulary

- Multi-tenant vocabulary namespaces
- Vocabulary inheritance (base + domain-specific)
- Federated type sharing across organizations

---

**Status:** Proposed
**Next Steps:**
1. Review with development team
2. Prototype auto-expansion in feature branch
3. Test naive mode with sample ingestions
4. Pilot HITL workflow with curator
5. Evaluate AITL with safety checks
