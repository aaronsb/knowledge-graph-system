/**
 * Document Viewer Modal - Shared Component
 *
 * Displays document content in a modal with download capability.
 * Used by ReportWorkspace, DocumentExplorer, and other views.
 * Renders markdown files with proper formatting.
 * Supports passage search highlighting via the highlights prop.
 */

import React, { useState, useEffect, useCallback, useMemo, useRef, type MouseEvent } from 'react';
import { FileText, Download, X, Loader2, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { apiClient } from '../../api/client';

/** Sanitization schema: default markdown + our highlight <mark> tags only. */
const highlightSanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), 'mark'],
  attributes: {
    ...defaultSchema.attributes,
    mark: ['style', 'data-hl-color', 'data-hl-idx'],
  },
};
import type { DocumentHighlight } from '../../explorers/DocumentExplorer/types';

export interface DocumentViewerProps {
  /** Document to view */
  document: {
    document_id: string;
    filename: string;
    content_type?: string;
  } | null;
  /** Called when the modal should close */
  onClose: () => void;
  /** Passage search highlights to apply */
  highlights?: DocumentHighlight[];
  /** Optional content injected below the header (e.g. query hit indicators). */
  headerExtra?: React.ReactNode;
  /** Color → query text lookup for the internal query hit bar with scroll-to cycling. */
  queryLabels?: Map<string, string>;
}

interface DocumentContent {
  content: unknown;
  chunks: Array<{
    source_id: string;
    paragraph: number;
    full_text: string;
  }>;
}

/** Escape special regex characters in a string. */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Insert <mark> tags into text for each highlight match.
 * Uses string matching on chunkText to find highlight positions.
 */
function applyHighlightsToText(
  text: string,
  highlights: Array<{ chunkText: string; color: string }>
): string {
  if (!highlights.length) return text;

  // Build ranges: find each chunkText in the source text
  const ranges: Array<{ start: number; end: number; color: string }> = [];

  for (const h of highlights) {
    if (!h.chunkText) continue;
    // Search for the chunk text — use first 100 chars for matching to avoid huge regex
    const needle = h.chunkText.substring(0, 100);
    const escapedNeedle = escapeRegex(needle);
    try {
      const regex = new RegExp(escapedNeedle, 'g');
      let match;
      while ((match = regex.exec(text)) !== null) {
        ranges.push({
          start: match.index,
          end: Math.min(match.index + h.chunkText.length, text.length),
          color: h.color,
        });
      }
    } catch {
      // Skip invalid regex
    }
  }

  if (ranges.length === 0) return text;

  // Sort ranges by start position
  ranges.sort((a, b) => a.start - b.start);

  // Build highlighted text by inserting <mark> tags with scroll-target attributes
  let result = '';
  let cursor = 0;
  const colorIndexCounters = new Map<string, number>();

  for (const range of ranges) {
    if (range.start < cursor) continue; // skip overlapping
    const idx = colorIndexCounters.get(range.color) || 0;
    colorIndexCounters.set(range.color, idx + 1);
    result += text.slice(cursor, range.start);
    result += `<mark data-hl-color="${range.color}" data-hl-idx="${idx}" style="background-color: ${range.color}40; padding: 1px 0;">`;
    result += text.slice(range.start, range.end);
    result += '</mark>';
    cursor = range.end;
  }

  result += text.slice(cursor);
  return result;
}

/**
 * Render text with inline highlight <mark> elements (for non-markdown chunks).
 */
