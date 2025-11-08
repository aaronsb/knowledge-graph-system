/**
 * Rich Color Scheme for Graph Visualization
 * Using ansis for enhanced terminal styling
 */

import ansis from 'ansis';

/**
 * Concept colors - vibrant colors for different similarity levels
 */
export const concept = {
  // High similarity (90-100%)
  high: ansis.bold.hex('#00FF87'),  // Bright green
  // Good similarity (70-90%)
  good: ansis.hex('#00D7FF'),       // Cyan
  // Medium similarity (50-70%)
  medium: ansis.hex('#FFD700'),     // Gold
  // Low similarity (<50%)
  low: ansis.hex('#FF8787'),        // Light red

  // Concept label emphasis
  label: ansis.bold.hex('#B4F8C8'),
  id: ansis.dim.hex('#87CEEB'),
  searchTerms: ansis.italic.hex('#DDA0DD'),
};

/**
 * Relationship type colors - color-coded by semantic meaning
 */
export const relationship = {
  IMPLIES: ansis.bold.hex('#00FF00'),       // Green - positive connection
  SUPPORTS: ansis.bold.hex('#00D7AF'),      // Teal - reinforcement
  CONTRADICTS: ansis.bold.hex('#FF5F5F'),   // Red - conflict
  RELATES_TO: ansis.hex('#FFD700'),         // Gold - general connection
  CAUSES: ansis.bold.hex('#FF8C00'),        // Dark orange - causation
  REQUIRES: ansis.hex('#9370DB'),           // Purple - dependency
  INCLUDES: ansis.hex('#87CEEB'),           // Sky blue - containment

  // Generic fallback
  default: ansis.hex('#FFFFFF'),
};

/**
 * Path visualization colors
 */
export const path = {
  node: ansis.bold.hex('#B4F8C8'),
  arrow: ansis.dim.hex('#666666'),
  hop: ansis.italic.hex('#87CEEB'),
  distance: ansis.bold.hex('#FFD700'),
};

/**
 * Evidence/Instance colors
 */
export const evidence = {
  quote: ansis.italic.hex('#E6E6FA'),       // Lavender - quoted text
  document: ansis.bold.hex('#87CEEB'),      // Sky blue - source
  paragraph: ansis.dim.hex('#A9A9A9'),      // Gray - metadata
  count: ansis.hex('#00D7AF'),              // Teal - count
};

/**
 * Status colors
 */
export const status = {
  success: ansis.bold.hex('#00FF87'),       // Bright green
  warning: ansis.bold.hex('#FFD700'),       // Gold
  error: ansis.bold.hex('#FF5F5F'),         // Red
  info: ansis.hex('#00D7FF'),               // Cyan
  dim: ansis.dim.hex('#808080'),            // Gray
};

/**
 * Database stats colors
 */
export const stats = {
  label: ansis.bold.hex('#00D7FF'),         // Cyan
  value: ansis.hex('#00FF87'),              // Bright green
  section: ansis.bold.underline.hex('#FFD700'),  // Gold with underline
  count: ansis.hex('#B4F8C8'),
};

/**
 * UI elements
 */
export const ui = {
  title: ansis.bold.hex('#FFD700'),         // Gold
  subtitle: ansis.hex('#00D7FF'),           // Cyan
  bullet: ansis.hex('#87CEEB'),             // Sky blue
  separator: ansis.dim.hex('#666666'),      // Dark gray
  header: ansis.bold.underline.hex('#B4F8C8'),
  key: ansis.hex('#9370DB'),                // Purple
  value: ansis.hex('#E6E6FA'),              // Lavender
  command: ansis.hex('#228B22'),            // Forest green for commands and options
};

/**
 * Get relationship color by type
 */
export function getRelationshipColor(relType: string): typeof ansis {
  const type = relType.toUpperCase();
  if (type in relationship) {
    return (relationship as any)[type];
  }
  return relationship.default;
}

/**
 * Get concept color by similarity score (0-1)
 */
export function getConceptColor(score: number): typeof ansis {
  if (score >= 0.9) return concept.high;
  if (score >= 0.7) return concept.good;
  if (score >= 0.5) return concept.medium;
  return concept.low;
}

/**
 * Format a percentage with color
 */
export function coloredPercentage(value: number): string {
  const pct = (value * 100).toFixed(1);
  const color = getConceptColor(value);
  return color(`${pct}%`);
}

/**
 * Format a count with color
 */
export function coloredCount(count: number): string {
  if (count === 0) return status.dim(String(count));
  if (count > 100) return status.success(String(count));
  if (count > 10) return stats.count(String(count));
  return stats.value(String(count));
}

/**
 * Create a visual separator
 */
export function separator(length: number = 80, char: string = '─'): string {
  return ui.separator(char.repeat(length));
}

/**
 * Format a box around text
 */
export function box(title: string, content: string[]): string {
  const width = 80;
  const lines: string[] = [];

  lines.push(ui.separator('┌' + '─'.repeat(width - 2) + '┐'));
  lines.push(ui.separator('│ ') + ui.title(title) + ui.separator(' '.repeat(width - title.length - 4) + '│'));
  lines.push(ui.separator('├' + '─'.repeat(width - 2) + '┤'));

  content.forEach(line => {
    const strippedLength = line.replace(/\x1b\[[0-9;]*m/g, '').length;
    const padding = ' '.repeat(Math.max(0, width - strippedLength - 4));
    lines.push(ui.separator('│ ') + line + padding + ui.separator('│'));
  });

  lines.push(ui.separator('└' + '─'.repeat(width - 2) + '┘'));

  return lines.join('\n');
}
