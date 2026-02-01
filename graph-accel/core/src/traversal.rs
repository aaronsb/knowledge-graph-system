use std::collections::{HashMap, VecDeque};

use crate::graph::{Graph, NodeId, RelTypeId};

/// A node found during BFS neighborhood traversal.
#[derive(Debug, Clone)]
pub struct NeighborResult {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub distance: u32,
    /// Relationship types on one shortest path from start to this node.
    pub path_types: Vec<String>,
}

/// A single step in a shortest path.
#[derive(Debug, Clone)]
pub struct PathStep {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub rel_type: Option<String>,
}

/// Result of a traversal operation.
#[derive(Debug)]
pub struct TraversalResult {
    pub neighbors: Vec<NeighborResult>,
    pub nodes_visited: usize,
}

/// BFS neighborhood: find all nodes reachable from `start` within `max_depth` hops.
///
/// Traverses both outgoing and incoming edges (undirected). Uses visited-set
/// pruning — each node is visited at most once, at its minimum distance.
///
/// Stores parent pointers instead of cloning path Vecs at each node —
/// paths are reconstructed lazily during result collection.
pub fn bfs_neighborhood(graph: &Graph, start: NodeId, max_depth: u32) -> TraversalResult {
    if graph.node(start).is_none() {
        return TraversalResult {
            neighbors: Vec::new(),
            nodes_visited: 0,
        };
    }

    // visited maps node → (distance, parent_node, edge_rel_type)
    // Start node uses itself as parent with a dummy rel_type of 0.
    let mut visited: HashMap<NodeId, (u32, NodeId, RelTypeId)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32)> = VecDeque::new();

    visited.insert(start, (0, start, 0));
    queue.push_back((start, 0));

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        for edge in graph.neighbors_all(current) {
            if !visited.contains_key(&edge.target) {
                visited.insert(edge.target, (depth + 1, current, edge.rel_type));
                queue.push_back((edge.target, depth + 1));
            }
        }
    }

    let nodes_visited = visited.len();

    // Reconstruct path_types lazily by walking parent pointers
    let neighbors: Vec<NeighborResult> = visited
        .iter()
        .filter(|(&id, _)| id != start)
        .map(|(&id, &(distance, _, _))| {
            let info = graph.node(id);
            let path_types = reconstruct_path_types(graph, &visited, start, id);
            NeighborResult {
                node_id: id,
                label: info.map(|n| n.label.clone()).unwrap_or_default(),
                app_id: info.and_then(|n| n.app_id.clone()),
                distance,
                path_types,
            }
        })
        .collect();

    TraversalResult {
        neighbors,
        nodes_visited,
    }
}

/// Walk parent pointers from `node` back to `start`, collecting rel_type names.
fn reconstruct_path_types(
    graph: &Graph,
    visited: &HashMap<NodeId, (u32, NodeId, RelTypeId)>,
    start: NodeId,
    node: NodeId,
) -> Vec<String> {
    let mut types = Vec::new();
    let mut current = node;

    while current != start {
        let &(_, parent, rel_type) = &visited[&current];
        if let Some(name) = graph.rel_type_name(rel_type) {
            types.push(name.to_string());
        }
        current = parent;
    }

    types.reverse();
    types
}

