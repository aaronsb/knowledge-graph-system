"""
Polarity axis analysis tests.

Tests for: kg polarity analyze
Endpoint: POST /query/polarity-axis
ADR: ADR-070 Polarity Axis Analysis
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any

# Import the polarity axis module
from api.app.lib.polarity_axis import (
    PolarityAxis,
    Concept,
    calculate_grounding_correlation
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_concept_a():
    """Mock concept A with embedding"""
    return Concept(
        concept_id="test_a",
        label="Concept A",
        embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        description="Test concept A",
        grounding=0.5
    )


@pytest.fixture
def mock_concept_b():
    """Mock concept B with embedding (opposite of A)"""
    return Concept(
        concept_id="test_b",
        label="Concept B",
        embedding=np.array([0.0, 1.0, 0.0], dtype=np.float32),
        description="Test concept B",
        grounding=-0.3
    )


@pytest.fixture
def mock_concept_c():
    """Mock concept C with embedding (neutral between A and B)"""
    return Concept(
        concept_id="test_c",
        label="Concept C",
        embedding=np.array([0.5, 0.5, 0.0], dtype=np.float32),
        description="Test concept C",
        grounding=0.1
    )


@pytest.fixture
def mock_concept_duplicate():
    """Mock concept that's nearly identical to concept A"""
    return Concept(
        concept_id="test_a_dup",
        label="Concept A Duplicate",
        embedding=np.array([1.0, 1e-10, 0.0], dtype=np.float32),  # Nearly identical to A
        description="Nearly identical to A",
        grounding=0.5
    )


# ============================================================================
# Unit Tests: PolarityAxis Class
# ============================================================================

def _make_axis(positive_pole, negative_pole):
    """Helper to construct PolarityAxis with placeholder fields that __post_init__ recalculates."""
    return PolarityAxis(
        positive_pole=positive_pole,
        negative_pole=negative_pole,
        axis_vector=np.zeros_like(positive_pole.embedding),
        axis_magnitude=0.0
    )


@pytest.mark.unit
def test_polarity_axis_creation(mock_concept_a, mock_concept_b):
    """Test that PolarityAxis can be created with valid poles"""
    axis = _make_axis(mock_concept_a, mock_concept_b)

    assert axis.positive_pole == mock_concept_a
    assert axis.negative_pole == mock_concept_b
    assert axis.axis_magnitude > 0
    assert axis.axis_vector is not None
    assert len(axis.axis_vector) == 3  # 3D test embeddings


@pytest.mark.unit
def test_polarity_axis_magnitude(mock_concept_a, mock_concept_b):
    """Test that axis magnitude is calculated correctly"""
    axis = _make_axis(mock_concept_a, mock_concept_b)

    # Manual calculation: distance between [1,0,0] and [0,1,0]
    expected_magnitude = np.linalg.norm(
        mock_concept_a.embedding - mock_concept_b.embedding
    )

    assert np.isclose(axis.axis_magnitude, expected_magnitude)


@pytest.mark.unit
def test_polarity_axis_unit_vector(mock_concept_a, mock_concept_b):
    """Test that axis vector is normalized"""
    axis = _make_axis(mock_concept_a, mock_concept_b)

    # Unit vector should have magnitude 1
    unit_magnitude = np.linalg.norm(axis.axis_vector)
    assert np.isclose(unit_magnitude, 1.0)


@pytest.mark.unit
def test_polarity_axis_rejects_similar_poles(mock_concept_a, mock_concept_duplicate):
    """Test that similar poles are rejected"""
    with pytest.raises(ValueError, match="too similar"):
        _make_axis(mock_concept_a, mock_concept_duplicate)


@pytest.mark.unit
def test_polarity_axis_rejects_zero_magnitude():
    """Test that identical poles are rejected (zero magnitude)"""
    concept = Concept(
        concept_id="test",
        label="Test",
        embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        description="Test",
        grounding=0.0
    )

    with pytest.raises(ValueError, match="too similar"):
        _make_axis(concept, concept)


# ============================================================================
# Unit Tests: Concept Projection
# ============================================================================

