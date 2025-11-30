#!/usr/bin/env python3
"""
Polarity Axis Triangulation - Simplified 2D Visualization
A cleaner demonstration of ADR-058 focusing on the key concept
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Slider
from matplotlib.animation import FuncAnimation

def create_simple_demo():
    """Create a simplified 2D demonstration of polarity axis triangulation"""
    
    # Create figure with subplots
    fig = plt.figure(figsize=(15, 6))
    fig.suptitle('Polarity Axis Triangulation: From Binary to Continuous', 
                 fontsize=14, fontweight='bold')
    
    # --- LEFT PANEL: Old Binary Approach ---
    ax1 = fig.add_subplot(131)
    ax1.set_title('Old: Binary Classification', fontsize=11)
    ax1.set_xlim([-2, 2])
    ax1.set_ylim([-2, 2])
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.2)
    ax1.axhline(y=0, color='k', linewidth=0.5)
    ax1.axvline(x=0, color='k', linewidth=0.5)
    
    # Plot SUPPORTS and CONTRADICTS as points
    supports_pos = np.array([1.2, 0.8])
    contradicts_pos = np.array([-1.0, -0.6])
    
    ax1.scatter(*supports_pos, c='green', s=200, marker='o', 
                edgecolors='darkgreen', linewidth=2, zorder=5)
    ax1.text(supports_pos[0], supports_pos[1]-0.3, 'SUPPORTS', 
             fontsize=9, ha='center')
    
    ax1.scatter(*contradicts_pos, c='red', s=200, marker='o',
                edgecolors='darkred', linewidth=2, zorder=5)
    ax1.text(contradicts_pos[0], contradicts_pos[1]-0.3, 'CONTRADICTS', 
             fontsize=9, ha='center')
    
    # Example edge: MOUNTED_ON
    edge_pos = np.array([0.3, 1.5])
    ax1.scatter(*edge_pos, c='purple', s=150, marker='^',
                edgecolors='darkviolet', linewidth=2, zorder=5)
    ax1.text(edge_pos[0], edge_pos[1]+0.2, 'MOUNTED_ON', 
             fontsize=9, ha='center')
    
    # Draw distances
    dist_to_support = np.linalg.norm(edge_pos - supports_pos)
    dist_to_contradict = np.linalg.norm(edge_pos - contradicts_pos)
    
    ax1.plot([edge_pos[0], supports_pos[0]], [edge_pos[1], supports_pos[1]], 
             'g--', alpha=0.5, linewidth=1)
    ax1.plot([edge_pos[0], contradicts_pos[0]], [edge_pos[1], contradicts_pos[1]], 
             'r--', alpha=0.5, linewidth=1)
    
    # Show binary decision
    if dist_to_support < dist_to_contradict:
        winner = "→ 100% SUPPORT"
        color = 'green'
    else:
        winner = "→ 100% CONTRADICT"
        color = 'red'
    
    ax1.text(0, -1.7, f'Distance to SUPPORTS: {dist_to_support:.2f}\n' +
                      f'Distance to CONTRADICTS: {dist_to_contradict:.2f}\n' +
                      f'Result: {winner}',
             fontsize=9, ha='center', 
             bbox=dict(boxstyle='round', facecolor=color, alpha=0.2))
    
    # --- MIDDLE PANEL: Multiple Pairs & Triangulation ---
    ax2 = fig.add_subplot(132)
    ax2.set_title('New: Triangulation from Multiple Pairs', fontsize=11)
    ax2.set_xlim([-2, 2])
    ax2.set_ylim([-2, 2])
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.2)
    ax2.axhline(y=0, color='k', linewidth=0.5)
    ax2.axvline(x=0, color='k', linewidth=0.5)
    
    # Define multiple polarity pairs (2D projections for visualization)
    pairs = [
        {'pos': [1.2, 0.8], 'neg': [-1.0, -0.6], 'name': 'SUP/CON', 'color': '#4ade80'},
        {'pos': [1.0, 1.2], 'neg': [-0.8, -1.0], 'name': 'VAL/REF', 'color': '#60a5fa'},
        {'pos': [1.4, 0.4], 'neg': [-1.2, -0.3], 'name': 'CON/DIS', 'color': '#a78bfa'},
        {'pos': [0.8, 1.3], 'neg': [-0.6, -1.1], 'name': 'REI/OPP', 'color': '#f472b6'},
        {'pos': [1.3, 0.9], 'neg': [-1.1, -0.7], 'name': 'ENA/PRE', 'color': '#fb923c'}
    ]
    
    # Plot pairs and calculate difference vectors
    diff_vectors = []
    for pair in pairs:
        pos = np.array(pair['pos'])
        neg = np.array(pair['neg'])
        
        # Small dots for poles
        ax2.scatter(*pos, c='green', s=40, alpha=0.6)
        ax2.scatter(*neg, c='red', s=40, alpha=0.6)
        
        # Difference vector
        diff = pos - neg
        diff_vectors.append(diff)
        
        # Draw arrow from negative to positive
        ax2.arrow(neg[0], neg[1], diff[0], diff[1], 
                 head_width=0.08, head_length=0.1, 
                 fc=pair['color'], ec=pair['color'], 
                 alpha=0.5, linewidth=1.5)
    
    # Calculate and draw polarity axis (average of difference vectors)
    polarity_axis = np.mean(diff_vectors, axis=0)
    polarity_axis = polarity_axis / np.linalg.norm(polarity_axis) * 2  # Normalize and scale
    
    # Draw polarity axis
    ax2.arrow(-polarity_axis[0], -polarity_axis[1], 
              polarity_axis[0]*2, polarity_axis[1]*2,
              head_width=0.15, head_length=0.2, 
              fc='gold', ec='gold', linewidth=3, zorder=10)
    ax2.text(polarity_axis[0], polarity_axis[1]+0.2, 'Polarity Axis', 
             fontsize=10, ha='center', fontweight='bold', color='darkgoldenrod')
    
    # Legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=p['color'], alpha=0.5, label=p['name']) 
                       for p in pairs]
    ax2.legend(handles=legend_elements, loc='upper left', fontsize=7)
    
    # --- RIGHT PANEL: Continuous Projection ---
    ax3 = fig.add_subplot(133)
    ax3.set_title('New: Continuous Projection onto Axis', fontsize=11)
    ax3.set_xlim([-2, 2])
    ax3.set_ylim([-0.5, 2])
    ax3.grid(True, alpha=0.2)
    
    # Draw horizontal polarity axis
    ax3.arrow(-1.8, 0, 3.6, 0, head_width=0.08, head_length=0.1,
              fc='gold', ec='gold', linewidth=3)
    ax3.text(-1.8, -0.2, 'CONTRADICT', fontsize=9, color='red', ha='center')
    ax3.text(1.8, -0.2, 'SUPPORT', fontsize=9, color='green', ha='center')
    ax3.text(0, -0.2, '0', fontsize=9, ha='center')
    
    # Mark axis points
    for x in [-1.5, -1, -0.5, 0, 0.5, 1, 1.5]:
        ax3.axvline(x=x, color='gray', linewidth=0.5, alpha=0.3)
        if x != 0:
            ax3.text(x, -0.35, f'{x:.1f}', fontsize=8, ha='center', color='gray')
    
    # Show projections of various edge types
    edge_types = [
        {'name': 'MOUNTED_ON', 'projection': 0.15, 'color': 'purple'},
        {'name': 'PART_OF', 'projection': 0.02, 'color': 'blue'},
        {'name': 'SUPPORTS', 'projection': 0.85, 'color': 'green'},
        {'name': 'CONTRADICTS', 'projection': -0.78, 'color': 'red'},
        {'name': 'RELATED_TO', 'projection': 0.08, 'color': 'orange'}
    ]
    
    for i, edge in enumerate(edge_types):
        y_pos = 0.3 + i * 0.25
        
        # Draw edge as point
        ax3.scatter([edge['projection']], [y_pos], 
                   c=edge['color'], s=100, marker='^', 
                   edgecolors='dark'+edge['color'], linewidth=1.5, zorder=5)
        
        # Draw projection line
        ax3.plot([edge['projection'], edge['projection']], [0, y_pos],
                 color=edge['color'], linestyle='--', alpha=0.4)
        
        # Label
        ax3.text(edge['projection'], y_pos + 0.1, edge['name'], 
                fontsize=8, ha='center')
        
        # Grounding value
        grounding = edge['projection'] * 100
        ax3.text(2.1, y_pos, f'{grounding:+.0f}%', 
                fontsize=8, ha='left', color=edge['color'])
    
    ax3.set_xlabel('Projection Value (Dot Product)', fontsize=10)
    ax3.set_ylabel('Different Edge Types', fontsize=10)
    ax3.set_yticks([])
    
    # Add summary box
    fig.text(0.5, 0.02, 
             'Key Insight: Instead of binary "closer to which?" we ask "where on the spectrum?"',
             ha='center', fontsize=11, style='italic', 
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.08, top=0.92)
    return fig

def create_interactive_demo():
    """Create an interactive version with slider control"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Interactive Polarity Axis Projection', fontsize=14, fontweight='bold')
    
    # Left: 2D vector space
    ax1.set_title('Vector Space (2D Projection)', fontsize=11)
    ax1.set_xlim([-2, 2])
    ax1.set_ylim([-2, 2])
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.2)
    ax1.axhline(y=0, color='k', linewidth=0.5)
    ax1.axvline(x=0, color='k', linewidth=0.5)
    
    # Define polarity pairs
    pairs = [
        {'pos': [1.2, 0.8], 'neg': [-1.0, -0.6], 'color': '#4ade80'},
        {'pos': [1.0, 1.2], 'neg': [-0.8, -1.0], 'color': '#60a5fa'},
        {'pos': [1.4, 0.4], 'neg': [-1.2, -0.3], 'color': '#a78bfa'}
    ]
    
    # Calculate polarity axis
    diff_vectors = []
    for pair in pairs:
        pos = np.array(pair['pos'])
        neg = np.array(pair['neg'])
        ax1.scatter(*pos, c='green', s=60, alpha=0.6)
        ax1.scatter(*neg, c='red', s=60, alpha=0.6)
        diff = pos - neg
        diff_vectors.append(diff)
        ax1.arrow(neg[0], neg[1], diff[0], diff[1],
                 head_width=0.08, head_length=0.1,
                 fc=pair['color'], ec=pair['color'], 
                 alpha=0.4, linewidth=1.5)
    
    polarity_axis = np.mean(diff_vectors, axis=0)
    polarity_axis = polarity_axis / np.linalg.norm(polarity_axis)
    
    # Draw polarity axis
    axis_scale = 1.8
    ax1.arrow(-polarity_axis[0]*axis_scale, -polarity_axis[1]*axis_scale,
              polarity_axis[0]*axis_scale*2, polarity_axis[1]*axis_scale*2,
              head_width=0.12, head_length=0.15,
              fc='gold', ec='gold', linewidth=3, zorder=10)
    
    # Right: Projection visualization
    ax2.set_title('Projection onto Polarity Axis', fontsize=11)
    ax2.set_xlim([-1.5, 1.5])
    ax2.set_ylim([-0.5, 1])
    ax2.grid(True, alpha=0.2)
    ax2.axhline(y=0, color='k', linewidth=0.5)
    
    # Draw horizontal axis
    ax2.arrow(-1.4, 0, 2.8, 0, head_width=0.05, head_length=0.08,
              fc='gold', ec='gold', linewidth=3)
    ax2.text(-1.3, -0.15, 'CONTRADICT (-)', fontsize=9, color='red')
    ax2.text(1.3, -0.15, 'SUPPORT (+)', fontsize=9, color='green')
    
    # Initial edge position
    edge_angle = np.pi/4
    edge_vec = np.array([np.cos(edge_angle), np.sin(edge_angle)])
    
    # Plot edge vector
    edge_point = ax1.scatter(*edge_vec, c='magenta', s=150, marker='^',
                            edgecolors='darkmagenta', linewidth=2, zorder=5)
    edge_arrow = ax1.arrow(0, 0, edge_vec[0], edge_vec[1],
                          head_width=0.08, head_length=0.1,
                          fc='magenta', ec='magenta', alpha=0.6, linewidth=2)
    
    # Calculate projection
    projection = np.dot(edge_vec, polarity_axis)
    projected_point = polarity_axis * projection
    
    # Projection line
    proj_line = ax1.plot([edge_vec[0], projected_point[0]],
                        [edge_vec[1], projected_point[1]],
                        'magenta', linestyle='--', alpha=0.5, linewidth=2)[0]
    
    # Show projection on right plot
    proj_marker = ax2.scatter([projection], [0.3], c='magenta', s=200, marker='^',
                             edgecolors='darkmagenta', linewidth=2, zorder=5)
    proj_vline = ax2.axvline(x=projection, color='magenta', linestyle='--', alpha=0.5)
    
    # Projection text
    proj_text = ax2.text(0, 0.6, 
                        f'Projection: {projection:.3f}\n' +
                        f'Grounding: {projection*100:.1f}%',
                        fontsize=12, ha='center',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Add slider
    ax_slider = plt.axes([0.2, 0.02, 0.6, 0.03])
    slider = Slider(ax_slider, 'Edge Angle', 0, 2*np.pi, valinit=edge_angle)
    
    def update(val):
        angle = slider.val
        edge_vec = np.array([np.cos(angle), np.sin(angle)])
        
        # Update edge position
        edge_point.set_offsets([edge_vec])
        
        # Remove old arrow and add new one
        nonlocal edge_arrow
        edge_arrow.remove()
        edge_arrow = ax1.arrow(0, 0, edge_vec[0], edge_vec[1],
                              head_width=0.08, head_length=0.1,
                              fc='magenta', ec='magenta', alpha=0.6, linewidth=2)
        
        # Update projection
        projection = np.dot(edge_vec, polarity_axis)
        projected_point = polarity_axis * projection
        
        proj_line.set_data([edge_vec[0], projected_point[0]],
                          [edge_vec[1], projected_point[1]])
        
        proj_marker.set_offsets([[projection, 0.3]])
        proj_vline.set_xdata([projection])
        
        # Update text and color
        proj_text.set_text(f'Projection: {projection:.3f}\n' +
                          f'Grounding: {projection*100:.1f}%')
        
        color = 'green' if projection > 0.1 else 'red' if projection < -0.1 else 'gray'
        proj_marker.set_color(color)
        
        fig.canvas.draw_idle()
    
    slider.on_changed(update)
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.1)
    return fig, slider

# Run the demos
if __name__ == '__main__':
    # Create static comparison
    fig1 = create_simple_demo()
    
    # Create interactive version
    fig2, slider = create_interactive_demo()
    
    plt.show()
