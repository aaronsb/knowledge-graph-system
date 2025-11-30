#!/usr/bin/env python3
"""
Polarity Axis Triangulation Visualization
Demonstrates ADR-058: How multiple opposing pairs create a robust polarity axis
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.proj3d import proj_transform
from matplotlib.widgets import Slider, Button
import matplotlib.patches as mpatches

# Custom Arrow class for 3D
class Arrow3D(FancyArrowPatch):
    def __init__(self, xs, ys, zs, *args, **kwargs):
        FancyArrowPatch.__init__(self, (0, 0), (0, 0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def do_3d_projection(self, renderer=None):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
        return np.min(zs)

class PolarityAxisDemo:
    def __init__(self):
        # Define polarity pairs with their embeddings (simulated positions in 3D space)
        self.polarity_pairs = [
            {
                'name': ('SUPPORTS', 'CONTRADICTS'),
                'positive': np.array([0.6, 0.4, 0.3]),
                'negative': np.array([-0.4, -0.3, -0.2]),
                'color': '#4ade80'  # green
            },
            {
                'name': ('VALIDATES', 'REFUTES'),
                'positive': np.array([0.5, 0.2, 0.6]),
                'negative': np.array([-0.3, -0.1, -0.4]),
                'color': '#60a5fa'  # blue
            },
            {
                'name': ('CONFIRMS', 'DISPROVES'),
                'positive': np.array([0.2, 0.6, 0.4]),
                'negative': np.array([-0.1, -0.4, -0.3]),
                'color': '#a78bfa'  # purple
            },
            {
                'name': ('REINFORCES', 'OPPOSES'),
                'positive': np.array([0.6, 0.2, 0.3]),
                'negative': np.array([-0.5, -0.15, -0.2]),
                'color': '#f472b6'  # pink
            },
            {
                'name': ('ENABLES', 'PREVENTS'),
                'positive': np.array([0.3, 0.5, 0.5]),
                'negative': np.array([-0.2, -0.4, -0.4]),
                'color': '#fb923c'  # orange
            }
        ]
        
        # Normalize all positions
        for pair in self.polarity_pairs:
            pair['positive'] = pair['positive'] / np.linalg.norm(pair['positive'])
            pair['negative'] = pair['negative'] / np.linalg.norm(pair['negative'])
        
        # Calculate difference vectors and polarity axis
        self.difference_vectors = []
        for pair in self.polarity_pairs:
            diff_vec = pair['positive'] - pair['negative']
            self.difference_vectors.append(diff_vec)
        
        # Average and normalize to get polarity axis
        self.polarity_axis = np.mean(self.difference_vectors, axis=0)
        self.polarity_axis = self.polarity_axis / np.linalg.norm(self.polarity_axis)
        
        # Initialize edge position
        self.edge_position = np.array([0.5, 0.3, 0.2])
        self.edge_position = self.edge_position / np.linalg.norm(self.edge_position)
        
    def create_3d_plot(self):
        """Create the 3D visualization"""
        fig = plt.figure(figsize=(16, 8))
        fig.suptitle('Polarity Axis Triangulation (ADR-058)', fontsize=16, fontweight='bold')
        
        # 3D plot
        ax3d = fig.add_subplot(121, projection='3d')
        ax3d.set_title('3D View: Vector Space', fontsize=12)
        ax3d.set_xlabel('X')
        ax3d.set_ylabel('Y')
        ax3d.set_zlabel('Z')
        ax3d.set_xlim([-1.5, 1.5])
        ax3d.set_ylim([-1.5, 1.5])
        ax3d.set_zlim([-1.5, 1.5])
        ax3d.view_init(elev=20, azim=45)
        
        # Plot polarity pairs
        for i, pair in enumerate(self.polarity_pairs):
            # Positive poles (support-like)
            ax3d.scatter(*pair['positive'], c='green', s=100, marker='o', 
                        edgecolors='darkgreen', linewidth=2, alpha=0.8,
                        label='Positive poles' if i == 0 else '')
            
            # Negative poles (contradict-like)
            ax3d.scatter(*pair['negative'], c='red', s=100, marker='o',
                        edgecolors='darkred', linewidth=2, alpha=0.8,
                        label='Negative poles' if i == 0 else '')
            
            # Difference vectors
            diff_vec = pair['positive'] - pair['negative']
            arrow = Arrow3D([pair['negative'][0], pair['positive'][0]],
                           [pair['negative'][1], pair['positive'][1]],
                           [pair['negative'][2], pair['positive'][2]],
                           mutation_scale=20, lw=2, color=pair['color'], 
                           alpha=0.6, arrowstyle='->')
            ax3d.add_artist(arrow)
        
        # Plot polarity axis
        axis_scale = 1.5
        axis_arrow = Arrow3D([0, self.polarity_axis[0] * axis_scale],
                            [0, self.polarity_axis[1] * axis_scale],
                            [0, self.polarity_axis[2] * axis_scale],
                            mutation_scale=25, lw=4, color='gold',
                            arrowstyle='->', label='Polarity Axis')
        ax3d.add_artist(axis_arrow)
        
        # Plot negative direction of axis
        neg_axis_arrow = Arrow3D([0, -self.polarity_axis[0] * axis_scale],
                                [0, -self.polarity_axis[1] * axis_scale],
                                [0, -self.polarity_axis[2] * axis_scale],
                                mutation_scale=25, lw=4, color='gold',
                                arrowstyle='->', alpha=0.3)
        ax3d.add_artist(neg_axis_arrow)
        
        # Add origin
        ax3d.scatter([0], [0], [0], c='black', s=50, marker='o')
        
        # 2D Projection plot
        ax2d = fig.add_subplot(122)
        ax2d.set_title('2D View: Projection onto Polarity Axis', fontsize=12)
        ax2d.set_xlim([-1.5, 1.5])
        ax2d.set_ylim([-0.5, 1.5])
        ax2d.set_aspect('equal')
        ax2d.grid(True, alpha=0.3)
        ax2d.axhline(y=0, color='k', linewidth=0.5)
        ax2d.axvline(x=0, color='k', linewidth=0.5)
        
        # Draw the polarity axis as a horizontal line
        ax2d.arrow(-1.5, 0, 3, 0, head_width=0.08, head_length=0.1, 
                  fc='gold', ec='gold', linewidth=3, alpha=0.8)
        ax2d.text(-1.4, -0.15, 'CONTRADICTS', fontsize=9, color='red', ha='left')
        ax2d.text(1.4, -0.15, 'SUPPORTS', fontsize=9, color='green', ha='right')
        
        # Project difference vectors onto axis (show as vertical bars)
        for i, (pair, diff_vec) in enumerate(zip(self.polarity_pairs, self.difference_vectors)):
            projection = np.dot(diff_vec, self.polarity_axis)
            ax2d.bar(projection, 0.8, width=0.05, bottom=0.2, 
                    color=pair['color'], alpha=0.7,
                    label=f"{pair['name'][0][:3]}-{pair['name'][1][:3]}")
            ax2d.text(projection, 1.05, f'{projection:.2f}', 
                     fontsize=8, ha='center', rotation=45)
        
        # Show average (the polarity axis magnitude)
        avg_projection = np.mean([np.dot(dv, self.polarity_axis) 
                                 for dv in self.difference_vectors])
        ax2d.axvline(x=avg_projection, color='gold', linewidth=3, 
                    linestyle='--', alpha=0.8, label='Average')
        
        ax2d.set_xlabel('Projection Value', fontsize=10)
        ax2d.set_ylabel('Difference Vectors', fontsize=10)
        ax2d.legend(loc='upper left', fontsize=8)
        
        # Create edge point and projection (will be updated)
        self.edge_point_3d = ax3d.scatter(*self.edge_position, c='magenta', 
                                          s=150, marker='^', 
                                          edgecolors='darkmagenta', linewidth=2)
        
        # Calculate projection
        projection = np.dot(self.edge_position, self.polarity_axis)
        projected_point = self.polarity_axis * projection
        
        # Projection line in 3D
        self.proj_line_3d = ax3d.plot([self.edge_position[0], projected_point[0]],
                                      [self.edge_position[1], projected_point[1]],
                                      [self.edge_position[2], projected_point[2]],
                                      'magenta', linestyle='--', alpha=0.5)[0]
        
        # Edge projection in 2D
        self.edge_marker_2d = ax2d.scatter([projection], [0], c='magenta', 
                                           s=200, marker='^', zorder=5,
                                           edgecolors='darkmagenta', linewidth=2)
        
        # Add projection value text
        self.proj_text = ax2d.text(0.5, 1.3, 
                                   f'Edge Projection: {projection:.3f}\n' + 
                                   f'Grounding: {projection*100:.1f}%',
                                   fontsize=11, ha='center',
                                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Add sliders for edge position
        ax_theta = plt.axes([0.15, 0.05, 0.3, 0.03])
        ax_phi = plt.axes([0.15, 0.01, 0.3, 0.03])
        self.slider_theta = Slider(ax_theta, 'Theta', 0, 2*np.pi, valinit=np.pi/4)
        self.slider_phi = Slider(ax_phi, 'Phi', 0, np.pi, valinit=np.pi/3)
        
        # Animation button
        ax_button = plt.axes([0.55, 0.01, 0.15, 0.04])
        self.btn_animate = Button(ax_button, 'Animate Rotation')
        
        # Connect sliders
        self.slider_theta.on_changed(self.update_edge_position)
        self.slider_phi.on_changed(self.update_edge_position)
        self.btn_animate.on_clicked(self.animate_rotation)
        
        self.ax3d = ax3d
        self.ax2d = ax2d
        self.fig = fig
        
        return fig
    
    def update_edge_position(self, val=None):
        """Update edge position based on sliders"""
        theta = self.slider_theta.val
        phi = self.slider_phi.val
        
        # Convert spherical to Cartesian
        self.edge_position = np.array([
            np.sin(phi) * np.cos(theta),
            np.sin(phi) * np.sin(theta),
            np.cos(phi)
        ])
        
        # Update 3D plot
        self.edge_point_3d._offsets3d = ([self.edge_position[0]], 
                                         [self.edge_position[1]], 
                                         [self.edge_position[2]])
        
        # Calculate projection
        projection = np.dot(self.edge_position, self.polarity_axis)
        projected_point = self.polarity_axis * projection
        
        # Update projection line
        self.proj_line_3d.set_data_3d([self.edge_position[0], projected_point[0]],
                                      [self.edge_position[1], projected_point[1]],
                                      [self.edge_position[2], projected_point[2]])
        
        # Update 2D plot
        self.edge_marker_2d.set_offsets([[projection, 0]])
        
        # Update text
        self.proj_text.set_text(f'Edge Projection: {projection:.3f}\n' + 
                               f'Grounding: {projection*100:.1f}%')
        
        # Color code based on projection value
        if projection > 0.1:
            color = 'green'
        elif projection < -0.1:
            color = 'red'
        else:
            color = 'gray'
        self.edge_marker_2d.set_color(color)
        
        self.fig.canvas.draw_idle()
    
    def animate_rotation(self, event):
        """Animate a rotation of the 3D view"""
        for angle in np.linspace(45, 405, 60):
            self.ax3d.view_init(elev=20, azim=angle)
            self.fig.canvas.draw()
            plt.pause(0.05)

def main():
    """Create and display the visualization"""
    demo = PolarityAxisDemo()
    fig = demo.create_3d_plot()
    
    # Add info text
    fig.text(0.5, 0.95, 
             'Multiple opposing pairs → Difference vectors → Average & normalize → Robust polarity axis',
             ha='center', fontsize=10, style='italic', color='darkblue')
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.1)
    plt.show()

if __name__ == '__main__':
    main()
