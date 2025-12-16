/**
 * Common utilities for explorers
 */

import * as d3 from 'd3';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { getCategoryColor } from '../../config/categoryColors';

/**
 * Two-dimensional epistemic model result
 */
export interface GroundingDisplayResult {
  emoji: string;
  label: string;
  confidenceScore: string;  // e.g., "[64% conf]"
  color: string;
}

/**
 * Format grounding with confidence (two-dimensional epistemic model)
 *
 * Uses grounding_display from API if available (3×3 matrix label),
 * otherwise falls back to calculating from raw grounding value.
 *
 * @param grounding - Raw grounding strength (-1.0 to +1.0)
 * @param groundingDisplay - Pre-computed display label from API (e.g., "Well-supported", "Unclear")
 * @param confidenceScore - Numeric confidence (0.0 to 1.0) - data richness metric
 */
export function formatGroundingWithConfidence(
  grounding: number | undefined | null,
  groundingDisplay?: string | null,
  confidenceScore?: number | null
): GroundingDisplayResult | null {
  // If we have grounding_display from API, use it
  if (groundingDisplay) {
    const confStr = confidenceScore !== undefined && confidenceScore !== null
      ? `[${(confidenceScore * 100).toFixed(0)}% conf]`
      : '';

    // Map display labels to emoji and color
    const { emoji, color } = getDisplayStyle(groundingDisplay, grounding);

    return {
      emoji,
      label: groundingDisplay,
      confidenceScore: confStr,
      color,
    };
  }

  // Fallback: compute from raw grounding (legacy behavior)
  if (grounding === undefined || grounding === null) return null;

  const fallback = formatGrounding(grounding);
  if (!fallback) return null;

  const confStr = confidenceScore !== undefined && confidenceScore !== null
    ? `[${(confidenceScore * 100).toFixed(0)}% conf]`
    : '';

  return {
    emoji: fallback.emoji,
    label: fallback.label,
    confidenceScore: confStr,
    color: fallback.color,
  };
}

/**
 * Get emoji and color for a grounding display label
 */
function getDisplayStyle(displayLabel: string, grounding?: number | null): { emoji: string; color: string } {
  const label = displayLabel.toLowerCase();

  // Positive grounding labels
  if (label.includes('well-supported')) {
    return { emoji: '✓', color: '#22c55e' }; // green
  }
  if (label.includes('some support')) {
    return { emoji: '⚡', color: '#84cc16' }; // lime
  }
  if (label.includes('possibly supported')) {
    return { emoji: '◐', color: '#eab308' }; // yellow
  }

  // Neutral/unclear labels
  if (label.includes('balanced')) {
    return { emoji: '⚖', color: '#6b7280' }; // gray
  }
  if (label.includes('unclear')) {
    return { emoji: '◯', color: '#9ca3af' }; // light gray
  }
  if (label.includes('unexplored')) {
    return { emoji: '?', color: '#d1d5db' }; // lighter gray
  }

  // Negative grounding labels
  if (label.includes('contested')) {
    return { emoji: '⚠', color: '#f97316' }; // orange
  }
  if (label.includes('possibly contested')) {
    return { emoji: '◑', color: '#f59e0b' }; // amber
  }
  if (label.includes('unknown')) {
    return { emoji: '?', color: '#d1d5db' }; // lighter gray
  }

  // Fallback: derive from raw grounding if available
  if (grounding !== undefined && grounding !== null) {
    if (grounding >= 0.4) return { emoji: '⚡', color: '#84cc16' };
    if (grounding >= 0.0) return { emoji: '◯', color: '#f97316' };
    if (grounding >= -0.4) return { emoji: '⚠', color: '#ef4444' };
    return { emoji: '✗', color: '#dc2626' };
  }

  return { emoji: '◯', color: '#9ca3af' }; // default gray
}

/**
 * Format grounding strength with emoji indicator (legacy format)
 * @deprecated Use formatGroundingWithConfidence for two-dimensional display
 */
