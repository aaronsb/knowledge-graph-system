/**
 * Annealing Pressure Panel (#249, ADR-206 §Phase 3)
 *
 * Renders the current ecological-pressure read-out as an SVG Bezier curve
 * plus per-control recommendations. Polls /ontology/annealing/pressure on
 * mount and on the parent tab's refresh — observational, no controls.
 *
 * Trend chart over kg_api.annealing_pressure_history is a focused follow-up.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import { Section } from './components';
import type {
  EcologicalPressureCurve,
  EcologicalPressureSnapshot,
} from '../../types/annealing';

interface AnnealingPressurePanelProps {
  onError: (error: string) => void;
}

const ZONE_STYLES: Record<string, string> = {
  comfort: 'bg-status-active/20 text-status-active',
  watch: 'bg-status-info/20 text-status-info',
  tight: 'bg-status-warning/20 text-status-warning',
  over: 'bg-status-warning/30 text-status-warning',
  emergency: 'bg-destructive/20 text-destructive',
};

/**
 * Cubic Bezier on x with fixed endpoints (0,0) and (1,1). Mirrors the
 * Python implementation in api/app/lib/aggressiveness_curve.py — the
 * server tells us the control points, we compute the SVG path from them
 * so the rendered curve always matches whatever profile the server used.
 */
function bezierY(t: number, p1y: number, p2y: number): number {
  const u = 1 - t;
  return 3 * u * u * t * p1y + 3 * u * t * t * p2y + t * t * t;
}

function bezierX(t: number, p1x: number, p2x: number): number {
  const u = 1 - t;
  return 3 * u * u * t * p1x + 3 * u * t * t * p2x + t * t * t;
}

function pressureFromAvg(
  avg: number,
  curve: EcologicalPressureCurve,
): { score: number; position: number } {
  if (avg <= 0 || (avg >= curve.comfort_min && avg <= curve.comfort_max)) {
    return { score: 0, position: 0 };
  }
  if (avg < curve.comfort_min) {
    const position = Math.min(1, (curve.comfort_min - avg) / curve.comfort_min);
    return { score: bezierY(position, curve.bezier_p1[1], curve.bezier_p2[1]), position };
  }
  if (avg >= curve.emergency_threshold) {
    return { score: 1, position: 1 };
  }
  const position = (avg - curve.comfort_max) / (curve.emergency_threshold - curve.comfort_max);
  return { score: bezierY(position, curve.bezier_p1[1], curve.bezier_p2[1]), position };
}

/** Build SVG path string for the Bezier curve, sampled at 50 points. */
function buildCurvePath(curve: EcologicalPressureCurve, width: number, height: number): string {
  const samples = 50;
  const [p1x, p1y] = curve.bezier_p1;
  const [p2x, p2y] = curve.bezier_p2;
  const points: string[] = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const x = bezierX(t, p1x, p2x) * width;
    const y = height - bezierY(t, p1y, p2y) * height;
    points.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return `M ${points.join(' L ')}`;
}

interface PressureCurveSvgProps {
  curve: EcologicalPressureCurve;
  current: EcologicalPressureSnapshot;
}

const PressureCurveSvg: React.FC<PressureCurveSvgProps> = ({ curve, current }) => {
  // Plot area in SVG coordinates. The actual pressure curve only spans
  // the right half (above comfort_max); the left side is the comfort
  // band rendered as a flat zero stripe so operators see the shape
  // symmetrically.
  const width = 400;
  const height = 140;
  const padLeft = 36;
  const padBottom = 28;
  const padTop = 12;
  const padRight = 12;
  const innerW = width - padLeft - padRight;
  const innerH = height - padTop - padBottom;

  const curvePath = buildCurvePath(curve, innerW, innerH);

  const { position } = pressureFromAvg(current.avg_concepts_per_ontology, curve);
  const inComfort =
    current.avg_concepts_per_ontology >= curve.comfort_min &&
    current.avg_concepts_per_ontology <= curve.comfort_max;
  const dotPositionX = inComfort
    ? -1 // hide
    : position;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-auto"
      role="img"
      aria-label="Ecological pressure response curve"
    >
      {/* Plot frame */}
      <rect
        x={padLeft}
        y={padTop}
        width={innerW}
        height={innerH}
        fill="currentColor"
        className="text-muted/10"
      />

      {/* Bezier curve (offset into the inner plot) */}
      <g transform={`translate(${padLeft} ${padTop})`}>
        <path d={curvePath} fill="none" strokeWidth={2} className="stroke-primary" />

        {/* Comfort-band marker (zero-pressure baseline) */}
        <line
          x1={0}
          y1={innerH}
          x2={innerW}
          y2={innerH}
          strokeWidth={1}
          strokeDasharray="2 3"
          className="stroke-status-active/40"
        />

        {/* You-are-here dot */}
        {dotPositionX >= 0 && (
          <>
            <circle
              cx={dotPositionX * innerW}
              cy={innerH - bezierY(dotPositionX, curve.bezier_p1[1], curve.bezier_p2[1]) * innerH}
              r={5}
              className="fill-status-warning stroke-status-warning"
            />
            <circle
              cx={dotPositionX * innerW}
              cy={innerH - bezierY(dotPositionX, curve.bezier_p1[1], curve.bezier_p2[1]) * innerH}
              r={10}
              fill="none"
              strokeWidth={1.5}
              className="stroke-status-warning/40"
            />
          </>
        )}
      </g>

      {/* Axis labels */}
      <text x={padLeft} y={height - 8} className="fill-muted-foreground text-[10px]">
        comfort
      </text>
      <text
        x={padLeft + innerW}
        y={height - 8}
        textAnchor="end"
        className="fill-muted-foreground text-[10px]"
      >
        emergency
      </text>
      <text
        x={6}
        y={padTop + 8}
        className="fill-muted-foreground text-[10px]"
      >
        1.0
      </text>
      <text
        x={6}
        y={padTop + innerH}
        className="fill-muted-foreground text-[10px]"
      >
        0.0
      </text>
      <text
        x={padLeft + innerW / 2}
        y={height - 8}
        textAnchor="middle"
        className="fill-muted-foreground text-[10px]"
      >
        avg concepts / ontology — {curve.comfort_max.toFixed(0)} →{' '}
        {curve.emergency_threshold.toFixed(0)}
      </text>
    </svg>
  );
};