@pytest.mark.unit
def test_project_concept_at_positive_pole(mock_concept_a, mock_concept_b):
    """Test projection of concept at positive pole"""
    axis = _make_axis(mock_concept_a, mock_concept_b)
    projection = axis.project_concept(mock_concept_a)

    # Concept at positive pole should have position close to +1
    assert projection['position'] > 0.9
    assert projection['direction'] == 'positive'
    assert projection['axis_distance'] < 0.1  # Very close to axis


@pytest.mark.unit
def test_project_concept_at_negative_pole(mock_concept_a, mock_concept_b):
    """Test projection of concept at negative pole"""
    axis = _make_axis(mock_concept_a, mock_concept_b)
    projection = axis.project_concept(mock_concept_b)

    # Concept at negative pole should have position close to -1
    assert projection['position'] < -0.9
    assert projection['direction'] == 'negative'
    assert projection['axis_distance'] < 0.1  # Very close to axis


@pytest.mark.unit
def test_project_concept_neutral(mock_concept_a, mock_concept_b, mock_concept_c):
    """Test projection of neutral concept"""
    axis = _make_axis(mock_concept_a, mock_concept_b)
    projection = axis.project_concept(mock_concept_c)

    # Concept between poles should have neutral position
    assert -0.3 <= projection['position'] <= 0.3
    assert projection['direction'] == 'neutral'


@pytest.mark.unit
def test_direction_classification_thresholds(mock_concept_a, mock_concept_b):
    """Test direction classification thresholds (±0.3)"""
    axis = _make_axis(mock_concept_a, mock_concept_b)

    # Create concepts at specific positions
    concept_positive = Concept(
        concept_id="pos",
        label="Positive",
        embedding=np.array([0.8, 0.2, 0.0], dtype=np.float32),  # Closer to A
        description="Should be positive",
        grounding=0.0
    )

    concept_neutral = Concept(
        concept_id="neu",
        label="Neutral",
        embedding=np.array([0.5, 0.5, 0.0], dtype=np.float32),  # Midpoint
        description="Should be neutral",
        grounding=0.0
    )

    concept_negative = Concept(
        concept_id="neg",
        label="Negative",
        embedding=np.array([0.2, 0.8, 0.0], dtype=np.float32),  # Closer to B
        description="Should be negative",
        grounding=0.0
    )

    proj_pos = axis.project_concept(concept_positive)
    proj_neu = axis.project_concept(concept_neutral)
    proj_neg = axis.project_concept(concept_negative)

    assert proj_pos['direction'] == 'positive'
    assert proj_neu['direction'] == 'neutral'
    assert proj_neg['direction'] == 'negative'


@pytest.mark.unit
def test_pole_inversion_flips_positions(mock_concept_a, mock_concept_b, mock_concept_c):
    """
    Test that swapping poles inverts position signs (mathematical correctness).

    This is the critical validation test mentioned in the code review.
    """
    # Create axis with A as positive, B as negative
    axis1 = _make_axis(mock_concept_a, mock_concept_b)
    proj1 = axis1.project_concept(mock_concept_c)

    # Create axis with B as positive, A as negative (swapped)
    axis2 = _make_axis(mock_concept_b, mock_concept_a)
    proj2 = axis2.project_concept(mock_concept_c)

    # Positions should have opposite signs
    assert np.isclose(proj1['position'], -proj2['position'], atol=0.01)

    # Magnitude should be unchanged
    assert np.isclose(axis1.axis_magnitude, axis2.axis_magnitude)

    # Axis distance should be unchanged (orthogonality is independent of pole order)
    assert np.isclose(proj1['axis_distance'], proj2['axis_distance'], atol=0.01)


@pytest.mark.unit
def test_orthogonal_concept_high_axis_distance():
    """Test that orthogonal concepts have high axis distance"""
    concept_a = Concept(
        concept_id="a",
        label="A",
        embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        description="X-axis",
        grounding=0.0
    )

    concept_b = Concept(
        concept_id="b",
        label="B",
        embedding=np.array([0.0, 1.0, 0.0], dtype=np.float32),
        description="Y-axis",
        grounding=0.0
    )

    concept_orthogonal = Concept(
        concept_id="ortho",
        label="Orthogonal",
        embedding=np.array([0.0, 0.0, 1.0], dtype=np.float32),  # Z-axis (orthogonal)
        description="Z-axis",
        grounding=0.0
    )

    axis = _make_axis(concept_a, concept_b)
    projection = axis.project_concept(concept_orthogonal)

    # Orthogonal concept should have high axis distance
    assert projection['axis_distance'] > 0.5


