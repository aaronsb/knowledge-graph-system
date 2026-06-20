---
id: 08.001.E
domain: ai
mode: explanation
---

# Embedding Landscape

Kappa Graph stores concepts, evidence instances, and edge text as high-dimensional vectors. Visualizing those vectors as a 2D map reveals semantic neighborhoods, outliers, and ontological groupings that are invisible in raw graph traversal. This page explains how dimensionality reduction works, which algorithms to use at different scales, and how to compose multiple embedding types into a coherent visualization.

---

## What projection preserves — and what it does not

Dimensionality reduction maps N-dimensional embedding vectors to 2D coordinates while minimizing distortion. No projection is lossless. The two forms of structure that matter most are **local structure** (whether close neighbors in the high-dimensional space remain close in 2D) and **global structure** (whether large-scale cluster relationships survive the collapse).

The algorithm choice matters less than the initialization. A key finding from Kobak & Linderman (Nature Biotechnology, 2021): UMAP's apparent advantage over t-SNE in global structure comes almost entirely from its default spectral initialization. With identical initialization, both algorithms preserve global structure similarly.

The practical consequence: initialize with PCA (first two principal components, scaled to standard deviation 0.0001) or Laplacian eigenmaps regardless of which algorithm you use. Random initialization loses global structure for every method.

---

## Algorithm selection by dataset size and goal

Four algorithms cover the current landscape:

| Method | Local structure | Global structure | Speed | When to use |
|--------|----------------|------------------|-------|-------------|
| t-SNE (FIt-SNE) | Excellent | Poor without PCA init | Medium | Tight cluster identification |
| UMAP | Excellent | Medium | Fast | General purpose, large datasets |
| PaCMAP | Very good | Excellent | Fast | When both structures matter |
| TriMAP | Good | Very good | Very fast | Global structure priority, millions of points |

For Kappa Graph embeddings where semantic neighborhoods (local) and ontological relationships (global) both carry meaning, **PaCMAP or PCA-initialized UMAP** is the recommended starting point.

PaCMAP (Pairwise Controlled Manifold Approximation) uses three point-pair types during optimization: neighbor pairs for local structure, mid-near pairs for global structure in early iterations, and further pairs for repulsion. This design captures both scales without manual tuning and is less sensitive to hyperparameter choices than t-SNE or UMAP.

---

## Scaling past 10K points

The original t-SNE algorithm's O(N²) complexity becomes impractical beyond roughly 10,000 points. Three acceleration tiers extend it further:

**Barnes-Hut t-SNE** (O(N log N)) approximates gradient computations via space-partitioning trees. A trade-off parameter θ (default 0.5) controls the approximation. It handles up to ~500K points before memory access patterns in tree traversal become the bottleneck.

**FIt-SNE** achieves effectively O(N) by interpolating points onto a grid and using Fast Fourier Transform for convolutions. Benchmarks show 30–100x speedups over Barnes-Hut on million-point datasets. Current implementations are limited to 2D output.

**GPU implementations** (cuML, t-SNE-CUDA) deliver the largest speedups — up to 2000x versus scikit-learn in benchmarks, with 10M+ points tractable on consumer hardware. Most GPU implementations also restrict output to 2D.

Dataset size guides the approach:

| Dataset size | Approach | Expected runtime |
|-------------|----------|-----------------|
| < 10K | Barnes-Hut | Seconds |
| 10K – 100K | FIt-SNE or UMAP | Minutes |
| 100K – 1M | FIt-SNE with approximate nearest neighbors, GPU | 1–10 minutes |
| 1M – 10M | t-SNE-CUDA or cuML | 10–30 minutes |
| > 10M | Sampling + GPU, hierarchical strategies | Variable |

---

## Hyperparameter guidance

**For t-SNE:** Set perplexity to approximately N/100 for large datasets, with a floor of 30. Set learning rate to approximately N/12; scikit-learn's `auto` mode uses `max(N / early_exaggeration / 4, 50)`. Note that scikit-learn's learning rate definition is 4× larger than other implementations — account for this when comparing runs.

**For UMAP:** `n_neighbors` controls the local-global balance:
- 2–5: Very local structure, may miss global patterns
- 15–30: Balanced (recommended for most applications)
- 50–100: Emphasizes global structure, loses fine detail

`min_dist` (0.0–1.0) controls cluster tightness:
- 0.0–0.1: Tight, dense clusters for fine structure
- 0.1–0.3: Good group separation (commonly used)
- 0.5+: Dispersed, smoother layout

**Additional global-structure techniques:**
- Late exaggeration: raising the exaggeration coefficient to ~4× late in optimization improves cluster separation
- Multi-scale perplexity: combining multiple perplexity values captures structure at different scales

---

## Hierarchical visualization for large point clouds

