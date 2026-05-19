/**
 * Principal-component framing — the geometry behind "orient the camera to
 * the best perpendicular tangent to the bulk of the graph".
 *
 * A force layout settles into an irregular blob with a natural broad
 * face. Framing it by its bounding *sphere* (what useFitCamera does today)
 * over-estimates and leaves the graph small; worse, it ignores the blob's
 * shape, so a flat, wide layout is viewed edge-on as often as face-on.
 *
 * pcaFrame finds that shape. It computes the covariance of the point
 * cloud and eigen-decomposes it: the eigenvectors are the cloud's own
 * axes, sorted by variance. The two high-variance axes span the broad
 * face; the lowest-variance (minor) axis is the thinnest direction —
 * looking *along* it puts the camera square to the broad face, which is
 * exactly "perpendicular tangent to the bulk".
 *
 * Hybrid focus (ADR-tracked task #29): orientation and extent are
 * decoupled. Pass the whole visible cloud as the orientation set so the
 * viewing angle stays globally stable, and a subset (a clicked node's
 * neighbourhood) as the extent set so the framing tightens onto that
 * region without spinning the camera. For a whole-graph fit, omit the
 * subset and the two coincide.
 *
 * Pure geometry, no three.js: the camera placement, sign choice, and
 * fill/overscan live in orientAndFrame (task #26). This file only answers
 * "where is the cloud, which way does it face, and how big is the part we
 * want to frame" — and is unit-tested in isolation like positions.ts.
 *
 * @verified f8ee93b9
 */

/** A 3-vector as a plain tuple — keeps this module three.js-free.  @verified f8ee93b9 */
export type Vec3 = [number, number, number];

/** The cloud's intrinsic frame plus the bounds of the part to be framed.  @verified f8ee93b9 */
export interface PcaFrame {
  /** Centroid of the orientation point set, world space. */
  center: Vec3;
  /**
   * Orthonormal eigenvectors of the orientation set's covariance, sorted
   * by variance DESC: [major, mid, minor]. major×mid span the broad
   * face; minor is the thinnest direction — the camera looks along it.
   */
  axes: [Vec3, Vec3, Vec3];
  /** Eigenvalues (variances) parallel to `axes`, DESC. ~0 ⇒ degenerate. */
  variances: [number, number, number];
  /**
   * Bounds of the EXTENT set in the PCA frame: min/max projection of each
   * extent point onto each axis, measured relative to `center` (the
   * orientation centroid, which the extent set need not be centred on).
   * orientAndFrame turns these into a world-space box centre + radius.
   */
  bounds: { min: Vec3; max: Vec3 };
}

/** Number of cyclic Jacobi sweeps — 3×3 symmetric converges well under 10.  @verified f8ee93b9 */
const JACOBI_SWEEPS = 12;

/**
 * Eigen-decompose a symmetric 3×3 matrix via cyclic Jacobi rotation.
 * Returns eigenvalues and column eigenvectors (`vectors[k]` is the k-th
 * eigenvector). Robust on degenerate (planar/linear/point) clouds where a
 * closed-form solver divides by zero — there the zero-variance axes come
 * back as an arbitrary-but-orthonormal basis, which is exactly what a
 * degenerate frame needs.
 *
 * @verified f8ee93b9
 */
