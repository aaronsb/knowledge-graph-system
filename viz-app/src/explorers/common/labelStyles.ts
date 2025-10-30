/**
 * Shared Label Styling System
 *
 * Provides consistent text rendering styles across 2D and 3D explorers.
 * Centralizes font families, colors, stroke styles, and text transformations.
 *
 * NOTE: 2D (SVG) and 3D (Canvas) have different rendering approaches:
 * - 2D uses SVG text elements with D3 color transforms
 * - 3D uses canvas textures with THREE.js color math
 *
 * This module provides utilities for both approaches while maintaining visual consistency.
 */

import * as THREE from 'three';
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
 * 2D (SVG) label styling configuration
 */
export const LABEL_STYLE_2D = {
  edge: {
    fontWeight: LABEL_FONTS.weights.edge2D,
    fillBrightness: 0.4,       // D3 brighter(0.4) - increases lightness by 40%
    strokeColor: '#1a1a2e',    // Dark blue/black
    strokeWidth: 0.5,
    paintOrder: 'stroke',      // Render stroke first, then fill
  },
  node: {
    fontWeight: LABEL_FONTS.weights.node2D,
    fillColor: '#fff',         // White text
    strokeColor: '#000',       // Black outline
    strokeWidth: 0.3,
    paintOrder: 'stroke',      // Render stroke first, then fill
  },
} as const;

/**
 * 3D (Canvas) label styling configuration
 */
export const LABEL_STYLE_3D = {
  edge: {
    fontWeight: LABEL_FONTS.weights.edge3D,
    fillBrightness: 1.4,       // THREE multiplyScalar(1.4) - 40% brighter
    strokeDarkness: 0.4,       // THREE multiplyScalar(0.4) - 60% darker
    strokeWidth: 1,            // Will be scaled by canvasScale (4x)
  },
  node: {
    fontWeight: LABEL_FONTS.weights.node3D,
    fillBrightness: 1.6,       // THREE multiplyScalar(1.6) - 60% brighter for visibility in 3D
    strokeColor: 'rgba(0, 0, 0, 0.8)',
    strokeWidth: 3,            // Will be scaled by canvasScale (4x)
  },
} as const;

// Legacy exports for backward compatibility
export const EDGE_LABEL_STYLE = LABEL_STYLE_3D.edge;
export const NODE_LABEL_STYLE = LABEL_STYLE_3D.node;

/**
 * Color transformation utilities
 */
export const ColorTransform = {
  /**
   * Brighten a color by a multiplier (clamped to valid RGB range)
   */
  brighten(color: string, multiplier: number): string {
    const threeColor = new THREE.Color(color);
    const brightened = threeColor.clone().multiplyScalar(multiplier);

    // Clamp RGB components to [0, 1]
    brightened.r = Math.min(1, brightened.r);
    brightened.g = Math.min(1, brightened.g);
    brightened.b = Math.min(1, brightened.b);

    return `rgb(${Math.floor(brightened.r * 255)}, ${Math.floor(brightened.g * 255)}, ${Math.floor(brightened.b * 255)})`;
  },

  /**
   * Darken a color by a multiplier
   */
  darken(color: string, multiplier: number): string {
    const threeColor = new THREE.Color(color);
    const darkened = threeColor.clone().multiplyScalar(multiplier);

    return `rgb(${Math.floor(darkened.r * 255)}, ${Math.floor(darkened.g * 255)}, ${Math.floor(darkened.b * 255)})`;
  },
};

/**
 * Apply edge label styling to a canvas context
 */
export function applyEdgeLabelStyle(
  ctx: CanvasRenderingContext2D,
  baseColor: string,
  fontSize: number
): void {
  const scale = LABEL_RENDERING.canvasScale;

  // Set font
  ctx.font = `${EDGE_LABEL_STYLE.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
  ctx.textAlign = LABEL_RENDERING.textAlign;
  ctx.textBaseline = LABEL_RENDERING.textBaseline;

  // Set colors
  ctx.fillStyle = ColorTransform.brighten(baseColor, EDGE_LABEL_STYLE.fillBrightness);
  ctx.strokeStyle = ColorTransform.darken(baseColor, EDGE_LABEL_STYLE.strokeDarkness);
  ctx.lineWidth = EDGE_LABEL_STYLE.strokeWidth * scale;
}

/**
 * Apply node label styling to a canvas context
 */
export function applyNodeLabelStyle(
  ctx: CanvasRenderingContext2D,
  baseColor: string,
  fontSize: number
): void {
  const scale = LABEL_RENDERING.canvasScale;

  // Set font
  ctx.font = `${NODE_LABEL_STYLE.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
  ctx.textAlign = LABEL_RENDERING.textAlign;
  ctx.textBaseline = LABEL_RENDERING.textBaseline;

  // Set colors
  ctx.fillStyle = ColorTransform.brighten(baseColor, NODE_LABEL_STYLE.fillBrightness);
  ctx.strokeStyle = NODE_LABEL_STYLE.strokeColor;
  ctx.lineWidth = NODE_LABEL_STYLE.strokeWidth * scale;
}

/**
 * Measure text dimensions with proper font settings
 */
export function measureText(
  text: string,
  fontSize: number,
  fontWeight: number = LABEL_FONTS.weights.edge
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
