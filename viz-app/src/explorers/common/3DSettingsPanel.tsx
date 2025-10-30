/**
 * 3D Settings Panel
 *
 * Camera and movement controls for 3D graph explorers.
 * Controls roll, pitch, and yaw axis locking to reduce disorientation.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Camera3DSettings {
  lockRoll: boolean;   // Lock camera roll axis (keep upright relative to ground)
  lockPitch: boolean;  // Lock camera pitch axis (prevent looking up/down)
  lockYaw: boolean;    // Lock camera yaw axis (prevent rotating left/right)
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

  const updateCamera = (key: keyof Camera3DSettings, value: boolean) => {
    onCameraChange({
      ...camera,
      [key]: value,
    });
  };

  return (
    <div
      className="absolute left-4 bg-gray-800/95 border border-gray-600 rounded-lg shadow-xl z-10 flex flex-col"
      style={{ width: '280px', maxHeight: '95vh', top: '80px' }} // Below stats panel, left side
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Camera Section */}
        <div>
          <button
            onClick={() => toggleSection('camera')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Camera Controls</span>
            {expandedSections.has('camera') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('camera') && (
            <div className="mt-3 space-y-2">
              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={camera.lockRoll}
                  onChange={(e) => updateCamera('lockRoll', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Lock Roll (Keep Upright)</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={camera.lockPitch}
                  onChange={(e) => updateCamera('lockPitch', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Lock Pitch (No Look Up/Down)</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={camera.lockYaw}
                  onChange={(e) => updateCamera('lockYaw', e.target.checked)}
                  className="rounded"
                />
                <span className="text-gray-200">Lock Yaw (No Rotate Left/Right)</span>
              </label>

              <div className="mt-3 p-2 bg-gray-700/50 rounded text-xs text-gray-300">
                <p className="font-medium mb-1">Tip:</p>
                <p>Lock Roll to prevent disorienting camera tilt when rotating around the graph.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
