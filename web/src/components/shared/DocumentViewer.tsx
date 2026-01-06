/**
 * Document Viewer Modal - Shared Component
 *
 * Displays document content in a modal with download capability.
 * Used by ReportWorkspace, DocumentExplorer, and other views.
 * Renders markdown files with proper formatting.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Download, X, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { apiClient } from '../../api/client';

export interface DocumentViewerProps {
  /** Document to view */
  document: {
    document_id: string;
    filename: string;
    content_type?: string;
  } | null;
  /** Called when the modal should close */
  onClose: () => void;
}

interface DocumentContent {
  content: unknown;
  chunks: Array<{
    source_id: string;
    paragraph: number;
    full_text: string;
  }>;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  document,
  onClose,
}) => {
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      // For text content, concatenate chunks
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

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
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
                  <ReactMarkdown>{getFullText()}</ReactMarkdown>
                </div>
              ) : content.chunks.length > 0 ? (
                content.chunks.map((chunk) => (
                  <div key={chunk.source_id} className="border rounded-lg p-4">
                    <div className="text-xs text-muted-foreground mb-2">
                      Paragraph {chunk.paragraph + 1}
                    </div>
                    <div className="text-sm whitespace-pre-wrap">
                      {chunk.full_text}
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
