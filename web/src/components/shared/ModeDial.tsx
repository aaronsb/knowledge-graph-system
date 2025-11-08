/**
 * Circular Mode Dial Component
 *
 * A modern circular dial for switching between query modes.
 * - Click mode icons directly to select
 * - Click left arrow to advance forward (+)
 * - Click right arrow to go backward (-)
 * - Click center to advance forward (+)
 */

import React, { useState, useEffect, useRef } from 'react';
import { Search, Blocks, Code, ChevronLeft, ChevronRight } from 'lucide-react';

export type QueryMode = 'smart-search' | 'block-builder' | 'cypher-editor';

interface ModeConfig {
  id: QueryMode;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const MODES: ModeConfig[] = [
  { id: 'smart-search', icon: Search, label: 'Smart Search' },
  { id: 'block-builder', icon: Blocks, label: 'Block Builder' },
  { id: 'cypher-editor', icon: Code, label: 'openCypher' },
];

// Calculate degrees based on number of modes
const DEGREES_PER_MODE = 360 / MODES.length;

interface ModeDialProps {
  mode: QueryMode;
  onChange: (mode: QueryMode) => void;
}

export const ModeDial: React.FC<ModeDialProps> = ({ mode, onChange }) => {
  const currentIndex = MODES.findIndex((m) => m.id === mode);
  const [rotationAngle, setRotationAngle] = useState(0);
  const prevIndexRef = useRef(currentIndex);

  // Track rotation cumulatively so we always proceed forward
  useEffect(() => {
    const prevIndex = prevIndexRef.current;
    const newIndex = currentIndex;

    if (prevIndex !== newIndex) {
      let delta = newIndex - prevIndex;

      // Detect wrap-around forward (2 → 0)
      if (delta < 0 && Math.abs(delta) > MODES.length / 2) {
        delta = delta + MODES.length;
      }
      // Detect wrap-around backward (0 → 2)
      else if (delta > 0 && Math.abs(delta) > MODES.length / 2) {
        delta = delta - MODES.length;
      }

      setRotationAngle((prev) => prev + delta * DEGREES_PER_MODE);
      prevIndexRef.current = newIndex;
    }
  }, [currentIndex]);

  const advanceForward = () => {
    const nextIndex = (currentIndex + 1) % MODES.length;
    onChange(MODES[nextIndex].id);
  };

  const goBackward = () => {
    const prevIndex = (currentIndex - 1 + MODES.length) % MODES.length;
    onChange(MODES[prevIndex].id);
  };

  const selectMode = (modeId: QueryMode) => {
    onChange(modeId);
  };

  return (
    <div className="flex items-center gap-3">
      {/* Mode Label */}
      <div className="text-right">
        <div className="text-xs text-muted-foreground">Mode</div>
        <div className="text-sm font-medium">{MODES[currentIndex].label}</div>
      </div>

      {/* Dial Container with External Arrows */}
      <div className="relative" style={{ width: 100, height: 100 }}>
        {/* Left Arrow (Advance Forward) */}
        <button
          onClick={advanceForward}
          className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-2 w-6 h-6 flex items-center justify-center rounded-full bg-muted/50 hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          title="Next mode"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Right Arrow (Go Backward) */}
        <button
          onClick={goBackward}
          className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 w-6 h-6 flex items-center justify-center rounded-full bg-muted/50 hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          title="Previous mode"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Circular Dial */}
        <div className="absolute inset-[10px]" style={{ width: 80, height: 80 }}>
          {/* Mode Icons (radially positioned, clickable) */}
          {MODES.map((modeConfig, index) => {
            const isActive = modeConfig.id === mode;
            const radius = 32; // Distance from center
            const angle = index * DEGREES_PER_MODE;
            const angleRad = ((angle - 90) * Math.PI) / 180; // Convert to radians, offset by 90° to start at top
            const x = 40 + radius * Math.cos(angleRad); // Center is at 40,40
            const y = 40 + radius * Math.sin(angleRad);

            const Icon = modeConfig.icon;

            return (
              <button
                key={modeConfig.id}
                onClick={() => selectMode(modeConfig.id)}
                className={`absolute transition-all duration-200 rounded-full p-1 ${
                  isActive
                    ? 'text-foreground scale-110 bg-primary/10'
                    : 'text-muted-foreground scale-90 opacity-50 hover:opacity-100 hover:scale-100'
                }`}
                style={{
                  left: x - 12, // Icon is 24px (20px + padding), so offset by half
                  top: y - 12,
                  width: 24,
                  height: 24,
                }}
                title={modeConfig.label}
              >
                <Icon className="w-5 h-5" />
              </button>
            );
          })}

          {/* Dial Circle */}
          <div
            className="absolute inset-0 rounded-full border-2 border-border bg-muted/30 transition-colors hover:border-primary/50"
            style={{ width: 80, height: 80 }}
          >
            {/* Rotation Indicator (arrow pointing to current mode) */}
            <div
              className="absolute w-full h-full transition-transform duration-300 ease-out"
              style={{
                transform: `rotate(${rotationAngle}deg)`,
              }}
            >
              {/* Indicator dot at top */}
              <div className="absolute top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-primary shadow-lg" />
            </div>

            {/* Center button (advance forward) */}
            <button
              onClick={advanceForward}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-background border border-border shadow-sm hover:bg-muted transition-colors cursor-pointer"
              title="Next mode"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
