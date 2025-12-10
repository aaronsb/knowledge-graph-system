/**
 * Theme Harmony Hook
 *
 * Initializes and applies color harmony, fonts, and background settings on app startup.
 * Should be called once at the app root level.
 */

import { useEffect } from 'react';
import { useThemeStore } from '../store/themeStore';
import {
  loadColorSettings,
  defaultColorSettings,
  computeHarmony,
  applyHarmonyToCSS,
  loadFontSettings,
  defaultFontSettings,
  applyFontsToCSS,
  loadBackgroundStyle,
  defaultBackgroundStyle,
  applyBackgroundStyle,
} from '../lib/themeHarmony';

/**
 * Initialize theme harmony on app load.
 * Reads stored color, font, and background settings from localStorage and applies them.
 */
export function useThemeHarmony() {
  const { appliedTheme } = useThemeStore();

  useEffect(() => {
    // Load stored settings or use defaults
    const colorSettings = loadColorSettings() || defaultColorSettings;

    // Compute and apply color harmony
    const harmony = computeHarmony(appliedTheme, colorSettings);
    applyHarmonyToCSS(harmony, {
      h: colorSettings.shared.primaryHue,
      s: colorSettings.shared.primarySat,
      l: colorSettings.shared.primaryLight,
    });

    // Load and apply font settings
    const fontSettings = loadFontSettings() || defaultFontSettings;
    applyFontsToCSS(fontSettings);

    // Load and apply background style
    const bgStyle = loadBackgroundStyle() || defaultBackgroundStyle;
    applyBackgroundStyle(bgStyle);
  }, [appliedTheme]);
}
