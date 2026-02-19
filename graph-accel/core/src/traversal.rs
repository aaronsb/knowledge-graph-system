use std::collections::{HashMap, HashSet, VecDeque};

use crate::graph::{Direction, Graph, NodeId, RelTypeId, TraversalDirection};

/// A node found during BFS neighborhood traversal.
#[derive(Debug, Clone)]
pub struct NeighborResult {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub distance: u32,
    /// Relationship types on one shortest path from start to this node.
    pub path_types: Vec<String>,
    /// Traversal direction of each edge on the path (parallel to path_types).
    pub path_directions: Vec<Direction>,
}

/// A single step in a shortest path.
#[derive(Debug, Clone)]
pub struct PathStep {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub rel_type: Option<String>,
    /// Direction the edge was traversed to reach this node. None for the start node.
    pub direction: Option<Direction>,
}

/// Result of a traversal operation.
#[derive(Debug)]
pub struct TraversalResult {
    pub neighbors: Vec<NeighborResult>,
    pub nodes_visited: usize,
}

/// A single edge in an extracted subgraph.
#[derive(Debug, Clone)]
pub struct SubgraphEdge {
    pub from_id: NodeId,
    pub from_label: String,
    pub from_app_id: Option<String>,
    pub to_id: NodeId,
    pub to_label: String,
    pub to_app_id: Option<String>,
    pub rel_type: String,
}

/// Result of subgraph extraction.
#[derive(Debug)]
pub struct SubgraphResult {
    pub node_count: usize,
    pub edges: Vec<SubgraphEdge>,
}

/// Degree information for a single node.
#[derive(Debug, Clone)]
pub struct DegreeResult {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub out_degree: u32,
    pub in_degree: u32,
    pub total_degree: u32,
}

/// Iterate neighbors according to a traversal direction filter and optional
/// minimum confidence threshold.
///
/// Uses boolean flags to avoid Box/dyn dispatch — the compiler optimizes
/// this into direct slice iteration with dead-code elimination.
///
/// Edges with NAN confidence (not loaded) always pass the filter — safe default.
fn iter_neighbors<'a>(
    graph: &'a Graph,
    node: NodeId,
    dir: TraversalDirection,
    min_confidence: Option<f32>,
) -> impl Iterator<Item = (&'a crate::graph::Edge, Direction)> {
    let (use_out, use_inc) = match dir {
        TraversalDirection::Outgoing => (true, false),
        TraversalDirection::Incoming => (false, true),
        TraversalDirection::Both => (true, true),
    };

    let out_iter = graph
        .neighbors_out(node)
        .iter()
        .map(|e| (e, Direction::Outgoing))
        .filter(move |_| use_out);

    let in_iter = graph
        .neighbors_in(node)
        .iter()
        .map(|e| (e, Direction::Incoming))
        .filter(move |_| use_inc);

    out_iter.chain(in_iter).filter(move |(e, _)| {
        match min_confidence {
            None => true,
            Some(min) => !e.has_confidence() || e.confidence >= min,
        }
    })
}

/// BFS neighborhood: find all nodes reachable from `start` within `max_depth` hops.
///
/// `direction` controls which edges to follow: `Both` for undirected,
/// `Outgoing` for forward-only, `Incoming` for reverse-only.
///
/// Uses visited-set pruning — each node is visited at most once, at its
/// minimum distance. Stores parent pointers instead of cloning path Vecs
/// at each node — paths are reconstructed lazily during result collection.
pub fn bfs_neighborhood(
    graph: &Graph,
    start: NodeId,
    max_depth: u32,
    direction: TraversalDirection,
    min_confidence: Option<f32>,
) -> TraversalResult {
    if graph.node(start).is_none() {
        return TraversalResult {
            neighbors: Vec::new(),
            nodes_visited: 0,
        };
    }

    // visited maps node → (distance, parent_node, edge_rel_type, direction)
    // Start node uses itself as parent with dummy rel_type and direction.
    let mut visited: HashMap<NodeId, (u32, NodeId, RelTypeId, Direction)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32)> = VecDeque::new();

    visited.insert(start, (0, start, 0, Direction::Outgoing));
    queue.push_back((start, 0));

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        for (edge, dir) in iter_neighbors(graph, current, direction, min_confidence) {
            if !visited.contains_key(&edge.target) {
                visited.insert(edge.target, (depth + 1, current, edge.rel_type, dir));
                queue.push_back((edge.target, depth + 1));
            }
        }
    }

    let nodes_visited = visited.len();

    // Reconstruct path_types + path_directions lazily by walking parent pointers
    let neighbors: Vec<NeighborResult> = visited
        .iter()
        .filter(|(&id, _)| id != start)
        .map(|(&id, &(distance, _, _, _))| {
            let info = graph.node(id);
            let (path_types, path_directions) = reconstruct_path(graph, &visited, start, id);
            NeighborResult {
                node_id: id,
                label: info.map(|n| n.label.clone()).unwrap_or_default(),
                app_id: info.and_then(|n| n.app_id.clone()),
                distance,
                path_types,
                path_directions,
            }
        })
        .collect();

    TraversalResult {
        neighbors,
        nodes_visited,
    }
}

/// Walk parent pointers from `node` back to `start`, collecting rel_type names and directions.
fn reconstruct_path(
    graph: &Graph,
    visited: &HashMap<NodeId, (u32, NodeId, RelTypeId, Direction)>,
    start: NodeId,
    node: NodeId,
) -> (Vec<String>, Vec<Direction>) {
    let mut types = Vec::new();
    let mut directions = Vec::new();
    let mut current = node;

    while current != start {
        let &(_, parent, rel_type, dir) = &visited[&current];
        if let Some(name) = graph.rel_type_name(rel_type) {
            types.push(name.to_string());
        }
        directions.push(dir);
        current = parent;
    }

    types.reverse();
    directions.reverse();
    (types, directions)
}