function HighlightedText({ text, highlights }: {
  text: string;
  highlights: Array<{ chunkText: string; color: string }>;
}): React.ReactElement {
  if (!highlights.length) {
    return <>{text}</>;
  }

  // Build ranges
  const ranges: Array<{ start: number; end: number; color: string }> = [];

  for (const h of highlights) {
    if (!h.chunkText) continue;
    const needle = h.chunkText.substring(0, 100);
    const idx = text.indexOf(needle);
    if (idx >= 0) {
      ranges.push({
        start: idx,
        end: Math.min(idx + h.chunkText.length, text.length),
        color: h.color,
      });
    }
  }

  if (ranges.length === 0) return <>{text}</>;

  ranges.sort((a, b) => a.start - b.start);

  const parts: React.ReactNode[] = [];
  let cursor = 0;
  const colorIndexCounters = new Map<string, number>();

  for (let i = 0; i < ranges.length; i++) {
    const range = ranges[i];
    if (range.start < cursor) continue;
    if (range.start > cursor) {
      parts.push(text.slice(cursor, range.start));
    }
    const idx = colorIndexCounters.get(range.color) || 0;
    colorIndexCounters.set(range.color, idx + 1);
    parts.push(
      <mark
        key={`hl-${i}`}
        data-hl-color={range.color}
        data-hl-idx={idx}
        style={{ backgroundColor: `${range.color}40`, padding: '1px 0' }}
      >
        {text.slice(range.start, range.end)}
      </mark>
    );
    cursor = range.end;
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return <>{parts}</>;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  document,
  onClose,
  highlights,
  headerExtra,
  queryLabels,
}) => {
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [scrollIndex, setScrollIndex] = useState<Record<string, number>>({});

  // Load document content when document changes
  useEffect(() => {
    if (!document) {
      setContent(null);
      return;
    }

    const loadContent = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await apiClient.getDocumentContent(document.document_id);
        setContent(result);
      } catch (err) {
        console.error('Failed to load document content:', err);
        setError('Failed to load document content');
        setContent(null);
      } finally {
        setIsLoading(false);
      }
    };

    loadContent();
  }, [document]);

  // Build per-chunk highlight lookup from sourceId
  const chunkHighlights = useMemo(() => {
    if (!highlights?.length || !content?.chunks.length) return new Map<string, Array<{ chunkText: string; color: string }>>();

    const map = new Map<string, Array<{ chunkText: string; color: string }>>();
    for (const h of highlights) {
      const existing = map.get(h.sourceId) || [];
      existing.push({ chunkText: h.chunkText, color: h.color });
      map.set(h.sourceId, existing);
    }
    return map;
  }, [highlights, content]);

  // All highlights flattened (for markdown full-text highlighting)
  const allHighlightTexts = useMemo(() => {
    if (!highlights?.length) return [];
    return highlights.map(h => ({ chunkText: h.chunkText, color: h.color }));
  }, [highlights]);

  // Count highlights per query color for the internal hit bar
  const hitCountsByColor = useMemo(() => {
    if (!highlights?.length || !queryLabels?.size) return new Map<string, number>();
    const counts = new Map<string, number>();
    for (const h of highlights) {
      counts.set(h.color, (counts.get(h.color) || 0) + 1);
    }
    return counts;
  }, [highlights, queryLabels]);

  // Reset scroll indices when document changes
  useEffect(() => {
    setScrollIndex({});
  }, [document]);

  // Scroll to highlight by color, cycling through matches
  const handleScrollToHighlight = useCallback((color: string, _e: MouseEvent) => {
    const container = contentRef.current;
    if (!container) return;

    const marks = container.querySelectorAll<HTMLElement>(`mark[data-hl-color="${color}"]`);
    if (marks.length === 0) return;

    const currentIdx = scrollIndex[color] ?? -1;
    const nextIdx = (currentIdx + 1) % marks.length;

    setScrollIndex(prev => ({ ...prev, [color]: nextIdx }));

    // Remove previous "active" ring from all marks of this color
    marks.forEach(m => m.style.outline = '');

    const target = marks[nextIdx];
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.style.outline = `2px solid ${color}`;
    target.style.outlineOffset = '1px';

    // Clear outline after a brief moment
    setTimeout(() => { target.style.outline = ''; }, 2000);
  }, [scrollIndex]);

  // Download document
  const handleDownload = useCallback(() => {
    if (!document || !content) return;

    let downloadContent: string;
    let mimeType: string;
    let extension: string;

    const contentType = document.content_type || 'text/plain';

    if (contentType === 'application/json' || typeof content.content === 'object') {
      downloadContent = JSON.stringify(content.content, null, 2);
      mimeType = 'application/json';
      extension = '.json';
    } else {
      downloadContent = content.chunks.length > 0
        ? content.chunks.map(c => c.full_text).join('\n\n')
        : String(content.content);
      mimeType = 'text/plain';
      extension = '.txt';
    }

    const blob = new Blob([downloadContent], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = document.filename.replace(/\.[^.]+$/, '') + extension;
    a.click();
    URL.revokeObjectURL(url);
  }, [document, content]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!document) return null;

  // Detect if file is markdown
  const isMarkdown = document.filename.endsWith('.md') ||
                     document.content_type === 'text/markdown';

  // Get full text content for markdown rendering
  const getFullText = (): string => {
    if (!content) return '';
    if (content.chunks.length > 0) {
      return content.chunks.map(c => c.full_text).join('\n\n');
    }
    return typeof content.content === 'string' ? content.content : '';
  };

  // Get highlighted markdown (with <mark> tags injected)
  const getHighlightedMarkdown = (): string => {
    const text = getFullText();
    if (!allHighlightTexts.length) return text;
    return applyHighlightsToText(text, allHighlightTexts);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-card border rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col m-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-muted-foreground" />
            <div>
              <h3 className="font-semibold">{document.filename}</h3>
              <p className="text-xs text-muted-foreground">
                {document.content_type || 'document'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              disabled={!content}
              className="p-2 rounded hover:bg-accent disabled:opacity-50"
              title="Download"
            >
              <Download className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-accent"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Injected header content (e.g. query hit indicators) */}
        {headerExtra}

        {/* Internal query hit bar with scroll-to cycling */}
        {queryLabels && hitCountsByColor.size > 0 && (
          <div className="flex border-b">
            {Array.from(hitCountsByColor.entries()).map(([color, count]) => (
              <button
                key={color}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 text-[10px] font-medium cursor-pointer hover:brightness-110 transition-all"
                style={{ backgroundColor: `${color}25`, color }}
                onClick={(e) => handleScrollToHighlight(color, e)}
                title={`Click to cycle through "${queryLabels.get(color) || '?'}" highlights`}
              >
                <span className="truncate">{queryLabels.get(color) || '?'}</span>
                <span className="opacity-70">{count}</span>
                <ChevronDown className="w-3 h-3 opacity-50" />
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        <div ref={contentRef} className="flex-1 overflow-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-destructive">
              {error}
            </div>
          ) : content ? (
            <div className="space-y-4">
              {isMarkdown ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown rehypePlugins={[rehypeRaw, [rehypeSanitize, highlightSanitizeSchema]]}>
                    {getHighlightedMarkdown()}
                  </ReactMarkdown>
                </div>
              ) : content.chunks.length > 0 ? (
                content.chunks.map((chunk, idx) => (
                  <div key={`${chunk.source_id}-${idx}`} className="border rounded-lg p-4">
                    <div className="text-xs text-muted-foreground mb-2">
                      Paragraph {chunk.paragraph + 1}
                    </div>
                    <div className="text-sm whitespace-pre-wrap">
                      <HighlightedText
                        text={chunk.full_text}
                        highlights={chunkHighlights.get(chunk.source_id) || []}
                      />
                    </div>
                  </div>
                ))
              ) : typeof content.content === 'object' ? (
                <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto">
                  {JSON.stringify(content.content, null, 2)}
                </pre>
              ) : (
                <div className="text-sm whitespace-pre-wrap">
                  {String(content.content)}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              No content available
            </div>
          )}
        </div>

        {/* Footer */}
        {content && content.chunks.length > 0 && !isMarkdown && (
          <div className="px-4 py-2 border-t text-xs text-muted-foreground">
            {content.chunks.length} chunk{content.chunks.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentViewer;
