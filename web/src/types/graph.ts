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
// Extend API types so the full API payload flows through to the renderer.
// D3 only needs `id` for node identity — everything else is carried along
// so UI components can read from the store without re-fetching.
export interface D3Node extends APIGraphNode {
  id: string;           // alias for concept_id (D3 requires `id`)
  group: string;        // alias for ontology
  grounding?: number;   // alias for grounding_strength
  size: number;         // calculated from degree
  color: string;        // calculated from ontology
  centrality?: number;
  fx?: number; fy?: number; fz?: number;  // fixed positions
  x?: number;  y?: number;  z?: number;   // computed positions
  vx?: number; vy?: number; vz?: number;  // velocities
}

export interface D3Link extends APIGraphLink {
  source: string | D3Node;
  target: string | D3Node;
  type: string;    // alias for relationship_type
  value: number;   // category confidence for rendering
  color: string;   // category color
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
