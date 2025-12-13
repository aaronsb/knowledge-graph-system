# Scaling t-SNE and Embedding Visualization for Knowledge Graphs

Modern knowledge graph visualization demands techniques that handle millions of points while preserving both local cluster structure and global semantic relationships. **PaCMAP and properly-initialized UMAP/t-SNE now offer the best trade-offs**, with GPU implementations achieving 50-700x speedups over traditional approaches. The most critical insight from recent research: initialization—not algorithm choice—determines whether global structure survives the projection.

For systems with multiple embedding types (concepts, evidence, edge text), the emerging consensus favors **linked coordinated views** with a unified embedding space for semantically related elements. This report synthesizes academic research and production best practices across scaling, algorithms, visualization design, and implementation.

---

## Scaling to millions of points requires algorithmic acceleration

The original t-SNE algorithm's O(N²) complexity makes it impractical beyond ~10,000 points. Three acceleration strategies now enable million-scale visualization:

**Barnes-Hut t-SNE** reduces complexity to O(N log N) by approximating gradient computations using space-partitioning trees. It treats clusters of distant points as single nodes when computing repulsive forces, controlled by a trade-off parameter θ (default **0.5**). While faster, it still struggles beyond ~500K points due to memory access patterns in tree traversal.

**FFT-accelerated t-SNE (FIt-SNE)** achieves effectively O(N) complexity by interpolating points onto an equispaced grid and using Fast Fourier Transform for convolutions. Benchmarks show **30-100x speedups** over Barnes-Hut on million-point datasets. The limitation: it currently supports only 2D embeddings.

**GPU implementations** deliver the most dramatic improvements. NVIDIA's cuML t-SNE achieves up to **2000x speedup** versus scikit-learn, processing MNIST (70K points) in ~7 seconds versus 19 minutes. The t-SNE-CUDA library handles 10M+ points on consumer GPUs. Most GPU implementations restrict output to 2D due to architectural constraints.

| Dataset Size | Recommended Approach | Expected Runtime |
|-------------|---------------------|------------------|
| < 10K | Standard Barnes-Hut | Seconds |
| 10K - 100K | FIt-SNE or UMAP | Minutes |
| 100K - 1M | FIt-SNE with Annoy, GPU | 1-10 minutes |
| 1M - 10M | t-SNE-CUDA, cuML | 10-30 minutes |
| > 10M | Sampling + GPU, hierarchical | Variable |

---

## UMAP and PaCMAP now outperform t-SNE for most use cases

The dimensionality reduction landscape has shifted significantly. **UMAP** offers comparable local structure preservation to t-SNE with 2-10x faster computation, better scaling with embedding dimensionality, and no restriction on output dimensions. Its default spectral initialization provides reasonable global structure out of the box.

**PaCMAP** (Pairwise Controlled Manifold Approximation) has emerged as the strongest all-around performer. It uses three types of point pairs—neighbor pairs for local structure, mid-near pairs for global structure in early optimization, and further pairs for repulsion—achieving the **best combined local and global structure preservation** in comprehensive evaluations. It's also less sensitive to initialization and hyperparameter choices.

**TriMAP** excels when global cluster relationships matter more than fine local detail. Its triplet-based approach scales to millions of points without memory issues, though it struggles with fine structure preservation.

| Method | Local Structure | Global Structure | Speed | Best Use Case |
|--------|----------------|------------------|-------|---------------|
| t-SNE (FIt-SNE) | Excellent | Poor without init | Medium | Tight cluster identification |
| UMAP | Excellent | Medium | Fast | General purpose, large data |
| PaCMAP | Very Good | Excellent | Fast | When both structures matter |
| TriMAP | Good | Very Good | Very Fast | Global structure priority |

For knowledge graph embeddings where both semantic neighborhoods (local) and ontological relationships (global) matter, **PaCMAP or UMAP with PCA initialization** is the recommended starting point.

---

## Initialization determines global structure more than algorithm choice

A crucial finding from Kobak & Linderman (Nature Biotechnology, 2021): UMAP's apparent global structure advantage over t-SNE comes primarily from its **default spectral initialization**, not the algorithm itself. With identical initialization, both algorithms preserve global structure similarly.

**Practical recommendation**: Always initialize with PCA (first two principal components scaled to standard deviation **0.0001**) or Laplacian eigenmaps. Random initialization should be avoided for any application where cluster relationships matter.

