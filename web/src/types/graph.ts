/**
 * Graph Data Types
 *
 * Types matching the REST API responses from the Knowledge Graph System.
 */

// API Response Types
export interface APIGraphNode {
  concept_id: string;
  label: string;
  ontology: string;
  search_terms: string[];
  instance_count?: number;
  created_at?: string;
  grounding_strength?: number; // -1.0 to +1.0, measures truth convergence
  // Two-dimensional epistemic model (grounding × confidence)
  grounding_display?: string;    // Categorical label from 3×3 matrix (e.g., "Well-supported", "Unclear")
  confidence_level?: string;     // "confident" | "tentative" | "insufficient"
  confidence_score?: number;     // 0.0 to 1.0, nonlinear saturation of data richness
}

export interface APIGraphLink {
  from_id: string;
  to_id: string;
  relationship_type: string;
  confidence?: number;
  category?: string;
}

export interface SubgraphResponse {
  nodes: APIGraphNode[];
  links: APIGraphLink[];
  stats: {
    node_count: number;
    edge_count: number;
  };
}

// D3 Visualization Types
export interface D3Node {
  id: string;
  label: string;
  group: string; // ontology
  size: number; // node size (degree-based)
  color: string;
  grounding?: number; // grounding strength (-1.0 to +1.0)
  centrality?: number; // centrality measure for graph analysis
  fx?: number; // fixed position X
  fy?: number; // fixed position Y
  fz?: number; // fixed position Z (for 3D)
  x?: number; // computed position X
  y?: number; // computed position Y
  z?: number; // computed position Z (for 3D)
  vx?: number; // velocity X
  vy?: number; // velocity Y
  vz?: number; // velocity Z (for 3D)
}

export interface D3Link {
  source: string | D3Node;
  target: string | D3Node;
  type: string;
  value: number; // category confidence or weight
  color: string;
  confidence?: number; // edge confidence score
  category?: string; // relationship category from vocabulary
}

export interface GraphData {
  nodes: D3Node[];
  links: D3Link[];
}

// Three.js 3D Types
export interface Node3D extends D3Node {
  z?: number; // 3D position
  vz?: number; // 3D velocity
  fz?: number; // fixed position Z
}

export interface Link3D extends D3Link {
  source: string | Node3D;
  target: string | Node3D;
}

export interface Graph3DData {
  nodes: Node3D[];
  links: Link3D[];
}
