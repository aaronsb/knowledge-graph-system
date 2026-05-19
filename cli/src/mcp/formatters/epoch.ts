/**
 * MCP formatters for the graph epoch event log (ADR-203).
 *
 * Renders responses as compact markdown for token-efficient consumption
 * by agents. Visualizes the two-dimension model: logical-time ordering
 * via event_id, wall-clock via occurred_at, and the per-kind
 * `semantic_wallclock` flag (sourced from the API, originally from the
 * graph_epoch_kinds lookup table) as the discriminator for whether
 * wall-clock is semantically primary.
 *
 * Previously this formatter hardcoded a `KINDS_WITH_WALLCLOCK` set —
 * removed in the migration-064 round so kinds and their semantics live
 * in one place (the database).
 */

import type {
  ConceptLifetimeResponse,
  EpochListResponse,
} from '../../types/index.js';

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  // Strip milliseconds for compactness, keep timezone
  return iso.replace(/\.\d+/, '');
}

function truncateQuote(quote: string, max = 120): string {
  if (quote.length <= max) return quote;
  return quote.slice(0, max - 1).trimEnd() + '…';
}

function forensicSuffix(semanticWallclock: boolean | null | undefined): string {
  // null = no epoch row joined (e.g. pre-ADR-203 Instance). Treat as
  // "no statement" and omit the suffix entirely.
  if (semanticWallclock === null || semanticWallclock === undefined) return '';
  return semanticWallclock ? '' : ' _(forensic)_';
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
  const summary = [
    `Total Instances (full chain): ${result.total_instances}`,
    `Returned this page: ${result.returned_instances}`,
    `Distinct Epochs (page): ${result.distinct_epochs}`,
  ];
  if (result.pre_epoch_count > 0) {
    summary.push(`Pre-epoch cohort (page): ${result.pre_epoch_count}`);
  }
  lines.push(summary.join(' · '));
  lines.push(`Page: limit=${result.limit}, offset=${result.offset}${result.has_more ? ' — `has_more=true`' : ''}`);
  lines.push('');

  if (result.returned_instances === 0) {
    if (result.total_instances === 0) {
      lines.push('_No Instances recorded for this concept._');
    } else {
      lines.push('_Offset is past the end of the chain — try a smaller offset._');
    }
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
      lines.push('_Created before ADR-203 (or `record_epoch` failed) — no event metadata available._');
    } else {
      const head = bucket[0];
      const kind = head.kind ?? '?';
      const wallclock = formatTime(head.occurred_at);
      const suffix = forensicSuffix(head.semantic_wallclock);
      lines.push(
        `## Epoch ${key} · \`${kind}\` · ${wallclock}${suffix}` +
          (head.actor ? ` · actor: ${head.actor}` : '')
      );
    }
    for (const inst of bucket) {
      const source = inst.source_id ? ` → ${inst.source_id}` : '';
      lines.push(`- "${truncateQuote(inst.quote)}"${source}`);
    }
    lines.push('');
  }

  if (result.has_more) {
    lines.push(`---`);
    lines.push(`Next page: pass \`lifetime_offset=${result.offset + result.returned_instances}\` to continue.`);
  }

  return lines.join('\n').trimEnd();
}

/**
 * Epoch event log page — most-recent-first, with next_cursor hint.
 *
 * Each row's `_forensic_` suffix is driven by `semantic_wallclock` from
 * the API (originally from kg_api.graph_epoch_kinds), not by a local
 * hardcoded set — adding a new kind only requires inserting a row in
 * the lookup table.
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
    const suffix = forensicSuffix(ev.semantic_wallclock);
    const actor = ev.actor ? ` · actor: ${ev.actor}` : '';
    const counter = ev.counter_after !== null ? ` · counter: ${ev.counter_after}` : '';
    lines.push(
      `- **${ev.event_id}** \`${ev.kind}\` · ${wallclock}${suffix}${actor}${counter}`
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
