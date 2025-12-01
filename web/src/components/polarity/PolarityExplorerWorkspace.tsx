/**
 * Polarity Explorer Workspace (ADR-070)
 *
 * Interactive visualization for polarity axis analysis.
 * Projects concepts onto bidirectional semantic dimensions.
 */

import React, { useState } from 'react';
import {
  GitBranch,
  Search,
  Play,
  Settings,
  ArrowRight,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { IconRailPanel } from '../shared/IconRailPanel';

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

export const PolarityExplorerWorkspace: React.FC = () => {
  // Search state
  const [positivePoleQuery, setPositivePoleQuery] = useState('');
  const [negativePoleQuery, setNegativePoleQuery] = useState('');
  const [positivePoleResults, setPositivePoleResults] = useState<Concept[]>([]);
  const [negativePoleResults, setNegativePoleResults] = useState<Concept[]>([]);
  const [selectedPositivePole, setSelectedPositivePole] = useState<Concept | null>(null);
  const [selectedNegativePole, setSelectedNegativePole] = useState<Concept | null>(null);

  // Analysis options
  const [maxCandidates, setMaxCandidates] = useState(20);
  const [maxHops, setMaxHops] = useState(2);
  const [autoDiscover, setAutoDiscover] = useState(true);

  // Analysis state
  const [isSearching, setIsSearching] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [activeTab, setActiveTab] = useState<string>('search');
  const [expandedSections, setExpandedSections] = useState({
    positive: true,
    neutral: true,
    negative: true,
  });

  const searchConcepts = async (query: string, setPole: 'positive' | 'negative') => {
    if (query.trim().length < 2) return;

    setIsSearching(true);
    setError(null);

    try {
      const response = await apiClient.searchConcepts({
        query: query.trim(),
        limit: 10,
        min_similarity: 0.6,
      });

      const concepts = response.results.map((r: any) => ({
        concept_id: r.concept_id,
        label: r.label,
        description: r.description,
      }));

      if (setPole === 'positive') {
        setPositivePoleResults(concepts);
      } else {
        setNegativePoleResults(concepts);
      }
    } catch (err: any) {
      setError(err.message || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

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
    setAnalysisResult(null);

    try {
      const result = await apiClient.analyzePolarityAxis({
        positive_pole_id: selectedPositivePole.concept_id,
        negative_pole_id: selectedNegativePole.concept_id,
        auto_discover: autoDiscover,
        max_candidates: maxCandidates,
        max_hops: maxHops,
      });

      setAnalysisResult(result);
      setActiveTab('results');
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
          <label className="block text-sm font-medium mb-2">
            Positive Pole (e.g., "Modern", "Centralized")
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={positivePoleQuery}
              onChange={(e) => setPositivePoleQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') searchConcepts(positivePoleQuery, 'positive');
              }}
              placeholder="Search for positive pole concept..."
              className="flex-1 px-3 py-2 border rounded-lg bg-background text-sm"
            />
            <button
              onClick={() => searchConcepts(positivePoleQuery, 'positive')}
              disabled={isSearching || positivePoleQuery.trim().length < 2}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              Search
            </button>
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
                  onClick={() => setSelectedPositivePole(null)}
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
                    setSelectedPositivePole(concept);
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
          <label className="block text-sm font-medium mb-2">
            Negative Pole (e.g., "Traditional", "Distributed")
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={negativePoleQuery}
              onChange={(e) => setNegativePoleQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') searchConcepts(negativePoleQuery, 'negative');
              }}
              placeholder="Search for negative pole concept..."
              className="flex-1 px-3 py-2 border rounded-lg bg-background text-sm"
            />
            <button
              onClick={() => searchConcepts(negativePoleQuery, 'negative')}
              disabled={isSearching || negativePoleQuery.trim().length < 2}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              Search
            </button>
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
                  onClick={() => setSelectedNegativePole(null)}
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
                    setSelectedNegativePole(concept);
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
              <Loader2 className="w-5 h-5 animate-spin" />
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
      <div className="max-w-2xl mx-auto space-y-4">
        <h2 className="text-lg font-semibold mb-4">Analysis Options</h2>

        <div>
          <label className="flex items-center gap-2 mb-2">
            <input
              type="checkbox"
              checked={autoDiscover}
              onChange={(e) => setAutoDiscover(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm font-medium">Auto-discover related concepts</span>
          </label>
          <p className="text-xs text-muted-foreground ml-6">
            Automatically find concepts connected to the poles via graph traversal
          </p>
        </div>

        {autoDiscover && (
          <>
            <div>
              <label className="block text-sm font-medium mb-2">
                Max Candidates: {maxCandidates}
              </label>
              <input
                type="range"
                min="5"
                max="100"
                step="5"
                value={maxCandidates}
                onChange={(e) => setMaxCandidates(parseInt(e.target.value))}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum number of concepts to discover and analyze
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Max Hops: {maxHops}</label>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={maxHops}
                onChange={(e) => setMaxHops(parseInt(e.target.value))}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum graph distance from poles to search for related concepts
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );

  // Results tab content
  const resultsContent = analysisResult ? (
    <div className="flex-1 overflow-auto p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Axis Info */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-3">Polarity Axis</h3>
          <div className="flex items-center justify-between mb-4">
            <div className="flex-1">
              <div className="text-sm font-medium text-blue-500">
                {analysisResult.axis.positive_pole.label}
              </div>
              <div className="text-xs text-muted-foreground">
                Grounding: {analysisResult.axis.positive_pole.grounding.toFixed(3)}
              </div>
            </div>
            <div className="px-4">
              <ArrowRight className="w-6 h-6 text-muted-foreground" />
            </div>
            <div className="flex-1 text-right">
              <div className="text-sm font-medium text-orange-500">
                {analysisResult.axis.negative_pole.label}
              </div>
              <div className="text-xs text-muted-foreground">
                Grounding: {analysisResult.axis.negative_pole.grounding.toFixed(3)}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Axis Magnitude:</span>{' '}
              <span className="font-mono">{analysisResult.axis.magnitude.toFixed(4)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Axis Quality:</span>{' '}
              <span className="font-medium capitalize">{analysisResult.axis.axis_quality}</span>
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="border rounded-lg p-4 bg-card">
          <h3 className="font-semibold mb-3">Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Total Concepts</div>
              <div className="text-xl font-semibold">
                {analysisResult.statistics.total_concepts}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Mean Position</div>
              <div className="text-xl font-semibold font-mono">
                {analysisResult.statistics.mean_position.toFixed(3)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Std Deviation</div>
              <div className="text-xl font-semibold font-mono">
                {analysisResult.statistics.std_deviation.toFixed(3)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Positive</div>
              <div className="text-xl font-semibold text-blue-500">
                {analysisResult.statistics.direction_distribution.positive}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Neutral</div>
              <div className="text-xl font-semibold text-muted-foreground">
                {analysisResult.statistics.direction_distribution.neutral}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Negative</div>
              <div className="text-xl font-semibold text-orange-500">
                {analysisResult.statistics.direction_distribution.negative}
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
                {analysisResult.grounding_correlation.pearson_r.toFixed(3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">p-value:</span>
              <span className="font-mono text-sm">
                {analysisResult.grounding_correlation.p_value.toFixed(4)}
              </span>
            </div>
            <div className="mt-2 p-2 bg-muted rounded text-sm">
              {analysisResult.grounding_correlation.interpretation}
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
                  Positive ({analysisResult.statistics.direction_distribution.positive})
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
                {analysisResult.projections
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
                  Neutral ({analysisResult.statistics.direction_distribution.neutral})
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
                {analysisResult.projections
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
                  Negative ({analysisResult.statistics.direction_distribution.negative})
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
                {analysisResult.projections
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
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="text-center text-muted-foreground">
        <GitBranch className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>No analysis results yet</p>
        <p className="text-sm mt-2">Select poles and run analysis to see results</p>
      </div>
    </div>
  );

  // Tab definitions
  const tabs = [
    {
      id: 'search',
      label: 'Search',
      icon: Search,
      content: searchContent,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      content: settingsContent,
    },
    {
      id: 'results',
      label: 'Results',
      icon: GitBranch,
      content: resultsContent,
    },
  ];

  return (
    <div className="flex h-full">
      {/* Left sidebar with tabs */}
      <IconRailPanel tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main content area */}
      <div className="flex-1 flex flex-col">
        {tabs.find((t) => t.id === activeTab)?.content}
      </div>
    </div>
  );
};