/// Shortest path from `start` to `target` using BFS (unweighted).
///
/// `direction` controls which edges to follow: `Both` for undirected,
/// `Outgoing` for forward-only, `Incoming` for reverse-only.
///
/// Returns None if no path exists within `max_hops`, or if either node
/// is not in the graph.
/// Returns the path as a sequence of steps including both endpoints.
pub fn shortest_path(
    graph: &Graph,
    start: NodeId,
    target: NodeId,
    max_hops: u32,
    direction: TraversalDirection,
    min_confidence: Option<f32>,
) -> Option<Vec<PathStep>> {
    if graph.node(start).is_none() || graph.node(target).is_none() {
        return None;
    }

    if start == target {
        let info = graph.node(start);
        return Some(vec![PathStep {
            node_id: start,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: None,
            direction: None,
        }]);
    }

    if max_hops == 0 {
        return None;
    }

    // BFS with parent tracking: node → (parent, rel_type, direction)
    let mut visited: HashMap<NodeId, (NodeId, RelTypeId, Direction)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32)> = VecDeque::new();

    // Sentinel: start node's parent is itself
    visited.insert(start, (start, 0, Direction::Outgoing));
    queue.push_back((start, 0));

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_hops {
            continue;
        }

        for (edge, dir) in iter_neighbors(graph, current, direction, min_confidence) {
            if !visited.contains_key(&edge.target) {
                visited.insert(edge.target, (current, edge.rel_type, dir));

                if edge.target == target {
                    return Some(reconstruct_sp_path(graph, &visited, start, target));
                }

                queue.push_back((edge.target, depth + 1));
            }
        }
    }

    None
}

fn reconstruct_sp_path(
    graph: &Graph,
    visited: &HashMap<NodeId, (NodeId, RelTypeId, Direction)>,
    start: NodeId,
    target: NodeId,
) -> Vec<PathStep> {
    let mut path = Vec::new();
    let mut current = target;

    loop {
        let info = graph.node(current);
        let &(parent, rel_type, dir) = &visited[&current];

        path.push(PathStep {
            node_id: current,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: if current == start {
                None
            } else {
                graph.rel_type_name(rel_type).map(|s| s.to_string())
            },
            direction: if current == start { None } else { Some(dir) },
        });

        if current == start {
            break;
        }
        current = parent;
    }

    path.reverse();
    path
}

/// Find up to `k` shortest simple paths between two nodes using Yen's algorithm.
///
/// Returns paths sorted by hop count (shortest first). Each path is loop-free.
/// Uses BFS as the inner pathfinding step, with node and edge exclusion sets
/// to force alternative routes at each spur node.
///
/// Complexity: O(k * L * (V + E)) where L is the longest path length.
/// For typical use (k=5, L~4, 1K nodes / 400K edges) this runs in microseconds.
pub fn k_shortest_paths(
    graph: &Graph,
    start: NodeId,
    target: NodeId,
    max_hops: u32,
    k: usize,
    direction: TraversalDirection,
    min_confidence: Option<f32>,
) -> Vec<Vec<PathStep>> {
    if k == 0 {
        return Vec::new();
    }

    // A[0]: first shortest path via standard BFS
    let first = match shortest_path(graph, start, target, max_hops, direction, min_confidence) {
        Some(path) => path,
        None => return Vec::new(),
    };

    let mut result: Vec<Vec<PathStep>> = vec![first];
    // Candidate pool: paths found but not yet selected, sorted by length when picking
    let mut candidates: Vec<Vec<PathStep>> = Vec::new();

    for ki in 1..k {
        let prev_path = &result[ki - 1];

        // For each spur node in the previous path (skip the last — no edge to deviate from)
        for spur_idx in 0..prev_path.len().saturating_sub(1) {
            let spur_node = prev_path[spur_idx].node_id;

            // Root path: start → spur_node (spur_idx hops)
            let root_path: Vec<PathStep> = prev_path[..=spur_idx].to_vec();
            let root_ids: Vec<NodeId> = root_path.iter().map(|s| s.node_id).collect();

            // Exclude edges leaving the spur node that are used by paths sharing this root
            let mut excluded_edges: HashSet<(NodeId, NodeId)> = HashSet::new();
            for path in &result {
                if path.len() > spur_idx
                    && path[..=spur_idx]
                        .iter()
                        .map(|s| s.node_id)
                        .eq(root_ids.iter().copied())
                {
                    excluded_edges.insert((
                        path[spur_idx].node_id,
                        path[spur_idx + 1].node_id,
                    ));
                }
            }

            // Exclude root-path nodes (except the spur node) to force simple paths
            let excluded_nodes: HashSet<NodeId> =
                root_ids[..spur_idx].iter().copied().collect();

            // Remaining hop budget for the spur path
            let remaining_hops = max_hops.saturating_sub(spur_idx as u32);
            if remaining_hops == 0 {
                continue;
            }

            // Find spur path: spur_node → target avoiding excluded nodes/edges
            if let Some(spur_path) = shortest_path_excluding(
                graph,
                spur_node,
                target,
                remaining_hops,
                direction,
                min_confidence,
                &excluded_nodes,
                &excluded_edges,
            ) {
                // Combine root + spur (skip spur_node duplicate)
                let mut candidate = root_path.clone();
                candidate.extend(spur_path.into_iter().skip(1));

                // Deduplicate by node sequence
                let candidate_ids: Vec<NodeId> =
                    candidate.iter().map(|s| s.node_id).collect();
                let is_dup = result
                    .iter()
                    .chain(candidates.iter())
                    .any(|p| {
                        p.len() == candidate_ids.len()
                            && p.iter()
                                .map(|s| s.node_id)
                                .eq(candidate_ids.iter().copied())
                    });

                if !is_dup {
                    candidates.push(candidate);
                }
            }
        }

        if candidates.is_empty() {
            break;
        }

        // Pick the shortest candidate (fewest hops)
        candidates.sort_by_key(|p| p.len());
        result.push(candidates.remove(0));
    }

    result
}

/// BFS shortest path with node and edge exclusion (inner loop for Yen's algorithm).
///
/// `excluded_nodes`: nodes that cannot appear on the path (except start/target).
/// `excluded_edges`: (from, to) pairs that cannot be traversed.
fn shortest_path_excluding(
    graph: &Graph,
    start: NodeId,
    target: NodeId,
    max_hops: u32,
    direction: TraversalDirection,
    min_confidence: Option<f32>,
    excluded_nodes: &HashSet<NodeId>,
    excluded_edges: &HashSet<(NodeId, NodeId)>,
) -> Option<Vec<PathStep>> {
    if graph.node(start).is_none() || graph.node(target).is_none() {
        return None;
    }
    if excluded_nodes.contains(&start) || excluded_nodes.contains(&target) {
        return None;
    }

    if start == target {
        let info = graph.node(start);
        return Some(vec![PathStep {
            node_id: start,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: None,
            direction: None,
        }]);
    }

    if max_hops == 0 {
        return None;
    }

    let mut visited: HashMap<NodeId, (NodeId, RelTypeId, Direction)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32)> = VecDeque::new();

    visited.insert(start, (start, 0, Direction::Outgoing));
    queue.push_back((start, 0));

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_hops {
            continue;
        }

        for (edge, dir) in iter_neighbors(graph, current, direction, min_confidence) {
            if excluded_nodes.contains(&edge.target) {
                continue;
            }
            if excluded_edges.contains(&(current, edge.target)) {
                continue;
            }

            if !visited.contains_key(&edge.target) {
                visited.insert(edge.target, (current, edge.rel_type, dir));

                if edge.target == target {
                    return Some(reconstruct_sp_path(graph, &visited, start, target));
                }

                queue.push_back((edge.target, depth + 1));
            }
        }
    }

    None
}

