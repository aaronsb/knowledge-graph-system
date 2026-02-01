use graph_accel_core::Graph;
use std::collections::VecDeque;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mode = args.get(1).map(|s| s.as_str()).unwrap_or("all");
    let node_count: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(5_000_000);

    if mode == "help" || mode == "--help" {
        println!("Usage: graph-accel-bench [mode] [node_count]");
        println!();
        println!("Modes:");
        println!("  all         Run all generators and benchmark each (default)");
        println!("  lsystem     Fractal branching tree (deep paths)");
        println!("  scalefree   Preferential attachment via edge sampling (hub-and-spoke)");
        println!("  smallworld  Watts-Strogatz ring lattice + shortcuts");
        println!("  random      Erdos-Renyi uniform random edges");
        println!("  barbell     Two dense cliques connected by a thin bridge");
        println!("  dla         Diffusion-limited aggregation (organic branching)");
        println!();
        println!("Default node_count: 5000000");
        return;
    }

    println!("graph-accel-bench");
    println!("=================");
    println!();

    let generators: Vec<(&str, fn(u64) -> Graph)> = match mode {
        "lsystem" => vec![("L-system tree", gen_lsystem)],
        "scalefree" => vec![("Scale-free (edge sampling)", gen_scale_free)],
        "smallworld" => vec![("Small-world (Watts-Strogatz)", gen_small_world)],
        "random" => vec![("Erdos-Renyi random", gen_random)],
        "barbell" => vec![("Barbell (clique-bridge-clique)", gen_barbell)],
        "dla" => vec![("DLA (organic branching)", gen_dla)],
        "all" => vec![
            ("L-system tree", gen_lsystem as fn(u64) -> Graph),
            ("Scale-free (edge sampling)", gen_scale_free),
            ("Small-world (Watts-Strogatz)", gen_small_world),
            ("Erdos-Renyi random", gen_random),
            ("Barbell (clique-bridge-clique)", gen_barbell),
            ("DLA (organic branching)", gen_dla),
        ],
        _ => {
            eprintln!("Unknown mode: {}. Use --help for options.", mode);
            return;
        }
    };

    for (name, generator) in generators {
        run_benchmark(name, generator, node_count);
    }
}

fn run_benchmark(name: &str, generator: fn(u64) -> Graph, node_count: u64) {
    println!("--- {} ---", name);
    println!("Target: {} nodes", node_count);

    let t = Instant::now();
    let graph = generator(node_count);
    let gen_time = t.elapsed();
    println!(
        "Generated in {:.2}s — {} nodes, {} edges, ~{:.0}MB",
        gen_time.as_secs_f64(),
        graph.node_count(),
        graph.edge_count(),
        graph.memory_usage() as f64 / 1_048_576.0
    );

    // BFS from node 0 (typically a hub or root)
    println!();
    println!("{:>8} {:>12} {:>12} {:>10}", "depth", "found", "visited", "time");
    println!("{:->8} {:->12} {:->12} {:->10}", "", "", "", "");

    for depth in [1, 2, 3, 5, 10, 20, 50] {
        let t = Instant::now();
        let result = graph_accel_core::bfs_neighborhood(&graph, 0, depth);
        let elapsed = t.elapsed();
        println!(
            "{:>8} {:>12} {:>12} {:>8.1}ms",
            depth,
            result.neighbors.len(),
            result.nodes_visited,
            elapsed.as_secs_f64() * 1000.0
        );
        // Stop if we already found everything
        if result.nodes_visited >= graph.node_count() {
            println!("{:>8} (entire graph reached)", "");
            break;
        }
    }

    // Shortest path: node 0 to last node
    let far_node = graph.node_count() as u64 - 1;
    println!();
    let t = Instant::now();
    let path = graph_accel_core::shortest_path(&graph, 0, far_node, 100);
    let elapsed = t.elapsed();
    match path {
        Some(p) => println!(
            "Shortest path 0 → {}: {} hops in {:.1}ms",
            far_node,
            p.len() - 1,
            elapsed.as_secs_f64() * 1000.0
        ),
        None => println!(
            "Shortest path 0 → {}: no path ({:.1}ms)",
            far_node,
            elapsed.as_secs_f64() * 1000.0
        ),
    }
    println!();
}

// ---------------------------------------------------------------------------
// Generators — all O(n) or O(n + edges), single-threaded, deterministic
// ---------------------------------------------------------------------------

/// Simple LCG for deterministic, fast pseudo-random numbers.
struct FastRng(u64);

