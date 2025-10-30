/**
 * Common utilities for explorers
 */

import * as d3 from 'd3';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { getCategoryColor } from '../../config/categoryColors';

/**
 * Format grounding strength with emoji indicator (matches CLI format)
 */
export function formatGrounding(grounding: number | undefined | null): { emoji: string; label: string; percentage: string; color: string } | null {
  if (grounding === undefined || grounding === null) return null;

  const percentage = (grounding * 100).toFixed(0);

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
    return { emoji: '✓', label: 'Strong', percentage: `${percentage}%`, color };
  } else if (grounding >= 0.4) {
    return { emoji: '⚡', label: 'Moderate', percentage: `${percentage}%`, color };
  } else if (grounding >= 0.0) {
    return { emoji: '◯', label: 'Weak', percentage: `${percentage}%`, color };
  } else if (grounding >= -0.4) {
    return { emoji: '◯', label: 'Contested', percentage: `${percentage}%`, color };
  } else {
    return { emoji: '✗', label: 'Contradicted', percentage: `${percentage}%`, color };
  }
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
