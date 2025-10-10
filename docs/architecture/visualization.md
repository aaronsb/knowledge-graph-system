
## 9. 3D Visualization Interface

### 9.1 Visualization Architecture

**Tech Stack:**
- React + TypeScript
- force-graph-3d (Three.js wrapper)
- FastAPI backend
- WebSocket for real-time updates (optional)

### 9.2 Frontend Implementation

```typescript
// src/components/Graph3DViewer.tsx
import React, { useEffect, useState, useRef } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';

interface Node {
  id: string;
  label: string;
  sources: string[];
  evidenceCount: number;
  color?: string;
}

interface Link {
  source: string;
  target: string;
  type: string;
  confidence: number;
}

interface GraphData {
  nodes: Node[];
  links: Link[];
}

interface Graph3DViewerProps {
  sessionId: string;
}

export function Graph3DViewer({ sessionId }: Graph3DViewerProps) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(true);
  const fgRef = useRef<any>();

  useEffect(() => {
    // Fetch graph data from API
    fetch(`/api/graph/session/${sessionId}`)
      .then(res => res.json())
      .then(data => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load graph:', err);
        setLoading(false);
      });
  }, [sessionId]);

  const handleNodeClick = (node: Node) => {
    setSelectedNode(node);
    
    // Fetch full concept details
    fetch(`/api/concept/${node.id}`)
      .then(res => res.json())
      .then(details => {
        // Update side panel with details
        setSelectedNode({ ...node, ...details });
      });
  };

  const getNodeColor = (node: Node) => {
    // Color by number of sources
    const sourceCount = node.sources.length;
    if (sourceCount >= 5) return '#ff6b6b';  // Red: appears in many docs
    if (sourceCount >= 3) return '#ffd93d';  // Yellow: medium frequency
    return '#6bcf7f';  // Green: single or few sources
  };

  const getLinkColor = (link: Link) => {
    // Color by relationship type
    const colors: Record<string, string> = {
      'implies': '#4dabf7',
      'contradicts': '#ff6b6b',
      'supports': '#51cf66',
      'part_of': '#845ef7',
      'requires': '#ffd43b'
    };
    return colors[link.type] || '#adb5bd';
  };

  if (loading) {
    return <div className="loading">Loading graph...</div>;
  }

  return (
    <div className="graph-container">
      <div className="graph-3d">
        <ForceGraph3D
          ref={fgRef}
          graphData={graphData}
          
          // Node configuration
          nodeLabel={(node: any) => `${node.label}\n${node.evidenceCount} instances`}
          nodeAutoColorBy="sources"
          nodeColor={getNodeColor}
          nodeVal={(node: any) => Math.sqrt(node.evidenceCount) * 3}
          
          // Link configuration
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          linkLabel={(link: any) => `${link.type} (${link.confidence})`}
          linkColor={getLinkColor}
          linkWidth={(link: any) => link.confidence * 2}
          
          // Interaction
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => {
            document.body.style.cursor = node ? 'pointer' : 'default';
          }}
          
          // Custom rendering
          nodeThreeObject={(node: any) => {
            const sprite = new THREE.Sprite(
              new THREE.SpriteMaterial({
                map: new THREE.CanvasTexture(
                  generateNodeTexture(node.label)
                ),
                transparent: true
              })
            );
            sprite.scale.set(12, 6, 1);
            return sprite;
          }}
          
          // Camera
          backgroundColor="#1a1a1a"
        />
      </div>
      
      {selectedNode && (
        <div className="side-panel">
          <h2>{selectedNode.label}</h2>
          <div className="node-details">
            <h3>Sources:</h3>
            <ul>
              {selectedNode.sources.map(src => (
                <li key={src}>{src}</li>
              ))}
            </ul>
            
            <h3>Evidence ({selectedNode.evidenceCount} instances):</h3>
            {/* Render instances if available */}
            
            <button onClick={() => {
              // Expand graph from this node
              expandFromNode(selectedNode.id);
            }}>
              Expand from this concept
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function to generate node texture
function generateNodeTexture(label: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  
  canvas.width = 256;
  canvas.height = 128;
  
  // Background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
  ctx.fillRect(0, 0, 256, 128);
  
  // Text
  ctx.fillStyle = 'white';
  ctx.font = '20px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  
  // Word wrap
  const words = label.split(' ');
  let line = '';
  let y = 64;
  const lineHeight = 25;
  
  words.forEach(word => {
    const testLine = line + word + ' ';
    const metrics = ctx.measureText(testLine);
    if (metrics.width > 230 && line !== '') {
      ctx.fillText(line, 128, y);
      line = word + ' ';
      y += lineHeight;
    } else {
      line = testLine;
    }
  });
  ctx.fillText(line, 128, y);
  
  return canvas;
}
