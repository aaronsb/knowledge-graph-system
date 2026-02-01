use std::collections::HashMap;

/// Internal node identifier (maps to AGE's graph-internal ID in production).
pub type NodeId = u64;

/// Interned relationship type index (avoids storing duplicate strings per edge).
pub type RelTypeId = u16;

/// Maximum number of distinct relationship types (u16::MAX).
pub const MAX_REL_TYPES: usize = u16::MAX as usize;

/// Metadata about a node.
#[derive(Debug, Clone)]
pub struct NodeInfo {
    pub label: String,
    pub app_id: Option<String>,
}

/// A directed edge in the adjacency list.
#[derive(Debug, Clone, Copy)]
pub struct Edge {
    pub target: NodeId,
    pub rel_type: RelTypeId,
}

/// A record describing an edge to load into the graph.
/// Named fields prevent the field-ordering bugs that tuples invite.
#[derive(Debug, Clone)]
pub struct EdgeRecord {
    pub from_id: NodeId,
    pub to_id: NodeId,
    pub rel_type: String,
    pub from_label: String,
    pub to_label: String,
    pub from_app_id: Option<String>,
    pub to_app_id: Option<String>,
}

/// In-memory graph: adjacency lists + node metadata + relationship type interning.
///
/// Edges are stored bidirectionally — `outgoing[a]` contains edges from a,
/// `incoming[b]` contains edges into b. Both are populated on load.
pub struct Graph {
    outgoing: HashMap<NodeId, Vec<Edge>>,
    incoming: HashMap<NodeId, Vec<Edge>>,
    nodes: HashMap<NodeId, NodeInfo>,
    app_id_index: HashMap<String, NodeId>,
    rel_types: Vec<String>,
    rel_type_map: HashMap<String, RelTypeId>,
    /// Hint for Vec pre-allocation in add_edge. Set by with_capacity().
    estimated_avg_degree: usize,
}

impl Graph {
    pub fn new() -> Self {
        Self {
            outgoing: HashMap::new(),
            incoming: HashMap::new(),
            nodes: HashMap::new(),
            app_id_index: HashMap::new(),
            rel_types: Vec::new(),
            rel_type_map: HashMap::new(),
            estimated_avg_degree: 4,
        }
    }

    /// Pre-allocate for a known graph size.
    ///
    /// `edge_count` is used to estimate average edges per node for Vec pre-allocation
    /// in `add_edge`, avoiding repeated re-allocation during bulk loading.
    pub fn with_capacity(node_count: usize, edge_count: usize) -> Self {
        Self {
            outgoing: HashMap::with_capacity(node_count),
            incoming: HashMap::with_capacity(node_count),
            nodes: HashMap::with_capacity(node_count),
            app_id_index: HashMap::with_capacity(node_count),
            rel_types: Vec::new(),
            rel_type_map: HashMap::new(),
            estimated_avg_degree: if node_count > 0 {
                (edge_count / node_count).max(1)
            } else {
                4
            },
        }
    }

    /// Intern a relationship type string, returning its compact ID.
    ///
    /// # Panics
    /// Panics if more than 65,535 distinct relationship types are interned.
    /// In the pgrx extension this panic is caught by `#[pg_guard]` and
    /// converted to a Postgres ERROR.
    pub fn intern_rel_type(&mut self, rel_type: &str) -> RelTypeId {
        if let Some(&id) = self.rel_type_map.get(rel_type) {
            return id;
        }
        assert!(
            self.rel_types.len() < MAX_REL_TYPES,
            "graph_accel: exceeded maximum of {} distinct relationship types",
            MAX_REL_TYPES
        );
        let id = self.rel_types.len() as RelTypeId;
        self.rel_types.push(rel_type.to_string());
        self.rel_type_map.insert(rel_type.to_string(), id);
        id
    }

    /// Resolve a RelTypeId back to its string name.
    /// Returns None if the ID is out of range.
    pub fn rel_type_name(&self, id: RelTypeId) -> Option<&str> {
        self.rel_types.get(id as usize).map(|s| s.as_str())
    }

    /// Register a node with metadata.
    pub fn add_node(&mut self, id: NodeId, label: String, app_id: Option<String>) {
        if let Some(ref aid) = app_id {
            self.app_id_index.insert(aid.clone(), id);
        }
        self.nodes.insert(id, NodeInfo { label, app_id });
    }

    /// Add a directed edge. Also inserts into the incoming adjacency list.
    pub fn add_edge(&mut self, from: NodeId, to: NodeId, rel_type: RelTypeId) {
        let avg = self.estimated_avg_degree;
        self.outgoing
            .entry(from)
            .or_insert_with(|| Vec::with_capacity(avg))
            .push(Edge { target: to, rel_type });
        self.incoming
            .entry(to)
            .or_insert_with(|| Vec::with_capacity(avg))
            .push(Edge { target: from, rel_type });
    }

