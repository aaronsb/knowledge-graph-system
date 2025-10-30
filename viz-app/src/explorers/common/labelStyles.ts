/**
 * Shared Label Styling System
 *
 * Provides consistent text rendering styles across 2D and 3D explorers.
 * Centralizes font families, colors, stroke styles, and text transformations.
 *
 * COLOR PROCESSING PIPELINE:
 * 1. Base color comes from visual settings (node by ontology/degree, edge by category/confidence)
 * 2. Text fill: Increase luminance significantly (toward white for readability)
 * 3. Text stroke: Decrease luminance (toward black for contrast)
 * 4. Explorer-specific scaling applied via settings
 *
 * NOTE: 2D (SVG) and 3D (Canvas) have different rendering approaches but use the same color rules:
 * - 2D uses SVG text elements with D3 color transforms
 * - 3D uses canvas textures with D3 HSL color transforms (rendered to canvas)
 */

import * as d3 from 'd3';

/**
 * Font configuration (shared across 2D and 3D)
 */
export const LABEL_FONTS = {
  // System font stack for cross-platform consistency
  family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',

  // Font weights
  weights: {
    edge2D: 400,   // Regular weight for 2D edge labels
    node2D: 500,   // Medium weight for 2D node labels
    edge3D: 400,   // Regular weight for 3D edge labels
    node3D: 600,   // Semi-bold for 3D node labels (better readability in 3D space)
  },
} as const;

/**
 * Text rendering configuration
 */
export const LABEL_RENDERING = {
  // Canvas scale for high-DPI rendering (4x for crisp text)
  canvasScale: 4,

  // Padding around text in canvas (prevents edge clipping)
  padding: 8,

  // Text alignment
  textAlign: 'center' as CanvasTextAlign,
  textBaseline: 'middle' as CanvasTextBaseline,
} as const;

/**
 * Luminance transformation configuration
 *
 * Controls how base colors are transformed into text fill and stroke colors.
 * Unified across 2D and 3D for visual consistency.
 */
export const LUMINANCE_TRANSFORMS = {
  // Node labels: Very light fill (almost white), dark stroke
  node: {
    fillLuminance: 0.92,       // Target luminance for fill (92% = nearly white)
    strokeLuminance: 0.10,     // Target luminance for stroke (10% = very dark)
  },
  // Edge labels: Lighter fill (readable), darker stroke
  edge: {
    fillLuminance: 0.80,       // Target luminance for fill (80% = light but with color)
    strokeLuminance: 0.20,     // Target luminance for stroke (20% = dark)
  },
} as const;

/**
 * 2D (SVG) label styling configuration
 */
export const LABEL_STYLE_2D = {
  edge: {
    fontWeight: LABEL_FONTS.weights.edge2D,
    strokeWidth: 0.5,
    paintOrder: 'stroke' as const,  // Render stroke first, then fill
  },
  node: {
    fontWeight: LABEL_FONTS.weights.node2D,
    strokeWidth: 0.3,
    paintOrder: 'stroke' as const,  // Render stroke first, then fill
  },
} as const;

/**
 * 3D (Canvas) label styling configuration
 */
export const LABEL_STYLE_3D = {
  edge: {
    fontWeight: LABEL_FONTS.weights.edge3D,
    strokeWidth: 1,            // Will be scaled by canvasScale (4x)
  },
  node: {
    fontWeight: LABEL_FONTS.weights.node3D,
    strokeWidth: 3,            // Will be scaled by canvasScale (4x)
  },
} as const;

/**
 * Color transformation utilities
 *
 * Provides luminance-based color transformations that work consistently
 * across 2D (D3/SVG) and 3D (THREE.js/Canvas) rendering.
 */