export function formatGrounding(grounding: number | undefined | null): { emoji: string; label: string; percentage: string; color: string } | null {
  if (grounding === undefined || grounding === null) return null;

  const percentValue = grounding * 100;
  // Use ≈ symbol when value is very close to zero but not exactly zero
  const percentage = (Math.abs(percentValue) < 0.1 && percentValue !== 0)
    ? `≈${percentValue >= 0 ? '0' : '-0'}%`
    : `${percentValue.toFixed(1)}%`;

  // Color mapping: green (100%) → yellow (50%) → red (0% or negative)
  let color: string;
  if (grounding >= 0.8) {
    color = '#22c55e'; // green
  } else if (grounding >= 0.6) {
    color = '#84cc16'; // lime
  } else if (grounding >= 0.4) {
    color = '#eab308'; // yellow
  } else if (grounding >= 0.2) {
    color = '#f59e0b'; // amber
  } else if (grounding >= 0.0) {
    color = '#f97316'; // orange
  } else if (grounding >= -0.4) {
    color = '#ef4444'; // red
  } else {
    color = '#dc2626'; // deep red
  }

  if (grounding >= 0.8) {
    return { emoji: '✓', label: 'Strong', percentage, color };
  } else if (grounding >= 0.4) {
    return { emoji: '⚡', label: 'Moderate', percentage, color };
  } else if (grounding >= 0.0) {
    return { emoji: '◯', label: 'Weak', percentage, color };
  } else if (grounding >= -0.4) {
    return { emoji: '◯', label: 'Contested', percentage, color };
  } else {
    return { emoji: '✗', label: 'Contradicted', percentage, color };
  }
}

/**
 * Format diversity score for display (ADR-063)
 */
export function formatDiversity(diversity: number | undefined | null, relatedCount: number | undefined | null): { emoji: string; label: string; percentage: string; count: string; color: string } | null {
  if (diversity === undefined || diversity === null || relatedCount === undefined || relatedCount === null) return null;

  const percentage = `${(diversity * 100).toFixed(1)}%`;
  const count = `${relatedCount} concepts`;

  let color: string;
  if (diversity > 0.6) {
    color = '#22c55e'; // green - very high
  } else if (diversity > 0.4) {
    color = '#84cc16'; // lime - high
  } else if (diversity > 0.2) {
    color = '#eab308'; // yellow - moderate
  } else if (diversity > 0.1) {
    color = '#f59e0b'; // orange - low
  } else {
    color = '#ef4444'; // red - very low
  }

  if (diversity > 0.6) {
    return { emoji: '🌐', label: 'Very High', percentage, count, color };
  } else if (diversity > 0.4) {
    return { emoji: '🌐', label: 'High', percentage, count, color };
  } else if (diversity > 0.2) {
    return { emoji: '◐', label: 'Moderate', percentage, count, color };
  } else if (diversity > 0.1) {
    return { emoji: '◑', label: 'Low', percentage, count, color };
  } else {
    return { emoji: '◯', label: 'Very Low', percentage, count, color };
  }
}

/**
 * Format authenticated diversity for display (ADR-044 + ADR-063)
 *
 * Uses saturation-weighted grounding × diversity calculation.
 * Near-zero values (|authDiv| < 0.05) are "unclear" - grounding too weak to authenticate.
 */
export function formatAuthenticatedDiversity(authDiv: number | undefined | null): { emoji: string; label: string; percentage: string; color: string } | null {
  if (authDiv === undefined || authDiv === null) return null;

  const percentage = `${authDiv >= 0 ? '+' : ''}${(Math.abs(authDiv) * 100).toFixed(1)}%`;

  let color: string;
  let emoji: string;
  let label: string;

  // Near-zero values are "unclear" - grounding too weak to authenticate
  if (Math.abs(authDiv) < 0.05) {
    color = '#9ca3af'; // gray
    emoji = '◯';
    label = 'Unclear';
  } else if (authDiv > 0.3) {
    color = '#22c55e'; // green
    emoji = '✅';
    label = 'Diverse Support';
  } else if (authDiv > 0) {
    color = '#84cc16'; // lime
    emoji = '✓';
    label = 'Some Support';
  } else if (authDiv > -0.3) {
    color = '#f59e0b'; // amber (less alarming than yellow)
    emoji = '⚠';
    label = 'Weak Contradiction';
  } else {
    color = '#ef4444'; // red
    emoji = '❌';
    label = 'Diverse Contradiction';
  }

  return { emoji, label, percentage, color };
}

/**
 * Get brighter color for relationship type text
 * Uses same category colors as edges but +40% brightness
 */
export function getRelationshipTextColor(relationshipType: string): string {
  // Get category from vocabulary store
  const vocabStore = useVocabularyStore.getState();
  const category = vocabStore.getCategory(relationshipType) || 'default';

  // Get base color from shared config
  const baseColor = getCategoryColor(category);
  return d3.color(baseColor)?.brighter(0.4).toString() || baseColor;
}