Additional techniques for global structure:
- **Late exaggeration**: Increasing the exaggeration coefficient late in optimization (to ~4x) improves cluster separation
- **Multi-scale perplexity**: Combining multiple perplexity values captures structure at different scales
- **PaCMAP's mid-near pairs**: Automatically captures global structure during early iterations without manual tuning

---

## Hyperparameter selection follows predictable rules

For t-SNE, **perplexity** controls the effective number of neighbors considered. The classic recommendation of 5-50 has been refined: modern guidance suggests **perplexity ≈ N/100** for large datasets (where N is sample count), with a minimum of ~30 for small datasets. Higher perplexity increases runtime linearly.

**Learning rate** should scale with dataset size: the formula `learning_rate ≈ N/12` works well across scales. Scikit-learn's 'auto' setting uses `max(N / early_exaggeration / 4, 50)`. Note that scikit-learn's learning rate definition is 4x larger than other implementations.

For UMAP, **n_neighbors** (analogous to perplexity) controls local vs global balance:
- 2-5: Very local structure, may miss global patterns
- **15-30**: Balanced (recommended for most applications)
- 50-100: Emphasizes global structure, loses fine detail

**min_dist** (0.0 to 1.0) controls cluster tightness:
- 0.0-0.1: Tight, dense clusters revealing fine structure
- **0.1-0.3**: Good separation between groups (commonly used)
- 0.5+: Dispersed, smoother layout

---

## Hierarchical visualization enables multi-scale exploration

Point clouds at scale require **level-of-detail (LOD)** strategies. The most effective approaches:

**Semantic zooming** implements three layers: an information layer controlling which attributes appear, an aggregation layer that groups elements at low zoom, and a visual appearance layer managing graphical detail. At overview zoom, show only cluster hulls or centroids with counts; at medium zoom, show cluster boundaries with representative samples; at maximum zoom, reveal individual points with full metadata.

**Continuous LOD** eliminates jarring transitions by adding a random value (0-1) to each point's level, creating smooth dither-like transitions as the camera moves. Points are filtered based on camera distance, screen position, and orientation.

**HDBSCAN integration** provides automatic hierarchical clustering that can drive LOD. The condensed tree visualization shows cluster hierarchy where width represents point counts at each level. Soft clustering probabilities can modulate point saturation—confident assignments appear vivid, uncertain ones desaturated.

---

## Color encodes meaning through deliberate design choices

