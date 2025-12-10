/**
 * Appearance Tab
 *
 * Advanced theme customization with mode selection and independent
 * background/foreground/accent color controls. Mode provides soft
 * guidance (lightness ranges, fg lightness) while user controls hue/saturation.
 *
 * Hue, saturation, and accent are shared across modes for easy comparison.
 * Only lightness varies per mode (constrained to mode-appropriate ranges).
 */

import React, { useState, useEffect } from 'react';
import {
  Sun,
  Moon,
  Monitor,
  Sunset,
  Palette,
  RotateCcw,
} from 'lucide-react';
import { useThemeStore, type ThemePreference } from '../../store/themeStore';
import {
  Section,
  HueGrid,
  SaturationGrid,
  LightnessGrid,
  SVGrid,
  ColorPreview,
  Subsection,
} from './components';
import {
  modeConfigs,
  defaultColorSettings,
  computeHarmony,
  applyHarmonyToCSS,
  hslToHex,
  loadColorSettings,
  saveColorSettings,
  clearColorSettings,
  type ColorSettings,
  type SharedColorSettings,
  type ModeLightnessSettings,
} from '../../lib/themeHarmony';

export const AppearanceTab: React.FC = () => {
  const { theme, appliedTheme, setTheme } = useThemeStore();

  // Color settings (shared + per-mode lightness)
  const [colorSettings, setColorSettings] = useState<ColorSettings>(() => {
    const stored = loadColorSettings();
    return stored || { ...defaultColorSettings };
  });

  const modeConfig = modeConfigs[appliedTheme] || modeConfigs.dark;

  // Get current lightness for the applied mode
  const currentLightness = colorSettings.lightness[appliedTheme as keyof ModeLightnessSettings]
    ?? modeConfig.defaultLight;

  // Update a shared setting (hue, saturation, accent)
  const updateShared = <K extends keyof SharedColorSettings>(key: K, value: SharedColorSettings[K]) => {
    const newSettings: ColorSettings = {
      ...colorSettings,
      shared: {
        ...colorSettings.shared,
        [key]: value,
      },
    };
    setColorSettings(newSettings);
    saveColorSettings(newSettings);
  };

  // Update lightness for current mode
  const updateLightness = (value: number) => {
    const newSettings: ColorSettings = {
      ...colorSettings,
      lightness: {
        ...colorSettings.lightness,
        [appliedTheme]: value,
      },
    };
    setColorSettings(newSettings);
    saveColorSettings(newSettings);
  };

  // Apply harmony whenever settings or mode change
  useEffect(() => {
    const harmony = computeHarmony(appliedTheme, colorSettings);
    applyHarmonyToCSS(harmony, {
      h: colorSettings.shared.primaryHue,
      s: colorSettings.shared.primarySat,
      l: colorSettings.shared.primaryLight,
    });
  }, [appliedTheme, colorSettings]);

  // Reset all to defaults
  const handleResetAll = () => {
    const defaults = { ...defaultColorSettings };
    setColorSettings(defaults);
    clearColorSettings();
  };

  // Check if settings are customized
  const isCustomized = JSON.stringify(colorSettings) !== JSON.stringify(defaultColorSettings);

  const themeOptions: { id: ThemePreference; label: string; icon: React.ComponentType<{ className?: string }>; time: string }[] = [
    { id: 'dark', label: 'Dark', icon: Moon, time: '23:00' },
    { id: 'twilight', label: 'Twilight', icon: Sunset, time: '18:30' },
    { id: 'light', label: 'Light', icon: Sun, time: '12:00' },
    { id: 'system', label: 'System', icon: Monitor, time: 'auto' },
  ];

  // Computed harmony for display
  const harmony = computeHarmony(appliedTheme, colorSettings);

  return (
    <>
      {/* Mode Selector */}
      <Section title="Environment Mode" icon={<Palette className="w-5 h-5" />}>
        <div className="py-4">
          {/* Mode buttons */}
          <div className="grid grid-cols-4 gap-0.5 bg-border p-0.5 mb-4">
            {themeOptions.map((option) => {
              const Icon = option.icon;
              const isSelected = theme === option.id;
              return (
                <button
                  key={option.id}
                  onClick={() => setTheme(option.id)}
                  className={`
                    relative flex flex-col items-center gap-1 p-3 transition-all
                    ${option.id === 'dark' ? 'bg-[hsl(20,8%,12%)] text-[hsl(20,15%,75%)]' : ''}
                    ${option.id === 'twilight' ? 'bg-gradient-to-br from-[hsl(30,25%,45%)] to-[hsl(220,30%,35%)] text-[hsl(40,30%,90%)]' : ''}
                    ${option.id === 'light' ? 'bg-[hsl(40,20%,92%)] text-[hsl(20,15%,25%)]' : ''}
                    ${option.id === 'system' ? 'bg-muted text-muted-foreground' : ''}
                    ${isSelected ? '' : 'opacity-80 hover:opacity-100'}
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-xs font-mono uppercase tracking-wide font-semibold">
                    {option.label}
                  </span>
                  <span className="text-[9px] opacity-70">{option.time}</span>
                  {isSelected && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Mode preview strip */}
          <div className="flex h-10 border border-border overflow-hidden mb-3">
            <div
              className="flex-1 flex items-center justify-center font-mono text-xs"
              style={{
                backgroundColor: `hsl(${harmony.bg.h}, ${harmony.bg.s}%, ${harmony.bg.l}%)`,
                color: `hsl(${harmony.fg.h}, ${harmony.fg.s}%, ${harmony.fg.l}%)`,
              }}
            >
              BG
              <div className="flex flex-col gap-0.5 ml-2">
                <div
                  className="w-3 h-1.5"
                  style={{ backgroundColor: `hsl(${harmony.fg.h}, ${harmony.fg.s}%, ${harmony.fg.l}%)` }}
                />
                <div
                  className="w-3 h-1.5"
                  style={{ backgroundColor: `hsl(${harmony.fg.h}, ${harmony.fg.s * 0.6}%, ${harmony.fg.l - 15}%)` }}
                />
                <div
                  className="w-3 h-1.5"
                  style={{ backgroundColor: `hsl(${harmony.fg.h}, ${harmony.fg.s * 0.4}%, ${harmony.fg.l - 35}%)` }}
                />
              </div>
            </div>
          </div>

          {/* Harmony info */}
          <div className="bg-surface-2 p-3 font-mono text-[10px] space-y-1">
            <div className="flex justify-between text-muted-foreground">
              <span>BG Lightness</span>
              <span className="text-card-foreground">{harmony.bg.l}%</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>FG Lightness</span>
              <span className="text-card-foreground">{harmony.fg.l}% (mode-controlled)</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>Contrast Ratio</span>
              <span className="text-card-foreground">{harmony.contrastRatio}</span>
            </div>
          </div>
        </div>
      </Section>

      {/* Background Tone */}
      <Section
        title="Background Tone"
        icon={
          <div
            className="w-5 h-5 border border-border"
            style={{ backgroundColor: `hsl(${colorSettings.shared.bgHue}, ${colorSettings.shared.bgSat}%, ${currentLightness}%)` }}
          />
        }
      >
        <Subsection title="Background Controls">
          <HueGrid
            value={colorSettings.shared.bgHue}
            onChange={(h) => updateShared('bgHue', h)}
            lightness={35}
            saturation={25}
            label="Hue (30° steps)"
          />
          <SaturationGrid
            value={colorSettings.shared.bgSat}
            onChange={(s) => updateShared('bgSat', s)}
            hue={colorSettings.shared.bgHue}
            lightness={35}
            steps={[0, 6, 12, 18, 24, 30]}
            label="Saturation"
          />
          <LightnessGrid
            value={currentLightness}
            onChange={updateLightness}
            hue={colorSettings.shared.bgHue}
            saturation={colorSettings.shared.bgSat}
            stops={modeConfig.lightStops}
            label="Lightness (mode-constrained)"
          />
          <ColorPreview
            hue={colorSettings.shared.bgHue}
            saturation={colorSettings.shared.bgSat}
            lightness={currentLightness}
            hex={hslToHex(colorSettings.shared.bgHue, colorSettings.shared.bgSat, currentLightness)}
            compact
          />
        </Subsection>
      </Section>

      {/* Text/Foreground Tone */}
      <Section
        title="Text Tone"
        icon={
          <div
            className="w-5 h-5 border border-border"
            style={{ backgroundColor: `hsl(${colorSettings.shared.fgHue}, ${colorSettings.shared.fgSat}%, ${modeConfig.fgLightness}%)` }}
          />
        }
        description="Lightness is controlled by mode for guaranteed contrast"
      >
        <Subsection title="Foreground Controls">
          <HueGrid
            value={colorSettings.shared.fgHue}
            onChange={(h) => updateShared('fgHue', h)}
            lightness={70}
            saturation={30}
            label="Hue (30° steps)"
          />
          <SaturationGrid
            value={colorSettings.shared.fgSat}
            onChange={(s) => updateShared('fgSat', s)}
            hue={colorSettings.shared.fgHue}
            lightness={60}
            steps={[0, 10, 20, 30, 40, 50]}
            label="Saturation"
          />
          <ColorPreview
            hue={colorSettings.shared.fgHue}
            saturation={colorSettings.shared.fgSat}
            lightness={modeConfig.fgLightness}
            hex={hslToHex(colorSettings.shared.fgHue, colorSettings.shared.fgSat, modeConfig.fgLightness)}
            compact
          />
        </Subsection>
      </Section>

      {/* Primary Accent */}
      <Section
        title="Primary Accent"
        icon={
          <div
            className="w-5 h-5 rounded-full border border-border"
            style={{ backgroundColor: `hsl(${colorSettings.shared.primaryHue}, ${colorSettings.shared.primarySat}%, ${colorSettings.shared.primaryLight}%)` }}
          />
        }
        description="The highlight color used for interactive elements"
      >
        <Subsection title="Accent Color">
          <HueGrid
            value={colorSettings.shared.primaryHue}
            onChange={(h) => updateShared('primaryHue', h)}
            lightness={55}
            saturation={80}
            label="Hue (30° steps)"
          />
          <SVGrid
            hue={colorSettings.shared.primaryHue}
            saturation={colorSettings.shared.primarySat}
            lightness={colorSettings.shared.primaryLight}
            onChange={(s, l) => {
              const newSettings: ColorSettings = {
                ...colorSettings,
                shared: {
                  ...colorSettings.shared,
                  primarySat: s,
                  primaryLight: l,
                },
              };
              setColorSettings(newSettings);
              saveColorSettings(newSettings);
            }}
            label="Saturation / Lightness"
          />
          <ColorPreview
            hue={colorSettings.shared.primaryHue}
            saturation={colorSettings.shared.primarySat}
            lightness={colorSettings.shared.primaryLight}
            hex={hslToHex(colorSettings.shared.primaryHue, colorSettings.shared.primarySat, colorSettings.shared.primaryLight)}
          />
        </Subsection>

        {/* Preview */}
        <div className="py-4">
          <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">Preview</div>
          <div className="flex flex-wrap items-center gap-3">
            <button className="px-4 py-2 rounded bg-primary text-primary-foreground text-sm font-medium">
              Primary Button
            </button>
            <button className="px-4 py-2 rounded border-2 border-primary text-primary text-sm font-medium">
              Outline Button
            </button>
            <span className="px-3 py-1 rounded-full bg-primary/20 text-primary text-xs font-medium">
              Badge
            </span>
            <div className="w-32 h-2 rounded-full bg-muted overflow-hidden">
              <div className="w-2/3 h-full bg-primary" />
            </div>
          </div>
        </div>
      </Section>

      {/* Reset */}
      {isCustomized && (
        <div className="flex justify-end">
          <button
            onClick={handleResetAll}
            className="flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset all colors to defaults
          </button>
        </div>
      )}
    </>
  );
};

export default AppearanceTab;
