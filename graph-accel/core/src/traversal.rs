use std::collections::{HashMap, VecDeque};

use crate::graph::{Graph, NodeId, RelTypeId};

/// A node found during BFS neighborhood traversal.
#[derive(Debug, Clone)]
pub struct NeighborResult {
    pub node_id: NodeId,
    pub label: String,
    pub app_id: Option<String>,
    pub distance: u32,
    /// Relationship types on one path from start to this node (not all paths).
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
pub fn bfs_neighborhood(graph: &Graph, start: NodeId, max_depth: u32) -> TraversalResult {
    let mut visited: HashMap<NodeId, (u32, Vec<RelTypeId>)> = HashMap::new();
    let mut queue: VecDeque<(NodeId, u32, Vec<RelTypeId>)> = VecDeque::new();

    visited.insert(start, (0, Vec::new()));
    queue.push_back((start, 0, Vec::new()));

    while let Some((current, depth, path_types)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        for edge in graph.neighbors_all(current) {
            if !visited.contains_key(&edge.target) {
                let mut new_path = path_types.clone();
                new_path.push(edge.rel_type);
                visited.insert(edge.target, (depth + 1, new_path.clone()));
                queue.push_back((edge.target, depth + 1, new_path));
            }
        }
    }

    let nodes_visited = visited.len();

    let neighbors: Vec<NeighborResult> = visited
        .into_iter()
        .filter(|(id, _)| *id != start)
        .map(|(id, (distance, rel_ids))| {
            let info = graph.node(id);
            NeighborResult {
                node_id: id,
                label: info.map(|n| n.label.clone()).unwrap_or_default(),
                app_id: info.and_then(|n| n.app_id.clone()),
                distance,
                path_types: rel_ids
                    .iter()
                    .map(|&rt| graph.rel_type_name(rt).to_string())
                    .collect(),
            }
        })
        .collect();

    TraversalResult {
        neighbors,
        nodes_visited,
    }
}

/// Shortest path from `start` to `target` using BFS (unweighted).
///
/// Returns None if no path exists within `max_hops`.
/// Returns the path as a sequence of steps including both endpoints.
pub fn shortest_path(
    graph: &Graph,
    start: NodeId,
    target: NodeId,
    max_hops: u32,
) -> Option<Vec<PathStep>> {
    if start == target {
        let info = graph.node(start);
        return Some(vec![PathStep {
            node_id: start,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: None,
        }]);
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
                    // Reconstruct path
                    return Some(reconstruct_path(graph, &visited, start, target));
                }

                queue.push_back((edge.target, depth + 1));
            }
        }
    }

    None
}

fn reconstruct_path(
    graph: &Graph,
    visited: &HashMap<NodeId, (NodeId, RelTypeId)>,
    start: NodeId,
    target: NodeId,
) -> Vec<PathStep> {
    let mut path = Vec::new();
    let mut current = target;

    loop {
        let info = graph.node(current);
        let (parent, rel_type) = visited[&current];

        path.push(PathStep {
            node_id: current,
            label: info.map(|n| n.label.clone()).unwrap_or_default(),
            app_id: info.and_then(|n| n.app_id.clone()),
            rel_type: if current == start {
                None
            } else {
                Some(graph.rel_type_name(rel_type).to_string())
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
    use crate::graph::Graph;

    fn make_chain(n: u64) -> Graph {
        // 0 -> 1 -> 2 -> ... -> n-1
        let mut g = Graph::new();
        let edges: Vec<_> = (0..n - 1)
            .map(|i| (i, i + 1, "NEXT".to_string(), "Node".to_string(), "Node".to_string()))
            .collect();
        g.load_edges(edges);
        g
    }

    fn make_star(center: u64, leaves: u64) -> Graph {
        // center -> 1, center -> 2, ..., center -> leaves
        let mut g = Graph::new();
        let edges: Vec<_> = (1..=leaves)
            .map(|i| (center, i, "HAS".to_string(), "Hub".to_string(), "Leaf".to_string()))
            .collect();
        g.load_edges(edges);
        g
    }

    fn make_cycle(n: u64) -> Graph {
        // 0 -> 1 -> 2 -> ... -> n-1 -> 0
        let mut g = Graph::new();
        let edges: Vec<_> = (0..n)
            .map(|i| (i, (i + 1) % n, "NEXT".to_string(), "Node".to_string(), "Node".to_string()))
            .collect();
        g.load_edges(edges);
        g
    }

    #[test]
    fn test_bfs_chain() {
        let g = make_chain(6); // 0->1->2->3->4->5
        let result = bfs_neighborhood(&g, 0, 10);
        assert_eq!(result.neighbors.len(), 5);
        // Node 5 is at distance 5
        let node5 = result.neighbors.iter().find(|n| n.node_id == 5).unwrap();
        assert_eq!(node5.distance, 5);
    }

    #[test]
    fn test_bfs_chain_depth_limited() {
        let g = make_chain(10);
        let result = bfs_neighborhood(&g, 0, 3);
        // Should only reach nodes 1, 2, 3
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
        // Should visit all 4 other nodes, not loop
        assert_eq!(result.neighbors.len(), 4);
    }

    #[test]
    fn test_bfs_undirected() {
        // 0 -> 1, but BFS should also find 0 from 1 via incoming edge
        let g = make_chain(2); // 0 -> 1
        let result = bfs_neighborhood(&g, 1, 1);
        assert_eq!(result.neighbors.len(), 1);
        assert_eq!(result.neighbors[0].node_id, 0);
    }

    #[test]
    fn test_shortest_path_chain() {
        let g = make_chain(6);
        let path = shortest_path(&g, 0, 5, 10).unwrap();
        assert_eq!(path.len(), 6); // 6 nodes: 0,1,2,3,4,5
        assert_eq!(path[0].node_id, 0);
        assert_eq!(path[5].node_id, 5);
        assert!(path[0].rel_type.is_none()); // start has no incoming rel
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
        // Two disconnected nodes
        let mut g = Graph::new();
        g.add_node(0, "A".into(), None);
        g.add_node(1, "B".into(), None);
        let path = shortest_path(&g, 0, 1, 10);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_max_hops() {
        let g = make_chain(10);
        // Path from 0 to 9 is 9 hops — limit to 5 should fail
        let path = shortest_path(&g, 0, 9, 5);
        assert!(path.is_none());
    }

    #[test]
    fn test_shortest_path_cycle() {
        let g = make_cycle(6);
        // 0->1->2->3->4->5->0, shortest from 0 to 3 is 3 hops (forward)
        // or 3 hops backward (0<-5<-4<-3), both length 3
        let path = shortest_path(&g, 0, 3, 10).unwrap();
        assert_eq!(path.len(), 4); // 4 nodes in a 3-hop path
    }

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
        assert_eq!(g.node_count(), 51); // center + 50 leaves
        assert_eq!(g.edge_count(), 50);
    }
}
