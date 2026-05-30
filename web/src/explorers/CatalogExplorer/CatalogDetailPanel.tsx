/**
 * Catalog Detail Panel (ADR-501)
 *
 * Shows full metadata for the selected catalog node, hydrated from
 * /catalog/node/{id} (the stat call) so we pick up graph_epoch / indexed_at
 * and any kind-specific properties not carried in the tree listing.
 */

import React, { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { CatalogNode, CatalogNodeResponse } from '../../types/catalog';

interface CatalogDetailPanelProps {
  node: CatalogNode | null;
}

const KIND_LABEL: Record<string, string> = {
  ontology: 'Ontology',
  document: 'Document',
  concept: 'Concept',
};

export const CatalogDetailPanel: React.FC<CatalogDetailPanelProps> = ({ node }) => {
  const [detail, setDetail] = useState<CatalogNodeResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!node) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    apiClient
      .getCatalogNode(node.id, node.kind)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [node]);

  if (!node) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        Select a node to see its details.
      </div>
    );
  }

  const d = detail || node;
  const props = Object.entries((d as CatalogNodeResponse).properties || {});

  return (
    <div className="p-4 space-y-3 text-sm">
      <div>
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {KIND_LABEL[d.kind] || d.kind}
        </div>
        <div className="font-medium break-words">{d.name}</div>
      </div>

      <dl className="space-y-1.5">
        <Row label="ID" value={d.id} mono />
        {d.kind !== 'concept' && d.child_count != null && (
          <Row label="Children" value={String(d.child_count)} />
        )}
        {d.content_type && <Row label="Content type" value={d.content_type} />}
        {(d as CatalogNodeResponse).graph_epoch != null && (
          <Row label="Indexed at epoch" value={String((d as CatalogNodeResponse).graph_epoch)} />
        )}
        {props.map(([k, v]) => (
          <Row key={k} label={k} value={String(v)} />
        ))}
      </dl>

      {loading && <div className="text-xs text-muted-foreground">Refreshing…</div>}
    </div>
  );
};

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground min-w-[7rem] flex-shrink-0">{label}</dt>
      <dd className={`break-words ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}
