//! graph-accel-core: In-memory graph traversal engine.
//!
//! A pure Rust library that maintains an adjacency list and provides
//! fast BFS neighborhood traversal and shortest path queries.
//! No PostgreSQL dependencies — this crate compiles standalone.
//!
//! Designed as the core engine for the graph_accel PostgreSQL extension
//! (ADR-201), but usable independently for benchmarking and testing.

mod graph;
mod traversal;

pub use graph::{
    Direction, Edge, EdgeRecord, Graph, NodeId, NodeInfo, RelTypeId, TraversalDirection,
    MAX_REL_TYPES,
};
pub use traversal::{
    bfs_neighborhood, degree_centrality, extract_subgraph, shortest_path, DegreeResult,
    NeighborResult, PathStep, SubgraphEdge, SubgraphResult, TraversalResult,
};
