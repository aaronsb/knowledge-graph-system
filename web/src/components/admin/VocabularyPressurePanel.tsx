/**
 * Vocabulary Pressure Panel (ADR-701).
 *
 * The vocabulary-cycle sibling of AnnealingPressurePanel. Renders the current
 * vocabulary zone plus the aggressiveness response curve as an SVG Bézier,
 * with a "you-are-here" marker at the current vocabulary size. Read-only —
 * interactive curve editing is the deferred Profiles tab. Draws the real curve
 * from the active profile's control points so it always matches the server.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Gauge, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import { Section } from './components';
import type { VocabularyStatus, AggressivenessProfile } from '../../types/vocabulary';

interface VocabularyPressurePanelProps {
  onError: (error: string) => void;
}

// Zone values are lowercase (ZoneEnum in api/app/models/vocabulary.py).
const ZONE_STYLES: Record<string, string> = {
  comfort: 'bg-status-active/20 text-status-active',
  watch: 'bg-status-info/20 text-status-info',
  merge: 'bg-status-warning/20 text-status-warning',
  mixed: 'bg-status-warning/30 text-status-warning',
  emergency: 'bg-destructive/20 text-destructive',
  block: 'bg-destructive/20 text-destructive',
};

/**
 * Cubic Bézier with fixed endpoints (0,0) and (1,1). Mirrors the Python
 * implementation in api/app/lib/aggressiveness_curve.py — we render from the
 * profile's control points so the curve matches whatever the server computes.
 */
function bezierY(t: number, p1y: number, p2y: number): number {
  const u = 1 - t;
  return 3 * u * u * t * p1y + 3 * u * t * t * p2y + t * t * t;
}

function bezierX(t: number, p1x: number, p2x: number): number {
  const u = 1 - t;
  return 3 * u * u * t * p1x + 3 * u * t * t * p2x + t * t * t;
}

/** Build SVG path for the curve, sampled at 50 points. */
function buildCurvePath(
  profile: AggressivenessProfile,
  width: number,
  height: number,
): string {
  const samples = 50;
  const points: string[] = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const x = bezierX(t, profile.control_x1, profile.control_x2) * width;
    const y = height - bezierY(t, profile.control_y1, profile.control_y2) * height;
    points.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return `M ${points.join(' L ')}`;
}

/** Current vocabulary utilization on [0,1] across the min→max range. */
function utilization(status: VocabularyStatus): number {
  const span = status.vocab_max - status.vocab_min;
  if (span <= 0) return 0;
  return Math.min(1, Math.max(0, (status.vocab_size - status.vocab_min) / span));
}

interface AggressivenessCurveSvgProps {
  profile: AggressivenessProfile;
  status: VocabularyStatus;
}

const AggressivenessCurveSvg: React.FC<AggressivenessCurveSvgProps> = ({ profile, status }) => {
  const width = 400;
  const height = 140;
  const padLeft = 36;
  const padBottom = 28;
  const padTop = 12;
  const padRight = 12;
  const innerW = width - padLeft - padRight;
  const innerH = height - padTop - padBottom;

  const curvePath = buildCurvePath(profile, innerW, innerH);

  // Place the dot at the server-computed aggressiveness for the current
  // utilization — no need to invert the Bézier.
  const posX = utilization(status);
  const dotY = Math.min(1, Math.max(0, status.aggressiveness));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-auto"
      role="img"
      aria-label="Vocabulary aggressiveness response curve"
    >
      <rect
        x={padLeft}
        y={padTop}
        width={innerW}
        height={innerH}
        fill="currentColor"
        className="text-muted/10"
      />

      <g transform={`translate(${padLeft} ${padTop})`}>
        <path d={curvePath} fill="none" strokeWidth={2} className="stroke-primary" />

        {/* baseline */}
        <line
          x1={0}
          y1={innerH}
          x2={innerW}
          y2={innerH}
          strokeWidth={1}
          strokeDasharray="2 3"
          className="stroke-status-active/40"
        />

        {/* you-are-here dot */}
        <circle
          cx={posX * innerW}
          cy={innerH - dotY * innerH}
          r={5}
          className="fill-status-warning stroke-status-warning"
        />
        <circle
          cx={posX * innerW}
          cy={innerH - dotY * innerH}
          r={10}
          fill="none"
          strokeWidth={1.5}
          className="stroke-status-warning/40"
        />
      </g>

      <text x={padLeft} y={height - 8} className="fill-muted-foreground text-[10px]">
        {status.vocab_min}
      </text>
      <text
        x={padLeft + innerW}
        y={height - 8}
        textAnchor="end"
        className="fill-muted-foreground text-[10px]"
      >
        {status.vocab_max}
      </text>
      <text x={6} y={padTop + 8} className="fill-muted-foreground text-[10px]">
        1.0
      </text>
      <text x={6} y={padTop + innerH} className="fill-muted-foreground text-[10px]">
        0.0
      </text>
      <text
        x={padLeft + innerW / 2}
        y={height - 8}
        textAnchor="middle"
        className="fill-muted-foreground text-[10px]"
      >
        vocabulary size — aggressiveness curve
      </text>
    </svg>
  );
};

