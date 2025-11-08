/**
 * Common visual styles and theme for explorers
 * Centralized styling makes it easy to update visuals across all explorers
 */

export const explorerTheme = {
  // Info box styling
  infoBox: {
    background: 'bg-gray-800',
    border: 'border-gray-600',
    shadow: '8px 8px 12px rgba(0, 0, 0, 0.8)',
    textPrimary: 'text-gray-100',
    textSecondary: 'text-gray-400',
    textMuted: 'text-gray-500',
    hoverBg: 'hover:bg-gray-700',
    borderColor: 'rgb(31, 41, 55)', // gray-800 for speech bubble pointer
    minWidth: '280px',
    maxWidth: '400px',
    zIndex: 9999,
  },

  // Panel styling (stats, legend, settings)
  panel: {
    background: 'bg-gray-800/95',
    border: 'border-gray-600',
    borderLine: 'border-b border-gray-700',
    shadow: 'shadow-xl',
    textPrimary: 'text-gray-200',
    textSecondary: 'text-gray-400',
    textMuted: 'text-gray-500',
    zIndex: 10,
  },

  // Context menu styling
  contextMenu: {
    background: 'bg-gray-800',
    border: 'border-gray-600',
    shadow: 'shadow-xl',
    hoverBg: 'hover:bg-gray-700',
    textPrimary: 'text-gray-100',
    zIndex: 10000,
  },

  // Canvas background colors
  canvas: {
    light: '#ffffff',
    dark: '#1a1a2e',
  },

  // Animation durations (ms)
  animation: {
    fast: 150,
    normal: 300,
    slow: 500,
  },
} as const;

export type ExplorerTheme = typeof explorerTheme;