export const ColorTransform = {
  /**
   * Adjust luminance of a color to a target value (0-1 range)
   * Preserves hue and saturation while adjusting lightness
   *
   * @param color - Input color (any CSS color format)
   * @param targetLuminance - Target luminance (0=black, 1=white)
   * @returns RGB color string
   */
  setLuminance(color: string, targetLuminance: number): string {
    // Use D3 to convert to HSL (works with any CSS color)
    const d3Color = d3.color(color);
    if (!d3Color) return color; // Fallback if parsing fails

    const hslColor = d3.hsl(d3Color);

    // Set luminance (L component in HSL)
    hslColor.l = Math.max(0, Math.min(1, targetLuminance));

    // Convert back to RGB
    const rgbColor = d3.rgb(hslColor);
    return `rgb(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b})`;
  },

  /**
   * Get label colors (fill and stroke) from a base color
   * Uses luminance transformation rules for consistent appearance
   *
   * @param baseColor - Base color from visual settings (node/edge color)
   * @param type - Label type ('node' or 'edge')
   * @returns Object with fill and stroke colors
   */
  getLabelColors(baseColor: string, type: 'node' | 'edge'): { fill: string; stroke: string } {
    const transforms = LUMINANCE_TRANSFORMS[type];

    return {
      fill: this.setLuminance(baseColor, transforms.fillLuminance),
      stroke: this.setLuminance(baseColor, transforms.strokeLuminance),
    };
  },
};

/**
 * Apply edge label styling to a canvas context
 * Uses luminance-based color transformation for consistent appearance
 */
export function applyEdgeLabelStyle(
  ctx: CanvasRenderingContext2D,
  baseColor: string,
  fontSize: number
): void {
  const scale = LABEL_RENDERING.canvasScale;
  const colors = ColorTransform.getLabelColors(baseColor, 'edge');

  // Set font
  ctx.font = `${LABEL_STYLE_3D.edge.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
  ctx.textAlign = LABEL_RENDERING.textAlign;
  ctx.textBaseline = LABEL_RENDERING.textBaseline;

  // Set colors (from luminance transformation)
  ctx.fillStyle = colors.fill;
  ctx.strokeStyle = colors.stroke;
  ctx.lineWidth = LABEL_STYLE_3D.edge.strokeWidth * scale;
}

/**
 * Apply node label styling to a canvas context
 * Uses luminance-based color transformation for consistent appearance
 */
export function applyNodeLabelStyle(
  ctx: CanvasRenderingContext2D,
  baseColor: string,
  fontSize: number
): void {
  const scale = LABEL_RENDERING.canvasScale;
  const colors = ColorTransform.getLabelColors(baseColor, 'node');

  // Set font
  ctx.font = `${LABEL_STYLE_3D.node.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
  ctx.textAlign = LABEL_RENDERING.textAlign;
  ctx.textBaseline = LABEL_RENDERING.textBaseline;

  // Set colors (from luminance transformation)
  ctx.fillStyle = colors.fill;
  ctx.strokeStyle = colors.stroke;
  ctx.lineWidth = LABEL_STYLE_3D.node.strokeWidth * scale;
}

/**
 * Measure text dimensions with proper font settings
 */
export function measureText(
  text: string,
  fontSize: number,
  fontWeight: number = LABEL_FONTS.weights.edge3D
): { width: number; height: number } {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  const scale = LABEL_RENDERING.canvasScale;

  ctx.font = `${fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
  const metrics = ctx.measureText(text);

  return {
    width: metrics.width,
    height: fontSize * scale,
  };
}

/**
 * Create a canvas sized for text rendering with padding
 */
export function createTextCanvas(textWidth: number, textHeight: number): {
  canvas: HTMLCanvasElement;
  centerX: number;
  centerY: number;
} {
  const canvas = document.createElement('canvas');
  const scale = LABEL_RENDERING.canvasScale;
  const padding = LABEL_RENDERING.padding;

  canvas.width = Math.ceil(textWidth + padding * 2 * scale);
  canvas.height = Math.ceil(textHeight + padding * 2 * scale);

  return {
    canvas,
    centerX: canvas.width / 2,
    centerY: canvas.height / 2,
  };
}
