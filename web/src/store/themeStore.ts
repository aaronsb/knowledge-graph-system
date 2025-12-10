/**
 * Theme Store
 *
 * Manages theme state (light/dark/twilight/system mode) with localStorage persistence.
 * Supports the postmodern warm amber theme with three visual modes.
 */

import { create } from 'zustand';

export type ThemePreference = 'light' | 'dark' | 'twilight' | 'system';
export type AppliedTheme = 'light' | 'dark' | 'twilight';

interface ThemeStore {
  theme: ThemePreference;
  appliedTheme: AppliedTheme;
  setTheme: (theme: ThemePreference) => void;
  cycleTheme: () => void;
}

// All possible theme classes
const THEME_CLASSES = ['dark', 'twilight'] as const;

// Apply theme class to document root
const applyTheme = (theme: AppliedTheme) => {
  if (typeof document === 'undefined') return;

  // Remove all theme classes first
  document.documentElement.classList.remove(...THEME_CLASSES);

  // Add the appropriate class (light mode has no class)
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else if (theme === 'twilight') {
    document.documentElement.classList.add('twilight');
  }
};

// Get system theme preference (maps to light or dark)
const getSystemTheme = (): 'light' | 'dark' => {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

// Resolve theme preference to actual theme
const resolveTheme = (preference: ThemePreference): AppliedTheme => {
  if (preference === 'system') {
    return getSystemTheme();
  }
  return preference;
};

// Get initial theme from localStorage or default to system
const getInitialTheme = (): ThemePreference => {
  if (typeof window === 'undefined') return 'system';

  const stored = localStorage.getItem('kg-theme');
  if (stored === 'dark' || stored === 'light' || stored === 'twilight' || stored === 'system') {
    return stored;
  }

  return 'system';
};

// Theme cycle order: light -> twilight -> dark -> light
const THEME_CYCLE: AppliedTheme[] = ['light', 'twilight', 'dark'];

export const useThemeStore = create<ThemeStore>((set, get) => {
  const initialPreference = getInitialTheme();
  const initialApplied = resolveTheme(initialPreference);

  // Apply initial theme
  applyTheme(initialApplied);

  // Listen for system theme changes
  if (typeof window !== 'undefined') {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', () => {
      const currentPref = get().theme;
      if (currentPref === 'system') {
        const newApplied = getSystemTheme();
        applyTheme(newApplied);
        set({ appliedTheme: newApplied });
      }
    });
  }

  return {
    theme: initialPreference,
    appliedTheme: initialApplied,

    setTheme: (theme: ThemePreference) => {
      localStorage.setItem('kg-theme', theme);
      const applied = resolveTheme(theme);
      applyTheme(applied);
      set({ theme, appliedTheme: applied });
    },

    cycleTheme: () => {
      const current = get().appliedTheme;
      const currentIndex = THEME_CYCLE.indexOf(current);
      const nextIndex = (currentIndex + 1) % THEME_CYCLE.length;
      const nextTheme = THEME_CYCLE[nextIndex];
      get().setTheme(nextTheme);
    },
  };
});
