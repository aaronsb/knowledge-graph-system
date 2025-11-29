import sys
sys.path.insert(0, '/workspace/experiments/semantic_gradients')

from polarity_axis_analysis import analyze_polarity_axis

# Better polarity axis with stronger exemplars
positive_pole_id = "sha256:2af75_chunk1_78594e1b"  # Modern Operating Model
negative_pole_id = "sha256:0f72d_chunk1_9a13bb20"  # Traditional Operating Models

# Better candidates with clear polarity
candidate_ids = [
    # Should align with Traditional/Legacy (negative)
    "sha256:ecaa1_chunk1_2716e555",  # Legacy Systems (-0.075)
    "sha256:ecaa1_chunk1_eaeb5a0d",  # Fragmented Digital Strategy (-0.017)

    # Should align with Modern (positive)
    "sha256:53ab8_chunk1_257d1065",  # Agile (+0.227)
    "sha256:a01ef_chunk1_a7bdf96a",  # Enterprise Momentum (+0.128)
    "sha256:0d5be_chunk1_a2ccadba",  # Modern Ways of Working (+0.104)

    # Interesting middle ground
    "sha256:0d5be_chunk2_dabab979",  # Digital Transformation (-0.022)
    "sha256:e53b1_chunk1_dae749c1",  # Siloed Digital Transformation (+0.098)

    # Previous neutral concepts
    "sha256:0d5be_chunk1_d22215ed",  # Enterprise Operating Model
    "sha256:23ba4_chunk4_0343189a",  # AI-Enabled Operating Models
]

axis = analyze_polarity_axis(positive_pole_id, negative_pole_id, candidate_ids)
