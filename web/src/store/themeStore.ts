/**
 * Theme Store
 *
 * Manages theme state (light/dark/system mode) with localStorage persistence.
 */

import { create } from 'zustand';

type ThemePreference = 'light' | 'dark' | 'system';
type AppliedTheme = 'light' | 'dark';

interface ThemeStore {
  theme: ThemePreference;
  appliedTheme: AppliedTheme;
  setTheme: (theme: ThemePreference) => void;
  toggleTheme: () => void;
}

// Apply theme class to document root
const applyTheme = (theme: AppliedTheme) => {
  if (typeof document === 'undefined') return;

  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
};

// Get system theme preference
const getSystemTheme = (): AppliedTheme => {
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
  if (stored === 'dark' || stored === 'light' || stored === 'system') {
    return stored;
  }

  return 'system';
};

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

    toggleTheme: () => {
      const current = get().appliedTheme;
      const newTheme: ThemePreference = current === 'light' ? 'dark' : 'light';
      get().setTheme(newTheme);
    },
  };
});
