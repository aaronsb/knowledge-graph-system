/**
 * Position seeding for the unified rendering engine.
 *
 * The engine owns a single Float32Array of length 3N holding x,y,z for
 * every node, shared by the simulation and the renderer. M1 static mode
 * seeds it once; M2 (CPU/GPU force sim) mutates it in place each frame.
 * z is always present — 2D mode (phase 2) will clamp z to 0 rather than
 * carry a separate buffer shape.
 */

/** Seed N positions uniformly inside a sphere.  @verified c17bbeb9 */
export function seedSpherePositions(count: number, radius = 120): Float32Array {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    const r = radius * Math.cbrt(Math.random());
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);
  }
  return positions;
}

/** Radius heuristic — grows gently with node count so graphs stay visible.  @verified c17bbeb9 */
export function defaultSeedRadius(count: number): number {
  return Math.max(120, Math.cbrt(count) * 15);
}