function jacobiEigen(m: number[][]): { values: number[]; vectors: Vec3[] } {
  // Working copy of the (symmetric) matrix; a accumulates as it diagonalises.
  const a = [
    [m[0][0], m[0][1], m[0][2]],
    [m[1][0], m[1][1], m[1][2]],
    [m[2][0], m[2][1], m[2][2]],
  ];
  // Eigenvector accumulator, starts as identity.
  const v = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
  ];

  for (let sweep = 0; sweep < JACOBI_SWEEPS; sweep++) {
    // Zero the largest off-diagonal each (p,q) in the upper triangle.
    for (let p = 0; p < 2; p++) {
      for (let q = p + 1; q < 3; q++) {
        const apq = a[p][q];
        if (Math.abs(apq) < 1e-12) continue;
        const app = a[p][p];
        const aqq = a[q][q];
        // Rotation angle that annihilates a[p][q].
        const phi = 0.5 * Math.atan2(2 * apq, aqq - app);
        const c = Math.cos(phi);
        const s = Math.sin(phi);

        // a := Rᵀ a R, exploiting symmetry (only p,q rows/cols change).
        for (let k = 0; k < 3; k++) {
          const akp = a[k][p];
          const akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < 3; k++) {
          const apk = a[p][k];
          const aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        // Accumulate the rotation into the eigenvectors.
        for (let k = 0; k < 3; k++) {
          const vkp = v[k][p];
          const vkq = v[k][q];
          v[k][p] = c * vkp - s * vkq;
          v[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }

  const values = [a[0][0], a[1][1], a[2][2]];
  // Columns of v are the eigenvectors.
  const vectors: Vec3[] = [
    [v[0][0], v[1][0], v[2][0]],
    [v[0][1], v[1][1], v[2][1]],
    [v[0][2], v[1][2], v[2][2]],
  ];
  return { values, vectors };
}

/** Project (x,y,z) minus origin onto a unit axis.  @verified f8ee93b9 */
function project(
  x: number,
  y: number,
  z: number,
  ox: number,
  oy: number,
  oz: number,
  axis: Vec3
): number {
  return (x - ox) * axis[0] + (y - oy) * axis[1] + (z - oz) * axis[2];
}

/**
 * Compute the PCA frame of a point cloud.
 *
 * `positions` is a flat xyz buffer (length ≥ 3·N). `orientIndices`
 * selects the points whose covariance defines the viewing axes — pass
 * the whole visible graph for a globally-stable angle. `extentIndices`
 * selects the points to actually frame (e.g. a node's neighbourhood);
 * omit it to frame the orientation set itself. Indices are *node*
 * indices (the i-th node is positions[3i..3i+2]); when omitted the set
 * is all of `0..count-1` where count = positions.length/3.
 *
 * Degenerate inputs (0–1 points, or a perfectly co-planar/linear cloud)
 * return an orthonormal basis with zero variances on the collapsed axes
 * and bounds reduced to the points' actual spread; orientAndFrame floors
 * the resulting radius so the camera still gets a sane frame.
 *
 * @verified f8ee93b9
 */
export function pcaFrame(
  positions: Float32Array | number[],
  orientIndices?: ArrayLike<number>,
  extentIndices?: ArrayLike<number>
): PcaFrame {
  const count = Math.floor(positions.length / 3);
  const orient = orientIndices ?? defaultRange(count);
  const extent = extentIndices ?? orient;
  const nOrient = orient.length;

  // Centroid of the orientation set.
  let cx = 0;
  let cy = 0;
  let cz = 0;
  for (let k = 0; k < nOrient; k++) {
    const i = orient[k];
    cx += positions[i * 3];
    cy += positions[i * 3 + 1];
    cz += positions[i * 3 + 2];
  }
  if (nOrient > 0) {
    cx /= nOrient;
    cy /= nOrient;
    cz /= nOrient;
  }
  const center: Vec3 = [cx, cy, cz];

  // Covariance (symmetric; population form — scale is irrelevant to the
  // eigenvectors and we never compare variances across different clouds).
  let xx = 0;
  let xy = 0;
  let xz = 0;
  let yy = 0;
  let yz = 0;
  let zz = 0;
  for (let k = 0; k < nOrient; k++) {
    const i = orient[k];
    const dx = positions[i * 3] - cx;
    const dy = positions[i * 3 + 1] - cy;
    const dz = positions[i * 3 + 2] - cz;
    xx += dx * dx;
    xy += dx * dy;
    xz += dx * dz;
    yy += dy * dy;
    yz += dy * dz;
    zz += dz * dz;
  }
  const inv = nOrient > 0 ? 1 / nOrient : 0;
  const cov = [
    [xx * inv, xy * inv, xz * inv],
    [xy * inv, yy * inv, yz * inv],
    [xz * inv, yz * inv, zz * inv],
  ];

  const { values, vectors } = jacobiEigen(cov);

  // Sort axes by variance DESC → [major, mid, minor].
  const order = [0, 1, 2].sort((p, q) => values[q] - values[p]);
  const axes: [Vec3, Vec3, Vec3] = [
    normalize(vectors[order[0]]),
    normalize(vectors[order[1]]),
    normalize(vectors[order[2]]),
  ];
  const variances: [number, number, number] = [
    Math.max(values[order[0]], 0),
    Math.max(values[order[1]], 0),
    Math.max(values[order[2]], 0),
  ];

  // Bounds of the EXTENT set, projected onto the axes relative to center.
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let k = 0; k < extent.length; k++) {
    const i = extent[k];
    const x = positions[i * 3];
    const y = positions[i * 3 + 1];
    const z = positions[i * 3 + 2];
    for (let ax = 0; ax < 3; ax++) {
      const p = project(x, y, z, cx, cy, cz, axes[ax]);
      if (p < min[ax]) min[ax] = p;
      if (p > max[ax]) max[ax] = p;
    }
  }
  // Empty extent set ⇒ collapse bounds to the centre (zero-size box).
  for (let ax = 0; ax < 3; ax++) {
    if (!Number.isFinite(min[ax])) {
      min[ax] = 0;
      max[ax] = 0;
    }
  }

  return { center, axes, variances, bounds: { min, max } };
}

/** 0..count-1, the implicit "all nodes" index set.  @verified f8ee93b9 */
function defaultRange(count: number): number[] {
  const r = new Array<number>(count);
  for (let i = 0; i < count; i++) r[i] = i;
  return r;
}

/** Unit-length copy; falls back to +X for a zero vector (degenerate axis).  @verified f8ee93b9 */
function normalize(v: Vec3): Vec3 {
  const len = Math.hypot(v[0], v[1], v[2]);
  if (len < 1e-12) return [1, 0, 0];
  return [v[0] / len, v[1] / len, v[2] / len];
}
