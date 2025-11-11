/**
 * Common visual styles and theme for explorers
 * Centralized styling makes it easy to update visuals across all explorers
 *
 * NOTE: Components now use Tailwind's dark mode classes directly.
 * This file serves as a reference for theme-aware patterns.
 */

export const explorerTheme = {
  // Info box styling (theme-aware)
  infoBox: {
    background: 'bg-card dark:bg-gray-800',
    border: 'border-border dark:border-gray-600',
    shadow: 'shadow-lg dark:shadow-[8px_8px_12px_rgba(0,0,0,0.8)]',
    textPrimary: 'text-card-foreground dark:text-gray-100',
    textSecondary: 'text-muted-foreground dark:text-gray-400',
    textMuted: 'text-muted-foreground dark:text-gray-500',
    hoverBg: 'hover:bg-muted dark:hover:bg-gray-700',
    minWidth: '280px',
    maxWidth: '400px',
    zIndex: 9999,
  },

  // Panel styling (stats, legend, settings) - theme-aware
  panel: {
    background: 'bg-card/95 dark:bg-gray-800/95',
    border: 'border-border dark:border-gray-600',
    borderLine: 'border-b border-border dark:border-gray-700',
    shadow: 'shadow-xl',
    textPrimary: 'text-card-foreground dark:text-gray-200',
    textSecondary: 'text-muted-foreground dark:text-gray-400',
    textMuted: 'text-muted-foreground dark:text-gray-500',
    zIndex: 10,
  },

  // Context menu styling - theme-aware
  contextMenu: {
    background: 'bg-card dark:bg-gray-800',
    border: 'border-border dark:border-gray-600',
    shadow: 'shadow-xl',
    hoverBg: 'hover:bg-muted dark:hover:bg-gray-700',
    textPrimary: 'text-card-foreground dark:text-gray-100',
    zIndex: 10000,
  },

  // Canvas background - theme-aware gradients
  canvas: {
    light: 'bg-gradient-to-br from-gray-300 to-gray-400',
    dark: 'bg-gradient-to-br from-gray-900 to-black',
  },

  // 3D Canvas background colors (Three.js backgroundColor prop)
  canvas3D: {
    light: '#bcc1c9',
    dark: '#1a1a2e',
  },

  // 3D Grid colors (Three.js GridHelper colors)
  grid3D: {
    light: {
      centerLine: 0xa0a8b0,  // Slightly darker than light background
      gridLines: 0xb0b5bd,   // Very close to light background
    },
    dark: {
      centerLine: 0x2a2a3e,  // Slightly lighter than dark background
      gridLines: 0x20202e,   // Very close to dark background
    },
  },

  // Animation durations (ms)
  animation: {
    fast: 150,
    normal: 300,
    slow: 500,
  },
} as const;

export type ExplorerTheme = typeof explorerTheme;
