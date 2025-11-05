#!/usr/bin/env python3
"""
Quick demo runner for Polarity Axis Triangulation visualizations
"""

print("=" * 60)
print("POLARITY AXIS TRIANGULATION DEMO")
print("ADR-058 Visualization Suite")
print("=" * 60)
print()

import sys

try:
    import numpy as np
    import matplotlib
    import matplotlib.pyplot as plt
    print("✓ Dependencies loaded successfully")
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    print("  Please install: pip install numpy matplotlib")
    sys.exit(1)

print()
print("Choose which demo to run:")
print("1. 3D Visualization (with interactive sliders)")
print("2. 2D Simplified Demo (comparison of old vs new)")
print("3. Both demos")
print()

choice = input("Enter choice (1-3): ").strip()

if choice == "1" or choice == "3":
    print("\nLaunching 3D visualization...")
    from polarity_axis_visualization import main
    main()

if choice == "2" or choice == "3":
    print("\nLaunching 2D demos...")
    from polarity_axis_2d_demo import create_simple_demo, create_interactive_demo
    
    # Static comparison
    fig1 = create_simple_demo()
    
    # Interactive version
    fig2, slider = create_interactive_demo()
    
    plt.show()

if choice not in ["1", "2", "3"]:
    print("Invalid choice. Please run again and select 1, 2, or 3.")
