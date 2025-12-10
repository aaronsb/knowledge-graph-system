/**
 * Theme Harmony System
 *
 * Computes color harmony based on mode (dark/twilight/light) and user-selected
 * hue/saturation values. The mode provides soft guidance rather than hard rules:
 * - Mode sets lightness constraints and foreground lightness
 * - User controls hue and saturation independently for bg and fg
 * - Primary accent color remains fully user-controlled
 *
 * Based on experimental theme from postmodern-ui.html
 */

// Mode configuration - defines how each mode influences colors
export interface ModeConfig {
  // Available lightness stops for background picker
  lightStops: number[];
  // Default lightness for this mode
  defaultLight: number;
  // Minimum saturation (twilight needs visible color)
  bgMinSat?: number;

  // Foreground computation
  fgLightness: number;

  // Surface stepping (how much lighter/darker each level)
  surfaceStep: number;

  // Border contrast relative to background
  borderStep: number;

  // Saturation multiplier for surfaces
  surfaceSatMult: number;

  // Approximate contrast ratio (for display)
  contrastRatio: string;
}

export const modeConfigs: Record<string, ModeConfig> = {
  dark: {
    // Lightness range for dark mode - very low values
    lightStops: [5, 8, 10, 12, 15, 18],
    defaultLight: 10,

    // Foreground: bright for high contrast
    fgLightness: 85,

    // Surface stepping (lighter for elevation)
    surfaceStep: 3,

    // Border contrast
    borderStep: 12,

    // Neutral saturation on surfaces
    surfaceSatMult: 1.0,

    contrastRatio: '~12:1',
  },

  twilight: {
    // Lightness range for twilight - medium darks with warmth
    lightStops: [12, 16, 20, 25, 30, 35],
    defaultLight: 16,
    bgMinSat: 15, // Ensure visible warmth

    // Foreground: near-white, crisp
    fgLightness: 96,

    surfaceStep: 5,
    borderStep: 15,
    surfaceSatMult: 1.2, // Slightly more saturated surfaces

    contrastRatio: '~12:1',
  },

  light: {
    // Lightness range for light mode - high values
    lightStops: [88, 90, 92, 94, 96, 98],
    defaultLight: 94,

    // Foreground: dark for contrast
    fgLightness: 15,

    // Surface stepping (darker for depth)
    surfaceStep: -3,
    borderStep: -15,
    surfaceSatMult: 0.8,

    contrastRatio: '~12:1',
  },
};

// Shared color settings (persist across mode changes)
export interface SharedColorSettings {
  // Background tone (hue and saturation shared, lightness per-mode)
  bgHue: number;
  bgSat: number;

  // Foreground/text tone (lightness is mode-controlled)
  fgHue: number;
  fgSat: number;

  // Primary accent (fully shared)
  primaryHue: number;
  primarySat: number;
  primaryLight: number;
}

// Per-mode lightness settings
export interface ModeLightnessSettings {
  dark: number;
  twilight: number;
  light: number;
}

// Combined settings for storage and use
export interface ColorSettings {
  shared: SharedColorSettings;
  lightness: ModeLightnessSettings;
}

// Computed harmony result
export interface ColorHarmony {
  bg: { h: number; s: number; l: number };
  fg: { h: number; s: number; l: number };
  border: { h: number; s: number; l: number };
  surface: { h: number; s: number };
  surfaceStep: number;
  contrastRatio: string;
}

// Default shared settings
export const defaultSharedSettings: SharedColorSettings = {
  bgHue: 18,
  bgSat: 8,
  fgHue: 18,
  fgSat: 15,
  primaryHue: 18,
  primarySat: 100,
  primaryLight: 60,
};

// Default lightness per mode
export const defaultLightnessSettings: ModeLightnessSettings = {
  dark: 10,
  twilight: 16,
  light: 94,
};

// Default combined settings
export const defaultColorSettings: ColorSettings = {
  shared: { ...defaultSharedSettings },
  lightness: { ...defaultLightnessSettings },
};

/**
 * Compute color harmony based on mode and user settings
 */
export function computeHarmony(
  mode: string,
  settings: ColorSettings
): ColorHarmony {
  const config = modeConfigs[mode] || modeConfigs.dark;
  const { shared, lightness } = settings;

  // Get lightness for current mode
  const bgLight = lightness[mode as keyof ModeLightnessSettings] ?? config.defaultLight;

  // Background: use user-controlled values
  let effectiveBgSat = shared.bgSat;

  // Enforce minimum saturation if specified (twilight needs visible color)
  if (config.bgMinSat !== undefined) {
    effectiveBgSat = Math.max(effectiveBgSat, config.bgMinSat);
  }

  // Apply surface saturation multiplier
  const surfaceSat = effectiveBgSat * config.surfaceSatMult;

  // Compute border lightness
  const borderL = bgLight + config.borderStep;

  return {
    bg: {
      h: shared.bgHue,
      s: effectiveBgSat,
      l: bgLight,
    },
    fg: {
      h: shared.fgHue,
      s: shared.fgSat,
      l: config.fgLightness,
    },
    border: {
      h: shared.bgHue,
      s: effectiveBgSat + 2,
      l: Math.max(5, Math.min(95, borderL)),
    },
    surface: {
      h: shared.bgHue,
      s: surfaceSat,
    },
    surfaceStep: config.surfaceStep,
    contrastRatio: config.contrastRatio,
  };
}

/**
 * Apply harmony to CSS custom properties
 */
export function applyHarmonyToCSS(harmony: ColorHarmony, primary: { h: number; s: number; l: number }) {
  const root = document.documentElement;

  // Background
  root.style.setProperty('--bg-h', String(harmony.bg.h));
  root.style.setProperty('--bg-s', `${harmony.bg.s}%`);
  root.style.setProperty('--bg-l', `${harmony.bg.l}%`);

  // Foreground
  root.style.setProperty('--fg-h', String(harmony.fg.h));
  root.style.setProperty('--fg-s', `${harmony.fg.s}%`);
  root.style.setProperty('--fg-l', `${harmony.fg.l}%`);

  // Border
  root.style.setProperty('--border-h', String(harmony.border.h));
  root.style.setProperty('--border-s', `${harmony.border.s}%`);
  root.style.setProperty('--border-l', `${harmony.border.l}%`);

  // Surface
  root.style.setProperty('--surface-s', `${harmony.surface.s}%`);
  root.style.setProperty('--surface-step', `${harmony.surfaceStep}%`);

  // Primary accent
  root.style.setProperty('--primary-h', String(primary.h));
  root.style.setProperty('--primary-s', `${primary.s}%`);
  root.style.setProperty('--primary-l', `${primary.l}%`);
}

/**
 * Convert HSL to hex color string
 */
export function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color)
      .toString(16)
      .padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`.toUpperCase();
}

// localStorage key for color settings
const STORAGE_KEY = 'kg-color-settings';

/**
 * Load color settings from localStorage
 */
export function loadColorSettings(): ColorSettings | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Validate it has the expected structure
      if (parsed?.shared && parsed?.lightness) {
        return parsed;
      }
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

/**
 * Save color settings to localStorage
 */
export function saveColorSettings(settings: ColorSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

/**
 * Clear color settings from localStorage
 */
export function clearColorSettings() {
  localStorage.removeItem(STORAGE_KEY);
}
