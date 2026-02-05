/**
 * Color Scale Utilities
 *
 * Pure color functions for graph visualization, renderer-agnostic.
 * Replaces d3.scaleOrdinal + d3.interpolateTurbo with a lightweight
 * custom implementation.
 */

/**
 * Attempt to approximate the Turbo colormap (same visual as d3.interpolateTurbo).
 * Maps t in [0, 1] to an RGB hex string.
 * Uses the polynomial approximation from the original Turbo paper.
 */
export function interpolateTurbo(t: number): string {
  // Clamp to [0, 1]
  t = Math.max(0, Math.min(1, t));

  // Polynomial coefficients (Anton Mikhailov's Turbo approximation)
  const r = Math.max(0, Math.min(255, Math.round(
    34.61 + t * (1172.33 + t * (-10793.56 + t * (33300.12 + t * (-38394.49 + t * 14825.05))))
  )));
  const g = Math.max(0, Math.min(255, Math.round(
    23.31 + t * (557.33 + t * (1225.33 + t * (-3574.96 + t * (1073.77 + t * 707.56))))
  )));
  const b = Math.max(0, Math.min(255, Math.round(
    27.2 + t * (3211.1 + t * (-15327.97 + t * (27814.0 + t * (-22569.18 + t * 6838.66))))
  )));

  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Create an ordinal color scale mapping domain strings to Turbo ramp colors.
 * Distributes entries evenly across [0.1, 0.9] for good visibility.
 *
 * Returns a lookup function: (key: string) => string (RGB color).
 */
export function createOntologyColorScale(domains: string[]): (key: string) => string {
  const colorMap = new Map<string, string>();

  domains.forEach((domain, i) => {
    const t = domains.length === 1
      ? 0.5
      : 0.1 + (i / (domains.length - 1)) * 0.8;
    colorMap.set(domain, interpolateTurbo(t));
  });

  return (key: string) => colorMap.get(key) || interpolateTurbo(0.5);
}
