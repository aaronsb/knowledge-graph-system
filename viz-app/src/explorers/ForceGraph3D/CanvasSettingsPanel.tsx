/**
 * Canvas Settings Panel
 *
 * Collapsible settings panel that sits on the canvas in the upper right,
 * just below the stats panel. Matches Legend styling.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ForceGraph3DSettings } from './types';
import { SLIDER_RANGES } from './types';

interface CanvasSettingsPanelProps {
  settings: ForceGraph3DSettings;
  onChange: (settings: ForceGraph3DSettings) => void;
}

export const CanvasSettingsPanel: React.FC<CanvasSettingsPanelProps> = ({
  settings,
  onChange,
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

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
    <div
      className="absolute right-4 bg-gray-800/95 border border-gray-600 rounded-lg shadow-xl z-10 flex flex-col"
      style={{ width: '280px', maxHeight: '95vh', top: '80px' }} // Below stats panel
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Physics Section */}
        <div className="border-b border-gray-700 pb-3">
          <button
            onClick={() => toggleSection('physics')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Physics</span>
            {expandedSections.has('physics') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('physics') && (
            <div className="mt-3 space-y-3">
              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.physics.enabled}
                  onChange={(e) => updatePhysics('enabled', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Enable Physics</span>
              </label>

              {settings.physics.enabled && (
                <>
                  <div>
                    <label className="block text-xs text-gray-300 mb-1">
                      Charge: {settings.physics.charge}
                    </label>
                    <input
                      type="range"
                      min={SLIDER_RANGES.physics.charge.min}
                      max={SLIDER_RANGES.physics.charge.max}
                      step={SLIDER_RANGES.physics.charge.step}
                      value={settings.physics.charge}
                      onChange={(e) => updatePhysics('charge', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-300 mb-1">
                      Link Distance: {settings.physics.linkDistance}
                    </label>
                    <input
                      type="range"
                      min={SLIDER_RANGES.physics.linkDistance.min}
                      max={SLIDER_RANGES.physics.linkDistance.max}
                      step={SLIDER_RANGES.physics.linkDistance.step}
                      value={settings.physics.linkDistance}
                      onChange={(e) => updatePhysics('linkDistance', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-300 mb-1">
                      Gravity: {settings.physics.gravity.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min={SLIDER_RANGES.physics.gravity.min}
                      max={SLIDER_RANGES.physics.gravity.max}
                      step={SLIDER_RANGES.physics.gravity.step}
                      value={settings.physics.gravity}
                      onChange={(e) => updatePhysics('gravity', parseFloat(e.target.value))}
                      className="w-full"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Visual Section */}
        <div className="border-b border-gray-700 pb-3">
          <button
            onClick={() => toggleSection('visual')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Visual</span>
            {expandedSections.has('visual') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('visual') && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="block text-xs text-gray-300 mb-1">Node Color By</label>
                <select
                  value={settings.visual.nodeColorBy}
                  onChange={(e) => updateVisual('nodeColorBy', e.target.value)}
                  className="w-full rounded border border-gray-600 bg-gray-700 text-gray-200 p-1 text-xs"
                >
                  <option value="ontology">Ontology</option>
                  <option value="degree">Degree (Connections)</option>
                  <option value="centrality">Centrality</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-300 mb-1">Edge Color By</label>
                <select
                  value={settings.visual.edgeColorBy}
                  onChange={(e) => updateVisual('edgeColorBy', e.target.value)}
                  className="w-full rounded border border-gray-600 bg-gray-700 text-gray-200 p-1 text-xs"
                >
                  <option value="category">Category</option>
                  <option value="confidence">Confidence</option>
                  <option value="uniform">Uniform</option>
                </select>
              </div>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showLabels}
                  onChange={(e) => updateVisual('showLabels', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Show Labels</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showArrows}
                  onChange={(e) => updateVisual('showArrows', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Show Arrows</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showGrid}
                  onChange={(e) => updateVisual('showGrid', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Show Grid</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showShadows}
                  onChange={(e) => updateVisual('showShadows', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Shadows</span>
              </label>

              <div>
                <label className="block text-xs text-gray-300 mb-1">
                  Node Size: {settings.visual.nodeSize.toFixed(2)}x
                </label>
                <input
                  type="range"
                  min={SLIDER_RANGES.visual.nodeSize.min}
                  max={SLIDER_RANGES.visual.nodeSize.max}
                  step={SLIDER_RANGES.visual.nodeSize.step}
                  value={settings.visual.nodeSize}
                  onChange={(e) => updateVisual('nodeSize', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-300 mb-1">
                  Link Width: {settings.visual.linkWidth.toFixed(1)}x
                </label>
                <input
                  type="range"
                  min={SLIDER_RANGES.visual.linkWidth.min}
                  max={SLIDER_RANGES.visual.linkWidth.max}
                  step={SLIDER_RANGES.visual.linkWidth.step}
                  value={settings.visual.linkWidth}
                  onChange={(e) => updateVisual('linkWidth', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-300 mb-1">
                  Node Label Size: {settings.visual.nodeLabelSize}px
                </label>
                <input
                  type="range"
                  min={SLIDER_RANGES.visual.nodeLabelSize.min}
                  max={SLIDER_RANGES.visual.nodeLabelSize.max}
                  step={SLIDER_RANGES.visual.nodeLabelSize.step}
                  value={settings.visual.nodeLabelSize}
                  onChange={(e) => updateVisual('nodeLabelSize', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-300 mb-1">
                  Edge Label Size: {settings.visual.edgeLabelSize}px
                </label>
                <input
                  type="range"
                  min={SLIDER_RANGES.visual.edgeLabelSize.min}
                  max={SLIDER_RANGES.visual.edgeLabelSize.max}
                  step={SLIDER_RANGES.visual.edgeLabelSize.step}
                  value={settings.visual.edgeLabelSize}
                  onChange={(e) => updateVisual('edgeLabelSize', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </div>

        {/* Interaction Section */}
        <div>
          <button
            onClick={() => toggleSection('interaction')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Interaction</span>
            {expandedSections.has('interaction') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('interaction') && (
            <div className="mt-3 space-y-2">
              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enableDrag}
                  onChange={(e) => updateInteraction('enableDrag', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Enable Drag</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enableZoom}
                  onChange={(e) => updateInteraction('enableZoom', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Enable Zoom</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enablePan}
                  onChange={(e) => updateInteraction('enablePan', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Enable Pan</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.highlightNeighbors}
                  onChange={(e) => updateInteraction('highlightNeighbors', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Highlight Neighbors</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.showOriginNode}
                  onChange={(e) => updateInteraction('showOriginNode', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Show Origin</span>
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