**For cluster assignment**: Use categorical palettes with high discriminability (Seaborn's "deep" or "tab10"). Limit to **8-12 distinct colors** maximum; beyond this, combine color with shape or use faceting. Reserve gray (0.5, 0.5, 0.5) for noise points. Apply desaturation proportional to cluster membership probability for soft clustering results.

**For continuous attributes**: Perceptually uniform scales are essential. **Viridis** remains the default recommendation—wide perceptual range, colorblind-safe, grayscale-printable. **Magma** works well for density visualization (dark backgrounds, high contrast). **Cividis** is specifically optimized for color vision deficiency.

**For multiple embedding types** in knowledge graphs:
- **Concepts**: Circles, colored by ontological category, sized by degree/importance
- **Evidence**: Squares (smaller than concepts), colored by source or confidence
- **Edge centroids**: Diamonds, positioned between connected concepts
- **Outliers**: Triangles in red, positioned peripherally

Handle overlapping points with **alpha blending** (start with `alpha = min(1/sqrt(n_points), 0.8)`), smaller point sizes in dense regions, and density contour underlays.

---

## Spatial arrangement benefits from hybrid layout strategies

For knowledge graphs, pure embedding-based layout ignores valuable structural information. The research supports **hybrid approaches**:

**DR-first, force-refinement**: Apply UMAP/t-SNE on embeddings for initial 2D positions, then apply constrained force-directed refinement for aesthetics and edge bundling. This preserves embedding semantics while improving graph readability.

**Hierarchical initialization**: Place ontology anchors (power nodes) first using embedding distances, position regular nodes within their ontological neighborhoods, then apply Fruchterman-Reingold for within-cluster refinement. This approach preserves both semantic similarity and ontological hierarchy.

**DRGraph algorithm** achieves O(N) complexity for graph layout by combining sparse distance matrix approximation with negative sampling and multi-level schemes, scaling to millions of nodes.

---

## Interactive systems require GPU rendering and spatial indexing

WebGL enables million-point interactivity that SVG and Canvas cannot achieve:

| Rendering Tech | Max Points (60 FPS) | Max Points (Interactive) |
|----------------|---------------------|--------------------------|
| SVG | ~1,000 | ~5,000 |
| Canvas 2D | ~10,000 | ~50,000 |
| WebGL | ~1,000,000 | ~10,000,000 |

**regl-scatterplot** handles up to **20 million points** with performance mode enabled (square points, disabled alpha blending, point size ~0.25). It supports lasso selection, pan/zoom, and integrates with Jupyter via jscatter.

**deck.gl** maintains 60 FPS up to ~1M points with its ScatterplotLayer, scaling to billions with 3D Tiles streaming. Key optimizations: disable picking for static views, use constant props instead of accessor functions, supply pre-computed attribute buffers.

**Spatial indexing** is essential for hover detection at scale. D3's quadtree reduces linear O(N) search to O(log N), enabling instant hover feedback on millions of points:
```javascript
quadtree = d3.quadtree().x(d => d.x).y(d => d.y).addAll(data);
const nearest = quadtree.find(mouseX, mouseY);
```

For GPU-based picking, render the scene twice—once with object IDs encoded as colors to an off-screen framebuffer, then read the pixel under the cursor to identify the selected point.

---

## Multiple embedding types work best in coordinated views

For knowledge graph systems with concept, evidence, and edge embeddings, the research consensus favors **linked coordinated views** over forcing everything into one projection:

**Primary view**: Unified embedding space for concepts and evidence (semantically related types that benefit from joint projection). Apply lightweight projection layers to align different embedding dimensionalities to a common space before UMAP.

**Secondary panels**: Edge embeddings shown as a similarity heatmap or separate scatter linked to the main view. Ontology hierarchy as a tree view. Detail panel for selected items.

**Coordination**: Selections in any view highlight corresponding elements across all views. Cross-filtering enables focusing on subsets while maintaining context.

The architecture pattern:
```
┌─────────────────────────────────────────────────────┐
│           MAIN EMBEDDING VIEW (UMAP)                │
│   Concepts (●) + Evidence (■) in joint projection   │
├──────────────┬──────────────┬───────────────────────┤
│  Ontology    │ Edge Text    │ Detail Panel          │
│  Tree View   │ Heatmap      │ (selected metadata)   │
└──────────────┴──────────────┴───────────────────────┘
```

---

## Implementation libraries span CPU, GPU, and web rendering

**For CPU-based dimensionality reduction**: **openTSNE** is the fastest Python implementation, automatically selecting Barnes-Hut for <10K points and FIt-SNE for larger datasets. It supports PCA initialization, multi-perplexity runs, and mapping new data to existing embeddings. **umap-learn** is the standard UMAP implementation with numba JIT compilation.

**For GPU acceleration**: **RAPIDS cuML** provides drop-in replacements for scikit-learn with 10-80x speedups, including a zero-code-change mode that intercepts standard library calls. It supports batching for datasets larger than GPU memory.

**For web rendering**: 
- **regl-scatterplot**: Best for dedicated 2D scatter plots up to 20M points
- **deck.gl**: Best for geospatial integration and complex multi-layer visualizations
- **Potree/Three.js**: Best for streaming billions of points with LOD

**For production embedding exploration**: Apple's **Embedding Atlas** (2025) uses WebGPU for millions of points at interactive framerates with automatic clustering, labeling, and coordinated metadata views. TensorFlow Embedding Projector remains useful for quick exploration with built-in nearest neighbor search.

---

## Conclusion

Building a knowledge graph embedding visualization system at scale requires integrating multiple techniques: **PaCMAP or PCA-initialized UMAP** for projection, **GPU-accelerated computation** via cuML for training and **WebGL/regl-scatterplot** for rendering, **hierarchical clustering** (HDBSCAN) for automatic structure discovery, and **coordinated multiple views** for handling diverse embedding types.

The most impactful single change for existing t-SNE/UMAP implementations is switching from random to PCA initialization—this alone transforms global structure preservation. For truly large-scale systems, progressive streaming, spatial indexing for interaction, and semantic zooming become essential rather than optional.

The field continues advancing rapidly: WebGPU promises further rendering improvements, and methods like PaCMAP challenge assumptions about the local-global trade-off being fundamental. Systems designed with flexible architecture—separating projection computation from rendering and supporting multiple coordinated views—will adapt most readily to these advances.