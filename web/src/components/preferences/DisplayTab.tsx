/**
 * Display Tab
 *
 * UI display preferences.
 */

import React from 'react';
import {
  Layout,
  Minimize2,
  Maximize2,
  Sparkles,
  Bell,
  BellOff,
} from 'lucide-react';
import { usePreferencesStore } from '../../store/preferencesStore';
import { Section, Toggle } from './components';

export const DisplayTab: React.FC = () => {
  const { display, updateDisplayPreferences } = usePreferencesStore();

  return (
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
  );
};

export default DisplayTab;