export const AnnealingPressurePanel: React.FC<AnnealingPressurePanelProps> = ({ onError }) => {
  const [current, setCurrent] = useState<EcologicalPressureSnapshot | null>(null);
  const [curve, setCurve] = useState<EcologicalPressureCurve | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getEcologicalPressure();
      setCurrent(data.current);
      setCurve(data.curve);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load ecological pressure');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !current) {
    return (
      <Section title="Ecological Pressure" icon={<Activity className="w-5 h-5" />}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Section>
    );
  }

  if (!current || !curve) {
    return null;
  }

  const hasHistory = current.epoch > 0 || current.total_ontologies > 0;
  const zoneClass = ZONE_STYLES[current.pressure_zone] ?? 'bg-muted text-muted-foreground';

  return (
    <Section title="Ecological Pressure" icon={<Activity className="w-5 h-5" />}>
      {!hasHistory ? (
        <p className="text-sm text-muted-foreground py-4">
          No annealing cycles have run yet. Pressure curve will populate after
          the first cycle records a snapshot to{' '}
          <code className="font-mono">kg_api.annealing_pressure_history</code>.
        </p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-sm text-muted-foreground">Pressure score</span>
              <span className="text-2xl font-mono font-medium text-foreground">
                {current.pressure_score.toFixed(2)}
              </span>
              <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${zoneClass}`}>
                {current.pressure_zone}
              </span>
            </div>
            <PressureCurveSvg curve={curve} current={current} />
            <p className="mt-3 text-xs text-muted-foreground">
              {current.total_ontologies} ontologies, {current.total_concepts.toLocaleString()} concepts (avg{' '}
              {current.avg_concepts_per_ontology.toFixed(1)} per ontology). Comfort band{' '}
              [{curve.comfort_min.toFixed(0)}, {curve.comfort_max.toFixed(0)}]; emergency at{' '}
              {curve.emergency_threshold.toFixed(0)}. Profile{' '}
              <code className="font-mono">{curve.profile}</code>.
            </p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-foreground mb-3">
              Control recommendations
            </h4>
            {Object.keys(current.pressure_recommendation).length === 0 ? (
              <p className="text-sm text-muted-foreground">No recommendations.</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(current.pressure_recommendation).map(([key, block]) => {
                  const sign = block.delta > 0 ? '+' : '';
                  const tone =
                    block.delta === 0
                      ? 'text-muted-foreground'
                      : Math.abs(block.delta) < 2
                        ? 'text-status-info'
                        : 'text-status-warning';
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between gap-3 px-3 py-2 bg-muted/40 rounded"
                    >
                      <code className="font-mono text-xs text-foreground">{key}</code>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">
                          {block.current} →
                        </span>
                        <span className="font-mono font-medium text-foreground">
                          {block.recommended}
                        </span>
                        <span className={`text-xs font-mono ${tone}`}>
                          ({sign}
                          {block.delta})
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              Recommendations crossing the deadband emit{' '}
              <code className="font-mono">ADJUST_CONTROL</code> proposals
              (visible above when pending). The annealing cycle does not
              re-propose against a control while one is already in flight.
            </p>
          </div>
        </div>
      )}
    </Section>
  );
};

export default AnnealingPressurePanel;
