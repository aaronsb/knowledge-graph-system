/**
 * Preferences Store
 *
 * User preferences for search display, ingest defaults, and UI options.
 * All preferences are persisted to localStorage.
 */

import { create } from 'zustand';

// Search preferences
export interface SearchPreferences {
  showEvidenceQuotes: boolean;
  showImagesInline: boolean;
  defaultResultLimit: number;
}

// Ingest default settings
export interface IngestDefaults {
  autoApprove: boolean;
  defaultOntology: string;
  defaultChunkSize: number;
  defaultOverlapWords: number;
  defaultProcessingMode: 'serial' | 'parallel';
}

// Display preferences
export interface DisplayPreferences {
  compactMode: boolean;
  enableAnimations: boolean;
  showJobNotifications: boolean;
}

// Complete preferences state
export interface PreferencesState {
  search: SearchPreferences;
  ingest: IngestDefaults;
  display: DisplayPreferences;

  // Actions
  updateSearchPreferences: (prefs: Partial<SearchPreferences>) => void;
  updateIngestDefaults: (prefs: Partial<IngestDefaults>) => void;
  updateDisplayPreferences: (prefs: Partial<DisplayPreferences>) => void;
  resetToDefaults: () => void;
}

// Default values
const DEFAULT_SEARCH: SearchPreferences = {
  showEvidenceQuotes: true,
  showImagesInline: true,
  defaultResultLimit: 20,
};

const DEFAULT_INGEST: IngestDefaults = {
  autoApprove: false,
  defaultOntology: '',
  defaultChunkSize: 1000,
  defaultOverlapWords: 200,
  defaultProcessingMode: 'serial',
};

const DEFAULT_DISPLAY: DisplayPreferences = {
  compactMode: false,
  enableAnimations: true,
  showJobNotifications: true,
};

const STORAGE_KEY = 'kg-preferences';

// Load preferences from localStorage
const loadPreferences = (): {
  search: SearchPreferences;
  ingest: IngestDefaults;
  display: DisplayPreferences;
} => {
  if (typeof window === 'undefined') {
    return {
      search: DEFAULT_SEARCH,
      ingest: DEFAULT_INGEST,
      display: DEFAULT_DISPLAY,
    };
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        search: { ...DEFAULT_SEARCH, ...parsed.search },
        ingest: { ...DEFAULT_INGEST, ...parsed.ingest },
        display: { ...DEFAULT_DISPLAY, ...parsed.display },
      };
    }
  } catch (e) {
    console.warn('Failed to load preferences from localStorage:', e);
  }

  return {
    search: DEFAULT_SEARCH,
    ingest: DEFAULT_INGEST,
    display: DEFAULT_DISPLAY,
  };
};

// Save preferences to localStorage
const savePreferences = (state: {
  search: SearchPreferences;
  ingest: IngestDefaults;
  display: DisplayPreferences;
}) => {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save preferences to localStorage:', e);
  }
};

export const usePreferencesStore = create<PreferencesState>((set, get) => {
  const initial = loadPreferences();

  return {
    search: initial.search,
    ingest: initial.ingest,
    display: initial.display,

    updateSearchPreferences: (prefs) => {
      set((state) => {
        const newSearch = { ...state.search, ...prefs };
        const newState = { search: newSearch, ingest: state.ingest, display: state.display };
        savePreferences(newState);
        return { search: newSearch };
      });
    },

    updateIngestDefaults: (prefs) => {
      set((state) => {
        const newIngest = { ...state.ingest, ...prefs };
        const newState = { search: state.search, ingest: newIngest, display: state.display };
        savePreferences(newState);
        return { ingest: newIngest };
      });
    },

    updateDisplayPreferences: (prefs) => {
      set((state) => {
        const newDisplay = { ...state.display, ...prefs };
        const newState = { search: state.search, ingest: state.ingest, display: newDisplay };
        savePreferences(newState);
        return { display: newDisplay };
      });
    },

    resetToDefaults: () => {
      const defaults = {
        search: DEFAULT_SEARCH,
        ingest: DEFAULT_INGEST,
        display: DEFAULT_DISPLAY,
      };
      savePreferences(defaults);
      set(defaults);
    },
  };
});
