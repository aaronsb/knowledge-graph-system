/**
 * Catalog Detail Panel (ADR-501)
 *
 * Shows metadata for the selected catalog node. The base stat comes from
 * /catalog/node/{id}; kind-specific enrichment reuses existing endpoints (no
 * new API paths):
 *   - concept:  getConceptDetails  → description, grounding, search terms
 *   - document: getDocumentContent → stored content preview (text/image)
 *   - ontology: listOntologies     → document / concept / source counts
 */

import React, { useEffect, useState } from 'react';
import { Copy, Download, Check } from 'lucide-react';
import { apiClient } from '../../api/client';
import type { CatalogNode, CatalogNodeResponse } from '../../types/catalog';

/** Trigger a browser download of `content` as `filename` (no new endpoint —
 *  builds a Blob from data already in hand). */
function downloadBlob(content: string, filename: string, mime = 'text/plain') {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Copy + download actions for a piece of content. Copy uses the async
 *  clipboard API; download writes a Blob. Both operate on data already
 *  fetched — no extra requests. */
const ActionRow: React.FC<{
  copyText?: string;
  download?: { content: string; filename: string; mime?: string };
  copyLabel?: string;
}> = ({ copyText, download, copyLabel = 'Copy' }) => {
  const [copied, setCopied] = useState(false);
  const doCopy = async () => {
    if (!copyText) return;
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — no-op */
    }
  };
  return (
    <div className="flex gap-2 pt-1">
      {copyText && (
        <button
          onClick={doCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-border hover:bg-muted"
        >
          {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
          {copied ? 'Copied' : copyLabel}
        </button>
      )}
      {download && (
        <button
          onClick={() => downloadBlob(download.content, download.filename, download.mime)}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-border hover:bg-muted"
        >
          <Download className="w-3 h-3" />
          Download
        </button>
      )}
    </div>
  );
};

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
    <div className="p-4 space-y-3 text-sm overflow-auto">
      <div>
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {KIND_LABEL[d.kind] || d.kind}
        </div>
        <div className="font-medium break-words">{d.name}</div>
        <ActionRow copyText={d.id} copyLabel="Copy ID" />
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

      {/* Kind-specific enrichment, reusing existing endpoints. */}
      {node.kind === 'concept' && <ConceptDetail conceptId={node.id} />}
      {node.kind === 'document' && (
        <DocumentDetail documentId={node.id} filename={node.name} contentType={node.content_type} />
      )}
      {node.kind === 'ontology' && <OntologyDetail name={node.name} />}

      {loading && <div className="text-xs text-muted-foreground">Refreshing…</div>}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Concept: description + grounding + search terms (getConceptDetails)
// ---------------------------------------------------------------------------

const ConceptDetail: React.FC<{ conceptId: string }> = ({ conceptId }) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiClient
      .getConceptDetails(conceptId)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [conceptId]);

  if (loading) return <Loading />;
  if (!data) return null;

  const terms: string[] = data.search_terms || [];

  return (
    <div className="space-y-2 border-t border-border pt-3">
      {data.description && (
        <div>
          <SectionLabel>Description</SectionLabel>
          <p className="leading-snug">{data.description}</p>
          <ActionRow copyText={data.description} copyLabel="Copy description" />
        </div>
      )}
      <dl className="space-y-1.5">
        {data.grounding_display && <Row label="Grounding" value={data.grounding_display} />}
        {typeof data.grounding_strength === 'number' && (
          <Row label="Grounding strength" value={data.grounding_strength.toFixed(2)} />
        )}
        {typeof data.evidence_count === 'number' && (
          <Row label="Evidence" value={String(data.evidence_count)} />
        )}
      </dl>
      {terms.length > 0 && (
        <div>
          <SectionLabel>Search terms</SectionLabel>
          <div className="flex flex-wrap gap-1">
            {terms.map((t) => (
              <SearchTermChip key={t} term={t} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Document: stored content preview (getDocumentContent / image)
// ---------------------------------------------------------------------------

const DocumentDetail: React.FC<{
  documentId: string;
  filename: string;
  contentType?: string | null;
}> = ({ documentId, filename, contentType }) => {
  const [text, setText] = useState<string | null>(null);
  const [firstSourceId, setFirstSourceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    apiClient
      .getDocumentContent(documentId)
      .then((d) => {
        if (cancelled) return;
        // Prefer joined chunk text; fall back to a stringified content blob.
        const joined =
          Array.isArray(d.chunks) && d.chunks.length > 0
            ? d.chunks.map((c) => c.full_text).join('\n\n')
            : typeof d.content === 'string'
            ? d.content
            : JSON.stringify(d.content ?? '', null, 2);
        setText(joined);
        if (Array.isArray(d.chunks) && d.chunks.length > 0) {
          setFirstSourceId(d.chunks[0].source_id);
        }
      })
      .catch(() => !cancelled && setError(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const isImage = contentType === 'image';

  const downloadImage = async () => {
    if (!firstSourceId) return;
    // Reuses the existing /sources/{id}/image endpoint (returns a blob URL).
    const url = await apiClient.getSourceImageUrl(firstSourceId);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (loading) return <Loading />;

  return (
    <div className="space-y-1 border-t border-border pt-3">
      <SectionLabel>{isImage ? 'Stored content (prose)' : 'Content'}</SectionLabel>
      {error ? (
        <p className="text-xs text-muted-foreground">Content unavailable.</p>
      ) : (
        <>
          <pre className="text-xs whitespace-pre-wrap break-words max-h-96 overflow-auto bg-muted/50 rounded p-2">
            {text}
          </pre>
          <ActionRow
            copyText={text || undefined}
            copyLabel={isImage ? 'Copy prose' : 'Copy text'}
            download={
              text != null
                ? {
                    content: text,
                    filename: isImage ? `${filename}.prose.txt` : filename,
                    mime: 'text/plain',
                  }
                : undefined
            }
          />
          {isImage && firstSourceId && (
            <button
              onClick={downloadImage}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-border hover:bg-muted mt-1"
            >
              <Download className="w-3 h-3" />
              Download image
            </button>
          )}
        </>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Ontology: basic stats (listOntologies — already returns per-ontology counts)
// ---------------------------------------------------------------------------

const OntologyDetail: React.FC<{ name: string }> = ({ name }) => {
  const [stats, setStats] = useState<{
    source_count: number;
    file_count: number;
    concept_count: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiClient
      .listOntologies()
      .then((res) => {
        if (cancelled) return;
        const match = res.ontologies.find((o) => o.ontology === name);
        setStats(
          match
            ? {
                source_count: match.source_count,
                file_count: match.file_count,
                concept_count: match.concept_count,
              }
            : null
        );
      })
      .catch(() => !cancelled && setStats(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [name]);

  if (loading) return <Loading />;
  if (!stats) return null;

  return (
    <div className="space-y-1 border-t border-border pt-3">
      <SectionLabel>Statistics</SectionLabel>
      <dl className="space-y-1.5">
        <Row label="Documents" value={String(stats.file_count)} />
        <Row label="Source chunks" value={String(stats.source_count)} />
        <Row label="Concepts" value={String(stats.concept_count)} />
      </dl>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function Loading() {
  return <div className="text-xs text-muted-foreground border-t border-border pt-3">Loading…</div>;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">{children}</div>;
}

/** A search-term chip that copies its term to the clipboard on click. */
function SearchTermChip({ term }: { term: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(term);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard blocked — no-op */
    }
  };
  return (
    <button
      onClick={copy}
      title="Click to copy"
      className={`px-1.5 py-0.5 rounded text-xs transition-colors ${
        copied ? 'bg-green-500/20 text-green-600' : 'bg-muted hover:bg-muted-foreground/20'
      }`}
    >
      {copied ? 'Copied!' : term}
    </button>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground min-w-[7rem] flex-shrink-0">{label}</dt>
      <dd className={`break-words ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}
