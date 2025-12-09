/**
 * PreferencesWorkspace
 *
 * User preferences including theme, search display, ingest defaults, and UI options.
 * All preferences are persisted to localStorage.
 */

import React, { useState, useEffect } from 'react';
import {
  Settings,
  Sun,
  Moon,
  Monitor,
  Palette,
  Search,
  Upload,
  Layout,
  RotateCcw,
  Eye,
  EyeOff,
  Image,
  FileText,
  Zap,
  ListOrdered,
  CheckCircle2,
  Folder,
  Layers,
  Sparkles,
  Bell,
  BellOff,
  Minimize2,
  Maximize2,
} from 'lucide-react';
import { useThemeStore } from '../../store/themeStore';

// Theme preference type (matches themeStore)
type ThemePreference = 'light' | 'dark' | 'system';
import { usePreferencesStore } from '../../store/preferencesStore';
import { apiClient } from '../../api/client';
import type { OntologyItem } from '../../types/ingest';

// Toggle switch component
const Toggle: React.FC<{
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ enabled, onChange, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground dark:text-gray-400">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground dark:text-gray-200">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground dark:text-gray-400">{description}</div>
        )}
      </div>
    </div>
    <button
      onClick={() => onChange(!enabled)}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        ${enabled ? 'bg-primary dark:bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'}
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white transition-transform
          ${enabled ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  </div>
);

// Number input component
const NumberInput: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ value, onChange, min = 1, max = 1000, step = 1, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground dark:text-gray-400">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground dark:text-gray-200">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground dark:text-gray-400">{description}</div>
        )}
      </div>
    </div>
    <input
      type="number"
      value={value}
      onChange={(e) => {
        const v = parseInt(e.target.value, 10);
        if (!isNaN(v) && v >= min && v <= max) {
          onChange(v);
        }
      }}
      min={min}
      max={max}
      step={step}
      className="w-24 px-3 py-1.5 text-sm text-right bg-muted dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg text-card-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
    />
  </div>
);

// Select component
const Select: React.FC<{
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ value, onChange, options, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground dark:text-gray-400">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground dark:text-gray-200">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground dark:text-gray-400">{description}</div>
        )}
      </div>
    </div>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-1.5 text-sm bg-muted dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg text-card-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  </div>
);

// Section component
const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, icon, children }) => (
  <section className="bg-card dark:bg-gray-900 rounded-lg border border-border dark:border-gray-800 overflow-hidden">
    <div className="px-4 py-3 border-b border-border dark:border-gray-800 flex items-center gap-2">
      <span className="text-muted-foreground dark:text-gray-400">{icon}</span>
      <h2 className="font-semibold text-card-foreground dark:text-gray-200">{title}</h2>
    </div>
    <div className="px-4 divide-y divide-border dark:divide-gray-800">{children}</div>
  </section>
);

