/**
 * Polarity Explorer Workspace (ADR-070)
 *
 * Interactive visualization for polarity axis analysis.
 * Projects concepts onto bidirectional semantic dimensions.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GitBranch,
  Search,
  Play,
  Settings,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  FileSpreadsheet,
  Save,
  CheckCircle,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useGraphStore } from '../../store/graphStore';
import { useReportStore } from '../../store/reportStore';
import { useArtifactStore } from '../../store/artifactStore';
import type { PolarityReportData } from '../../store/reportStore';
import { IconRailPanel } from '../shared/IconRailPanel';
import { PolarityHelpModal } from './PolarityHelpModal';
import { PolarityScatterPlot } from './PolarityScatterPlot';

interface Concept {
  concept_id: string;
  label: string;
  description?: string;
}

interface Projection {
  concept_id: string;
  label: string;
  position: number;
  axis_distance: number;
  direction: 'positive' | 'negative' | 'neutral';
  grounding: number;
  alignment: {
    positive_pole_similarity: number;
    negative_pole_similarity: number;
  };
}

interface AnalysisResult {
  success: boolean;
  axis: {
    positive_pole: Concept & { grounding: number };
    negative_pole: Concept & { grounding: number };
    magnitude: number;
    axis_quality: string;
  };
  projections: Projection[];
  statistics: {
    total_concepts: number;
    position_range: [number, number];
    mean_position: number;
    std_deviation: number;
    mean_axis_distance: number;
    direction_distribution: {
      positive: number;
      negative: number;
      neutral: number;
    };
  };
  grounding_correlation: {
    pearson_r: number;
    p_value: number;
    interpretation: string;
    strength?: string;
    direction?: string;
  };
}

interface StoredAnalysis {
  id: string;
  timestamp: number;
  positivePoleLabel: string;
  negativePoleLabel: string;
  result: AnalysisResult;
}

export const PolarityExplorerWorkspace: React.FC = () => {
  const navigate = useNavigate();
  const { addReport } = useReportStore();
  const { persistArtifact } = useArtifactStore();

  // Get polarity state from Zustand store
  const {
    polarityState,
    setPolarityState,
    addPolarityAnalysis,
    removePolarityAnalysis,
    clearPolarityHistory,
  } = useGraphStore();

  const {
    selectedPositivePole,
    selectedNegativePole,
    analysisHistory,
    selectedAnalysisId,
    maxCandidates,
    maxHops,
    minSimilarity,
    autoDiscover,
    activeTab,
  } = polarityState;

  // Temporary search state (not persisted)
  const [positivePoleQuery, setPositivePoleQuery] = useState('');
  const [negativePoleQuery, setNegativePoleQuery] = useState('');
  const [positivePoleResults, setPositivePoleResults] = useState<Concept[]>([]);
  const [negativePoleResults, setNegativePoleResults] = useState<Concept[]>([]);

  // Debounced search queries for autocomplete
  const debouncedPositiveQuery = useDebouncedValue(positivePoleQuery, 500);
  const debouncedNegativeQuery = useDebouncedValue(negativePoleQuery, 500);

  // Loading/error state (not persisted)
  const [isSearchingPositive, setIsSearchingPositive] = useState(false);
  const [isSearchingNegative, setIsSearchingNegative] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI state (not persisted)
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    positive: false,
    neutral: false,
    negative: false,
  });
  const [isSavingArtifact, setIsSavingArtifact] = useState(false);
  const [savedArtifactId, setSavedArtifactId] = useState<number | null>(null);

  // Computed: Get currently selected analysis
  const selectedAnalysis = selectedAnalysisId
    ? analysisHistory.find((a) => a.id === selectedAnalysisId)
    : null;

  const searchConcepts = useCallback(async (query: string, pole: 'positive' | 'negative') => {
    if (query.trim().length < 2) {
      // Clear results if query is too short
      if (pole === 'positive') {
        setPositivePoleResults([]);
      } else {
        setNegativePoleResults([]);
      }
      return;
    }

    const setLoading = pole === 'positive' ? setIsSearchingPositive : setIsSearchingNegative;
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.searchConcepts({
        query: query.trim(),
        limit: 10,
        min_similarity: minSimilarity,
      });

      const concepts = response.results.map((r) => ({
        concept_id: r.concept_id,
        label: r.label,
        description: r.description,
      }));

      if (pole === 'positive') {
        setPositivePoleResults(concepts);
      } else {
        setNegativePoleResults(concepts);
      }
    } catch (err: any) {
      setError(err.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [minSimilarity]);

  // Auto-search when debounced positive query changes
  useEffect(() => {
    if (debouncedPositiveQuery && !selectedPositivePole) {
      searchConcepts(debouncedPositiveQuery, 'positive');
    }
  }, [debouncedPositiveQuery, selectedPositivePole, searchConcepts]);

  // Auto-search when debounced negative query changes
  useEffect(() => {
    if (debouncedNegativeQuery && !selectedNegativePole) {
      searchConcepts(debouncedNegativeQuery, 'negative');
    }
  }, [debouncedNegativeQuery, selectedNegativePole, searchConcepts]);

  const runAnalysis = async () => {
    if (!selectedPositivePole || !selectedNegativePole) {
      setError('Please select both poles');
      return;
    }

    if (selectedPositivePole.concept_id === selectedNegativePole.concept_id) {
      setError('Poles must be different concepts');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const result = await apiClient.analyzePolarityAxis({
        positive_pole_id: selectedPositivePole.concept_id,
        negative_pole_id: selectedNegativePole.concept_id,
        auto_discover: autoDiscover,
        max_candidates: maxCandidates,
        max_hops: maxHops,
      });

      // Store analysis in history (Zustand store)
      const storedAnalysis: StoredAnalysis = {
        id: `analysis-${Date.now()}`,
        timestamp: Date.now(),
        positivePoleLabel: selectedPositivePole.label,
        negativePoleLabel: selectedNegativePole.label,
        result,
      };

      addPolarityAnalysis(storedAnalysis);
      setPolarityState({ activeTab: 'results' });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleSection = (section: 'positive' | 'neutral' | 'negative') => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // Send current polarity analysis to Reports
  const handleSendToReports = useCallback(async () => {
    if (!selectedAnalysis) return;

    const reportData: PolarityReportData = {
      type: 'polarity',
      positivePole: {
        concept_id: selectedAnalysis.result.axis.positive_pole.concept_id,
        label: selectedAnalysis.result.axis.positive_pole.label,
      },
      negativePole: {
        concept_id: selectedAnalysis.result.axis.negative_pole.concept_id,
        label: selectedAnalysis.result.axis.negative_pole.label,
      },
      axisMagnitude: selectedAnalysis.result.axis.magnitude,
      concepts: selectedAnalysis.result.projections.map((p) => ({
        concept_id: p.concept_id,
        label: p.label,
        position: p.position,
        positive_similarity: p.alignment.positive_pole_similarity,
        negative_similarity: p.alignment.negative_pole_similarity,
        grounding_strength: p.grounding,
      })),
      directionDistribution: selectedAnalysis.result.statistics.direction_distribution,
      groundingCorrelation: selectedAnalysis.result.grounding_correlation.pearson_r,
    };

    await addReport({
      name: '', // Will auto-generate name based on content
      type: 'polarity',
      data: reportData,
      sourceExplorer: 'polarity',
    });

    navigate('/report');
  }, [selectedAnalysis, addReport, navigate]);

  // Save analysis to artifacts (ADR-083)
  const handleSaveAsArtifact = useCallback(async () => {
    if (!selectedAnalysis) return;

    setIsSavingArtifact(true);
    setSavedArtifactId(null);

    try {
      const artifact = await persistArtifact({
        artifact_type: 'polarity_analysis',
        representation: 'polarity_explorer',
        name: `${selectedAnalysis.positivePoleLabel} ↔ ${selectedAnalysis.negativePoleLabel}`,
        parameters: {
          positive_pole_id: selectedAnalysis.result.axis.positive_pole.concept_id,
          negative_pole_id: selectedAnalysis.result.axis.negative_pole.concept_id,
          max_candidates: maxCandidates,
          max_hops: maxHops,
          auto_discover: autoDiscover,
        },
        payload: selectedAnalysis.result as unknown as Record<string, unknown>,
        concept_ids: selectedAnalysis.result.projections.map((p) => p.concept_id),
      });

      if (artifact) {
        setSavedArtifactId(artifact.id);
        // Clear after 3 seconds
        setTimeout(() => setSavedArtifactId(null), 3000);
      }
    } catch (err) {
      console.error('Failed to save artifact:', err);
    } finally {
      setIsSavingArtifact(false);
    }
  }, [selectedAnalysis, persistArtifact, maxCandidates, maxHops, autoDiscover]);

  const getDirectionColor = (direction: string) => {
    switch (direction) {
      case 'positive':
        return 'text-blue-500';
      case 'negative':
        return 'text-orange-500';
      case 'neutral':
        return 'text-muted-foreground';
      default:
        return '';
    }
  };

  const getGroundingColor = (grounding: number) => {
    if (grounding > 0.7) return 'text-green-500';
    if (grounding > 0.3) return 'text-yellow-500';
    if (grounding > -0.3) return 'text-muted-foreground';
    return 'text-red-500';
  };

  // Search tab content
  const searchContent = (
    <div className="flex-1 overflow-auto p-4 space-y-6">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-lg font-semibold mb-2">Select Polarity Axis Poles</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Choose two opposing concepts to create a bidirectional semantic dimension.
        </p>

        {/* Positive Pole */}
        <div className="mb-6">
          <label className="block text-sm font-medium mb-2 text-blue-500">
            Positive Pole (e.g., "Modern", "Centralized")
          </label>
          <div className="relative mb-2">
            <input
              type="text"
              value={positivePoleQuery}
              onChange={(e) => setPositivePoleQuery(e.target.value)}
              placeholder="Type to search..."
              className="w-full px-3 py-2 pr-10 border border-blue-500/30 rounded-lg bg-background text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            {isSearchingPositive && (
              <LoadingSpinner className="absolute right-3 top-1/2 transform -translate-y-1/2 text-blue-500" />
            )}
          </div>

          {selectedPositivePole ? (
            <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-blue-500">{selectedPositivePole.label}</div>
                  {selectedPositivePole.description && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {selectedPositivePole.description}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setPolarityState({ selectedPositivePole: null })}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear
                </button>
              </div>
            </div>
          ) : positivePoleResults.length > 0 ? (
            <div className="border rounded-lg divide-y max-h-48 overflow-auto">
              {positivePoleResults.map((concept) => (
                <button
                  key={concept.concept_id}
                  onClick={() => {
                    setPolarityState({ selectedPositivePole: concept });
                    setPositivePoleResults([]);
                    setPositivePoleQuery('');
                  }}
                  className="w-full text-left p-3 hover:bg-accent transition-colors"
                >
                  <div className="font-medium text-sm">{concept.label}</div>
                  {concept.description && (
                    <div className="text-xs text-muted-foreground mt-1">{concept.description}</div>
                  )}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {/* Arrow */}
        {selectedPositivePole && selectedNegativePole && (
          <div className="flex items-center justify-center my-4">
            <ArrowRight className="w-6 h-6 text-muted-foreground" />
          </div>
        )}

        {/* Negative Pole */}
        <div className="mb-6">
          <label className="block text-sm font-medium mb-2 text-orange-500">
            Negative Pole (e.g., "Traditional", "Distributed")
          </label>
          <div className="relative mb-2">
            <input
              type="text"
              value={negativePoleQuery}
              onChange={(e) => setNegativePoleQuery(e.target.value)}
              placeholder="Type to search..."
              className="w-full px-3 py-2 pr-10 border border-orange-500/30 rounded-lg bg-background text-sm focus:border-orange-500 focus:ring-1 focus:ring-orange-500 focus:outline-none"
            />
            {isSearchingNegative && (
              <LoadingSpinner className="absolute right-3 top-1/2 transform -translate-y-1/2 text-orange-500" />
            )}
          </div>

          {selectedNegativePole ? (
            <div className="p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-orange-500">{selectedNegativePole.label}</div>
                  {selectedNegativePole.description && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {selectedNegativePole.description}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setPolarityState({ selectedNegativePole: null })}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear
                </button>
              </div>
            </div>
          ) : negativePoleResults.length > 0 ? (
            <div className="border rounded-lg divide-y max-h-48 overflow-auto">
              {negativePoleResults.map((concept) => (
                <button
                  key={concept.concept_id}
                  onClick={() => {
                    setPolarityState({ selectedNegativePole: concept });
                    setNegativePoleResults([]);
                    setNegativePoleQuery('');
                  }}
                  className="w-full text-left p-3 hover:bg-accent transition-colors"
                >
                  <div className="font-medium text-sm">{concept.label}</div>
                  {concept.description && (
                    <div className="text-xs text-muted-foreground mt-1">{concept.description}</div>
                  )}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {/* Analysis Button */}
        <button
          onClick={runAnalysis}
          disabled={!selectedPositivePole || !selectedNegativePole || isAnalyzing}
          className="w-full px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium"
        >
          {isAnalyzing ? (
            <>
              <LoadingSpinner className="text-primary-foreground" />
              Analyzing...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Analyze Polarity Axis
            </>
          )}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-500">
            {error}
          </div>
        )}
      </div>
    </div>
  );

  // Settings tab content
  const settingsContent = (
    <div className="flex-1 overflow-auto p-4">
      <div className="max-w-2xl mx-auto space-y-6">
        <h2 className="text-lg font-semibold mb-4">Analysis Options</h2>

        {/* Search Settings */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="text-sm font-semibold mb-3 text-muted-foreground">Search Settings</h3>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">Similarity Threshold</label>
              <span className="text-sm font-mono text-primary">{Math.round(minSimilarity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.3"
              max="0.95"
              step="0.05"
              value={minSimilarity}
              onChange={(e) => setPolarityState({ minSimilarity: parseFloat(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Minimum similarity for pole concept search results
            </p>
          </div>
        </div>

        {/* Auto-Discovery Settings */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="text-sm font-semibold mb-3 text-muted-foreground">Auto-Discovery</h3>

          <div className="mb-4">
            <label className="flex items-center gap-2 mb-2">
              <input
                type="checkbox"
                checked={autoDiscover}
                onChange={(e) => setPolarityState({ autoDiscover: e.target.checked })}
                className="rounded"
              />
              <span className="text-sm font-medium">Auto-discover related concepts</span>
            </label>
            <p className="text-xs text-muted-foreground ml-6">
              Automatically find concepts connected to the poles via graph traversal
            </p>
          </div>

          {autoDiscover && (
            <div className="space-y-4 border-t pt-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Max Candidates</label>
                  <span className="text-sm font-mono text-primary">{maxCandidates}</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={maxCandidates}
                  onChange={(e) => setPolarityState({ maxCandidates: parseInt(e.target.value) })}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Maximum number of concepts to discover and analyze
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Max Hops</label>
                  <span className="text-sm font-mono text-primary">{maxHops}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="1"
                  value={maxHops}
                  onChange={(e) => setPolarityState({ maxHops: parseInt(e.target.value) })}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Maximum graph distance from poles to search for related concepts (BFS optimized)
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Results list (for IconRailPanel sidebar)
  const resultsListContent = analysisHistory.length > 0 ? (
    <div className="flex-1 overflow-auto p-3">
      <div className="space-y-2">
        {analysisHistory.map((analysis) => (
          <div
            key={analysis.id}
            className="border rounded-lg p-3 bg-card hover:bg-accent/50 transition-colors group"
          >
            <button
              onClick={() => setPolarityState({ selectedAnalysisId: analysis.id })}
              className="w-full text-left"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-sm font-medium text-blue-500">
                  {analysis.positivePoleLabel}
                </span>
                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                <span className="text-sm font-medium text-orange-500">
                  {analysis.negativePoleLabel}
                </span>
              </div>
              <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span>{new Date(analysis.timestamp).toLocaleString()}</span>
                <span>
                  {analysis.result.statistics.total_concepts} concepts • r = {analysis.result.grounding_correlation.pearson_r.toFixed(2)}
                </span>
              </div>
            </button>
            <button
              onClick={() => removePolarityAnalysis(analysis.id)}
              className="mt-2 text-xs text-destructive hover:text-destructive/80 transition-colors opacity-0 group-hover:opacity-100"
            >
              Dismiss
            </button>
          </div>
        ))}
      </div>
    </div>
  ) : (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="text-center text-muted-foreground text-sm">
        <GitBranch className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No analyses yet</p>
      </div>
    </div>
  );

  // Analysis report (for main content area)
  const analysisReportContent = selectedAnalysis ? (
    // Show full report for selected analysis
    <div className="flex-1 overflow-auto p-4">
      <div className="space-y-6">
        {/* Top Actions Bar */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPolarityState({ selectedAnalysisId: null })}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronDown className="w-4 h-4 rotate-90" />
            <span>Back to Analysis List</span>
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveAsArtifact}
              disabled={isSavingArtifact || savedArtifactId !== null}
              className="flex items-center gap-2 px-4 py-2 border border-primary text-primary rounded-lg hover:bg-primary/10 disabled:opacity-50 transition-colors text-sm font-medium"
            >
              {savedArtifactId !== null ? (
                <>
                  <CheckCircle className="w-4 h-4" />
                  Saved
                </>
              ) : isSavingArtifact ? (
                <>
                  <LoadingSpinner className="text-primary" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save as Artifact
                </>
              )}
            </button>
            <button
              onClick={handleSendToReports}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
            >
              <FileSpreadsheet className="w-4 h-4" />
              Send to Reports
            </button>
          </div>
        </div>

        {/* Axis Info */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-3">Polarity Axis</h3>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1">
              <div className="text-sm font-medium text-blue-500">
                {selectedAnalysis.result.axis.positive_pole.label}
              </div>
              {selectedAnalysis.result.axis.positive_pole.description && (
                <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {selectedAnalysis.result.axis.positive_pole.description}
                </div>
              )}
              <div className="text-xs text-muted-foreground mt-1">
                Grounding: {selectedAnalysis.result.axis.positive_pole.grounding.toFixed(3)}
              </div>
            </div>
            <div className="px-4 pt-1">
              <ArrowRight className="w-6 h-6 text-muted-foreground" />
            </div>
            <div className="flex-1 text-right">
              <div className="text-sm font-medium text-orange-500">
                {selectedAnalysis.result.axis.negative_pole.label}
              </div>
              {selectedAnalysis.result.axis.negative_pole.description && (
                <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {selectedAnalysis.result.axis.negative_pole.description}
                </div>
              )}
              <div className="text-xs text-muted-foreground mt-1">
                Grounding: {selectedAnalysis.result.axis.negative_pole.grounding.toFixed(3)}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm border-t pt-3">
            <div>
              <span className="text-muted-foreground">Axis Magnitude:</span>{' '}
              <span className="font-mono">{selectedAnalysis.result.axis.magnitude.toFixed(4)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Axis Quality:</span>{' '}
              <span className="font-medium capitalize">{selectedAnalysis.result.axis.axis_quality}</span>
            </div>
          </div>
        </div>

        {/* Visualization */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-4">Visualization</h3>
          <PolarityScatterPlot
            analysisResult={selectedAnalysis.result}
            onConceptClick={(concept) => {
              // TODO: Future enhancement - open concept details in NodeInfoBox
              console.log('Concept clicked:', concept);
            }}
          />
        </div>

        {/* Statistics */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-3">Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Total Concepts</div>
              <div className="text-xl font-semibold">
                {selectedAnalysis.result.statistics.total_concepts}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Mean Position</div>
              <div className="text-xl font-semibold font-mono">
                {selectedAnalysis.result.statistics.mean_position.toFixed(3)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Std Deviation</div>
              <div className="text-xl font-semibold font-mono">
                {selectedAnalysis.result.statistics.std_deviation.toFixed(3)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Positive</div>
              <div className="text-xl font-semibold text-blue-500">
                {selectedAnalysis.result.statistics.direction_distribution.positive}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Neutral</div>
              <div className="text-xl font-semibold text-muted-foreground">
                {selectedAnalysis.result.statistics.direction_distribution.neutral}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Negative</div>
              <div className="text-xl font-semibold text-orange-500">
                {selectedAnalysis.result.statistics.direction_distribution.negative}
              </div>
            </div>
          </div>
        </div>

        {/* Grounding Correlation */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-3">Grounding Correlation</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Pearson r:</span>
              <span className="font-mono font-semibold">
                {selectedAnalysis.result.grounding_correlation.pearson_r.toFixed(3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">p-value:</span>
              <span className="font-mono text-sm">
                {selectedAnalysis.result.grounding_correlation.p_value.toFixed(4)}
              </span>
            </div>
            <div className="mt-2 p-2 bg-muted rounded text-sm">
              {selectedAnalysis.result.grounding_correlation.interpretation}
            </div>
          </div>
        </div>

        {/* Projected Concepts */}
        <div className="border rounded-lg bg-card">
          <div className="p-4 border-b">
            <h3 className="font-semibold">Projected Concepts</h3>
          </div>

          {/* Positive Direction */}
          <div className="border-b">
            <button
              onClick={() => toggleSection('positive')}
              className="w-full p-4 flex items-center justify-between hover:bg-accent transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500" />
                <span className="font-medium">
                  Positive ({selectedAnalysis.result.statistics.direction_distribution.positive})
                </span>
              </div>
              {expandedSections.positive ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedSections.positive && (
              <div className="divide-y">
                {selectedAnalysis.result.projections
                  .filter((p) => p.direction === 'positive')
                  .sort((a, b) => b.position - a.position)
                  .map((projection) => (
                    <div key={projection.concept_id} className="p-4 hover:bg-accent/50">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{projection.label}</div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                            <span>Position: {projection.position.toFixed(3)}</span>
                            <span className={getGroundingColor(projection.grounding)}>
                              Grounding: {projection.grounding.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>

          {/* Neutral Direction */}
          <div className="border-b">
            <button
              onClick={() => toggleSection('neutral')}
              className="w-full p-4 flex items-center justify-between hover:bg-accent transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-muted-foreground" />
                <span className="font-medium">
                  Neutral ({selectedAnalysis.result.statistics.direction_distribution.neutral})
                </span>
              </div>
              {expandedSections.neutral ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedSections.neutral && (
              <div className="divide-y">
                {selectedAnalysis.result.projections
                  .filter((p) => p.direction === 'neutral')
                  .sort((a, b) => b.position - a.position)
                  .map((projection) => (
                    <div key={projection.concept_id} className="p-4 hover:bg-accent/50">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{projection.label}</div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                            <span>Position: {projection.position.toFixed(3)}</span>
                            <span className={getGroundingColor(projection.grounding)}>
                              Grounding: {projection.grounding.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>

          {/* Negative Direction */}
          <div>
            <button
              onClick={() => toggleSection('negative')}
              className="w-full p-4 flex items-center justify-between hover:bg-accent transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-orange-500" />
                <span className="font-medium">
                  Negative ({selectedAnalysis.result.statistics.direction_distribution.negative})
                </span>
              </div>
              {expandedSections.negative ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedSections.negative && (
              <div className="divide-y">
                {selectedAnalysis.result.projections
                  .filter((p) => p.direction === 'negative')
                  .sort((a, b) => b.position - a.position)
                  .map((projection) => (
                    <div key={projection.concept_id} className="p-4 hover:bg-accent/50">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{projection.label}</div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                            <span>Position: {projection.position.toFixed(3)}</span>
                            <span className={getGroundingColor(projection.grounding)}>
                              Grounding: {projection.grounding.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ) : (
    // No analysis selected - show empty state
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="text-center text-muted-foreground">
        <GitBranch className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>Select an analysis to view details</p>
        <p className="text-sm mt-2">Choose from Results History or run a new analysis</p>
      </div>
    </div>
  );

  // Tab definitions
  const tabs = [
    {
      id: 'search',
      label: 'Search',
      icon: Search,
      content: null, // Search UI shown in main content area
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      content: null, // Settings shown in main content area
    },
    {
      id: 'results',
      label: 'Results History',
      icon: GitBranch,
      content: resultsListContent, // Results list shown in sidebar
    },
  ];

  return (
    <div className="flex h-full">
      {/* Left sidebar with tabs */}
      <IconRailPanel
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(tab) => setPolarityState({ activeTab: tab })}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col">
        {/* Header with help button */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-foreground">
            {activeTab === 'results' && selectedAnalysis
              ? 'Analysis Report'
              : tabs.find((t) => t.id === activeTab)?.label}
          </h3>
          <button
            onClick={() => setIsHelpOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-primary hover:bg-primary/10 rounded-md transition-colors"
          >
            <HelpCircle size={16} />
            <span>How do I use this?</span>
          </button>
        </div>

        {/* Main content - show appropriate content based on active tab */}
        <div className="flex-1 overflow-auto">
          {activeTab === 'search' && searchContent}
          {activeTab === 'settings' && settingsContent}
          {activeTab === 'results' && analysisReportContent}
        </div>
      </div>

      {/* Help Modal */}
      <PolarityHelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  );
};
