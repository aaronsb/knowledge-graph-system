/**
 * Common visual styles and theme for explorers
 * Centralized styling makes it easy to update visuals across all explorers
 *
 * NOTE: Components now use Tailwind's dark mode classes directly.
 * This file serves as a reference for theme-aware patterns.
 */

export const explorerTheme = {
  // Info box styling (theme-aware via CSS variables)
  infoBox: {
    background: 'bg-card',
    border: 'border-border',
    shadow: 'shadow-lg',
    textPrimary: 'text-card-foreground',
    textSecondary: 'text-muted-foreground',
    textMuted: 'text-muted-foreground',
    hoverBg: 'hover:bg-muted',
    minWidth: '280px',
    maxWidth: '400px',
    zIndex: 9999,
  },

  // Panel styling (stats, legend, settings) - theme-aware via CSS variables
  panel: {
    background: 'bg-card/95',
    border: 'border-border',
    borderLine: 'border-b border-border',
    shadow: 'shadow-xl',
    textPrimary: 'text-card-foreground',
    textSecondary: 'text-muted-foreground',
    textMuted: 'text-muted-foreground',
    zIndex: 10,
  },

  // Context menu styling - theme-aware via CSS variables
  contextMenu: {
    background: 'bg-card',
    border: 'border-border',
    shadow: 'shadow-xl',
    hoverBg: 'hover:bg-muted',
    textPrimary: 'text-card-foreground',
    zIndex: 10000,
  },

  // Canvas background - theme-aware (uses CSS variable)
  canvas: {
    light: 'bg-background',
    dark: 'bg-background',
  },

  // 3D Canvas background colors (Three.js backgroundColor prop)
  // Warm charcoal for dark mode to match postmodern theme (hue 18°)
  canvas3D: {
    light: '#ede8e4',  // Warm cream
    dark: '#1f1b19',   // Warm charcoal (hsl 18 8% 11%)
  },

  // 3D Grid colors (Three.js GridHelper colors)
  // Warm tones to match the postmodern theme
  grid3D: {
    light: {
      centerLine: 0xc4b8ac,  // Warm taupe
      gridLines: 0xd4c8bc,   // Lighter warm taupe
    },
    dark: {
      centerLine: 0x3d3532,  // Warm dark brown
      gridLines: 0x2d2825,   // Darker warm brown
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
