/**
 * Preferences Types
 *
 * Shared type definitions for preferences components.
 */

export type PreferencesTabType = 'appearance' | 'search' | 'ingest' | 'display';

// Re-export from stores for convenience
export type { ThemePreference, AppliedTheme } from '../../store/themeStore';