/// Extract the subgraph reachable from `start` within `max_depth` hops.
///
/// Phase 1: BFS to discover reachable nodes (respecting `direction` filter).
/// Phase 2: For each discovered node, emit outgoing edges where the target
/// is also in the discovered set. Uses outgoing-only iteration to avoid
/// emitting each edge twice.
pub fn extract_subgraph(
    graph: &Graph,
    start: NodeId,
    max_depth: u32,
    direction: TraversalDirection,
    min_confidence: Option<f32>,
) -> SubgraphResult {
    use std::collections::HashSet;

    if graph.node(start).is_none() {
        return SubgraphResult {
            node_count: 0,
            edges: Vec::new(),
        };
    }

    // Phase 1: BFS to discover reachable node set
    let bfs = bfs_neighborhood(graph, start, max_depth, direction, min_confidence);
    let mut node_set: HashSet<NodeId> = HashSet::with_capacity(bfs.nodes_visited);
    node_set.insert(start);
    for nr in &bfs.neighbors {
        node_set.insert(nr.node_id);
    }

    // Phase 2: collect edges between discovered nodes
    // Only iterate outgoing edges to avoid duplicates
    let mut edges = Vec::new();
    for &node_id in &node_set {
        for edge in graph.neighbors_out(node_id) {
            // Apply confidence filter to emitted edges
            if let Some(min) = min_confidence {
                if edge.has_confidence() && edge.confidence < min {
                    continue;
                }
            }
            if node_set.contains(&edge.target) {
                let from_info = graph.node(node_id);
                let to_info = graph.node(edge.target);
                edges.push(SubgraphEdge {
                    from_id: node_id,
                    from_label: from_info.map(|n| n.label.clone()).unwrap_or_default(),
                    from_app_id: from_info.and_then(|n| n.app_id.clone()),
                    to_id: edge.target,
                    to_label: to_info.map(|n| n.label.clone()).unwrap_or_default(),
                    to_app_id: to_info.and_then(|n| n.app_id.clone()),
                    rel_type: graph
                        .rel_type_name(edge.rel_type)
                        .unwrap_or("UNKNOWN")
                        .to_string(),
                });
            }
        }
    }

    SubgraphResult {
        node_count: node_set.len(),
        edges,
    }
}

