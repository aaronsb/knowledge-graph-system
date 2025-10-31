/**
 * Edge Info Box - Speech bubble style info display for edges
 * Shared component for both 2D and 3D explorers
 */

import React from 'react';

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
        zIndex: 9999, // Ensure info box draws on top of everything
      }}
    >
      {/* Speech bubble pointer - always dark */}
      <div className="relative">
        <div
          className="absolute left-1/2 bottom-0 w-0 h-0"
          style={{
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid rgb(31, 41, 55)', // gray-800
            transform: 'translateX(-50%) translateY(100%)',
          }}
        />
        {/* Info box content - always dark theme */}
        <div
          className="bg-gray-800 rounded-lg border border-gray-600 px-4 py-3 cursor-pointer transition-shadow"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          style={{
            minWidth: '200px',
            boxShadow: '8px 8px 12px rgba(0, 0, 0, 0.8)'
          }}
        >
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-gray-100 border-b border-gray-700 pb-2">
              Edge Information
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-400">Type:</span>
                <span className="font-medium text-gray-100">{info.type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Confidence:</span>
                <span className="font-medium text-gray-100">
                  {(info.confidence * 100).toFixed(1)}%
                </span>
              </div>
              {info.category && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Category:</span>
                  <span className="font-medium text-gray-100">{info.category}</span>
                </div>
              )}
              {/* ADR-051: Provenance metadata section */}
              {(info.created_by || info.source || info.job_id || info.document_id || info.created_at) && (
                <>
                  <div className="pt-2 border-t border-gray-700">
                    <div className="text-xs font-semibold text-gray-300 mb-1">Provenance</div>
                  </div>
                  {info.source && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-xs">Source:</span>
                      <span className="font-medium text-gray-100 text-xs">{info.source}</span>
                    </div>
                  )}
                  {info.created_by && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-xs">Created By:</span>
                      <span className="font-medium text-gray-100 text-xs">{info.created_by}</span>
                    </div>
                  )}
                  {info.created_at && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-xs">Created:</span>
                      <span className="font-medium text-gray-100 text-xs">
                        {new Date(info.created_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {info.job_id && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-xs">Job ID:</span>
                      <span className="font-mono text-gray-100 text-xs">
                        {info.job_id.substring(0, 8)}...
                      </span>
                    </div>
                  )}
                  {info.document_id && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-xs">Document:</span>
                      <span className="font-mono text-gray-100 text-xs">
                        {info.document_id.substring(0, 8)}...
                      </span>
                    </div>
                  )}
                </>
              )}
              <div className="text-xs text-gray-400 pt-2 border-t border-gray-700">
                Click to dismiss
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