impl FastRng {
    fn new(seed: u64) -> Self {
        Self(seed)
    }
    fn next(&mut self, max: u64) -> u64 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1);
        (self.0 >> 33) % max
    }
    fn next_f64(&mut self) -> f64 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1);
        (self.0 >> 11) as f64 / (1u64 << 53) as f64
    }
}

const REL_TYPES: [&str; 5] = ["IMPLIES", "SUPPORTS", "CONTRADICTS", "RELATED_TO", "REQUIRES"];

/// L-system fractal tree: deep branching with self-similar structure.
///
/// Each node spawns `branching_factor` children. Produces deep paths (log depth)
/// with exponential width. Tests deep BFS and path reconstruction.
fn gen_lsystem(node_count: u64) -> Graph {
    let mut graph = Graph::with_capacity(node_count as usize, node_count as usize);
    let mut rng = FastRng::new(42);

    let branching = 3u64; // each node gets 3 children
    graph.add_node(0, "Root".into(), Some("c_0".into()));

    let mut next_id: u64 = 1;
    let mut frontier: Vec<u64> = vec![0];

    while next_id < node_count && !frontier.is_empty() {
        let mut next_frontier = Vec::with_capacity(frontier.len() * branching as usize);
        for &parent in &frontier {
            for _ in 0..branching {
                if next_id >= node_count {
                    break;
                }
                let child = next_id;
                next_id += 1;
                graph.add_node(child, "Concept".into(), Some(format!("c_{}", child)));
                let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
                graph.add_edge(parent, child, rt);
                next_frontier.push(child);
            }
        }
        frontier = next_frontier;
    }

    graph
}

/// Scale-free via edge-list sampling (O(edges), not O(n²)).
///
/// Preferential attachment by picking a random existing edge and connecting
/// to one of its endpoints. Nodes with more edges are more likely to be picked.
fn gen_scale_free(node_count: u64) -> Graph {
    let edges_per_node = 10u64;
    let mut graph = Graph::with_capacity(node_count as usize, (node_count * edges_per_node) as usize);
    let mut rng = FastRng::new(12345);

    // Edge list for O(1) preferential attachment sampling
    let mut edge_endpoints: Vec<u64> = Vec::with_capacity((node_count * edges_per_node * 2) as usize);

    // Seed: small clique
    let seed = 5u64;
    for i in 0..seed {
        graph.add_node(i, "Concept".into(), Some(format!("c_{}", i)));
    }
    for i in 0..seed {
        for j in (i + 1)..seed {
            let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
            graph.add_edge(i, j, rt);
            edge_endpoints.push(i);
            edge_endpoints.push(j);
        }
    }

    // Grow: each new node attaches to `edges_per_node` existing nodes
    for new_node in seed..node_count {
        graph.add_node(new_node, "Concept".into(), Some(format!("c_{}", new_node)));

        let attach = edges_per_node.min(new_node);
        for _ in 0..attach {
            // Pick a random endpoint from the edge list — proportional to degree
            let idx = rng.next(edge_endpoints.len() as u64) as usize;
            let target = edge_endpoints[idx];
            if target != new_node {
                let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
                graph.add_edge(new_node, target, rt);
                edge_endpoints.push(new_node);
                edge_endpoints.push(target);
            }
        }
    }

    graph
}

/// Small-world (Watts-Strogatz): ring lattice + random rewiring.
///
/// Start with each node connected to K nearest neighbors on a ring,
/// then rewire each edge with probability p. Produces high clustering
/// with short path lengths.
fn gen_small_world(node_count: u64) -> Graph {
    let k = 10u64; // neighbors on each side
    let p = 0.05f64; // rewire probability
    let mut graph = Graph::with_capacity(node_count as usize, (node_count * k) as usize);
    let mut rng = FastRng::new(67890);

    for i in 0..node_count {
        graph.add_node(i, "Concept".into(), Some(format!("c_{}", i)));
    }

    // Ring lattice: connect each node to K nearest neighbors (forward direction only to avoid double-edges)
    for i in 0..node_count {
        for j in 1..=k {
            let neighbor = (i + j) % node_count;
            let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);

            // Rewire with probability p
            if rng.next_f64() < p {
                let rewired = rng.next(node_count);
                if rewired != i {
                    graph.add_edge(i, rewired, rt);
                } else {
                    graph.add_edge(i, neighbor, rt);
                }
            } else {
                graph.add_edge(i, neighbor, rt);
            }
        }
    }

    graph
}

