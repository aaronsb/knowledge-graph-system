#!/usr/bin/env python3
"""
Generate publication-quality static figures for ADR-058 documentation
Saves high-resolution PNG images suitable for inclusion in documentation
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
import matplotlib.lines as mlines

def create_documentation_figure():
    """Create a comprehensive figure explaining the polarity axis approach"""
    
    # Create figure with custom layout
    fig = plt.figure(figsize=(16, 10))
    
    # Main title
    fig.suptitle('ADR-058: Polarity Axis Triangulation for Grounding Calculation', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    # Create grid of subplots
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3, 
                          left=0.05, right=0.95, top=0.93, bottom=0.05)
    
    # ========== PANEL 1: The Problem ==========
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_title('The Problem: Binary Classification Produces Extremes', 
                  fontsize=12, fontweight='bold', color='darkred')
    ax1.axis('off')
    
    # Problem description box
    problem_text = (
        "Original Algorithm Issues:\n"
        "• SUPPORTS and CONTRADICTS are 81% similar in embedding space\n"
        "• Binary decision: 'which is closer?' provides minimal signal\n"
        "• Results: Only -100%, 0%, or +100% grounding values\n"
        "• Example: MOUNTED_ON → slightly closer to SUPPORTS → 100% support (wrong!)"
    )
    
    ax1.text(0.05, 0.5, problem_text, fontsize=10, 
             bbox=dict(boxstyle="round,pad=0.5", facecolor='#ffe6e6'),
             verticalalignment='center', family='monospace')
    
    # Visual of binary problem
    ax1_vis = ax1.inset_axes([0.5, 0.1, 0.48, 0.8])
    ax1_vis.set_xlim([0, 10])
    ax1_vis.set_ylim([0, 5])
    ax1_vis.axis('off')
    
    # Draw SUPPORTS and CONTRADICTS close together
    sup_circle = Circle((3, 2.5), 0.5, color='green', alpha=0.7)
    con_circle = Circle((4, 2.5), 0.5, color='red', alpha=0.7)
    ax1_vis.add_patch(sup_circle)
    ax1_vis.add_patch(con_circle)
    ax1_vis.text(3, 2.5, 'S', ha='center', va='center', fontsize=12, fontweight='bold')
    ax1_vis.text(4, 2.5, 'C', ha='center', va='center', fontsize=12, fontweight='bold')
    ax1_vis.text(3.5, 1.5, '81% similar!', ha='center', fontsize=9, style='italic')
    
    # Edge point
    ax1_vis.scatter([3.4], [3.5], s=100, c='purple', marker='^', zorder=5)
    ax1_vis.text(3.4, 3.8, 'Edge', ha='center', fontsize=10)
    
    # Show distances
    ax1_vis.plot([3.4, 3], [3.5, 2.5], 'g--', alpha=0.5)
    ax1_vis.plot([3.4, 4], [3.5, 2.5], 'r--', alpha=0.5)
    ax1_vis.text(7, 3, '0.22 < 0.24', ha='center', fontsize=10)
    ax1_vis.text(7, 2.5, '↓', ha='center', fontsize=14)
    ax1_vis.text(7, 2, '100% SUPPORT', ha='center', fontsize=11, 
                 fontweight='bold', color='green')
    
    # ========== PANEL 2: The Solution Concept ==========
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_title('Solution: Multiple Opposing Pairs', fontsize=11, fontweight='bold')
    ax2.set_xlim([-2, 2])
    ax2.set_ylim([-2, 2])
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.2)
    
    # Show multiple pairs
    pairs_data = [
        {'pos': [1.2, 0.8], 'neg': [-1.0, -0.6], 'label': 'SUP/CON', 'color': '#4ade80'},
        {'pos': [1.0, 1.2], 'neg': [-0.8, -1.0], 'label': 'VAL/REF', 'color': '#60a5fa'},
        {'pos': [1.4, 0.4], 'neg': [-1.2, -0.3], 'label': 'CON/DIS', 'color': '#a78bfa'},
        {'pos': [0.8, 1.3], 'neg': [-0.6, -1.1], 'label': 'REI/OPP', 'color': '#f472b6'},
        {'pos': [1.3, 0.9], 'neg': [-1.1, -0.7], 'label': 'ENA/PRE', 'color': '#fb923c'}
    ]
    
    for pair in pairs_data:
        pos = np.array(pair['pos'])
        neg = np.array(pair['neg'])
        
        # Plot points
        ax2.scatter(*pos, c='green', s=50, alpha=0.7, edgecolors='darkgreen', linewidth=1)
        ax2.scatter(*neg, c='red', s=50, alpha=0.7, edgecolors='darkred', linewidth=1)
        
        # Draw difference vector
        diff = pos - neg
        ax2.arrow(neg[0], neg[1], diff[0]*0.95, diff[1]*0.95,
                 head_width=0.08, head_length=0.08,
                 fc=pair['color'], ec=pair['color'], alpha=0.6, linewidth=1.5)
    
    ax2.set_xlabel('Embedding Dimension 1', fontsize=9)
    ax2.set_ylabel('Embedding Dimension 2', fontsize=9)
    
    # ========== PANEL 3: Triangulation ==========
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_title('Triangulation: Average Difference Vectors', fontsize=11, fontweight='bold')
    ax3.set_xlim([-1, 3])
    ax3.set_ylim([-1, 3])
    ax3.set_aspect('equal')
    ax3.grid(True, alpha=0.2)
    
    # Show difference vectors aligned at origin
    diff_vecs = []
    for i, pair in enumerate(pairs_data):
        pos = np.array(pair['pos'])
        neg = np.array(pair['neg'])
        diff = pos - neg
        diff_vecs.append(diff)
        
        # Draw from origin
        ax3.arrow(0, 0, diff[0], diff[1],
                 head_width=0.08, head_length=0.08,
                 fc=pair['color'], ec=pair['color'], 
                 alpha=0.4, linewidth=1.5)
        
        # Label
        ax3.text(diff[0]+0.1, diff[1]+0.1, pair['label'][:3], 
                fontsize=7, ha='center')
    
    # Calculate and show average
    avg_vec = np.mean(diff_vecs, axis=0)
    avg_vec_norm = avg_vec / np.linalg.norm(avg_vec) * 2
    
    ax3.arrow(0, 0, avg_vec_norm[0], avg_vec_norm[1],
             head_width=0.12, head_length=0.12,
             fc='gold', ec='gold', linewidth=3, zorder=10)
    ax3.text(avg_vec_norm[0]+0.1, avg_vec_norm[1]+0.1, 'Polarity Axis', 
            fontsize=10, fontweight='bold', color='darkgoldenrod')
    
    ax3.set_xlabel('Δ Vector X', fontsize=9)
    ax3.set_ylabel('Δ Vector Y', fontsize=9)
    
    # ========== PANEL 4: Projection ==========
    ax4 = fig.add_subplot(gs[1, 2])
    ax4.set_title('Projection: Continuous Values', fontsize=11, fontweight='bold')
    ax4.set_xlim([-1.5, 1.5])
    ax4.set_ylim([0, 5])
    ax4.grid(True, alpha=0.2, axis='x')
    ax4.set_yticks([])
    
    # Draw horizontal axis
    ax4.arrow(-1.4, 0.2, 2.8, 0, head_width=0.1, head_length=0.08,
             fc='gold', ec='gold', linewidth=3)
    ax4.text(-1.3, 0, 'CONTRADICT', fontsize=8, color='red', ha='center')
    ax4.text(1.3, 0, 'SUPPORT', fontsize=8, color='green', ha='center')
    ax4.text(0, 0, '0', fontsize=8, ha='center')
    
    # Show various edge projections
    edges = [
        {'name': 'MOUNTED_ON', 'proj': 0.001, 'y': 1},
        {'name': 'PART_OF', 'proj': 0.008, 'y': 1.7},
        {'name': 'IMPLIES', 'proj': 0.42, 'y': 2.4},
        {'name': 'SUPPORTS', 'proj': 0.85, 'y': 3.1},
        {'name': 'CONTRADICTS', 'proj': -0.78, 'y': 3.8},
        {'name': 'PREVENTS', 'proj': -0.35, 'y': 4.5}
    ]
    
    for edge in edges:
        color = 'green' if edge['proj'] > 0.1 else 'red' if edge['proj'] < -0.1 else 'gray'
        ax4.scatter([edge['proj']], [edge['y']], s=80, c=color, 
                   marker='^', edgecolors='dark'+color, linewidth=1.5, zorder=5)
        ax4.plot([edge['proj'], edge['proj']], [0.2, edge['y']], 
                color=color, linestyle='--', alpha=0.3)
        ax4.text(edge['proj'], edge['y']+0.2, edge['name'], 
                fontsize=8, ha='center')
        ax4.text(1.5, edge['y'], f"{edge['proj']*100:+.0f}%", 
                fontsize=8, ha='left', color=color)
    
    ax4.set_xlabel('Projection (π = edge · axis)', fontsize=9)
    
    # ========== PANEL 5: Mathematical Formula ==========
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_title('Mathematical Formulation', fontsize=12, fontweight='bold')
    ax5.axis('off')
    
    formula_text = (
        "1. Define polarity pairs: P = {(SUPPORTS, CONTRADICTS), (VALIDATES, REFUTES), ...}\n\n"
        "2. Calculate difference vectors: Δᵢ = E(p⁺ᵢ) - E(p⁻ᵢ)\n\n"
        "3. Triangulate polarity axis: a = normalize(Σ Δᵢ / n)\n\n"
        "4. Project edge embeddings: πᵢ = E(edgeᵢ) · a\n\n"
        "5. Calculate grounding: G = Σ(cᵢ × πᵢ) / Σ cᵢ"
    )
    
    ax5.text(0.05, 0.5, formula_text, fontsize=11,
            bbox=dict(boxstyle="round,pad=0.5", facecolor='#f0f8ff'),
            verticalalignment='center', family='monospace')
    
    # Results comparison table
    results_text = (
        "Results Comparison:\n"
        "┌──────────────────┬───────────────┬────────────────┐\n"
        "│ Concept          │ Old Binary    │ New Projection │\n"
        "├──────────────────┼───────────────┼────────────────┤\n"
        "│ Ford Truck       │ -100%         │ 0%             │\n"
        "│ Vehicle          │ -51%          │ -2%            │\n"
        "│ Travel Trailer   │ +9%           │ +4%            │\n"
        "│ Vehicle Branding │ -100%         │ -5%            │\n"
        "└──────────────────┴───────────────┴────────────────┘"
    )
    
    ax5.text(0.55, 0.5, results_text, fontsize=10,
            bbox=dict(boxstyle="round,pad=0.5", facecolor='#e6ffe6'),
            verticalalignment='center', family='monospace')
    
    return fig

def save_documentation_figures():
    """Generate and save all documentation figures"""
    
    print("Generating documentation figures...")
    
    # Main comprehensive figure
    fig = create_documentation_figure()
    fig.savefig('polarity_axis_documentation.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print("✓ Saved: polarity_axis_documentation.png")
    
    # Create a simpler before/after comparison
    fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig2.suptitle('Before vs After: Binary to Continuous', fontsize=14, fontweight='bold')
    
    # Before
    ax1.set_title('Before: Binary Classification', fontsize=11)
    ax1.bar(['MOUNTED_ON', 'PART_OF', 'RELATED'], [-1.0, 1.0, -1.0], 
           color=['red', 'green', 'red'], alpha=0.7)
    ax1.set_ylim([-1.2, 1.2])
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_ylabel('Grounding Value', fontsize=10)
    ax1.text(0.5, -1.15, 'Only -100%, 0%, or +100%', 
            transform=ax1.transAxes, ha='center', fontsize=9, style='italic')
    
    # After
    ax2.set_title('After: Polarity Axis Projection', fontsize=11)
    ax2.bar(['MOUNTED_ON', 'PART_OF', 'RELATED'], [0.001, 0.008, -0.053],
           color=['gray', 'gray', 'lightcoral'], alpha=0.7)
    ax2.set_ylim([-1.2, 1.2])
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_ylabel('Grounding Value', fontsize=10)
    ax2.text(0.5, -1.15, 'Continuous nuanced values', 
            transform=ax2.transAxes, ha='center', fontsize=9, style='italic')
    
    plt.tight_layout()
    fig2.savefig('polarity_axis_before_after.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print("✓ Saved: polarity_axis_before_after.png")
    
    print("\nDocumentation figures generated successfully!")
    print("Files saved in current directory:")
    print("  - polarity_axis_documentation.png (main comprehensive figure)")
    print("  - polarity_axis_before_after.png (simple comparison)")
    
    return fig, fig2

if __name__ == '__main__':
    # Generate and save figures
    fig1, fig2 = save_documentation_figures()
    
    # Also display them
    plt.show()
