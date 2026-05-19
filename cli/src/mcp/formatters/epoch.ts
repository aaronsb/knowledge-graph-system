/**
 * MCP formatters for the graph epoch event log (ADR-203).
 *
 * Renders responses as compact markdown for token-efficient consumption
 * by agents. Visualizes the two-dimension model: logical-time ordering
 * via event_id, wall-clock time via occurred_at, kind as the
 * discriminator for whether wall-clock is semantically primary.
 */

import type {
  ConceptLifetimeResponse,
  EpochListResponse,
} from '../../types/index.js';

const KINDS_WITH_WALLCLOCK = new Set(['ingestion', 'edit']);

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  // Strip milliseconds for compactness, keep timezone
  return iso.replace(/\.\d+/, '');
}

function truncateQuote(quote: string, max = 120): string {
  if (quote.length <= max) return quote;
  return quote.slice(0, max - 1).trimEnd() + '…';
}

/**
 * Concept re-evidence stream — grouped by epoch for readability.
 *
 * Each epoch block shows kind + wall-clock context + every Instance
 * attached to that epoch. Pre-epoch (NULL event_id) Instances are
 * listed last as a known cohort, honest about their lack of metadata.
 */
export function formatConceptLifetime(result: ConceptLifetimeResponse): string {
  const lines: string[] = [];
  lines.push(`# Concept Lifetime — ${result.label ?? '(unlabeled)'}`);
  lines.push('');
  lines.push(`Concept ID: \`${result.concept_id}\``);
  lines.push(
    `Total Instances: ${result.total_instances} · Distinct Epochs: ${result.distinct_epochs}` +
      (result.pre_epoch_count > 0
        ? ` · Pre-epoch cohort: ${result.pre_epoch_count}`
        : '')
  );
  lines.push('');

  if (result.total_instances === 0) {
    lines.push('_No Instances recorded for this concept._');
    return lines.join('\n');
  }

  // Group by event_id (null → pre-epoch bucket, listed last).
  const groups = new Map<number | null, typeof result.instances>();
  for (const inst of result.instances) {
    const key = inst.event_id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(inst);
  }

  const orderedKeys: (number | null)[] = [
    ...[...groups.keys()].filter((k): k is number => k !== null).sort((a, b) => a - b),
    ...(groups.has(null) ? [null] : []),
  ];

  for (const key of orderedKeys) {
    const bucket = groups.get(key)!;
    if (key === null) {
      lines.push(`## Pre-epoch cohort (${bucket.length} instance${bucket.length === 1 ? '' : 's'})`);
      lines.push('_Created before ADR-203 — no event metadata available._');
    } else {
      const head = bucket[0];
      const kind = head.kind ?? '?';
      const wallclock = formatTime(head.occurred_at);
      const wallclockMeaning = KINDS_WITH_WALLCLOCK.has(kind) ? '' : ' _(forensic)_';
      lines.push(
        `## Epoch ${key} · \`${kind}\` · ${wallclock}${wallclockMeaning}` +
          (head.actor ? ` · actor: ${head.actor}` : '')
      );
    }
    for (const inst of bucket) {
      const source = inst.source_id ? ` → ${inst.source_id}` : '';
      lines.push(`- "${truncateQuote(inst.quote)}"${source}`);
    }
    lines.push('');
  }

  return lines.join('\n').trimEnd();
}

/**
 * Epoch event log page — most-recent-first, with next_cursor hint.
 */
export function formatEpochList(result: EpochListResponse): string {
  const lines: string[] = [];
  lines.push(`# Graph Epochs (page of ${result.events.length}, limit ${result.limit})`);
  lines.push('');

  if (result.events.length === 0) {
    lines.push('_No events match the current filter._');
    return lines.join('\n');
  }

  for (const ev of result.events) {
    const wallclock = formatTime(ev.occurred_at);
    const wallclockMeaning = KINDS_WITH_WALLCLOCK.has(ev.kind) ? '' : ' _(forensic)_';
    const actor = ev.actor ? ` · actor: ${ev.actor}` : '';
    const counter = ev.counter_after !== null ? ` · counter: ${ev.counter_after}` : '';
    lines.push(
      `- **${ev.event_id}** \`${ev.kind}\` · ${wallclock}${wallclockMeaning}${actor}${counter}`
    );
    const metaKeys = Object.keys(ev.metadata || {});
    if (metaKeys.length > 0) {
      const metaPairs = metaKeys
        .slice(0, 5)
        .map((k) => `${k}=${JSON.stringify((ev.metadata as any)[k])}`)
        .join(' · ');
      lines.push(`  _${metaPairs}_`);
    }
  }
  lines.push('');

  if (result.next_cursor !== null) {
    lines.push(`---`);
    lines.push(`Next page: pass \`cursor=${result.next_cursor}\` to continue.`);
  } else {
    lines.push(`---`);
    lines.push(`_No further pages for current filter._`);
  }

  return lines.join('\n');
}
