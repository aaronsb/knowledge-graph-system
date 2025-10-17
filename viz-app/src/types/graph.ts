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
  fx?: number; // fixed position X
  fy?: number; // fixed position Y
  x?: number; // computed position X
  y?: number; // computed position Y
  vx?: number; // velocity X
  vy?: number; // velocity Y
}

export interface D3Link {
  source: string | D3Node;
  target: string | D3Node;
  type: string;
  value: number; // confidence or weight
  color: string;
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