At scale, showing every point at once produces unreadable overdraw. Semantic zooming implements three layers: an aggregation layer that shows cluster hulls or centroids at low zoom, a boundary layer that reveals representative samples at medium zoom, and a detail layer that exposes individual points with full metadata at maximum zoom.

**Continuous level-of-detail** eliminates jarring transitions by assigning each point a small random offset to its visibility threshold. Points fade in and out smoothly as the camera moves rather than appearing or disappearing in blocks.

**HDBSCAN** provides automatic hierarchical clustering that can drive these LOD levels. Its condensed tree visualization shows cluster hierarchy with width proportional to point counts. Soft clustering membership probabilities can modulate point saturation: confident assignments appear vivid, uncertain ones desaturated.

---

## Encoding multiple embedding types

Kappa Graph produces three distinct embedding types that benefit from different visual treatments in a shared 2D space:

- **Concepts**: circles, colored by ontological category, sized by degree or importance
- **Evidence instances**: squares (smaller than concepts), colored by source or confidence
- **Edge centroids**: diamonds, positioned between connected concepts
- **Outliers**: triangles in a distinct color, positioned peripherally

For color scales: categorical palettes (Seaborn `deep` or `tab10`) with a limit of 8–12 distinct hues for cluster assignment. Reserve a neutral gray (0.5, 0.5, 0.5) for noise points. For continuous attributes, use perceptually uniform scales — Viridis for general use, Magma for density on dark backgrounds, Cividis for color-vision accessibility.

Handle overplotting in dense regions with alpha blending (start at `alpha = min(1 / sqrt(n_points), 0.8)`) and reduce point size proportionally.

---

## Coordinated views for multi-type embeddings

Forcing concepts, evidence, and edge embeddings into a single projection degrades all three. The preferred architecture separates them into coordinated views with cross-linked selection:

```
┌─────────────────────────────────────────────────────┐
│           MAIN EMBEDDING VIEW (UMAP)                │
│   Concepts (●) + Evidence (■) in joint projection   │
├──────────────┬──────────────┬───────────────────────┤
│  Ontology    │ Edge Text    │ Detail Panel          │
│  Tree View   │ Heatmap      │ (selected metadata)   │
└──────────────┴──────────────┴───────────────────────┘
```

The main view holds a unified embedding space for concepts and evidence — types that are semantically related and benefit from joint projection, with a lightweight alignment layer to reconcile differing embedding dimensionalities. Edge embeddings appear as a similarity heatmap or separate scatter in the secondary panel. Selections in any panel highlight corresponding elements in all others.

---

## Layout strategies for graph-structured data

Pure embedding-based layout ignores structural information in the graph edges. Hybrid approaches combine both signals:

**DR-first, force-refinement**: Apply UMAP or PaCMAP on embeddings for initial 2D positions, then apply constrained force-directed refinement for edge aesthetics and bundling. This preserves embedding semantics while improving graph readability.

**Hierarchical initialization**: Place ontology anchors (high-degree nodes) first using embedding distances, position subordinate nodes within their ontological neighborhoods, then apply Fruchterman-Reingold for within-cluster refinement. This preserves both semantic similarity and ontological hierarchy.

---

## Rendering at scale

SVG and Canvas 2D become impractical as point counts grow. WebGL is required for interactive visualization beyond ~50K points:

| Rendering | Practical interactive ceiling |
|-----------|------------------------------|
| SVG | ~5,000 points |
| Canvas 2D | ~50,000 points |
| WebGL | ~10,000,000 points |

For hover detection at scale, a spatial index reduces O(N) linear search to O(log N). D3's quadtree is the standard choice:

```javascript
const quadtree = d3.quadtree().x(d => d.x).y(d => d.y).addAll(data);
const nearest = quadtree.find(mouseX, mouseY);
```

For GPU-based picking: render the scene to an off-screen framebuffer with each object's ID encoded as a color, then read the pixel under the cursor to identify the selected point.

---

## Implementation libraries

**Dimensionality reduction (CPU):** openTSNE selects Barnes-Hut automatically for < 10K points and FIt-SNE for larger datasets. It supports PCA initialization and can map new points into an existing embedding without recomputing from scratch. umap-learn is the reference UMAP implementation, using numba JIT compilation.

**GPU acceleration:** RAPIDS cuML provides drop-in scikit-learn replacements with 10–80× speedups and batching for datasets that exceed GPU memory.

**Web rendering:** regl-scatterplot handles up to 20M points in 2D scatter with lasso selection and pan/zoom. deck.gl maintains 60 FPS to ~1M points with its ScatterplotLayer and scales further with 3D Tiles streaming. Apple's Embedding Atlas (2025) uses WebGPU for millions of points with automatic clustering and coordinated metadata views.