/// Return nodes ranked by degree (total connections).
///
/// If `top_n` is 0, returns all nodes. Otherwise returns the top N by
/// total degree (descending). Ties are broken by node ID (ascending).
pub fn degree_centrality(graph: &Graph, top_n: usize) -> Vec<DegreeResult> {
    let mut results: Vec<DegreeResult> = graph
        .nodes_iter()
        .map(|(&id, info)| {
            let out_degree = graph.neighbors_out(id).len() as u32;
            let in_degree = graph.neighbors_in(id).len() as u32;
            DegreeResult {
                node_id: id,
                label: info.label.clone(),
                app_id: info.app_id.clone(),
                out_degree,
                in_degree,
                total_degree: out_degree + in_degree,
            }
        })
        .collect();

    // Sort by total degree descending, then by node_id ascending for stability
    results.sort_by(|a, b| {
        b.total_degree
            .cmp(&a.total_degree)
            .then(a.node_id.cmp(&b.node_id))
    });

    if top_n > 0 && top_n < results.len() {
        results.truncate(top_n);
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::{Edge, EdgeRecord, Graph, TraversalDirection};

    fn edge(from: u64, to: u64, rel: &str) -> EdgeRecord {
        EdgeRecord {
            from_id: from,
            to_id: to,
            rel_type: rel.to_string(),
            from_label: "Node".to_string(),
            to_label: "Node".to_string(),
            from_app_id: None,
            to_app_id: None,
            confidence: Edge::NO_CONFIDENCE,
        }
    }

    fn make_chain(n: u64) -> Graph {
        let mut g = Graph::new();
        g.load_edges((0..n - 1).map(|i| edge(i, i + 1, "NEXT")));
        g
    }

    fn make_star(center: u64, leaves: u64) -> Graph {
        let mut g = Graph::new();
        g.load_edges((1..=leaves).map(|i| EdgeRecord {
            from_id: center,
            to_id: i,
            rel_type: "HAS".to_string(),
            from_label: "Hub".to_string(),
            to_label: "Leaf".to_string(),
            from_app_id: None,
            to_app_id: None,
            confidence: Edge::NO_CONFIDENCE,
        }));
        g
    }

    fn make_cycle(n: u64) -> Graph {
        let mut g = Graph::new();
        g.load_edges((0..n).map(|i| edge(i, (i + 1) % n, "NEXT")));
        g
    }

    // --- BFS tests ---

    #[test]
    fn test_bfs_chain() {
        let g = make_chain(6);
        let result = bfs_neighborhood(&g, 0, 10, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 5);
        let node5 = result.neighbors.iter().find(|n| n.node_id == 5).unwrap();
        assert_eq!(node5.distance, 5);
    }

    #[test]
    fn test_bfs_chain_depth_limited() {
        let g = make_chain(10);
        let result = bfs_neighborhood(&g, 0, 3, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 3);
        assert!(result.neighbors.iter().all(|n| n.distance <= 3));
    }

    #[test]
    fn test_bfs_star() {
        let g = make_star(0, 100);
        let result = bfs_neighborhood(&g, 0, 1, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 100);
        assert!(result.neighbors.iter().all(|n| n.distance == 1));
    }

    #[test]
    fn test_bfs_cycle_no_infinite_loop() {
        let g = make_cycle(5);
        let result = bfs_neighborhood(&g, 0, 100, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 4);
    }

    #[test]
    fn test_bfs_undirected() {
        let g = make_chain(2);
        let result = bfs_neighborhood(&g, 1, 1, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 0);
    }

    #[test]
    fn test_bfs_empty_graph() {
        let g = Graph::new();
        let result = bfs_neighborhood(&g, 0, 10, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 0);
    }

    #[test]
    fn test_bfs_start_not_in_graph() {
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 999, 10, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 0);
    }

    #[test]
    fn test_bfs_depth_zero() {
        let g = make_chain(5);
        let result = bfs_neighborhood(&g, 0, 0, TraversalDirection::Both, None);
        // Depth 0 = only start node, no neighbors
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 1);
    }

    #[test]
    fn test_bfs_self_loop() {
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 0, "SELF")]);
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);
        // Self-loop: node 0 is already visited as start, so no neighbors
        assert_eq!(result.neighbors.len(), 0);
    }

    #[test]
    fn test_bfs_parallel_edges() {
        let mut g = Graph::new();
        g.load_edges(vec![
            edge(0, 1, "IMPLIES"),
            edge(0, 1, "SUPPORTS"),
            edge(0, 1, "CONTRADICTS"),
        ]);
        let result = bfs_neighborhood(&g, 0, 1, TraversalDirection::Both, None);
        // Should find node 1 once (at distance 1) despite 3 parallel edges
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].distance, 1);
    }

    // --- Shortest path tests ---

    #[test]
    fn test_shortest_path_chain() {
        let g = make_chain(6);
        let path = shortest_path(&g, 0, 5, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 6);
        assert_eq!(path[0].node_id, 0);
        assert_eq!(path[5].node_id, 5);
        assert!(path[0].rel_type.is_none());
        assert_eq!(path[1].rel_type.as_deref(), Some("NEXT"));
    }

    #[test]
    fn test_shortest_path_self() {
        let g = make_chain(3);
        let path = shortest_path(&g, 1, 1, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 1);
        assert_eq!(path[0].node_id, 1);
    }

    #[test]
    fn test_shortest_path_no_path() {
        let mut g = Graph::new();
        g.add_node(0, "A".into(), None);
        g.add_node(1, "B".into(), None);
        let path = shortest_path(&g, 0, 1, 10, TraversalDirection::Both, None);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_max_hops() {
        let g = make_chain(10);
        let path = shortest_path(&g, 0, 9, 5, TraversalDirection::Both, None);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_max_hops_zero() {
        let g = make_chain(3);
        // max_hops=0 means no traversal allowed
        let path = shortest_path(&g, 0, 1, 0, TraversalDirection::Both, None);
        assert!(path.is_none());
        // But start==target should still work even with max_hops=0
        let path = shortest_path(&g, 0, 0, 0, TraversalDirection::Both, None);
        assert!(path.is_some());
        assert_eq!(path.unwrap().len(), 1);
    }

    #[test]
    fn test_shortest_path_cycle() {
        let g = make_cycle(6);
        let path = shortest_path(&g, 0, 3, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 4);
    }

    #[test]
    fn test_shortest_path_start_not_in_graph() {
        let g = make_chain(3);
        assert!(shortest_path(&g, 999, 0, 10, TraversalDirection::Both, None).is_none());
    }

    #[test]
    fn test_shortest_path_target_not_in_graph() {
        let g = make_chain(3);
        assert!(shortest_path(&g, 0, 999, 10, TraversalDirection::Both, None).is_none());
    }

    // --- Path type recording ---

    #[test]
    fn test_path_types_recorded() {
        let mut g = Graph::new();
        let implies = g.intern_rel_type("IMPLIES");
        let supports = g.intern_rel_type("SUPPORTS");
        g.add_node(0, "A".into(), None);
        g.add_node(1, "B".into(), None);
        g.add_node(2, "C".into(), None);
        g.add_edge(0, 1, implies, Edge::NO_CONFIDENCE);
        g.add_edge(1, 2, supports, Edge::NO_CONFIDENCE);

        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);
        let node2 = result.neighbors.iter().find(|n| n.node_id == 2).unwrap();
        assert_eq!(node2.path_types, vec!["IMPLIES", "SUPPORTS"]);
    }

    // --- Graph structure tests ---

    #[test]
    fn test_app_id_resolution() {
        let mut g = Graph::new();
        g.add_node(42, "Concept".into(), Some("c_abc123".into()));
        assert_eq!(g.resolve_app_id("c_abc123"), Some(42));
        assert_eq!(g.resolve_app_id("nonexistent"), None);
    }

    #[test]
    fn test_graph_counts() {
        let g = make_star(0, 50);
        assert_eq!(g.node_count(), 51);
        assert_eq!(g.edge_count(), 50);
    }

    #[test]
    fn test_rel_type_name_valid() {
        let mut g = Graph::new();
        let id = g.intern_rel_type("IMPLIES");
        assert_eq!(g.rel_type_name(id), Some("IMPLIES"));
    }

    #[test]
    fn test_rel_type_name_invalid() {
        let g = Graph::new();
        assert_eq!(g.rel_type_name(999), None);
    }

    #[test]
    #[should_panic(expected = "exceeded maximum")]
    fn test_rel_type_overflow() {
        let mut g = Graph::new();
        for i in 0..=u16::MAX as u32 {
            g.intern_rel_type(&format!("REL_{}", i));
        }
    }

    #[test]
    fn test_edge_record_loading() {
        let mut g = Graph::new();
        g.load_edges(vec![EdgeRecord {
            from_id: 1,
            to_id: 2,
            rel_type: "IMPLIES".to_string(),
            from_label: "Concept".to_string(),
            to_label: "Concept".to_string(),
            from_app_id: Some("c_1".to_string()),
            to_app_id: Some("c_2".to_string()),
            confidence: Edge::NO_CONFIDENCE,
        }]);
        assert_eq!(g.node_count(), 2);
        assert_eq!(g.edge_count(), 1);
        assert_eq!(g.resolve_app_id("c_1"), Some(1));
        assert_eq!(g.resolve_app_id("c_2"), Some(2));
    }

    #[test]
    fn test_memory_usage_nonzero() {
        let g = make_star(0, 100);
        assert!(g.memory_usage() > 0);
    }

    // --- Direction tracking tests ---

    #[test]
    fn test_bfs_direction_outgoing() {
        // Chain 0→1→2, BFS from 0: both edges followed in their stored direction
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);
        let node2 = result.neighbors.iter().find(|n| n.node_id == 2).unwrap();
        assert_eq!(node2.path_directions, vec![Direction::Outgoing, Direction::Outgoing]);
    }

    #[test]
    fn test_bfs_direction_incoming() {
        // Chain 0→1→2, BFS from 2: both edges followed against their stored direction
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 2, 5, TraversalDirection::Both, None);
        let node0 = result.neighbors.iter().find(|n| n.node_id == 0).unwrap();
        assert_eq!(node0.path_directions, vec![Direction::Incoming, Direction::Incoming]);
    }

    #[test]
    fn test_bfs_direction_mixed() {
        // 0→1←2: from node 0, reach 1 via outgoing, reach 2 via 1's incoming list
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "A"), edge(2, 1, "B")]);
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);

        let node1 = result.neighbors.iter().find(|n| n.node_id == 1).unwrap();
        assert_eq!(node1.path_directions, vec![Direction::Outgoing]);

        let node2 = result.neighbors.iter().find(|n| n.node_id == 2).unwrap();
        assert_eq!(node2.distance, 2);
        // 0→1 (outgoing), then 1←2 means 2→1 stored, so from 1's perspective
        // node 2 is in 1's incoming list (2→1), traversed as Incoming from 1 to reach 2
        assert_eq!(node2.path_directions.len(), 2);
        assert_eq!(node2.path_directions[0], Direction::Outgoing); // 0→1
        assert_eq!(node2.path_directions[1], Direction::Incoming); // 1←2 (followed backward)
    }

    #[test]
    fn test_bfs_direction_parallel_to_path_types() {
        // Verify path_types and path_directions are always the same length
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "IMPLIES"), edge(1, 2, "SUPPORTS")]);
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);
        for n in &result.neighbors {
            assert_eq!(
                n.path_types.len(),
                n.path_directions.len(),
                "path_types and path_directions must be parallel for node {}",
                n.node_id
            );
        }
    }

    #[test]
    fn test_path_direction_forward() {
        // Chain 0→1→2, path from 0 to 2: both outgoing
        let g = make_chain(3);
        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 3);
        assert_eq!(path[0].direction, None); // start node
        assert_eq!(path[1].direction, Some(Direction::Outgoing));
        assert_eq!(path[2].direction, Some(Direction::Outgoing));
    }

    #[test]
    fn test_path_direction_reverse() {
        // Chain 0→1→2, path from 2 to 0: both incoming
        let g = make_chain(3);
        let path = shortest_path(&g, 2, 0, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 3);
        assert_eq!(path[0].direction, None); // start node
        assert_eq!(path[1].direction, Some(Direction::Incoming));
        assert_eq!(path[2].direction, Some(Direction::Incoming));
    }

    #[test]
    fn test_path_direction_mixed() {
        // 0→1←2, path from 0 to 2: first outgoing, second incoming
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "A"), edge(2, 1, "B")]);
        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 3);
        assert_eq!(path[0].direction, None);
        assert_eq!(path[1].direction, Some(Direction::Outgoing));   // 0→1
        assert_eq!(path[2].direction, Some(Direction::Incoming));   // 1←2
    }

    #[test]
    fn test_path_direction_self() {
        // start == target: single step, no direction
        let g = make_chain(3);
        let path = shortest_path(&g, 1, 1, 10, TraversalDirection::Both, None).unwrap();
        assert_eq!(path.len(), 1);
        assert_eq!(path[0].direction, None);
    }

    #[test]
    fn test_direction_symmetric() {
        // Edge 0→1: from 0's perspective it's Outgoing, from 1's perspective it's Incoming
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "SUPPORTS")]);

        let from_0 = bfs_neighborhood(&g, 0, 1, TraversalDirection::Both, None);
        let n1 = from_0.neighbors.iter().find(|n| n.node_id == 1).unwrap();
        assert_eq!(n1.path_directions, vec![Direction::Outgoing]);

        let from_1 = bfs_neighborhood(&g, 1, 1, TraversalDirection::Both, None);
        let n0 = from_1.neighbors.iter().find(|n| n.node_id == 0).unwrap();
        assert_eq!(n0.path_directions, vec![Direction::Incoming]);
    }

    // --- Directed-only traversal filter tests ---

    #[test]
    fn test_bfs_outgoing_only() {
        // Chain 0→1→2: outgoing-only from 0 finds 1 and 2
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Outgoing, None);
        assert_eq!(result.neighbors.len(), 2);
        assert!(result.neighbors.iter().any(|n| n.node_id == 1));
        assert!(result.neighbors.iter().any(|n| n.node_id == 2));

        // From 2, outgoing-only finds nothing (no outgoing edges from 2)
        let result = bfs_neighborhood(&g, 2, 5, TraversalDirection::Outgoing, None);
        assert_eq!(result.neighbors.len(), 0);
    }

    #[test]
    fn test_bfs_incoming_only() {
        // Chain 0→1→2: incoming-only from 2 finds 1 and 0
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 2, 5, TraversalDirection::Incoming, None);
        assert_eq!(result.neighbors.len(), 2);
        assert!(result.neighbors.iter().any(|n| n.node_id == 0));
        assert!(result.neighbors.iter().any(|n| n.node_id == 1));

        // From 0, incoming-only finds nothing (no incoming edges to 0)
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Incoming, None);
        assert_eq!(result.neighbors.len(), 0);
    }

    #[test]
    fn test_path_directed_outgoing() {
        // Chain 0→1→2: outgoing path 0→2 works, reverse 2→0 returns None
        let g = make_chain(3);
        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Outgoing, None);
        assert!(path.is_some());
        assert_eq!(path.unwrap().len(), 3);

        let path = shortest_path(&g, 2, 0, 10, TraversalDirection::Outgoing, None);
        assert!(path.is_none());
    }

    #[test]
    fn test_path_directed_incoming() {
        // Chain 0→1→2: incoming path 2→0 works, forward 0→2 returns None
        let g = make_chain(3);
        let path = shortest_path(&g, 2, 0, 10, TraversalDirection::Incoming, None);
        assert!(path.is_some());
        assert_eq!(path.unwrap().len(), 3);

        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Incoming, None);
        assert!(path.is_none());
    }

    #[test]
    fn test_star_directed() {
        // Hub 0 with outgoing edges to 50 leaves
        let g = make_star(0, 50);

        // Outgoing from hub: finds all 50 leaves
        let result = bfs_neighborhood(&g, 0, 1, TraversalDirection::Outgoing, None);
        assert_eq!(result.neighbors.len(), 50);

        // Incoming from hub: finds nothing (all edges point away from hub)
        let result = bfs_neighborhood(&g, 0, 1, TraversalDirection::Incoming, None);
        assert_eq!(result.neighbors.len(), 0);

        // Outgoing from leaf: finds nothing (leaves have no outgoing edges)
        let result = bfs_neighborhood(&g, 1, 1, TraversalDirection::Outgoing, None);
        assert_eq!(result.neighbors.len(), 0);

        // Incoming from leaf: finds hub
        let result = bfs_neighborhood(&g, 1, 1, TraversalDirection::Incoming, None);
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 0);
    }

    #[test]
    fn test_directed_both_matches_undirected() {
        // Both should give same results as the undirected tests
        let g = make_chain(6);
        let both = bfs_neighborhood(&g, 0, 10, TraversalDirection::Both, None);
        assert_eq!(both.neighbors.len(), 5);

        // Outgoing + Incoming from same start should cover all Both neighbors
        let out = bfs_neighborhood(&g, 0, 10, TraversalDirection::Outgoing, None);
        let inc = bfs_neighborhood(&g, 0, 10, TraversalDirection::Incoming, None);
        let mut union: Vec<NodeId> = out
            .neighbors
            .iter()
            .chain(inc.neighbors.iter())
            .map(|n| n.node_id)
            .collect();
        union.sort();
        union.dedup();
        let mut both_ids: Vec<NodeId> = both.neighbors.iter().map(|n| n.node_id).collect();
        both_ids.sort();
        assert_eq!(union, both_ids);
    }

    // --- Degree centrality tests ---

    #[test]
    fn test_degree_star() {
        // Hub 0 with 50 outgoing edges to leaves
        let g = make_star(0, 50);
        let results = degree_centrality(&g, 0);

        let hub = results.iter().find(|r| r.node_id == 0).unwrap();
        assert_eq!(hub.out_degree, 50);
        assert_eq!(hub.in_degree, 0);
        assert_eq!(hub.total_degree, 50);

        // Each leaf has in_degree=1 (from hub), out_degree=0
        let leaf = results.iter().find(|r| r.node_id == 1).unwrap();
        assert_eq!(leaf.out_degree, 0);
        assert_eq!(leaf.in_degree, 1);
        assert_eq!(leaf.total_degree, 1);
    }

    #[test]
    fn test_degree_chain() {
        // Chain 0→1→2→3→4
        let g = make_chain(5);
        let results = degree_centrality(&g, 0);

        // Endpoints: degree 1
        let node0 = results.iter().find(|r| r.node_id == 0).unwrap();
        assert_eq!(node0.out_degree, 1);
        assert_eq!(node0.in_degree, 0);
        assert_eq!(node0.total_degree, 1);

        let node4 = results.iter().find(|r| r.node_id == 4).unwrap();
        assert_eq!(node4.out_degree, 0);
        assert_eq!(node4.in_degree, 1);
        assert_eq!(node4.total_degree, 1);

        // Middle nodes: out=1, in=1, total=2
        let node2 = results.iter().find(|r| r.node_id == 2).unwrap();
        assert_eq!(node2.out_degree, 1);
        assert_eq!(node2.in_degree, 1);
        assert_eq!(node2.total_degree, 2);
    }

    #[test]
    fn test_degree_top_n() {
        // Star with hub having highest degree
        let g = make_star(0, 50);
        let results = degree_centrality(&g, 5);
        assert_eq!(results.len(), 5);
        // Hub should be first
        assert_eq!(results[0].node_id, 0);
        assert_eq!(results[0].total_degree, 50);
    }

    #[test]
    fn test_degree_sorted() {
        let g = make_star(0, 50);
        let results = degree_centrality(&g, 0);
        // Must be sorted descending by total_degree
        for w in results.windows(2) {
            assert!(
                w[0].total_degree >= w[1].total_degree,
                "not sorted: {} >= {} failed",
                w[0].total_degree,
                w[1].total_degree
            );
        }
    }

    #[test]
    fn test_degree_empty() {
        let g = Graph::new();
        let results = degree_centrality(&g, 10);
        assert!(results.is_empty());
    }

    // --- Subgraph extraction tests ---

    #[test]
    fn test_subgraph_chain() {
        // Chain 0→1→2→3→4, depth 2 from 0: nodes 0,1,2 — edges 0→1, 1→2
        let g = make_chain(5);
        let sub = extract_subgraph(&g, 0, 2, TraversalDirection::Both, None);
        assert_eq!(sub.node_count, 3); // 0, 1, 2
        assert_eq!(sub.edges.len(), 2); // 0→1, 1→2
    }

    #[test]
    fn test_subgraph_star() {
        // Hub 0 → 10 leaves, depth 1: 11 nodes, 10 edges
        let g = make_star(0, 10);
        let sub = extract_subgraph(&g, 0, 1, TraversalDirection::Both, None);
        assert_eq!(sub.node_count, 11);
        assert_eq!(sub.edges.len(), 10);
    }

    #[test]
    fn test_subgraph_directed() {
        // Chain 0→1→2→3→4, outgoing from 2: reaches 3, 4
        let g = make_chain(5);
        let sub = extract_subgraph(&g, 2, 5, TraversalDirection::Outgoing, None);
        assert_eq!(sub.node_count, 3); // 2, 3, 4
        assert_eq!(sub.edges.len(), 2); // 2→3, 3→4
    }

    #[test]
    fn test_subgraph_cycle() {
        // Cycle 0→1→2→3→4→0: all 5 nodes, exactly 5 edges (no duplicates)
        let g = make_cycle(5);
        let sub = extract_subgraph(&g, 0, 10, TraversalDirection::Both, None);
        assert_eq!(sub.node_count, 5);
        assert_eq!(sub.edges.len(), 5);
    }

    #[test]
    fn test_subgraph_rel_types() {
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "IMPLIES"), edge(1, 2, "SUPPORTS")]);
        let sub = extract_subgraph(&g, 0, 5, TraversalDirection::Both, None);
        let types: Vec<&str> = sub.edges.iter().map(|e| e.rel_type.as_str()).collect();
        assert!(types.contains(&"IMPLIES"));
        assert!(types.contains(&"SUPPORTS"));
    }

    #[test]
    fn test_subgraph_empty() {
        let g = make_chain(5);
        // Node 999 doesn't exist — should return empty
        let sub = extract_subgraph(&g, 999, 5, TraversalDirection::Both, None);
        assert_eq!(sub.node_count, 0);
        assert!(sub.edges.is_empty());
    }

    // --- Confidence filtering tests ---

    fn edge_conf(from: u64, to: u64, rel: &str, conf: f32) -> EdgeRecord {
        EdgeRecord {
            from_id: from,
            to_id: to,
            rel_type: rel.to_string(),
            from_label: "Node".to_string(),
            to_label: "Node".to_string(),
            from_app_id: None,
            to_app_id: None,
            confidence: conf,
        }
    }

    #[test]
    fn test_bfs_confidence_filter() {
        // 0→1 (high confidence), 1→2 (low confidence)
        let mut g = Graph::new();
        g.load_edges(vec![
            edge_conf(0, 1, "A", 0.9),
            edge_conf(1, 2, "B", 0.2),
        ]);

        // No filter: finds both
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 2);

        // Filter at 0.5: only finds node 1 (edge to 2 blocked)
        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, Some(0.5));
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 1);
    }

    #[test]
    fn test_confidence_nan_passes_filter() {
        // NAN confidence (not loaded) should pass any threshold
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "A")]); // edge() uses NO_CONFIDENCE = NAN

        let result = bfs_neighborhood(&g, 0, 5, TraversalDirection::Both, Some(0.99));
        assert_eq!(result.neighbors.len(), 1);
    }

    #[test]
    fn test_path_confidence_blocks() {
        // 0→1 (high), 1→2 (low): path 0→2 blocked at confidence 0.5
        let mut g = Graph::new();
        g.load_edges(vec![
            edge_conf(0, 1, "A", 0.9),
            edge_conf(1, 2, "B", 0.2),
        ]);

        // No filter: path exists
        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Both, None);
        assert!(path.is_some());

        // With filter: path blocked
        let path = shortest_path(&g, 0, 2, 10, TraversalDirection::Both, Some(0.5));
        assert!(path.is_none());
    }

    #[test]
    fn test_subgraph_confidence_filter() {
        // 0→1 (0.9), 1→2 (0.2), 0→3 (0.8)
        let mut g = Graph::new();
        g.load_edges(vec![
            edge_conf(0, 1, "A", 0.9),
            edge_conf(1, 2, "B", 0.2),
            edge_conf(0, 3, "C", 0.8),
        ]);

        // No filter: 4 nodes, 3 edges
        let sub = extract_subgraph(&g, 0, 5, TraversalDirection::Both, None);
        assert_eq!(sub.node_count, 4);
        assert_eq!(sub.edges.len(), 3);

        // Filter at 0.5: BFS can't reach node 2 (edge 1→2 is 0.2), so 3 nodes, 2 edges
        let sub = extract_subgraph(&g, 0, 5, TraversalDirection::Both, Some(0.5));
        assert_eq!(sub.node_count, 3); // 0, 1, 3
        assert_eq!(sub.edges.len(), 2); // 0→1, 0→3
    }

    // --- k-shortest-paths (Yen's algorithm) tests ---

    /// Diamond graph: two distinct 2-hop paths from 0 to 3.
    ///   0→1→3  (via IMPLIES)
    ///   0→2→3  (via SUPPORTS)
    fn make_diamond() -> Graph {
        let mut g = Graph::new();
        g.load_edges(vec![
            edge(0, 1, "IMPLIES"),
            edge(1, 3, "IMPLIES"),
            edge(0, 2, "SUPPORTS"),
            edge(2, 3, "SUPPORTS"),
        ]);
        g
    }

    /// Grid-like graph with multiple paths of different lengths.
    ///   0→1→2→5
    ///   0→3→4→5
    ///   0→1→4→5  (cross-edge 1→4)
    ///   0→3→2→5  (cross-edge 3→2)
    fn make_grid() -> Graph {
        let mut g = Graph::new();
        g.load_edges(vec![
            edge(0, 1, "A"),
            edge(1, 2, "A"),
            edge(2, 5, "A"),
            edge(0, 3, "B"),
            edge(3, 4, "B"),
            edge(4, 5, "B"),
            edge(1, 4, "C"), // cross-edge
            edge(3, 2, "C"), // cross-edge
        ]);
        g
    }

    #[test]
    fn test_ksp_single_path_same_as_shortest() {
        let g = make_chain(5); // 0→1→2→3→4
        let paths = k_shortest_paths(&g, 0, 4, 10, 1, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 1);
        let ids: Vec<NodeId> = paths[0].iter().map(|s| s.node_id).collect();
        assert_eq!(ids, vec![0, 1, 2, 3, 4]);
    }

    #[test]
    fn test_ksp_diamond_two_paths() {
        let g = make_diamond();
        let paths = k_shortest_paths(&g, 0, 3, 10, 5, TraversalDirection::Both, None);

        // Should find exactly 2 paths (both 2 hops)
        assert_eq!(paths.len(), 2);

        let path_ids: Vec<Vec<NodeId>> = paths
            .iter()
            .map(|p| p.iter().map(|s| s.node_id).collect())
            .collect();

        // Both paths should start at 0 and end at 3
        for ids in &path_ids {
            assert_eq!(ids[0], 0);
            assert_eq!(*ids.last().unwrap(), 3);
            assert_eq!(ids.len(), 3); // 2 hops = 3 steps
        }

        // Should find both routes: via 1 and via 2
        let middle_nodes: Vec<NodeId> = path_ids.iter().map(|p| p[1]).collect();
        assert!(middle_nodes.contains(&1));
        assert!(middle_nodes.contains(&2));
    }

    #[test]
    fn test_ksp_grid_multiple_paths() {
        let g = make_grid();
        let paths = k_shortest_paths(&g, 0, 5, 10, 10, TraversalDirection::Both, None);

        // Grid has at least 4 distinct 3-hop paths from 0 to 5,
        // plus longer paths via cross-edges with undirected traversal
        assert!(paths.len() >= 4, "expected at least 4 paths, got {}", paths.len());

        // All paths start at 0, end at 5
        for path in &paths {
            assert_eq!(path.first().unwrap().node_id, 0);
            assert_eq!(path.last().unwrap().node_id, 5);
        }

        // Sorted by length (shortest first)
        for w in paths.windows(2) {
            assert!(w[0].len() <= w[1].len());
        }

        // All paths are distinct (no duplicate node sequences)
        let path_ids: Vec<Vec<NodeId>> = paths
            .iter()
            .map(|p| p.iter().map(|s| s.node_id).collect())
            .collect();
        for i in 0..path_ids.len() {
            for j in (i + 1)..path_ids.len() {
                assert_ne!(path_ids[i], path_ids[j], "duplicate paths at {} and {}", i, j);
            }
        }
    }

    #[test]
    fn test_ksp_no_path() {
        // Disconnected graph: 0→1, 2→3 — no path from 0 to 3
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 1, "A"), edge(2, 3, "A")]);

        let paths = k_shortest_paths(&g, 0, 3, 10, 5, TraversalDirection::Both, None);
        assert!(paths.is_empty());
    }

    #[test]
    fn test_ksp_k_zero() {
        let g = make_diamond();
        let paths = k_shortest_paths(&g, 0, 3, 10, 0, TraversalDirection::Both, None);
        assert!(paths.is_empty());
    }

    #[test]
    fn test_ksp_k_exceeds_available() {
        // Chain has exactly 1 simple path
        let g = make_chain(4); // 0→1→2→3
        let paths = k_shortest_paths(&g, 0, 3, 10, 10, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 1);
    }

    #[test]
    fn test_ksp_same_node() {
        let g = make_chain(3);
        let paths = k_shortest_paths(&g, 1, 1, 10, 5, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 1);
        assert_eq!(paths[0].len(), 1);
        assert_eq!(paths[0][0].node_id, 1);
    }

    #[test]
    fn test_ksp_max_hops_limits() {
        let g = make_diamond();
        // max_hops=1: can't reach node 3 (needs 2 hops)
        let paths = k_shortest_paths(&g, 0, 3, 1, 5, TraversalDirection::Both, None);
        assert!(paths.is_empty());

        // max_hops=2: both 2-hop paths found
        let paths = k_shortest_paths(&g, 0, 3, 2, 5, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 2);
    }

    #[test]
    fn test_ksp_directed_outgoing() {
        let g = make_diamond();
        // Outgoing only: both paths should still work (all edges are forward)
        let paths = k_shortest_paths(
            &g, 0, 3, 10, 5, TraversalDirection::Outgoing, None,
        );
        assert_eq!(paths.len(), 2);

        // Reverse direction: no path from 3 to 0 via outgoing
        let paths = k_shortest_paths(
            &g, 3, 0, 10, 5, TraversalDirection::Outgoing, None,
        );
        assert!(paths.is_empty());
    }

    #[test]
    fn test_ksp_directed_incoming() {
        let g = make_diamond();
        // Incoming only from node 3 to 0: should find paths (traversing edges in reverse)
        let paths = k_shortest_paths(
            &g, 3, 0, 10, 5, TraversalDirection::Incoming, None,
        );
        assert_eq!(paths.len(), 2);
    }

    #[test]
    fn test_ksp_confidence_filter() {
        // Diamond with different confidences:
        //   0→1 (0.9), 1→3 (0.9) — high-confidence path
        //   0→2 (0.9), 2→3 (0.3) — low-confidence on second edge
        let mut g = Graph::new();
        g.load_edges(vec![
            edge_conf(0, 1, "A", 0.9),
            edge_conf(1, 3, "A", 0.9),
            edge_conf(0, 2, "B", 0.9),
            edge_conf(2, 3, "B", 0.3),
        ]);

        // No filter: both paths
        let paths = k_shortest_paths(&g, 0, 3, 10, 5, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 2);

        // Filter at 0.5: only the high-confidence path survives
        let paths = k_shortest_paths(&g, 0, 3, 10, 5, TraversalDirection::Both, Some(0.5));
        assert_eq!(paths.len(), 1);
        let ids: Vec<NodeId> = paths[0].iter().map(|s| s.node_id).collect();
        assert_eq!(ids, vec![0, 1, 3]);
    }

    #[test]
    fn test_ksp_paths_are_simple() {
        // Cycle graph: paths must not revisit nodes
        let g = make_cycle(6); // 0→1→2→3→4→5→0
        let paths = k_shortest_paths(&g, 0, 3, 10, 5, TraversalDirection::Both, None);

        for path in &paths {
            let ids: Vec<NodeId> = path.iter().map(|s| s.node_id).collect();
            let unique: HashSet<NodeId> = ids.iter().copied().collect();
            assert_eq!(
                ids.len(),
                unique.len(),
                "path has repeated nodes: {:?}",
                ids
            );
        }
    }

    #[test]
    fn test_ksp_rel_types_preserved() {
        let g = make_diamond();
        let paths = k_shortest_paths(&g, 0, 3, 10, 2, TraversalDirection::Both, None);
        assert_eq!(paths.len(), 2);

        // Each path should have rel_type info on non-start nodes
        for path in &paths {
            assert!(path[0].rel_type.is_none()); // start node
            for step in &path[1..] {
                assert!(step.rel_type.is_some(), "missing rel_type on step {:?}", step);
            }
        }
    }

    #[test]
    fn test_ksp_node_not_in_graph() {
        let g = make_chain(3);
        let paths = k_shortest_paths(&g, 0, 999, 10, 5, TraversalDirection::Both, None);
        assert!(paths.is_empty());

        let paths = k_shortest_paths(&g, 999, 0, 10, 5, TraversalDirection::Both, None);
        assert!(paths.is_empty());
    }

    // --- Two-phase loading tests (mimics ext load_vertices + load_edges) ---

    #[test]
    fn test_two_phase_loading_bfs() {
        // Reproduce the ext loading path: add_node first, then add_edge
        let mut g = Graph::new();

        // Phase 1: load vertices (like ext load_vertices)
        g.add_node(100, "Concept".into(), Some("concept_a".into()));
        g.add_node(200, "Concept".into(), Some("concept_b".into()));
        g.add_node(300, "Concept".into(), Some("concept_c".into()));

        // Phase 2: load edges (like ext load_edges)
        let rt = g.intern_rel_type("SUBSUMES");
        g.add_edge(100, 200, rt, Edge::NO_CONFIDENCE);
        g.add_edge(100, 300, rt, Edge::NO_CONFIDENCE);

        // Verify degree sees edges
        assert_eq!(g.neighbors_out(100).len(), 2);
        assert_eq!(g.neighbors_in(200).len(), 1);

        // Verify BFS finds neighbors
        let result = bfs_neighborhood(&g, 100, 2, TraversalDirection::Both, None);
        assert_eq!(
            result.neighbors.len(), 2,
            "BFS should find 2 neighbors from node 100, found {}",
            result.neighbors.len()
        );
    }

    #[test]
    fn test_two_phase_loading_app_id_resolution() {
        let mut g = Graph::new();

        // Phase 1: vertices
        g.add_node(100, "Concept".into(), Some("concept_a".into()));
        g.add_node(200, "Concept".into(), Some("concept_b".into()));

        // Phase 2: edges
        let rt = g.intern_rel_type("SUBSUMES");
        g.add_edge(100, 200, rt, Edge::NO_CONFIDENCE);

        // Resolve app_id → internal NodeId
        let resolved = g.resolve_app_id("concept_a").unwrap();
        assert_eq!(resolved, 100);

        // BFS via resolved ID
        let result = bfs_neighborhood(&g, resolved, 1, TraversalDirection::Both, None);
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 200);
    }
}
