/**
 * Theme Harmony Hook
 *
 * Initializes and applies color harmony settings on app startup.
 * Should be called once at the app root level.
 */

import { useEffect } from 'react';
import { useThemeStore } from '../store/themeStore';
import {
  loadColorSettings,
  defaultColorSettings,
  computeHarmony,
  applyHarmonyToCSS,
} from '../lib/themeHarmony';

/**
 * Initialize theme harmony on app load.
 * Reads stored color settings from localStorage and applies them.
 */
export function useThemeHarmony() {
  const { appliedTheme } = useThemeStore();

  useEffect(() => {
    // Load stored settings or use defaults
    const settings = loadColorSettings() || defaultColorSettings;

    // Compute and apply harmony
    const harmony = computeHarmony(appliedTheme, settings);
    applyHarmonyToCSS(harmony, {
      h: settings.shared.primaryHue,
      s: settings.shared.primarySat,
      l: settings.shared.primaryLight,
    });
  }, [appliedTheme]);
}