/// Erdos-Renyi: uniform random edges.
///
/// Each possible edge exists with probability p. We target ~10 edges per node
/// on average. Baseline topology with no structure.
fn gen_random(node_count: u64) -> Graph {
    let target_edges = node_count * 10;
    let mut graph = Graph::with_capacity(node_count as usize, target_edges as usize);
    let mut rng = FastRng::new(54321);

    for i in 0..node_count {
        graph.add_node(i, "Concept".into(), Some(format!("c_{}", i)));
    }

    for _ in 0..target_edges {
        let from = rng.next(node_count);
        let to = rng.next(node_count);
        if from != to {
            let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
            graph.add_edge(from, to, rt);
        }
    }

    graph
}

/// Barbell: two dense cliques connected by a single thin bridge.
///
/// Worst case for "find path through bottleneck." Each clique has n/2 nodes
/// densely connected; they're joined by a chain of ~10 bridge nodes.
fn gen_barbell(node_count: u64) -> Graph {
    let bridge_len = 10u64;
    let clique_size = (node_count - bridge_len) / 2;
    let mut graph = Graph::with_capacity(node_count as usize, (clique_size * 20 + bridge_len) as usize);
    let mut rng = FastRng::new(99999);

    // Clique A: nodes 0..clique_size, each connected to ~20 random others in the clique
    for i in 0..clique_size {
        graph.add_node(i, "ClusterA".into(), Some(format!("c_{}", i)));
    }
    for i in 0..clique_size {
        for _ in 0..20u64.min(clique_size - 1) {
            let target = rng.next(clique_size);
            if target != i {
                let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
                graph.add_edge(i, target, rt);
            }
        }
    }

    // Bridge: chain from last node of A to first node of B
    let bridge_start = clique_size;
    for i in 0..bridge_len {
        let id = bridge_start + i;
        graph.add_node(id, "Bridge".into(), Some(format!("c_{}", id)));
        if i == 0 {
            let rt = graph.intern_rel_type("BRIDGES");
            graph.add_edge(clique_size - 1, id, rt);
        } else {
            let rt = graph.intern_rel_type("NEXT");
            graph.add_edge(id - 1, id, rt);
        }
    }

    // Clique B: nodes after bridge
    let b_start = bridge_start + bridge_len;
    for i in 0..clique_size {
        let id = b_start + i;
        graph.add_node(id, "ClusterB".into(), Some(format!("c_{}", id)));
    }
    // Connect bridge to clique B
    let rt = graph.intern_rel_type("BRIDGES");
    graph.add_edge(b_start - 1, b_start, rt);

    for i in 0..clique_size {
        for _ in 0..20u64.min(clique_size - 1) {
            let target = rng.next(clique_size);
            if target != i {
                let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
                graph.add_edge(b_start + i, b_start + target, rt);
            }
        }
    }

    graph
}

/// DLA (Diffusion-Limited Aggregation): organic branching growth.
///
/// Simulates particles doing random walks that stick when they hit existing
/// structure. Produces organic, tree-like topology with winding paths.
/// Simplified: each new node attaches to a random existing node, with
/// occasional long-range jumps.
fn gen_dla(node_count: u64) -> Graph {
    let mut graph = Graph::with_capacity(node_count as usize, (node_count * 2) as usize);
    let mut rng = FastRng::new(77777);

    graph.add_node(0, "Seed".into(), Some("c_0".into()));

    // Track active "surface" nodes — recent additions that new particles attach to.
    // This keeps the growth at the frontier, like real DLA.
    // VecDeque for O(1) pop_front when evicting oldest surface nodes.
    let mut surface: VecDeque<u64> = VecDeque::with_capacity(10001);
    surface.push_back(0);
    let surface_max = 10000usize;

    for new_node in 1..node_count {
        graph.add_node(new_node, "Concept".into(), Some(format!("c_{}", new_node)));

        // Attach to a random surface node (primary edge)
        let attach_to = surface[rng.next(surface.len() as u64) as usize];
        let rt = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
        graph.add_edge(new_node, attach_to, rt);

        // 10% chance of a second connection (creates loops / shortcuts)
        if rng.next(10) == 0 && new_node > 1 {
            let other = rng.next(new_node);
            if other != attach_to {
                let rt2 = graph.intern_rel_type(REL_TYPES[rng.next(5) as usize]);
                graph.add_edge(new_node, other, rt2);
            }
        }

        // Maintain surface: add new node, evict oldest if over limit
        surface.push_back(new_node);
        if surface.len() > surface_max {
            surface.pop_front();
        }
    }

    graph
}
