/**
 * Embedding Landscape Workspace (ADR-078)
 *
 * 3D visualization of concept embeddings projected via t-SNE/UMAP.
 * Supports loading multiple ontologies to see overlapping semantic spaces.
 */

import { useState, useEffect, useMemo } from 'react';
import { apiClient } from '../../api/client';
import { Loader2, RefreshCw, Layers, Eye, EyeOff, Info } from 'lucide-react';
import type { ProjectionData, EmbeddingPoint, OntologySelection } from './types';
import { EmbeddingScatter3D } from './EmbeddingScatter3D';

// Color palette for ontologies (colorblind-friendly)
const ONTOLOGY_COLORS = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#22c55e', // green
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#84cc16', // lime
];

export function EmbeddingLandscapeWorkspace() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ontologies, setOntologies] = useState<OntologySelection[]>([]);
  const [projections, setProjections] = useState<Map<string, ProjectionData>>(new Map());
  const [selectedConcept, setSelectedConcept] = useState<EmbeddingPoint | null>(null);

  // Load available ontologies on mount
  useEffect(() => {
    loadOntologies();
  }, []);

  const loadOntologies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.listOntologies();

      // Initialize ontology selections with colors
      const selections: OntologySelection[] = response.ontologies.map((ont, index) => ({
        ontology: ont.ontology,
        enabled: true, // All enabled by default
        color: ONTOLOGY_COLORS[index % ONTOLOGY_COLORS.length],
        conceptCount: ont.concept_count,
      }));

      setOntologies(selections);

      // Load projections for all ontologies
      await loadAllProjections(selections.map(s => s.ontology));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load ontologies');
    } finally {
      setLoading(false);
    }
  };

  const loadAllProjections = async (ontologyNames: string[]) => {
    const newProjections = new Map<string, ProjectionData>();

    await Promise.all(
      ontologyNames.map(async (ontology) => {
        try {
          const projection = await apiClient.getProjection(ontology);
          newProjections.set(ontology, projection);
        } catch (err: any) {
          // Projection might not exist yet - that's okay
          console.warn(`No projection for ${ontology}:`, err.message);
        }
      })
    );

    setProjections(newProjections);
  };

  const regenerateProjection = async (ontology: string) => {
    try {
      setLoading(true);
      await apiClient.regenerateProjection(ontology, { force: true });
      // Reload the projection
      const projection = await apiClient.getProjection(ontology);
      setProjections(prev => new Map(prev).set(ontology, projection));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleOntology = (ontology: string) => {
    setOntologies(prev =>
      prev.map(o =>
        o.ontology === ontology ? { ...o, enabled: !o.enabled } : o
      )
    );
  };

  // Transform projections into visualization points
  const points: EmbeddingPoint[] = useMemo(() => {
    const result: EmbeddingPoint[] = [];

    ontologies.forEach(ont => {
      if (!ont.enabled) return;

      const projection = projections.get(ont.ontology);
      if (!projection) return;

      projection.concepts.forEach(concept => {
        result.push({
          id: concept.concept_id,
          label: concept.label,
          x: concept.x,
          y: concept.y,
          z: concept.z,
          ontology: ont.ontology,
          grounding: concept.grounding_strength,
          color: ont.color,
        });
      });
    });

    return result;
  }, [ontologies, projections]);

  // Calculate stats
  const stats = useMemo(() => {
    const enabledOntologies = ontologies.filter(o => o.enabled);
    const totalConcepts = points.length;
    const ontologiesWithProjections = enabledOntologies.filter(o => projections.has(o.ontology)).length;

    return {
      enabledOntologies: enabledOntologies.length,
      totalOntologies: ontologies.length,
      totalConcepts,
      ontologiesWithProjections,
    };
  }, [ontologies, projections, points]);

  return (
    <div className="flex h-full bg-gray-950">
      {/* Sidebar */}
      <div className="w-72 flex-shrink-0 border-r border-gray-800 bg-gray-900 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            Embedding Landscape
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            t-SNE projection of concept embeddings
          </p>
        </div>

        {/* Ontology list */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-300">Ontologies</span>
            <button
              onClick={loadOntologies}
              disabled={loading}
              className="p-1 text-gray-400 hover:text-white rounded"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {error && (
            <div className="mb-4 p-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="space-y-2">
            {ontologies.map(ont => {
              const hasProjection = projections.has(ont.ontology);
              const projection = projections.get(ont.ontology);

              return (
                <div
                  key={ont.ontology}
                  className={`p-3 rounded-lg border ${
                    ont.enabled
                      ? 'border-gray-700 bg-gray-800'
                      : 'border-gray-800 bg-gray-900 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleOntology(ont.ontology)}
                      className="p-1 hover:bg-gray-700 rounded"
                    >
                      {ont.enabled ? (
                        <Eye className="w-4 h-4 text-gray-300" />
                      ) : (
                        <EyeOff className="w-4 h-4 text-gray-500" />
                      )}
                    </button>

                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: ont.color }}
                    />

                    <span className="text-sm text-white truncate flex-1">
                      {ont.ontology}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-gray-400">
                      {hasProjection
                        ? `${projection?.statistics.concept_count} points`
                        : 'No projection'}
                    </span>

                    <button
                      onClick={() => regenerateProjection(ont.ontology)}
                      disabled={loading}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      {hasProjection ? 'Refresh' : 'Generate'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Stats footer */}
        <div className="p-4 border-t border-gray-800 bg-gray-900/50">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-500">Ontologies</span>
              <p className="text-white font-medium">
                {stats.enabledOntologies}/{stats.totalOntologies}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Total Points</span>
              <p className="text-white font-medium">{stats.totalConcepts}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main visualization area */}
      <div className="flex-1 relative">
        {loading && points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex items-center gap-3 text-gray-400">
              <Loader2 className="w-6 h-6 animate-spin" />
              <span>Loading projections...</span>
            </div>
          </div>
        ) : points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <Layers className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No projections available</p>
              <p className="text-sm mt-1">Generate projections for ontologies to visualize</p>
            </div>
          </div>
        ) : (
          <EmbeddingScatter3D
            points={points}
            onSelectPoint={setSelectedConcept}
            selectedPoint={selectedConcept}
          />
        )}

        {/* Selected concept info */}
        {selectedConcept && (
          <div className="absolute bottom-4 left-4 max-w-sm p-4 bg-gray-900/95 border border-gray-700 rounded-lg shadow-xl">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <div>
                <h3 className="font-medium text-white">{selectedConcept.label}</h3>
                <p className="text-xs text-gray-400 mt-1">
                  Ontology: {selectedConcept.ontology}
                </p>
                {selectedConcept.grounding !== null && (
                  <p className="text-xs text-gray-400">
                    Grounding: {selectedConcept.grounding.toFixed(2)}
                  </p>
                )}
                <p className="text-xs text-gray-500 mt-1 font-mono">
                  ({selectedConcept.x.toFixed(1)}, {selectedConcept.y.toFixed(1)}, {selectedConcept.z.toFixed(1)})
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
