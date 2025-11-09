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
 */
export function formatAuthenticatedDiversity(authDiv: number | undefined | null): { emoji: string; label: string; percentage: string; color: string } | null {
  if (authDiv === undefined || authDiv === null) return null;

  const percentage = `${authDiv >= 0 ? '+' : ''}${(Math.abs(authDiv) * 100).toFixed(1)}%`;

  let color: string;
  let emoji: string;
  let label: string;

  if (authDiv > 0.3) {
    color = '#22c55e'; // green
    emoji = '✅';
    label = 'Diverse Support';
  } else if (authDiv > 0) {
    color = '#84cc16'; // lime
    emoji = '✓';
    label = 'Some Support';
  } else if (authDiv > -0.3) {
    color = '#eab308'; // yellow
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
