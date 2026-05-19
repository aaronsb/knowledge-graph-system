/**
 * Shared visual-settings controls.
 *
 * The Force Graph and Document Explorer panels were drifting apart —
 * each hand-rolled its own visual section, so a control added to one
 * (e.g. the lighting toggle) silently skipped the other. This component
 * owns the visual controls both explorers share, so adding one here adds
 * it to both. Explorer-specific controls (Force Graph's colour-by,
 * Document Explorer's documentSize, etc.) stay in their own panels
 * around this block.
 *
 * Presentational + adapter: it takes a normalised value + per-field
 * callbacks rather than a settings object, so it never has to know
 * either explorer's settings shape. Each panel maps its own settings to
 * these props. The markup mirrors the existing row/slider/toggle/select
 * idiom so the panels stay visually consistent.
 *
 * @verified 50606a37
 */

import React from 'react';

export interface VisualControlsValue {
  showNodeLabels: boolean;
  nodeSize: number;
  lighting: 'flat' | 'lit';
  lightingFollowsProjection: boolean;
}

export interface VisualControlsProps extends VisualControlsValue {
  nodeSizeRange: { min: number; max: number; step: number };
  onShowNodeLabels: (v: boolean) => void;
  onNodeSize: (v: number) => void;
  onLighting: (v: 'flat' | 'lit') => void;
  onLightingFollowsProjection: (v: boolean) => void;
}

const rowCls = 'flex items-center gap-2 text-xs text-card-foreground';
const valCls =
  'font-mono text-muted-foreground tabular-nums w-12 text-right text-[10px]';

/** Visual controls shared by every graph explorer.  @verified 50606a37 */
export const VisualControls: React.FC<VisualControlsProps> = ({
  showNodeLabels,
  nodeSize,
  lighting,
  lightingFollowsProjection,
  nodeSizeRange,
  onShowNodeLabels,
  onNodeSize,
  onLighting,
  onLightingFollowsProjection,
}) => {
  return (
    <>
      <label className={rowCls}>
        <span className="flex-1 min-w-0 truncate">Show node labels</span>
        <span className={valCls}>{showNodeLabels ? 'on' : 'off'}</span>
        <input
          type="checkbox"
          className="ml-auto"
          checked={showNodeLabels}
          onChange={(e) => onShowNodeLabels(e.target.checked)}
        />
      </label>

      <label
        className={`${rowCls} ${
          lightingFollowsProjection ? 'opacity-50' : ''
        }`}
      >
        <span className="flex-1 min-w-0 truncate">
          {lightingFollowsProjection ? 'Shading (follows view)' : 'Shading'}
        </span>
        <select
          className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
          value={lighting}
          disabled={lightingFollowsProjection}
          onChange={(e) => onLighting(e.target.value as 'flat' | 'lit')}
        >
          <option value="flat">Flat (two-tone)</option>
          <option value="lit">Lit (3D light)</option>
        </select>
      </label>

      <label className={rowCls}>
        <span className="flex-1 min-w-0 truncate">Shading follows view</span>
        <span className={valCls}>
          {lightingFollowsProjection ? 'on' : 'off'}
        </span>
        <input
          type="checkbox"
          className="ml-auto"
          checked={lightingFollowsProjection}
          onChange={(e) => onLightingFollowsProjection(e.target.checked)}
        />
      </label>

      <label className={rowCls}>
        <span className="flex-1 min-w-0 truncate">Node size</span>
        <span className={valCls}>{nodeSize.toFixed(2)}</span>
        <input
          type="range"
          className="flex-[2]"
          min={nodeSizeRange.min}
          max={nodeSizeRange.max}
          step={nodeSizeRange.step}
          value={nodeSize}
          onChange={(e) => onNodeSize(parseFloat(e.target.value))}
        />
      </label>
    </>
  );
};
