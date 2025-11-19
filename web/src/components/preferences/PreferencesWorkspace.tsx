/**
 * Preferences Workspace
 *
 * User preferences including theme selection and profile settings.
 */

import React from 'react';
import { Settings, Sun, Moon, Monitor, Palette } from 'lucide-react';
import { useThemeStore } from '../../store/themeStore';

export const PreferencesWorkspace: React.FC = () => {
  const { theme, setTheme } = useThemeStore();

  const themeOptions = [
    { id: 'light', label: 'Light', icon: Sun, description: 'Light background with dark text' },
    { id: 'dark', label: 'Dark', icon: Moon, description: 'Dark background with light text' },
    { id: 'system', label: 'System', icon: Monitor, description: 'Follow system preference' },
  ] as const;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="h-12 border-b border-border bg-card px-4 flex items-center">
        <Settings className="w-5 h-5 text-muted-foreground mr-2" />
        <span className="font-semibold">Preferences</span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-8">
          {/* Theme Selection */}
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Palette className="w-5 h-5" />
              Appearance
            </h2>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-3 block">
                  Theme
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {themeOptions.map((option) => {
                    const Icon = option.icon;
                    const isSelected = theme === option.id;
                    return (
                      <button
                        key={option.id}
                        onClick={() => setTheme(option.id)}
                        className={`
                          p-4 rounded-lg border-2 transition-all text-left
                          ${isSelected
                            ? 'border-primary bg-primary/10'
                            : 'border-border bg-muted/40 hover:border-primary/50 hover:bg-accent'
                          }
                        `}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <Icon className={`w-5 h-5 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                          <span className={`font-medium ${isSelected ? 'text-primary' : ''}`}>
                            {option.label}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {option.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>

          {/* Future: User Profile */}
          <section>
            <h2 className="text-lg font-semibold mb-4 text-muted-foreground">
              Profile
            </h2>
            <div className="p-6 border border-dashed border-border rounded-lg text-center">
              <p className="text-sm text-muted-foreground">
                User profile settings coming soon
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Configure display name, avatar, and notification preferences
              </p>
            </div>
          </section>

          {/* Future: Accent Colors */}
          <section>
            <h2 className="text-lg font-semibold mb-4 text-muted-foreground">
              Accent Color
            </h2>
            <div className="p-6 border border-dashed border-border rounded-lg text-center">
              <p className="text-sm text-muted-foreground">
                Custom accent colors coming soon
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Choose a primary color for buttons and highlights
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
