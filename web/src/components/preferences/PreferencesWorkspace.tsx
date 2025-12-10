/**
 * Preferences Workspace
 *
 * User preferences interface with tabbed navigation.
 * All preferences are persisted to localStorage for future database sync.
 */

import React, { useState } from 'react';
import {
  Settings,
  Palette,
  Search,
  Upload,
  Layout,
  RotateCcw,
} from 'lucide-react';
import { useThemeStore } from '../../store/themeStore';
import { usePreferencesStore } from '../../store/preferencesStore';
import { TabButton } from './components';
import { AppearanceTab } from './AppearanceTab';
import { SearchTab } from './SearchTab';
import { IngestTab } from './IngestTab';
import { DisplayTab } from './DisplayTab';
import type { PreferencesTabType } from './types';

export const PreferencesWorkspace: React.FC = () => {
  const { setTheme } = useThemeStore();
  const { resetToDefaults } = usePreferencesStore();

  const [activeTab, setActiveTab] = useState<PreferencesTabType>('ingest');

  const handleResetAll = () => {
    if (confirm('Reset all preferences to defaults? This includes theme and accent color.')) {
      // Reset preferences store
      resetToDefaults();
      // Reset theme to system
      setTheme('system');
      // Clear accent color from localStorage
      localStorage.removeItem('kg-accent-color');
      // Reset CSS variables to defaults
      document.documentElement.style.setProperty('--primary-h', '18');
      document.documentElement.style.setProperty('--primary-s', '100%');
      document.documentElement.style.setProperty('--primary-l', '60%');
    }
  };

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            <h1 className="text-lg font-semibold text-foreground">
              Preferences
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <TabButton
              active={activeTab === 'ingest'}
              onClick={() => setActiveTab('ingest')}
              icon={<Upload className="w-4 h-4" />}
              label="Ingest"
            />
            <TabButton
              active={activeTab === 'search'}
              onClick={() => setActiveTab('search')}
              icon={<Search className="w-4 h-4" />}
              label="Search"
            />
            <TabButton
              active={activeTab === 'display'}
              onClick={() => setActiveTab('display')}
              icon={<Layout className="w-4 h-4" />}
              label="Display"
            />
            <TabButton
              active={activeTab === 'appearance'}
              onClick={() => setActiveTab('appearance')}
              icon={<Palette className="w-4 h-4" />}
              label="Appearance"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Tab Content */}
          {activeTab === 'appearance' && <AppearanceTab />}
          {activeTab === 'search' && <SearchTab />}
          {activeTab === 'ingest' && <IngestTab />}
          {activeTab === 'display' && <DisplayTab />}

          {/* Reset All */}
          <div className="pt-4 border-t border-border">
            <button
              onClick={handleResetAll}
              className="flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Reset all preferences to defaults
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PreferencesWorkspace;