    /// Bulk load from EdgeRecord structs.
    /// This is the primary load path — mirrors what the SPI query returns from AGE.
    pub fn load_edges<I>(&mut self, edges: I)
    where
        I: IntoIterator<Item = EdgeRecord>,
    {
        for rec in edges {
            // Register app IDs (first occurrence wins)
            if let Some(ref aid) = rec.from_app_id {
                self.app_id_index.entry(aid.clone()).or_insert(rec.from_id);
            }
            if let Some(ref aid) = rec.to_app_id {
                self.app_id_index.entry(aid.clone()).or_insert(rec.to_id);
            }

            // Register nodes (first occurrence wins for label/app_id)
            self.nodes.entry(rec.from_id).or_insert_with(|| NodeInfo {
                label: rec.from_label,
                app_id: rec.from_app_id,
            });
            self.nodes.entry(rec.to_id).or_insert_with(|| NodeInfo {
                label: rec.to_label,
                app_id: rec.to_app_id,
            });

            let rt = self.intern_rel_type(&rec.rel_type);
            self.add_edge(rec.from_id, rec.to_id, rt);
        }
    }

    /// Look up a node by its application-level ID (e.g. concept_id).
    pub fn resolve_app_id(&self, app_id: &str) -> Option<NodeId> {
        self.app_id_index.get(app_id).copied()
    }

    /// Get node metadata.
    pub fn node(&self, id: NodeId) -> Option<&NodeInfo> {
        self.nodes.get(&id)
    }

    /// Get outgoing edges for a node.
    pub fn neighbors_out(&self, id: NodeId) -> &[Edge] {
        self.outgoing.get(&id).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Get incoming edges for a node.
    pub fn neighbors_in(&self, id: NodeId) -> &[Edge] {
        self.incoming.get(&id).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Get both outgoing and incoming edges (undirected traversal).
    pub fn neighbors_all(&self, id: NodeId) -> impl Iterator<Item = &Edge> {
        self.neighbors_out(id)
            .iter()
            .chain(self.neighbors_in(id).iter())
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn edge_count(&self) -> usize {
        self.outgoing.values().map(|v| v.len()).sum()
    }

    pub fn rel_type_count(&self) -> usize {
        self.rel_types.len()
    }

    /// Approximate memory usage in bytes.
    ///
    /// Accounts for HashMap bucket arrays, Vec capacity (not just len),
    /// and String heap allocations.
    pub fn memory_usage(&self) -> usize {
        use std::mem::size_of;

        // HashMap overhead: ~1 byte control + key-value pair per bucket, load factor ~87.5%
        let hashmap_overhead = |len: usize, kv_size: usize| -> usize {
            let buckets = (len * 8 / 7).next_power_of_two().max(1);
            buckets * (1 + kv_size)
        };

        // Nodes: HashMap<NodeId, NodeInfo> + estimated 32 bytes avg String heap per node
        let nodes_mem = hashmap_overhead(
            self.nodes.len(),
            size_of::<NodeId>() + size_of::<NodeInfo>(),
        ) + self.nodes.len() * 32;

        // Edges: use Vec capacity (not len) to account for over-allocation
        let out_edges: usize = self
            .outgoing
            .values()
            .map(|v| v.capacity() * size_of::<Edge>())
            .sum::<usize>()
            + hashmap_overhead(
                self.outgoing.len(),
                size_of::<NodeId>() + size_of::<Vec<Edge>>(),
            );

        let in_edges: usize = self
            .incoming
            .values()
            .map(|v| v.capacity() * size_of::<Edge>())
            .sum::<usize>()
            + hashmap_overhead(
                self.incoming.len(),
                size_of::<NodeId>() + size_of::<Vec<Edge>>(),
            );

        // App ID index: HashMap<String, NodeId> + estimated 24 bytes avg String heap per key
        let index_mem = hashmap_overhead(
            self.app_id_index.len(),
            size_of::<String>() + size_of::<NodeId>(),
        ) + self.app_id_index.len() * 24;

        // Rel type interning
        let rel_mem = self
            .rel_types
            .iter()
            .map(|s| s.capacity() + size_of::<String>())
            .sum::<usize>()
            + hashmap_overhead(
                self.rel_type_map.len(),
                size_of::<String>() + size_of::<RelTypeId>(),
            );

        nodes_mem + out_edges + in_edges + index_mem + rel_mem
    }
}

impl Default for Graph {
    fn default() -> Self {
        Self::new()
    }
}
