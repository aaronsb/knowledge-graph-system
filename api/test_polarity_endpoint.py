#!/usr/bin/env python3
"""Test the /query/polarity-axis API endpoint."""

import requests
import json
import sys

# API base URL
API_BASE = "http://localhost:8000"

# Test credentials (admin user)
USERNAME = "admin"
PASSWORD = "admin"


def get_auth_token():
    """Get OAuth token for authentication"""
    print("🔑 Authenticating...")
    response = requests.post(
        f"{API_BASE}/auth/token",
        data={
            "username": USERNAME,
            "password": PASSWORD
        }
    )

    if response.status_code != 200:
        print(f"❌ Authentication failed: {response.status_code}")
        print(response.text)
        sys.exit(1)

    token_data = response.json()
    print(f"✓ Authenticated as {USERNAME}")
    return token_data["access_token"]


def test_polarity_axis(token):
    """Test polarity axis analysis endpoint"""
    print("\n" + "=" * 70)
    print("Testing POST /query/polarity-axis")
    print("=" * 70)
    print()

    # Test request
    request_data = {
        "positive_pole_id": "sha256:0d5be_chunk1_a2ccadba",  # Modern Ways of Working
        "negative_pole_id": "sha256:0f72d_chunk1_9a13bb20",  # Traditional Operating Models
        "auto_discover": True,
        "max_candidates": 10,
        "max_hops": 2
    }

    print(f"Request:")
    print(f"  Positive pole: {request_data['positive_pole_id']}")
    print(f"  Negative pole: {request_data['negative_pole_id']}")
    print(f"  Auto-discover: {request_data['auto_discover']}")
    print(f"  Max candidates: {request_data['max_candidates']}")
    print()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("⏳ Sending request...")
    response = requests.post(
        f"{API_BASE}/query/polarity-axis",
        headers=headers,
        json=request_data
    )

    if response.status_code != 200:
        print(f"\n❌ Request failed: {response.status_code}")
        print(response.text)
        return False

    result = response.json()
    print(f"\n✅ Request successful (200 OK)")
    print()

    # Display results
    print("📊 Results:")
    print("-" * 70)

    # Axis info
    axis = result['axis']
    print(f"\nPolarity Axis:")
    print(f"  Positive: {axis['positive_pole']['label']} (grounding: {axis['positive_pole']['grounding']:.3f})")
    print(f"  Negative: {axis['negative_pole']['label']} (grounding: {axis['negative_pole']['grounding']:.3f})")
    print(f"  Magnitude: {axis['magnitude']:.4f}")
    print(f"  Quality: {axis['axis_quality']}")

    # Statistics
    stats = result['statistics']
    print(f"\nStatistics:")
    print(f"  Total concepts: {stats['total_concepts']}")
    print(f"  Position range: [{stats['position_range'][0]:.3f}, {stats['position_range'][1]:.3f}]")
    print(f"  Mean position: {stats['mean_position']:.3f}")
    print(f"  Mean axis distance: {stats['mean_axis_distance']:.3f}")

    # Direction distribution
    dist = stats['direction_distribution']
    print(f"\nDirection Distribution:")
    print(f"  Positive: {dist['positive']}")
    print(f"  Neutral: {dist['neutral']}")
    print(f"  Negative: {dist['negative']}")

    # Grounding correlation
    corr = result['grounding_correlation']
    print(f"\nGrounding Correlation:")
    print(f"  Pearson r: {corr['pearson_r']:.3f}")
    print(f"  p-value: {corr['p_value']:.4f}")
    print(f"  {corr['interpretation']}")

    # Sample projections
    projections = result['projections']
    if projections:
        print(f"\nSample Projections (top 5):")
        for i, proj in enumerate(projections[:5], 1):
            print(f"  {i}. {proj['label']}")
            print(f"     Position: {proj['position']:+.3f} | Direction: {proj['direction']} | Grounding: {proj['grounding']:.3f}")

    print()
    print("=" * 70)
    print("✅ Test completed successfully!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        token = get_auth_token()
        success = test_polarity_axis(token)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
