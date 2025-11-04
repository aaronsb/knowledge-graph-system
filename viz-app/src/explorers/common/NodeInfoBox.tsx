/**
 * Node Info Box - Speech bubble style info display for nodes with collapsible sections
 * Shared component for both 2D and 3D explorers
 */

import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { apiClient } from '../../api/client';
import { formatGrounding, getRelationshipTextColor } from './utils';

/**
 * EvidenceImage - Display image from evidence source (ADR-057)
 */
const EvidenceImage: React.FC<{ sourceId: string }> = ({ sourceId }) => {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let currentUrl: string | null = null;

    const fetchImage = async () => {
      setLoading(true);
      setError(false);
      try {
        const url = await apiClient.getSourceImageUrl(sourceId);
        currentUrl = url;
        setImageUrl(url);
      } catch (err) {
        console.error('Failed to fetch image:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();

    // Cleanup: revoke blob URL when component unmounts or sourceId changes
    return () => {
      if (currentUrl) {
        URL.revokeObjectURL(currentUrl);
      }
    };
  }, [sourceId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-2 text-gray-500">
        <span className="text-xs">Loading image...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-2 text-gray-500">
        <span className="text-xs">🖼️ Image available (failed to load)</span>
      </div>
    );
  }

  if (!imageUrl) {
    return null;
  }

  return (
    <div className="rounded border border-gray-600 overflow-hidden">
      <img
        src={imageUrl}
        alt="Evidence"
        className="w-full h-auto"
        style={{ maxHeight: '200px', objectFit: 'contain', backgroundColor: '#1f2937' }}
      />
    </div>
  );
};

export interface NodeInfoBoxProps {
  info: {
    nodeId: string;
    label: string;
    group: string;
    degree: number;
    x: number;
    y: number;
  };
  onDismiss: () => void;
}

export const NodeInfoBox: React.FC<NodeInfoBoxProps> = ({ info, onDismiss }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['overview']));
  const [detailedData, setDetailedData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Fetch detailed node data on mount
  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      try {
        const response = await apiClient.getConceptDetails(info.nodeId);
        setDetailedData(response);
      } catch (error) {
        console.error('Failed to fetch node details:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [info.nodeId]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  };

  return (
    <div
      className="absolute pointer-events-auto"
      style={{
        left: `${info.x}px`,
        top: `${info.y}px`,
        transform: 'translate(-50%, calc(-100% - 20px))', // Position above node with offset
        zIndex: 9999, // Ensure info box draws on top of everything
      }}
    >
      <div className="relative">
        {/* Speech bubble pointer - always dark */}
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
          className="bg-gray-800 rounded-lg border border-gray-600 cursor-pointer transition-shadow"
          style={{
            minWidth: '280px',
            maxWidth: '400px',
            boxShadow: '8px 8px 12px rgba(0, 0, 0, 0.8)'
          }}
        >
          {/* Header - always visible */}
          <div
            className="px-4 py-3 border-b border-gray-700"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
          >
            <div className="font-semibold text-gray-100 text-base">
              {info.label}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              Click to dismiss
            </div>
          </div>

          {/* Collapsible sections */}
          <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
            {/* Overview Section */}
            <div className="border-b border-gray-700">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleSection('overview');
                }}
                className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
              >
                <span className="font-medium text-sm text-gray-300">Overview</span>
                {expandedSections.has('overview') ? (
                  <ChevronDown size={16} className="text-gray-500" />
                ) : (
                  <ChevronRight size={16} className="text-gray-500" />
                )}
              </button>
              {expandedSections.has('overview') && (
                <div className="px-4 py-3 space-y-2 text-sm bg-gray-750">
                  {detailedData?.description && (
                    <div className="pb-2 border-b border-gray-600">
                      <div className="text-gray-400 text-xs mb-1">Description:</div>
                      <div className="text-gray-300 italic">{detailedData.description}</div>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-400">Ontology:</span>
                    <span className="font-medium text-gray-100">{info.group}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Connections:</span>
                    <span className="font-medium text-gray-100">{info.degree}</span>
                  </div>
                  {detailedData?.grounding_strength !== undefined && detailedData?.grounding_strength !== null && (() => {
                    const grounding = formatGrounding(detailedData.grounding_strength);
                    return grounding && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Grounding:</span>
                        <span className="font-medium" style={{ color: grounding.color }}>
                          {grounding.emoji} {grounding.label} ({grounding.percentage})
                        </span>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Relationships Section */}
            {detailedData?.relationships && (
              <div className="border-b border-gray-700">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSection('relationships');
                  }}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
                >
                  <span className="font-medium text-sm text-gray-300">
                    Relationships ({detailedData.relationships.length})
                  </span>
                  {expandedSections.has('relationships') ? (
                    <ChevronDown size={16} className="text-gray-500" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-500" />
                  )}
                </button>
                {expandedSections.has('relationships') && (
                  <div className="px-4 py-3 space-y-2 text-xs bg-gray-750">
                    {detailedData.relationships.slice(0, 20).map((rel: any, idx: number) => {
                      const relType = rel.rel_type || rel.type;
                      const color = getRelationshipTextColor(relType);
                      return (
                        <div key={`${rel.to_id || rel.target_id}-${relType}-${idx}`} className="text-gray-300">
                          <span className="font-medium" style={{ color }}>{relType}</span> → {rel.to_label || rel.target_label || rel.to_id}
                        </div>
                      );
                    })}
                    {detailedData.relationships.length > 20 && (
                      <div className="text-gray-500 italic">
                        +{detailedData.relationships.length - 20} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Evidence Section */}
            {detailedData?.instances && (
              <div className="border-b border-gray-700">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSection('evidence');
                  }}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
                >
                  <span className="font-medium text-sm text-gray-300">
                    Evidence ({detailedData.instances.length})
                  </span>
                  {expandedSections.has('evidence') ? (
                    <ChevronDown size={16} className="text-gray-500" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-500" />
                  )}
                </button>
                {expandedSections.has('evidence') && (
                  <div className="px-4 py-3 space-y-3 text-xs bg-gray-750">
                    {detailedData.instances.slice(0, 10).map((instance: any, idx: number) => (
                      <div key={`${instance.instance_id || instance.id || idx}-${instance.quote?.substring(0, 20) || ''}`} className="space-y-2">
                        <div className="text-gray-300 italic border-l-2 border-gray-600 pl-2">
                          "{instance.quote?.substring(0, 150)}{instance.quote?.length > 150 ? '...' : ''}"
                        </div>
                        {/* ADR-057: Display image if available */}
                        {instance.has_image && instance.source_id && (
                          <EvidenceImage sourceId={instance.source_id} />
                        )}
                      </div>
                    ))}
                    {detailedData.instances.length > 10 && (
                      <div className="text-gray-500 italic">
                        +{detailedData.instances.length - 10} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ADR-051: Provenance Section */}
            {detailedData?.provenance && (
              <div className="border-b border-gray-700">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSection('provenance');
                  }}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
                >
                  <span className="font-medium text-sm text-gray-300">
                    Provenance
                  </span>
                  {expandedSections.has('provenance') ? (
                    <ChevronDown size={16} className="text-gray-500" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-500" />
                  )}
                </button>
                {expandedSections.has('provenance') && (
                  <div className="px-4 py-3 space-y-2 text-xs bg-gray-750">
                    {/* Document metadata (for DocumentMeta nodes) */}
                    {detailedData.provenance.filename && (
                      <div className="space-y-1">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Filename:</span>
                          <span className="font-medium text-gray-100">{detailedData.provenance.filename}</span>
                        </div>
                        {detailedData.provenance.source_type && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Source Type:</span>
                            <span className="font-medium text-gray-100">{detailedData.provenance.source_type}</span>
                          </div>
                        )}
                        {detailedData.provenance.source_path && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Path:</span>
                            <span className="font-mono text-gray-100 text-xs break-all">{detailedData.provenance.source_path}</span>
                          </div>
                        )}
                        {detailedData.provenance.hostname && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Hostname:</span>
                            <span className="font-medium text-gray-100">{detailedData.provenance.hostname}</span>
                          </div>
                        )}
                        {detailedData.provenance.ingested_by && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Ingested By:</span>
                            <span className="font-medium text-gray-100">{detailedData.provenance.ingested_by}</span>
                          </div>
                        )}
                        {detailedData.provenance.created_at && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Ingested:</span>
                            <span className="font-medium text-gray-100">
                              {new Date(detailedData.provenance.created_at).toLocaleString()}
                            </span>
                          </div>
                        )}
                        {detailedData.provenance.job_id && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Job ID:</span>
                            <span className="font-mono text-gray-100">{detailedData.provenance.job_id.substring(0, 12)}...</span>
                          </div>
                        )}
                        {detailedData.provenance.source_count && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Source Nodes:</span>
                            <span className="font-medium text-gray-100">{detailedData.provenance.source_count}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Source documents (for Concept nodes) */}
                    {detailedData.provenance.documents && detailedData.provenance.documents.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-gray-300 font-medium mb-1">Source Documents:</div>
                        {detailedData.provenance.documents.map((doc: any, idx: number) => (
                          <div key={doc.document_id || idx} className="pl-2 border-l-2 border-gray-600">
                            <div className="flex justify-between items-start mb-1">
                              <div className="text-gray-300 font-medium">{doc.filename}</div>
                              {doc.source_type && (
                                <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
                                  {doc.source_type}
                                </span>
                              )}
                            </div>
                            <div className="space-y-0.5 text-xs">
                              {doc.ingested_at && (
                                <div className="flex justify-between text-gray-400">
                                  <span>Ingested:</span>
                                  <span>{new Date(doc.ingested_at).toLocaleString()}</span>
                                </div>
                              )}
                              {doc.ingested_by && (
                                <div className="flex justify-between text-gray-400">
                                  <span>By:</span>
                                  <span>User {doc.ingested_by}</span>
                                </div>
                              )}
                              {doc.job_id && (
                                <div className="flex justify-between text-gray-400">
                                  <span>Job:</span>
                                  <span className="font-mono">{doc.job_id.substring(0, 12)}...</span>
                                </div>
                              )}
                              {doc.source_count !== null && doc.source_count !== undefined && (
                                <div className="flex justify-between text-gray-400">
                                  <span>Chunks:</span>
                                  <span>{doc.source_count}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {loading && (
              <div className="px-4 py-3 text-center text-sm text-gray-400">
                Loading details...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
