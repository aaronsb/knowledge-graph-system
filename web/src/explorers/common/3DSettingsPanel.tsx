/**
 * 3D Settings Panel
 *
 * Camera and movement controls for 3D graph explorers.
 * Controls roll, pitch, and yaw axis locking to reduce disorientation.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Camera3DSettings {
  fov: number;         // Field of view in degrees (30-120)
  autoLevel: boolean;  // Smoothly return to level ground when releasing mouse
  clampToFloor: boolean; // Prevent camera from going below grid floor
  orientLabels: boolean; // Rotate labels around edge axis to face camera
}

interface Settings3DPanelProps {
  camera: Camera3DSettings;
  onCameraChange: (camera: Camera3DSettings) => void;
}

export const Settings3DPanel: React.FC<Settings3DPanelProps> = ({
  camera,
  onCameraChange,
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['camera']));

  // Provide default camera settings if undefined (e.g., when switching from 2D)
  const cameraSettings = camera || {
    fov: 75,
    autoLevel: true,
    clampToFloor: true,
    orientLabels: true,
  };

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

  const updateCamera = (key: keyof Camera3DSettings, value: number | boolean) => {
    onCameraChange({
      ...cameraSettings,
      [key]: value,
    });
  };

  return (
    <div
      className="bg-card/95 border border-border rounded-lg shadow-xl flex flex-col"
      style={{ width: '280px', maxHeight: '95vh' }}
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Camera Section */}
        <div>
          <button
            onClick={() => toggleSection('camera')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground transition-colors"
          >
            <span>Camera Controls</span>
            {expandedSections.has('camera') ? (
              <ChevronDown size={14} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground" />
            )}
          </button>
          {expandedSections.has('camera') && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="block text-xs text-foreground mb-1">
                  Field of View: {cameraSettings.fov}°
                </label>
                <input
                  type="range"
                  min={30}
                  max={120}
                  step={5}
                  value={cameraSettings.fov}
                  onChange={(e) => updateCamera('fov', parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Narrow (30°)</span>
                  <span>Wide (120°)</span>
                </div>
              </div>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={cameraSettings.autoLevel}
                  onChange={(e) => updateCamera('autoLevel', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Auto-Level on Release</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={cameraSettings.clampToFloor}
                  onChange={(e) => updateCamera('clampToFloor', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Keep Camera Above Floor</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={cameraSettings.orientLabels}
                  onChange={(e) => updateCamera('orientLabels', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Orient Labels to Camera</span>
              </label>

              <div className="mt-3 p-2 bg-muted/50 rounded text-xs text-foreground">
                <p className="font-medium mb-1">Tip:</p>
                <p>Auto-Level and Orient Labels work together: when you release the mouse, the camera smoothly levels and labels rotate to face you for easy reading.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
