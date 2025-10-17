/**
 * Circular Mode Dial Component
 *
 * A modern circular dial for switching between search modes.
 * Click lower-left to go backwards, lower-right to go forwards.
 * Icons are positioned radially around the dial.
 */

import React from 'react';
import { Search, Blocks, Code } from 'lucide-react';

export type QueryMode = 'smart-search' | 'block-builder' | 'cypher-editor';

interface ModeConfig {
  id: QueryMode;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  angle: number; // degrees from top (0° = top)
}

const MODES: ModeConfig[] = [
  { id: 'smart-search', icon: Search, label: 'Smart Search', angle: 0 },
  { id: 'block-builder', icon: Blocks, label: 'Block Builder', angle: 120 },
  { id: 'cypher-editor', icon: Code, label: 'openCypher', angle: 240 },
];

interface ModeDialProps {
  mode: QueryMode;
  onChange: (mode: QueryMode) => void;
}

export const ModeDial: React.FC<ModeDialProps> = ({ mode, onChange }) => {
  const currentIndex = MODES.findIndex((m) => m.id === mode);
  const currentMode = MODES[currentIndex];

  const nextMode = () => {
    const nextIndex = (currentIndex + 1) % MODES.length;
    onChange(MODES[nextIndex].id);
  };

  const prevMode = () => {
    const prevIndex = (currentIndex - 1 + MODES.length) % MODES.length;
    onChange(MODES[prevIndex].id);
  };

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const clickX = e.clientX - rect.left - centerX;
    const clickY = e.clientY - rect.top - centerY;

    // Calculate angle of click (0° = right, counter-clockwise)
    const angleRad = Math.atan2(clickY, clickX);
    const angleDeg = (angleRad * 180) / Math.PI;

    // Convert to our coordinate system (0° = top, clockwise)
    const normalizedAngle = (90 - angleDeg + 360) % 360;

    // Bottom half: 90° to 270°
    if (normalizedAngle > 90 && normalizedAngle < 270) {
      // Left half: 90° to 180°
      if (normalizedAngle < 180) {
        prevMode();
      } else {
        // Right half: 180° to 270°
        nextMode();
      }
    }
  };

  return (
    <div className="flex items-center gap-3">
      {/* Mode Label */}
      <div className="text-right">
        <div className="text-xs text-muted-foreground">Mode</div>
        <div className="text-sm font-medium">{currentMode.label}</div>
      </div>

      {/* Circular Dial */}
      <div className="relative" style={{ width: 80, height: 80 }}>
        {/* Mode Icons (radially positioned) */}
        {MODES.map((modeConfig) => {
          const isActive = modeConfig.id === mode;
          const radius = 32; // Distance from center
          const angleRad = ((modeConfig.angle - 90) * Math.PI) / 180; // Convert to radians, offset by 90° to start at top
          const x = 40 + radius * Math.cos(angleRad); // Center is at 40,40
          const y = 40 + radius * Math.sin(angleRad);

          const Icon = modeConfig.icon;

          return (
            <div
              key={modeConfig.id}
              className={`absolute transition-all duration-200 ${
                isActive ? 'text-foreground scale-110' : 'text-muted-foreground scale-90 opacity-50'
              }`}
              style={{
                left: x - 10, // Icon is 20px, so offset by half
                top: y - 10,
                width: 20,
                height: 20,
              }}
            >
              <Icon className="w-5 h-5" />
            </div>
          );
        })}

        {/* Dial Circle */}
        <div
          onClick={handleClick}
          className="absolute inset-0 rounded-full border-2 border-border bg-muted/30 cursor-pointer transition-colors hover:border-primary/50"
          style={{ width: 80, height: 80 }}
        >
          {/* Rotation Indicator (arrow pointing to current mode) */}
          <div
            className="absolute w-full h-full transition-transform duration-300 ease-out"
            style={{
              transform: `rotate(${currentMode.angle}deg)`,
            }}
          >
            {/* Indicator dot at top */}
            <div className="absolute top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-primary shadow-lg" />
          </div>

          {/* Click zones visualization (subtle) */}
          <div className="absolute inset-0 rounded-full overflow-hidden opacity-0 hover:opacity-100 transition-opacity">
            {/* Left zone */}
            <div
              onClick={(e) => {
                e.stopPropagation();
                prevMode();
              }}
              className="absolute left-0 top-1/2 w-1/2 h-1/2 origin-top-right hover:bg-muted/20 transition-colors"
              style={{
                clipPath: 'polygon(0% 0%, 100% 100%, 0% 100%)',
              }}
            />
            {/* Right zone */}
            <div
              onClick={(e) => {
                e.stopPropagation();
                nextMode();
              }}
              className="absolute right-0 top-1/2 w-1/2 h-1/2 origin-top-left hover:bg-muted/20 transition-colors"
              style={{
                clipPath: 'polygon(100% 0%, 100% 100%, 0% 100%)',
              }}
            />
          </div>

          {/* Center dot */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-background border border-border shadow-sm" />
        </div>

        {/* Keyboard hint */}
        <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-muted-foreground whitespace-nowrap opacity-0 hover:opacity-100 transition-opacity">
          ← click →
        </div>
      </div>
    </div>
  );
};