export const PreferencesWorkspace: React.FC = () => {
  const { theme, setTheme } = useThemeStore();
  const {
    search,
    ingest,
    display,
    updateSearchPreferences,
    updateIngestDefaults,
    updateDisplayPreferences,
    resetToDefaults,
  } = usePreferencesStore();

  // Ontologies for default ontology selector
  const [ontologies, setOntologies] = useState<OntologyItem[]>([]);

  // Load ontologies (only when authenticated)
  useEffect(() => {
    apiClient.listOntologies()
      .then((response) => setOntologies(response.ontologies || []))
      .catch(() => {
        // Silently fail if not authenticated yet
        setOntologies([]);
      });
  }, []);

  const themeOptions: { id: ThemePreference; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'light', label: 'Light', icon: Sun },
    { id: 'dark', label: 'Dark', icon: Moon },
    { id: 'system', label: 'System', icon: Monitor },
  ];

  return (
    <div className="h-full flex flex-col bg-background dark:bg-gray-950">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border dark:border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary dark:text-blue-400" />
            <h1 className="text-lg font-semibold text-foreground dark:text-gray-100">
              Preferences
            </h1>
          </div>
          <button
            onClick={() => {
              if (confirm('Reset all preferences to defaults?')) {
                resetToDefaults();
                setTheme('system');
              }
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground dark:text-gray-400 hover:text-foreground dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Theme */}
          <Section title="Appearance" icon={<Palette className="w-5 h-5" />}>
            <div className="py-3">
              <div className="font-medium text-card-foreground dark:text-gray-200 mb-3">
                Theme
              </div>
              <div className="grid grid-cols-3 gap-2">
                {themeOptions.map((option) => {
                  const Icon = option.icon;
                  const isSelected = theme === option.id;
                  return (
                    <button
                      key={option.id}
                      onClick={() => setTheme(option.id)}
                      className={`
                        flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all
                        ${isSelected
                          ? 'border-primary dark:border-blue-500 bg-primary/10 dark:bg-blue-900/30'
                          : 'border-border dark:border-gray-700 hover:border-primary/50 dark:hover:border-blue-500/50'
                        }
                      `}
                    >
                      <Icon className={`w-5 h-5 ${isSelected ? 'text-primary dark:text-blue-400' : 'text-muted-foreground dark:text-gray-400'}`} />
                      <span className={`text-sm font-medium ${isSelected ? 'text-primary dark:text-blue-400' : 'text-muted-foreground dark:text-gray-400'}`}>
                        {option.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </Section>

          {/* Search Preferences */}
          <Section title="Search Results" icon={<Search className="w-5 h-5" />}>
            <Toggle
              enabled={search.showEvidenceQuotes}
              onChange={(v) => updateSearchPreferences({ showEvidenceQuotes: v })}
              label="Show evidence quotes"
              description="Display supporting quotes from source documents"
              icon={<FileText className="w-4 h-4" />}
            />
            <Toggle
              enabled={search.showImagesInline}
              onChange={(v) => updateSearchPreferences({ showImagesInline: v })}
              label="Show images inline"
              description="Display images directly in search results"
              icon={<Image className="w-4 h-4" />}
            />
            <NumberInput
              value={search.defaultResultLimit}
              onChange={(v) => updateSearchPreferences({ defaultResultLimit: v })}
              min={5}
              max={100}
              step={5}
              label="Default result limit"
              description="Maximum number of results to show"
              icon={<ListOrdered className="w-4 h-4" />}
            />
          </Section>

          {/* Ingest Defaults */}
          <Section title="Ingest Defaults" icon={<Upload className="w-5 h-5" />}>
            <Toggle
              enabled={ingest.autoApprove}
              onChange={(v) => updateIngestDefaults({ autoApprove: v })}
              label="Auto-approve jobs"
              description="Start processing immediately without review"
              icon={<CheckCircle2 className="w-4 h-4" />}
            />
            <Select
              value={ingest.defaultOntology}
              onChange={(v) => updateIngestDefaults({ defaultOntology: v })}
              options={[
                { value: '', label: 'None (select each time)' },
                ...ontologies.map((o) => ({ value: o.name, label: o.name })),
              ]}
              label="Default ontology"
              description="Pre-selected ontology for new ingestions"
              icon={<Folder className="w-4 h-4" />}
            />
            <NumberInput
              value={ingest.defaultChunkSize}
              onChange={(v) => updateIngestDefaults({ defaultChunkSize: v })}
              min={200}
              max={3000}
              step={100}
              label="Default chunk size"
              description="Target words per chunk (200-3000)"
              icon={<Layers className="w-4 h-4" />}
            />
            <Select
              value={ingest.defaultProcessingMode}
              onChange={(v) => updateIngestDefaults({ defaultProcessingMode: v as 'serial' | 'parallel' })}
              options={[
                { value: 'serial', label: 'Serial (reliable)' },
                { value: 'parallel', label: 'Parallel (faster)' },
              ]}
              label="Processing mode"
              description="How chunks are processed"
              icon={<Zap className="w-4 h-4" />}
            />
          </Section>

          {/* Display Preferences */}
          <Section title="Display" icon={<Layout className="w-5 h-5" />}>
            <Toggle
              enabled={display.compactMode}
              onChange={(v) => updateDisplayPreferences({ compactMode: v })}
              label="Compact mode"
              description="Reduce spacing for denser information display"
              icon={display.compactMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            />
            <Toggle
              enabled={display.enableAnimations}
              onChange={(v) => updateDisplayPreferences({ enableAnimations: v })}
              label="Enable animations"
              description="Smooth transitions and visual effects"
              icon={<Sparkles className="w-4 h-4" />}
            />
            <Toggle
              enabled={display.showJobNotifications}
              onChange={(v) => updateDisplayPreferences({ showJobNotifications: v })}
              label="Job notifications"
              description="Show alerts when jobs complete or fail"
              icon={display.showJobNotifications ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
            />
          </Section>
        </div>
      </div>
    </div>
  );
};

export default PreferencesWorkspace;
