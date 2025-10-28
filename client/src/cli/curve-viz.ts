/**
 * Aggressiveness Curve Visualization
 *
 * Utilities for plotting Bezier curves showing vocabulary aggressiveness.
 */

import * as asciichart from 'asciichart';

/**
 * Calculate a point on a cubic Bezier curve
 *
 * Bezier curve formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
 * where P₀=(0,0), P₁=(x1,y1), P₂=(x2,y2), P₃=(1,1)
 *
 * @param t - Parameter from 0 to 1
 * @param x1 - Control point 1 X coordinate
 * @param y1 - Control point 1 Y coordinate
 * @param x2 - Control point 2 X coordinate
 * @param y2 - Control point 2 Y coordinate
 * @returns [x, y] coordinates on the curve
 */
function bezierPoint(
  t: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number
): [number, number] {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  // P₀ = (0, 0), P₃ = (1, 1)
  const x = 3 * mt2 * t * x1 + 3 * mt * t2 * x2 + t3;
  const y = 3 * mt2 * t * y1 + 3 * mt * t2 * y2 + t3;

  return [x, y];
}

/**
 * Generate points along a cubic Bezier curve
 *
 * @param x1 - Control point 1 X coordinate (0-1)
 * @param y1 - Control point 1 Y coordinate
 * @param x2 - Control point 2 X coordinate (0-1)
 * @param y2 - Control point 2 Y coordinate
 * @param points - Number of points to generate (default: 50)
 * @returns Array of Y values (aggressiveness 0-100%) for plotting
 */
export function generateBezierCurve(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  points: number = 50
): number[] {
  const curve: number[] = [];

  for (let i = 0; i < points; i++) {
    const t = i / (points - 1);
    const [_x, y] = bezierPoint(t, x1, y1, x2, y2);
    // Convert to percentage (0-100)
    curve.push(Math.max(0, Math.min(100, y * 100)));
  }

  return curve;
}

/**
 * Marker for annotating specific positions on a curve
 */
export interface CurveMarker {
  /** Index or normalized position (0-1) on X-axis */
  position: number;
  /** Marker character (e.g., '▼', '│', '●') */
  char: string;
  /** Optional label to display */
  label?: string;
}

/**
 * Configuration for plotting a Bezier curve
 */
export interface CurvePlotConfig {
  /** Number of points to plot (chart width) */
  points?: number;
  /** Chart height in characters */
  height?: number;
  /** Chart color (default: green) */
  color?: any;
  /** Y-axis label format function */
  yLabelFormat?: (y: number) => string;
  /** Markers to display on the curve */
  markers?: CurveMarker[];
  /** Zone labels for X-axis annotations */
  zones?: Array<{ label: string; width: number }>;
}

/**
 * Plot a Bezier curve with optional annotations
 *
 * Generic curve plotting function that can be used for any Bezier visualization.
 *
 * @param x1 - Control point 1 X coordinate (0-1)
 * @param y1 - Control point 1 Y coordinate
 * @param x2 - Control point 2 X coordinate (0-1)
 * @param y2 - Control point 2 Y coordinate
 * @param config - Plot configuration
 * @returns ASCII chart string with annotations
 */
export function plotBezierCurve(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  config: CurvePlotConfig = {}
): string {
  const points = config.points || 60;
  const height = config.height || 12;
  const yFormat = config.yLabelFormat || ((y: number) => y.toFixed(0).padStart(4) + '%');
  const markers = config.markers || [];
  const zones = config.zones || [];

  // Generate curve data
  const curve = generateBezierCurve(x1, y1, x2, y2, points);

  // Build chart
  const chartConfig: any = {
    height,
    width: points,
    format: yFormat,
    colors: [config.color || asciichart.green]
  };

  const chart = asciichart.plot([curve], chartConfig);
  const lines = chart.split('\n');

  // Add marker line if markers provided
  if (markers.length > 0) {
    const markerLine = ' '.repeat(6) + // Left padding for Y-axis labels
      Array.from({ length: points }, (_, i) => {
        const marker = markers.find(m => {
          const pos = m.position <= 1 ? Math.floor(m.position * (points - 1)) : m.position;
          return Math.floor(pos) === i;
        });
        return marker ? marker.char : ' ';
      }).join('');
    lines.push(markerLine);

    // Add labels line if any markers have labels
    if (markers.some(m => m.label)) {
      const labelParts: string[] = [];
      labelParts.push(' '.repeat(6)); // Left padding

      // Sort markers by position for sequential label placement
      const sortedMarkers = [...markers].sort((a, b) => a.position - b.position);
      let lastPos = 0;

      sortedMarkers.forEach(marker => {
        if (marker.label) {
          const pos = marker.position <= 1
            ? Math.floor(marker.position * (points - 1))
            : marker.position;
          const padding = Math.max(0, pos - lastPos);
          labelParts.push(' '.repeat(padding) + marker.label);
          lastPos = pos + marker.label.length;
        }
      });

      lines.push(labelParts.join(''));
    }
  }

  // Add zone labels if provided
  if (zones.length > 0) {
    const zoneLine = ' '.repeat(6) +
      zones.map(z => z.label.padEnd(z.width)).join('');
    lines.push(zoneLine);
  }

  return lines.join('\n');
}

/**
 * Generate a compact curve summary for display
 */
export function formatCurveSummary(profile: {
  profile_name: string;
  control_x1: number;
  control_y1: number;
  control_x2: number;
  control_y2: number;
  description?: string;
}): string {
  const points = `(${profile.control_x1.toFixed(2)}, ${profile.control_y1.toFixed(2)}) → (${profile.control_x2.toFixed(2)}, ${profile.control_y2.toFixed(2)})`;
  return `${profile.profile_name} ${points}`;
}
