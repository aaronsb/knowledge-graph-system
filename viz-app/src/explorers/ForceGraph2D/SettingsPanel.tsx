/**
 * Force-Directed 2D Graph Explorer - Settings Panel
 *
 * Provides interactive controls for configuring graph visualization.
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { ForceGraph2DSettings } from './types';

export const SettingsPanel: React.FC<SettingsPanelProps<ForceGraph2DSettings>> = ({
  settings,
  onChange,
}) => {
  const updatePhysics = (key: keyof ForceGraph2DSettings['physics'], value: number | boolean) => {
    onChange({
      ...settings,
      physics: { ...settings.physics, [key]: value },
    });
  };

  const updateVisual = (key: keyof ForceGraph2DSettings['visual'], value: any) => {
    onChange({
      ...settings,
      visual: { ...settings.visual, [key]: value },
    });
  };

  const updateInteraction = (key: keyof ForceGraph2DSettings['interaction'], value: boolean) => {
    onChange({
      ...settings,
      interaction: { ...settings.interaction, [key]: value },
    });
  };

  return (
    <div className="space-y-6 p-4">
      {/* Physics Settings */}
      <section>
        <h3 className="text-lg font-semibold mb-3">Physics Simulation</h3>

        <div className="space-y-3">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.physics.enabled}
              onChange={(e) => updatePhysics('enabled', e.target.checked)}
              className="rounded"
            />
            <span>Enable Physics</span>
          </label>

          {settings.physics.enabled && (
            <>
              <div>
                <label className="block text-sm mb-1">
                  Charge (Repulsion): {settings.physics.charge}
                </label>
                <input
                  type="range"
                  min="-1000"
                  max="-100"
                  step="50"
                  value={settings.physics.charge}
                  onChange={(e) => updatePhysics('charge', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-sm mb-1">
                  Link Distance: {settings.physics.linkDistance}
                </label>
                <input
                  type="range"
                  min="10"
                  max="200"
                  step="10"
                  value={settings.physics.linkDistance}
                  onChange={(e) => updatePhysics('linkDistance', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-sm mb-1">
                  Gravity: {settings.physics.gravity.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.physics.gravity}
                  onChange={(e) => updatePhysics('gravity', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            </>
          )}
        </div>
      </section>

      {/* Visual Settings */}
      <section>
        <h3 className="text-lg font-semibold mb-3">Visual Appearance</h3>

        <div className="space-y-3">
          <div>
            <label className="block text-sm mb-1">Color By</label>
            <select
              value={settings.visual.colorBy}
              onChange={(e) => updateVisual('colorBy', e.target.value)}
              className="w-full rounded border p-2"
            >
              <option value="ontology">Ontology</option>
              <option value="degree">Degree (Connections)</option>
              <option value="centrality">Centrality</option>
            </select>
          </div>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.visual.showLabels}
              onChange={(e) => updateVisual('showLabels', e.target.checked)}
              className="rounded"
            />
            <span>Show Labels</span>
          </label>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.visual.showArrows}
              onChange={(e) => updateVisual('showArrows', e.target.checked)}
              className="rounded"
            />
            <span>Show Arrows</span>
          </label>

          <div>
            <label className="block text-sm mb-1">
              Node Size: {settings.visual.nodeSize.toFixed(1)}x
            </label>
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
              value={settings.visual.nodeSize}
              onChange={(e) => updateVisual('nodeSize', parseFloat(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm mb-1">
              Link Width: {settings.visual.linkWidth.toFixed(1)}x
            </label>
            <input
              type="range"
              min="0.5"
              max="5"
              step="0.1"
              value={settings.visual.linkWidth}
              onChange={(e) => updateVisual('linkWidth', parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </section>

      {/* Interaction Settings */}
      <section>
        <h3 className="text-lg font-semibold mb-3">Interaction</h3>

        <div className="space-y-3">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.interaction.enableDrag}
              onChange={(e) => updateInteraction('enableDrag', e.target.checked)}
              className="rounded"
            />
            <span>Enable Drag</span>
          </label>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.interaction.enableZoom}
              onChange={(e) => updateInteraction('enableZoom', e.target.checked)}
              className="rounded"
            />
            <span>Enable Zoom</span>
          </label>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.interaction.enablePan}
              onChange={(e) => updateInteraction('enablePan', e.target.checked)}
              className="rounded"
            />
            <span>Enable Pan</span>
          </label>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.interaction.highlightNeighbors}
              onChange={(e) => updateInteraction('highlightNeighbors', e.target.checked)}
              className="rounded"
            />
            <span>Highlight Neighbors on Hover</span>
          </label>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.interaction.showOriginNode}
              onChange={(e) => updateInteraction('showOriginNode', e.target.checked)}
              className="rounded"
            />
            <span>Show "You Are Here" Indicator</span>
          </label>
        </div>
      </section>
    </div>
  );
};