# ============================================================================
# Unit Tests: Grounding Correlation
# ============================================================================

@pytest.mark.unit
def test_grounding_correlation_positive():
    """Test strong positive correlation detection"""
    projections = [
        {'position': -1.0, 'grounding': -0.8},
        {'position': -0.5, 'grounding': -0.4},
        {'position': 0.0, 'grounding': 0.0},
        {'position': 0.5, 'grounding': 0.4},
        {'position': 1.0, 'grounding': 0.8},
    ]

    result = calculate_grounding_correlation(projections)

    assert result['pearson_r'] > 0.9  # Strong positive correlation
    assert result['p_value'] < 0.05  # Statistically significant
    assert 'positive' in result['interpretation'].lower()


@pytest.mark.unit
def test_grounding_correlation_negative():
    """Test strong negative correlation detection"""
    projections = [
        {'position': -1.0, 'grounding': 0.8},
        {'position': -0.5, 'grounding': 0.4},
        {'position': 0.0, 'grounding': 0.0},
        {'position': 0.5, 'grounding': -0.4},
        {'position': 1.0, 'grounding': -0.8},
    ]

    result = calculate_grounding_correlation(projections)

    assert result['pearson_r'] < -0.9  # Strong negative correlation
    assert result['p_value'] < 0.05  # Statistically significant
    assert 'negative' in result['interpretation'].lower()


@pytest.mark.unit
def test_grounding_correlation_none():
    """Test no correlation detection"""
    projections = [
        {'position': -1.0, 'grounding': 0.1},
        {'position': -0.5, 'grounding': -0.1},
        {'position': 0.0, 'grounding': 0.2},
        {'position': 0.5, 'grounding': -0.05},
        {'position': 1.0, 'grounding': 0.0},
    ]

    result = calculate_grounding_correlation(projections)

    assert -0.3 < result['pearson_r'] < 0.3  # Weak/no correlation
    assert 'weak' in result['interpretation'].lower() or 'no' in result['interpretation'].lower()


@pytest.mark.unit
def test_grounding_correlation_insufficient_data():
    """Test handling of insufficient data (< 3 points)"""
    projections = [
        {'position': -1.0, 'grounding': -0.5},
        {'position': 1.0, 'grounding': 0.5},
    ]

    result = calculate_grounding_correlation(projections)

    # Should handle gracefully with warning
    assert 'pearson_r' in result
    assert 'p_value' in result
    assert 'interpretation' in result


