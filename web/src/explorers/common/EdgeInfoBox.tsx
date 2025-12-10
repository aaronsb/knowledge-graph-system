/**
 * Edge Info Box - Speech bubble style info display for edges
 * Shared component for both 2D and 3D explorers
 */

import React from 'react';
import { getZIndexValue } from '../../config/zIndex';

export interface EdgeInfoBoxProps {
  info: {
    linkKey: string;
    sourceId: string;
    targetId: string;
    type: string;
    confidence: number;
    category?: string;
    // ADR-051: Edge provenance metadata
    created_by?: string;
    source?: string;
    job_id?: string;
    document_id?: string;
    created_at?: string;
    // ADR-065: Vocabulary epistemic status metadata
    avg_grounding?: number;
    epistemic_status?: string;
    x: number;
    y: number;
  };
  onDismiss: () => void;
}

export const EdgeInfoBox: React.FC<EdgeInfoBoxProps> = ({ info, onDismiss }) => {
  return (
    <div
      className="absolute pointer-events-auto"
      style={{
        left: `${info.x}px`,
        top: `${info.y}px`,
        transform: 'translate(-50%, -100%)', // Position above the edge midpoint
        zIndex: getZIndexValue('infoBox'), // Info boxes appear below search results
      }}
    >
      {/* Speech bubble pointer - theme-aware */}
      <div className="relative">
        <div
          className="absolute left-1/2 bottom-0 w-0 h-0 border-l-[8px] border-r-[8px] border-t-[8px] border-l-transparent border-r-transparent border-t-card dark:border-t-gray-800"
          style={{
            transform: 'translateX(-50%) translateY(100%)',
          }}
        />
        {/* Info box content - theme-aware */}
        <div
          className="bg-card rounded-lg border border-border px-4 py-3 cursor-pointer transition-shadow shadow-lg dark:shadow-[8px_8px_12px_rgba(0,0,0,0.8)]"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          style={{
            minWidth: '200px',
          }}
        >
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-card-foreground border-b border-border pb-2">
              Edge Information
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Type:</span>
                <span className="font-medium text-card-foreground">{info.type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Confidence:</span>
                <span className="font-medium text-card-foreground">
                  {(info.confidence * 100).toFixed(1)}%
                </span>
              </div>
              {info.category && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Category:</span>
                  <span className="font-medium text-card-foreground">{info.category}</span>
                </div>
              )}
              {/* ADR-065: Epistemic status metadata */}
              {info.avg_grounding !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Grounding:</span>
                  <span className="font-medium text-card-foreground">
                    {info.avg_grounding.toFixed(2)}
                  </span>
                </div>
              )}
              {info.epistemic_status && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status:</span>
                  <span className="font-medium text-card-foreground text-xs">{info.epistemic_status}</span>
                </div>
              )}
              {/* ADR-051: Provenance metadata section */}
              {(info.created_by || info.source || info.job_id || info.document_id || info.created_at) && (
                <>
                  <div className="pt-2 border-t border-border">
                    <div className="text-xs font-semibold text-foreground mb-1">Provenance</div>
                  </div>
                  {info.source && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground text-xs">Source:</span>
                      <span className="font-medium text-card-foreground text-xs">{info.source}</span>
                    </div>
                  )}
                  {info.created_by && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground text-xs">Created By:</span>
                      <span className="font-medium text-card-foreground text-xs">{info.created_by}</span>
                    </div>
                  )}
                  {info.created_at && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground text-xs">Created:</span>
                      <span className="font-medium text-card-foreground text-xs">
                        {new Date(info.created_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {info.job_id && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground text-xs">Job ID:</span>
                      <span className="font-mono text-card-foreground text-xs">
                        {info.job_id.substring(0, 8)}...
                      </span>
                    </div>
                  )}
                  {info.document_id && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground text-xs">Document:</span>
                      <span className="font-mono text-card-foreground text-xs">
                        {info.document_id.substring(0, 8)}...
                      </span>
                    </div>
                  )}
                </>
              )}
              <div className="text-xs text-muted-foreground pt-2 border-t border-border">
                Click to dismiss
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