/// Shortest path from `start` to `target` using BFS (unweighted).
///
/// Returns None if no path exists within `max_hops`, or if either node
/// is not in the graph.
/// Returns the path as a sequence of steps including both endpoints.
pub fn shortest_path(
    graph: &Graph,
    start: NodeId,
    target: NodeId,
    max_hops: u32,
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
        }]);
    }

    if max_hops == 0 {
        return None;
    }

    // BFS with parent tracking
    let mut visited: HashMap<NodeId, (NodeId, RelTypeId)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32)> = VecDeque::new();

    // Sentinel: start node's parent is itself
    visited.insert(start, (start, 0));
    queue.push_back((start, 0));

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_hops {
            continue;
        }

        for edge in graph.neighbors_all(current) {
            if !visited.contains_key(&edge.target) {
                visited.insert(edge.target, (current, edge.rel_type));

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
    visited: &HashMap<NodeId, (NodeId, RelTypeId)>,
    start: NodeId,
    target: NodeId,
) -> Vec<PathStep> {
    let mut path = Vec::new();
    let mut current = target;

    loop {
        let info = graph.node(current);
        let &(parent, rel_type) = &visited[&current];

        path.push(PathStep {
            node_id: current,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: if current == start {
                None
            } else {
                graph.rel_type_name(rel_type).map(|s| s.to_string())
            },
        });

        if current == start {
            break;
        }
        current = parent;
    }

    path.reverse();
    path
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::{EdgeRecord, Graph};

    fn edge(from: u64, to: u64, rel: &str) -> EdgeRecord {
        EdgeRecord {
            from_id: from,
            to_id: to,
            rel_type: rel.to_string(),
            from_label: "Node".to_string(),
            to_label: "Node".to_string(),
            from_app_id: None,
            to_app_id: None,
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
        let result = bfs_neighborhood(&g, 0, 10);
        assert_eq!(result.neighbors.len(), 5);
        let node5 = result.neighbors.iter().find(|n| n.node_id == 5).unwrap();
        assert_eq!(node5.distance, 5);
    }

    #[test]
    fn test_bfs_chain_depth_limited() {
        let g = make_chain(10);
        let result = bfs_neighborhood(&g, 0, 3);
        assert_eq!(result.neighbors.len(), 3);
        assert!(result.neighbors.iter().all(|n| n.distance <= 3));
    }

    #[test]
    fn test_bfs_star() {
        let g = make_star(0, 100);
        let result = bfs_neighborhood(&g, 0, 1);
        assert_eq!(result.neighbors.len(), 100);
        assert!(result.neighbors.iter().all(|n| n.distance == 1));
    }

    #[test]
    fn test_bfs_cycle_no_infinite_loop() {
        let g = make_cycle(5);
        let result = bfs_neighborhood(&g, 0, 100);
        assert_eq!(result.neighbors.len(), 4);
    }

    #[test]
    fn test_bfs_undirected() {
        let g = make_chain(2);
        let result = bfs_neighborhood(&g, 1, 1);
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 0);
    }

    #[test]
    fn test_bfs_empty_graph() {
        let g = Graph::new();
        let result = bfs_neighborhood(&g, 0, 10);
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 0);
    }

    #[test]
    fn test_bfs_start_not_in_graph() {
        let g = make_chain(3);
        let result = bfs_neighborhood(&g, 999, 10);
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 0);
    }

    #[test]
    fn test_bfs_depth_zero() {
        let g = make_chain(5);
        let result = bfs_neighborhood(&g, 0, 0);
        // Depth 0 = only start node, no neighbors
        assert_eq!(result.neighbors.len(), 0);
        assert_eq!(result.nodes_visited, 1);
    }

    #[test]
    fn test_bfs_self_loop() {
        let mut g = Graph::new();
        g.load_edges(vec![edge(0, 0, "SELF")]);
        let result = bfs_neighborhood(&g, 0, 5);
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
        let result = bfs_neighborhood(&g, 0, 1);
        // Should find node 1 once (at distance 1) despite 3 parallel edges
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].distance, 1);
    }

    // --- Shortest path tests ---

    #[test]
    fn test_shortest_path_chain() {
        let g = make_chain(6);
        let path = shortest_path(&g, 0, 5, 10).unwrap();
        assert_eq!(path.len(), 6);
        assert_eq!(path[0].node_id, 0);
        assert_eq!(path[5].node_id, 5);
        assert!(path[0].rel_type.is_none());
        assert_eq!(path[1].rel_type.as_deref(), Some("NEXT"));
    }

    #[test]
    fn test_shortest_path_self() {
        let g = make_chain(3);
        let path = shortest_path(&g, 1, 1, 10).unwrap();
        assert_eq!(path.len(), 1);
        assert_eq!(path[0].node_id, 1);
    }

    #[test]
    fn test_shortest_path_no_path() {
        let mut g = Graph::new();
        g.add_node(0, "A".into(), None);
        g.add_node(1, "B".into(), None);
        let path = shortest_path(&g, 0, 1, 10);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_max_hops() {
        let g = make_chain(10);
        let path = shortest_path(&g, 0, 9, 5);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_max_hops_zero() {
        let g = make_chain(3);
        // max_hops=0 means no traversal allowed
        let path = shortest_path(&g, 0, 1, 0);
        assert!(path.is_none());
        // But start==target should still work even with max_hops=0
        let path = shortest_path(&g, 0, 0, 0);
        assert!(path.is_some());
        assert_eq!(path.unwrap().len(), 1);
    }

    #[test]
    fn test_shortest_path_cycle() {
        let g = make_cycle(6);
        let path = shortest_path(&g, 0, 3, 10).unwrap();
        assert_eq!(path.len(), 4);
    }

    #[test]
    fn test_shortest_path_start_not_in_graph() {
        let g = make_chain(3);
        assert!(shortest_path(&g, 999, 0, 10).is_none());
    }

    #[test]
    fn test_shortest_path_target_not_in_graph() {
        let g = make_chain(3);
        assert!(shortest_path(&g, 0, 999, 10).is_none());
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
        g.add_edge(0, 1, implies);
        g.add_edge(1, 2, supports);

        let result = bfs_neighborhood(&g, 0, 5);
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
}