# ============================================================================
# Integration Tests: API Endpoint
# ============================================================================

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip(reason="Requires test database with real concepts and embeddings")
def test_polarity_axis_endpoint_requires_auth(api_client):
    """Test that /query/polarity-axis requires authentication"""
    response = api_client.post("/query/polarity-axis", json={
        "positive_pole_id": "test_a",
        "negative_pole_id": "test_b"
    })

    assert response.status_code == 401  # Unauthorized


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip(reason="Requires test database with real concepts and embeddings")
def test_polarity_axis_endpoint_validation(api_client):
    """Test input validation"""
    # Missing required fields
    response = api_client.post("/query/polarity-axis", json={})
    assert response.status_code == 422

    # Invalid max_candidates (exceeds limit)
    response = api_client.post("/query/polarity-axis", json={
        "positive_pole_id": "test_a",
        "negative_pole_id": "test_b",
        "max_candidates": 1000  # Exceeds 100 limit
    })
    assert response.status_code == 422

    # Invalid max_hops (exceeds limit)
    response = api_client.post("/query/polarity-axis", json={
        "positive_pole_id": "test_a",
        "negative_pole_id": "test_b",
        "max_hops": 10  # Exceeds 3 limit
    })
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip(reason="Requires test database with real concepts and embeddings")
def test_polarity_axis_endpoint_success(api_client, auth_token):
    """Test successful polarity axis analysis"""
    response = api_client.post(
        "/query/polarity-axis",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "positive_pole_id": "test_concept_a",
            "negative_pole_id": "test_concept_b",
            "auto_discover": True,
            "max_candidates": 20,
            "max_hops": 2
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Validate response structure
    assert data['success'] is True
    assert 'axis' in data
    assert 'projections' in data
    assert 'statistics' in data
    assert 'grounding_correlation' in data

    # Validate axis metadata
    assert 'positive_pole' in data['axis']
    assert 'negative_pole' in data['axis']
    assert 'magnitude' in data['axis']
    assert 'axis_quality' in data['axis']

    # Validate projections
    assert isinstance(data['projections'], list)
    if len(data['projections']) > 0:
        proj = data['projections'][0]
        assert 'concept_id' in proj
        assert 'label' in proj
        assert 'position' in proj
        assert 'direction' in proj
        assert 'grounding' in proj
        assert 'axis_distance' in proj
        assert -1.0 <= proj['position'] <= 1.0
        assert proj['direction'] in ['positive', 'neutral', 'negative']

    # Validate statistics
    stats = data['statistics']
    assert 'total_concepts' in stats
    assert 'position_range' in stats
    assert 'mean_position' in stats
    assert 'direction_distribution' in stats

    # Validate grounding correlation
    corr = data['grounding_correlation']
    assert 'pearson_r' in corr
    assert 'p_value' in corr
    assert 'interpretation' in corr


# ============================================================================
# Edge Case Tests
# ============================================================================

@pytest.mark.unit
def test_single_dimensional_embeddings():
    """Test with 1D embeddings (edge case)"""
    concept_a = Concept(
        concept_id="a",
        label="A",
        embedding=np.array([1.0], dtype=np.float32),
        description="1D positive",
        grounding=0.5
    )

    concept_b = Concept(
        concept_id="b",
        label="B",
        embedding=np.array([-1.0], dtype=np.float32),
        description="1D negative",
        grounding=-0.5
    )

    concept_mid = Concept(
        concept_id="mid",
        label="Mid",
        embedding=np.array([0.0], dtype=np.float32),
        description="1D midpoint",
        grounding=0.0
    )

    axis = _make_axis(concept_a, concept_b)
    projection = axis.project_concept(concept_mid)

    # Midpoint should project to position ~0
    assert -0.1 <= projection['position'] <= 0.1
    assert projection['direction'] == 'neutral'


@pytest.mark.unit
def test_high_dimensional_embeddings():
    """Test with high-dimensional embeddings (768D like real embeddings)"""
    np.random.seed(42)  # Reproducible

    concept_a = Concept(
        concept_id="a",
        label="A",
        embedding=np.random.rand(768).astype(np.float32),
        description="768D concept A",
        grounding=0.3
    )

    concept_b = Concept(
        concept_id="b",
        label="B",
        embedding=np.random.rand(768).astype(np.float32),
        description="768D concept B",
        grounding=-0.2
    )

    concept_c = Concept(
        concept_id="c",
        label="C",
        embedding=np.random.rand(768).astype(np.float32),
        description="768D concept C",
        grounding=0.1
    )

    # Should work with high-dimensional embeddings
    axis = _make_axis(concept_a, concept_b)
    projection = axis.project_concept(concept_c)

    assert -1.0 <= projection['position'] <= 1.0
    assert projection['direction'] in ['positive', 'neutral', 'negative']
    assert projection['axis_distance'] >= 0


@pytest.mark.unit
def test_normalized_embeddings():
    """Test with normalized (unit) embeddings"""
    concept_a = Concept(
        concept_id="a",
        label="A",
        embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32) / np.linalg.norm([1.0, 0.0, 0.0]),
        description="Unit vector A",
        grounding=0.0
    )

    concept_b = Concept(
        concept_id="b",
        label="B",
        embedding=np.array([0.0, 1.0, 0.0], dtype=np.float32) / np.linalg.norm([0.0, 1.0, 0.0]),
        description="Unit vector B",
        grounding=0.0
    )

    # Should work correctly with normalized embeddings
    axis = _make_axis(concept_a, concept_b)

    assert axis.axis_magnitude > 0
    assert np.isclose(np.linalg.norm(axis.axis_vector), 1.0)
