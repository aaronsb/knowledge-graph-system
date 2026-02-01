use std::collections::HashMap;

/// Internal node identifier (maps to AGE's graph-internal ID in production).
pub type NodeId = u64;

/// Interned relationship type index (avoids storing duplicate strings per edge).
pub type RelTypeId = u16;

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
        }
    }

    /// Pre-allocate for a known graph size.
    pub fn with_capacity(node_count: usize, edge_count: usize) -> Self {
        Self {
            outgoing: HashMap::with_capacity(node_count),
            incoming: HashMap::with_capacity(node_count),
            nodes: HashMap::with_capacity(node_count),
            app_id_index: HashMap::with_capacity(node_count),
            rel_types: Vec::new(),
            rel_type_map: HashMap::new(),
        }
    }

    /// Intern a relationship type string, returning its compact ID.
    pub fn intern_rel_type(&mut self, rel_type: &str) -> RelTypeId {
        if let Some(&id) = self.rel_type_map.get(rel_type) {
            return id;
        }
        let id = self.rel_types.len() as RelTypeId;
        self.rel_types.push(rel_type.to_string());
        self.rel_type_map.insert(rel_type.to_string(), id);
        id
    }

    /// Resolve a RelTypeId back to its string name.
    pub fn rel_type_name(&self, id: RelTypeId) -> &str {
        &self.rel_types[id as usize]
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
        self.outgoing
            .entry(from)
            .or_default()
            .push(Edge { target: to, rel_type });
        self.incoming
            .entry(to)
            .or_default()
            .push(Edge { target: from, rel_type });
    }

    /// Bulk load from an iterator of (from, to, rel_type_str, from_label, to_label) tuples.
    /// This is the primary load path — mirrors what the SPI query returns from AGE.
    pub fn load_edges<I>(&mut self, edges: I)
    where
        I: IntoIterator<Item = (NodeId, NodeId, String, String, String)>,
    {
        for (from, to, rel_type, from_label, to_label) in edges {
            // Ensure both nodes exist
            self.nodes
                .entry(from)
                .or_insert_with(|| NodeInfo { label: from_label, app_id: None });
            self.nodes
                .entry(to)
                .or_insert_with(|| NodeInfo { label: to_label, app_id: None });

            let rt = self.intern_rel_type(&rel_type);
            self.add_edge(from, to, rt);
        }
    }

    /// Bulk load with application-level IDs.
    pub fn load_edges_with_app_ids<I>(&mut self, edges: I)
    where
        I: IntoIterator<Item = (NodeId, NodeId, String, String, String, Option<String>, Option<String>)>,
    {
        for (from, to, rel_type, from_label, to_label, from_app_id, to_app_id) in edges {
            if let Some(ref aid) = from_app_id {
                self.app_id_index.insert(aid.clone(), from);
            }
            if let Some(ref aid) = to_app_id {
                self.app_id_index.insert(aid.clone(), to);
            }

            self.nodes
                .entry(from)
                .or_insert_with(|| NodeInfo { label: from_label, app_id: from_app_id });
            self.nodes
                .entry(to)
                .or_insert_with(|| NodeInfo { label: to_label, app_id: to_app_id });

            let rt = self.intern_rel_type(&rel_type);
            self.add_edge(from, to, rt);
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
        self.neighbors_out(id).iter().chain(self.neighbors_in(id).iter())
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn edge_count(&self) -> usize {
        self.outgoing.values().map(|v| v.len()).sum()
    }

    /// Approximate memory usage in bytes.
    pub fn memory_usage(&self) -> usize {
        use std::mem::size_of;

        let nodes_mem = self.nodes.len() * (size_of::<NodeId>() + size_of::<NodeInfo>() + 40);
        let out_edges: usize = self.outgoing.values().map(|v| v.len() * size_of::<Edge>()).sum();
        let in_edges: usize = self.incoming.values().map(|v| v.len() * size_of::<Edge>()).sum();
        let index_mem = self.app_id_index.len() * 80;

        nodes_mem + out_edges + in_edges + index_mem
    }
}

impl Default for Graph {
    fn default() -> Self {
        Self::new()
    }
}
