/**
 * Category Color Configuration
 *
 * Defines colors for the 11 vocabulary categories used throughout
 * the visualization (edges, arrows, labels, info boxes).
 */

export interface CategoryColorConfig {
  [category: string]: string;
}

/**
 * Default category color palette
 * Based on vocabulary taxonomy with 11 semantic categories
 */
export const DEFAULT_CATEGORY_COLORS: CategoryColorConfig = {
  // Primary categories (most common)
  derivation: '#8b5cf6',    // violet - most common (112 types)
  modification: '#f59e0b',  // amber
  operation: '#3b82f6',     // blue
  interaction: '#22c55e',   // green

  // Secondary categories
  composition: '#ec4899',   // pink
  causation: '#ef4444',     // red
  dependency: '#a855f7',    // purple

  // Tertiary categories (less common)
  logical: '#06b6d4',       // cyan
  temporal: '#f97316',      // orange
  semantic: '#84cc16',      // lime
  evidential: '#14b8a6',    // teal

  // Fallback
  default: '#6b7280',       // gray
};

/**
 * Active category colors (can be swapped for custom palettes)
 */
export let categoryColors: CategoryColorConfig = { ...DEFAULT_CATEGORY_COLORS };

/**
 * Update category colors with custom palette
 */
export function setCategoryColors(colors: Partial<CategoryColorConfig>): void {
  categoryColors = { ...DEFAULT_CATEGORY_COLORS, ...colors };
}

/**
 * Reset to default category colors
 */
export function resetCategoryColors(): void {
  categoryColors = { ...DEFAULT_CATEGORY_COLORS };
}

/**
 * Get color for a specific category
 */
export function getCategoryColor(category?: string): string {
  return categoryColors[category || 'default'] || categoryColors.default;
}
