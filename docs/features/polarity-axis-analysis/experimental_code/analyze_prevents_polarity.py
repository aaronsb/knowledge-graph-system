"""
Analyze polarity axes formed by PREVENTS relationships

PREVENTS relationships create natural oppositional polarity:
- Source (negative pole): The blocking/preventing concept
- Target (positive pole): The blocked/prevented concept

Example: Tech Debt -PREVENTS-> Technology Advantage
Forms axis: Tech Debt ↔ Technology Advantage
"""

import sys
sys.path.insert(0, '/workspace/experiments/semantic_gradients')

from polarity_axis_analysis import analyze_polarity_axis

print("\n" + "=" * 70)
print("PREVENTS Relationship Polarity Analysis")
print("=" * 70)
print()

print("Analyzing oppositional polarity axes formed by PREVENTS relationships:")
print()

# Polarity Axis 1: Tech Debt ↔ Technology Advantage
print("📊 Polarity Axis 1: Tech Debt ↔ Technology Advantage")
print("   Relationship: Tech Debt -PREVENTS-> Technology Advantage")
print()

negative_pole = "sha256:09671_chunk1_7018d2a6"  # Tech Debt (prevents)
positive_pole = "sha256:09671_chunk1_acb1d376"  # Technology Advantage (prevented)

# Candidates that might fall along this axis
candidates = [
    "sha256:09671_chunk1_470d9b67",  # Integration Challenges (also prevents Tech Advantage)
    "sha256:ecaa1_chunk1_2716e555",  # Legacy Systems
    "sha256:0d5be_chunk2_dabab979",  # Digital Transformation
    "sha256:53ab8_chunk1_257d1065",  # Agile
]

axis1 = analyze_polarity_axis(positive_pole, negative_pole, candidates)

print("\n" + "=" * 70)
print()

# Polarity Axis 2: Legacy Systems ↔ Digital Transformation
print("📊 Polarity Axis 2: Legacy Systems ↔ Digital Transformation")
print("   Relationship: Legacy Systems -PREVENTS-> Digital Transformation")
print()

negative_pole = "sha256:ecaa1_chunk1_2716e555"  # Legacy Systems (prevents)
positive_pole = "sha256:0d5be_chunk2_dabab979"  # Digital Transformation (prevented)

# Candidates
candidates = [
    "sha256:0f72d_chunk1_9a13bb20",  # Traditional Operating Models
    "sha256:2af75_chunk1_78594e1b",  # Modern Operating Model
    "sha256:e53b1_chunk1_dae749c1",  # Siloed Digital Transformation (also prevents)
    "sha256:09671_chunk1_7018d2a6",  # Tech Debt
]

axis2 = analyze_polarity_axis(positive_pole, negative_pole, candidates)

print("\n" + "=" * 70)
print()
print("💡 Key Insight: How to Determine Both Directions")
print("=" * 70)
print()
print("PREVENTS relationships create natural bidirectional axes:")
print()
print("  ➖ Negative Direction (Source of PREVENTS)")
print("     Concepts that BLOCK, HINDER, or OPPOSE")
print("     Examples: Tech Debt, Legacy Systems, Integration Challenges")
print()
print("  ➕ Positive Direction (Target of PREVENTS)")
print("     Concepts that are ENABLED when blockers are removed")
print("     Examples: Technology Advantage, Digital Transformation")
print()
print("Other concepts project onto the axis based on semantic similarity:")
print("  • Close to negative pole: Share characteristics with blockers")
print("  • Close to positive pole: Share characteristics with goals")
print("  • Neutral/Mixed: Orthogonal concerns or synthesis concepts")
print()
print("Grounding strength correlates with polarity:")
print("  • Negative grounding → Concepts society/evidence views as problematic")
print("  • Positive grounding → Concepts society/evidence views as beneficial")
print()