export const VocabularyPressurePanel: React.FC<VocabularyPressurePanelProps> = ({ onError }) => {
  const [status, setStatus] = useState<VocabularyStatus | null>(null);
  const [profile, setProfile] = useState<AggressivenessProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const statusData = await apiClient.getVocabularyStatus();
      setStatus(statusData);
      // The curve needs the active profile's control points; tolerate failure
      // (e.g. custom/unknown profile) by simply not drawing the curve.
      try {
        setProfile(await apiClient.getVocabularyProfile(statusData.profile));
      } catch {
        setProfile(null);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load vocabulary status');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !status) {
    return (
      <Section title="Vocabulary Pressure" icon={<Gauge className="w-5 h-5" />}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Section>
    );
  }

  if (!status) {
    return null;
  }

  const zoneClass =
    ZONE_STYLES[String(status.zone).toLowerCase()] ?? 'bg-muted text-muted-foreground';

  return (
    <Section title="Vocabulary Pressure" icon={<Gauge className="w-5 h-5" />}>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <div className="flex items-baseline gap-3 mb-2">
            <span className="text-sm text-muted-foreground">Aggressiveness</span>
            <span className="text-2xl font-mono font-medium text-foreground">
              {(status.aggressiveness * 100).toFixed(1)}%
            </span>
            <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${zoneClass}`}>
              {status.zone}
            </span>
          </div>
          {profile ? (
            <AggressivenessCurveSvg profile={profile} status={status} />
          ) : (
            <p className="text-xs text-muted-foreground py-4">
              Curve unavailable for profile{' '}
              <code className="font-mono">{status.profile}</code>.
            </p>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            {status.vocab_size} types — min {status.vocab_min}, max {status.vocab_max},
            emergency {status.vocab_emergency}. Profile{' '}
            <code className="font-mono">{status.profile}</code>.
          </p>
        </div>

        <div>
          <h4 className="text-sm font-medium text-foreground mb-3">Composition</h4>
          <div className="space-y-2">
            {[
              ['Builtin types', status.builtin_types],
              ['Custom types', status.custom_types],
              ['Categories', status.categories],
            ].map(([label, value]) => (
              <div
                key={label}
                className="flex items-center justify-between gap-3 px-3 py-2 bg-muted/40 rounded"
              >
                <span className="text-xs text-foreground">{label}</span>
                <span className="font-mono font-medium text-sm text-foreground">{value}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            The aggressiveness curve maps vocabulary size to consolidation
            pressure (ADR-032). Tune the curve via the <code className="font-mono">kg vocab</code>{' '}
            CLI; interactive editing is a deferred Profiles tab.
          </p>
        </div>
      </div>
    </Section>
  );
};

export default VocabularyPressurePanel;
