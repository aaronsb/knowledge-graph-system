/**
 * Embedding Landscape Workspace (ADR-078)
 *
 * 3D visualization of concept embeddings projected via t-SNE/UMAP.
 * Supports loading multiple ontologies to see overlapping semantic spaces.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { Loader2, RefreshCw, Layers, Eye, EyeOff, SlidersHorizontal, FolderOpen } from 'lucide-react';
import type { ProjectionData, EmbeddingPoint, ColorScheme, ProjectionItemType, DistanceMetric, GroundingScale, GroundingColorRamp } from './types';
import { EmbeddingScatter3D } from './EmbeddingScatter3D';
import { NodeInfoBox } from '../../explorers/common/NodeInfoBox';
import { IconRailPanel } from '../shared/IconRailPanel';
import { SavedQueriesPanel } from '../shared/SavedQueriesPanel';
import { useQueryReplay } from '../../hooks/useQueryReplay';

// Vibrant color palette for ontologies (high saturation for dark backgrounds)
const ONTOLOGY_COLORS = [
  '#4da6ff', // bright blue
  '#ff5555', // bright red
  '#55ff88', // bright green
  '#ffbb33', // bright amber
  '#aa77ff', // bright violet
  '#33ddff', // bright cyan
  '#ff66aa', // bright pink
  '#aaff44', // bright lime
];

// Color scheme descriptions
const COLOR_SCHEME_INFO: Record<ColorScheme, { label: string; description: string }> = {
  ontology: {
    label: 'By Ontology',
    description: 'Each dataset has a distinct color',
  },
  grounding: {
    label: 'By Grounding',
    description: 'Pink (contradicted) → Gray → Cyan (affirmed)',
  },
  position: {
    label: 'By Position',
    description: 'Color wheel around Y axis, brightness by height',
  },
};


/**
 * Color ramp definitions for grounding visualization.
 * Each ramp has: negative color, neutral color, positive color (as RGB arrays)
 */
const GROUNDING_COLOR_RAMPS: Record<GroundingColorRamp, {
  negative: [number, number, number];
  neutral: [number, number, number];
  positive: [number, number, number];
  label: string;
  gradient: string;
}> = {
  'pink-gray-cyan': {
    negative: [255, 68, 170],   // #ff44aa - hot pink
    neutral: [187, 187, 204],   // #bbbbcc - light gray
    positive: [0, 255, 187],    // #00ffbb - electric cyan
    label: 'Pink → Cyan',
    gradient: 'linear-gradient(to right, #ff44aa, #bbbbcc, #00ffbb)',
  },
  'blue-white-red': {
    negative: [59, 130, 246],   // #3b82f6 - blue
    neutral: [240, 240, 245],   // #f0f0f5 - off-white
    positive: [239, 68, 68],    // #ef4444 - red
    label: 'Blue → Red',
    gradient: 'linear-gradient(to right, #3b82f6, #f0f0f5, #ef4444)',
  },
  'purple-white-green': {
    negative: [147, 51, 234],   // #9333ea - purple
    neutral: [245, 245, 250],   // #f5f5fa - off-white
    positive: [34, 197, 94],    // #22c55e - green
    label: 'Purple → Green',
    gradient: 'linear-gradient(to right, #9333ea, #f5f5fa, #22c55e)',
  },
  'brown-white-teal': {
    negative: [180, 83, 9],     // #b45309 - brown/amber
    neutral: [245, 245, 240],   // #f5f5f0 - warm white
    positive: [20, 184, 166],   // #14b8a6 - teal
    label: 'Brown → Teal',
    gradient: 'linear-gradient(to right, #b45309, #f5f5f0, #14b8a6)',
  },
  'purple-white-orange': {
    negative: [126, 34, 206],   // #7e22ce - deep purple
    neutral: [250, 250, 255],   // #fafaff - cool white
    positive: [249, 115, 22],   // #f97316 - orange
    label: 'Purple → Orange',
    gradient: 'linear-gradient(to right, #7e22ce, #fafaff, #f97316)',
  },
};

// Order of ramps for cycling
const GROUNDING_RAMP_ORDER: GroundingColorRamp[] = [
  'pink-gray-cyan',
  'blue-white-red',
  'purple-white-green',
  'brown-white-teal',
  'purple-white-orange',
];

/**
 * Apply scale transformation to grounding value.
 * Returns a value in 0-1 range representing color intensity.
 */
function applyGroundingScale(absValue: number, scale: GroundingScale): number {
  switch (scale) {
    case 'linear':
      return absValue;
    case 'sqrt':
      // sqrt makes colors appear faster: 0.25 → 0.5, 0.5 → 0.71
      return Math.sqrt(absValue);
    case 'log':
      // log scale for maximum contrast: even tiny values show color
      // log(1 + x*9) / log(10) maps 0→0, 1→1 with steep initial curve
      return Math.log10(1 + absValue * 9);
    default:
      return absValue;
  }
}

/**
 * Convert grounding strength (-1 to 1) to a color using the selected ramp.
 */
function groundingToColor(
  grounding: number | null,
  scale: GroundingScale = 'sqrt',
  ramp: GroundingColorRamp = 'pink-gray-cyan'
): string {
  if (grounding === null) return '#778899'; // muted blue-gray for unknown

  const colors = GROUNDING_COLOR_RAMPS[ramp];

  // Clamp to -1..1
  const g = Math.max(-1, Math.min(1, grounding));

  // Apply chosen scale transformation
  const sign = g < 0 ? -1 : 1;
  const t = applyGroundingScale(Math.abs(g), scale);

  const [fromColor, toColor] = sign < 0
    ? [colors.neutral, colors.negative]
    : [colors.neutral, colors.positive];

  const r = Math.round(fromColor[0] + (toColor[0] - fromColor[0]) * t);
  const gv = Math.round(fromColor[1] + (toColor[1] - fromColor[1]) * t);
  const b = Math.round(fromColor[2] + (toColor[2] - fromColor[2]) * t);

  return `rgb(${r}, ${gv}, ${b})`;
}

/**
 * Get CSS gradient string for grounding legend that reflects the scale.
 * Creates multiple color stops to visualize how the scale affects distribution.
 */
function getGroundingGradient(ramp: GroundingColorRamp, scale: GroundingScale): string {
  const colors = GROUNDING_COLOR_RAMPS[ramp];

  // Generate color stops that reflect the scale transformation
  // We sample at multiple points to show the non-linear mapping
  const stops: string[] = [];
  const numStops = 11; // -1.0, -0.8, ..., 0, ..., 0.8, 1.0

  for (let i = 0; i <= numStops - 1; i++) {
    const position = i / (numStops - 1); // 0 to 1
    const grounding = (position * 2) - 1; // -1 to 1

    // Apply scale transformation
    const sign = grounding < 0 ? -1 : 1;
    const t = applyGroundingScale(Math.abs(grounding), scale);

    const [fromColor, toColor] = sign < 0
      ? [colors.neutral, colors.negative]
      : [colors.neutral, colors.positive];

    const r = Math.round(fromColor[0] + (toColor[0] - fromColor[0]) * t);
    const g = Math.round(fromColor[1] + (toColor[1] - fromColor[1]) * t);
    const b = Math.round(fromColor[2] + (toColor[2] - fromColor[2]) * t);

    stops.push(`rgb(${r}, ${g}, ${b}) ${position * 100}%`);
  }

  return `linear-gradient(to right, ${stops.join(', ')})`;
}

/**
 * Get next color ramp in cycle.
 */
function getNextGroundingRamp(current: GroundingColorRamp): GroundingColorRamp {
  const currentIndex = GROUNDING_RAMP_ORDER.indexOf(current);
  const nextIndex = (currentIndex + 1) % GROUNDING_RAMP_ORDER.length;
  return GROUNDING_RAMP_ORDER[nextIndex];
}

/**
 * Map 3D position to vibrant RGB color using HSL color space.
 * - Hue: derived from X and Z position (color wheel around Y axis)
 * - Saturation: high (80-100%) for vibrancy
 * - Lightness: modulated by Y position (50-70%) for depth cue
 */
function positionToColor(
  x: number, y: number, z: number,
  bounds: { minX: number; maxX: number; minY: number; maxY: number; minZ: number; maxZ: number }
): string {
  const rangeX = bounds.maxX - bounds.minX || 1;
  const rangeY = bounds.maxY - bounds.minY || 1;
  const rangeZ = bounds.maxZ - bounds.minZ || 1;

  // Normalize to 0-1
  const nx = (x - bounds.minX) / rangeX;
  const ny = (y - bounds.minY) / rangeY;
  const nz = (z - bounds.minZ) / rangeZ;

  // Map XZ plane to hue (0-360 degrees) - creates color wheel around Y axis
  // atan2 gives angle from -π to π, normalize to 0-360
  const angle = Math.atan2(nz - 0.5, nx - 0.5);
  const hue = ((angle + Math.PI) / (2 * Math.PI)) * 360;

  // Distance from center in XZ plane affects saturation (80-100%)
  const distFromCenter = Math.sqrt((nx - 0.5) ** 2 + (nz - 0.5) ** 2) * 2;
  const saturation = 80 + Math.min(distFromCenter, 1) * 20;

  // Y position affects lightness (50-70%) - higher = brighter
  const lightness = 50 + ny * 20;

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/** 3D t-SNE projection workspace for concept embeddings across ontologies.
 *  Uses IconRailPanel with Ontologies (visibility) and Settings (projection params) tabs.
 *  @verified b38d816f */
export function EmbeddingLandscapeWorkspace() {
  const navigate = useNavigate();
  const { replayQuery } = useQueryReplay();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Global projection data (all concepts from all ontologies)
  const [globalProjection, setGlobalProjection] = useState<ProjectionData | null>(null);

  // Ontology visibility toggles (derived from projection data)
  const [ontologyVisibility, setOntologyVisibility] = useState<Map<string, boolean>>(new Map());
  const [ontologyColors, setOntologyColors] = useState<Map<string, string>>(new Map());

  const [selectedConcept, setSelectedConcept] = useState<EmbeddingPoint | null>(null);
  const [selectedScreenPos, setSelectedScreenPos] = useState<{ x: number; y: number } | null>(null);

  // Context menu state for right-click actions
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    point: EmbeddingPoint;
  } | null>(null);

  // t-SNE perplexity control (5-100, default 30)
  const [perplexity, setPerplexity] = useState(30);
  const [activeTab, setActiveTab] = useState('ontologies');

  // Color scheme for visualization
  const [colorScheme, setColorScheme] = useState<ColorScheme>('ontology');

  // Distance metric for projection (cosine best for embeddings)
  const [metric, setMetric] = useState<DistanceMetric>('cosine');

  // Refresh grounding during regeneration (slower but accurate)
  const [refreshGrounding, setRefreshGrounding] = useState(false);

  // Color scale for grounding visualization
  const [groundingScale, setGroundingScale] = useState<GroundingScale>('sqrt');

  // Color ramp for grounding visualization
  const [groundingRamp, setGroundingRamp] = useState<GroundingColorRamp>('pink-gray-cyan');

  // Load global projection on mount
  useEffect(() => {
    loadGlobalProjection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Extract unique ontologies and assign colors when projection loads
  useEffect(() => {
    if (!globalProjection) return;

    // Get unique ontologies from the projection data
    const uniqueOntologies = new Set<string>();
    globalProjection.concepts.forEach(c => {
      if (c.ontology) uniqueOntologies.add(c.ontology);
    });

    // Initialize visibility (all visible) and colors
    const visibility = new Map<string, boolean>();
    const colors = new Map<string, string>();
    let colorIndex = 0;

    uniqueOntologies.forEach(ont => {
      visibility.set(ont, true);
      colors.set(ont, ONTOLOGY_COLORS[colorIndex % ONTOLOGY_COLORS.length]);
      colorIndex++;
    });

    setOntologyVisibility(visibility);
    setOntologyColors(colors);
  }, [globalProjection]);

  const loadGlobalProjection = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load the global projection (all ontologies combined)
      const projection = await apiClient.getProjection('__all__', 'concepts');
      setGlobalProjection(projection);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string }; status?: number }; message?: string };
      if (error.response?.status === 404) {
        // No global projection yet - prompt user to generate
        setError('No global projection found. Click "Regenerate" to compute.');
      } else {
        setError(error.response?.data?.detail || error.message || 'Failed to load projection');
      }
    } finally {
      setLoading(false);
    }
  };

  // Regenerate the global projection
  const regenerateGlobalProjection = async () => {
    try {
      setLoading(true);
      setError(null);

      // Regenerate global projection (all ontologies together with global centering)
      await apiClient.regenerateProjection('__all__', {
        force: true,
        perplexity,
        metric,
        refresh_grounding: refreshGrounding,
        embedding_source: 'concepts',
      });

      // Reload the projection
      await loadGlobalProjection();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(error.response?.data?.detail || error.message || 'Failed to regenerate projection');
    } finally {
      setLoading(false);
    }
  };

  const toggleOntology = (ontology: string) => {
    setOntologyVisibility(prev => {
      const next = new Map(prev);
      next.set(ontology, !prev.get(ontology));
      return next;
    });
  };

  // Transform global projection into visualization points with color scheme
  const points: EmbeddingPoint[] = useMemo(() => {
    if (!globalProjection) return [];

    // Filter by visible ontologies and collect points
    const rawPoints: Array<{
      id: string;
      label: string;
      x: number;
      y: number;
      z: number;
      ontology: string;
      grounding: number | null;
      ontologyColor: string;
      itemType: ProjectionItemType;
    }> = [];

    globalProjection.concepts.forEach(concept => {
      const ontology = concept.ontology || 'Unknown';

      // Skip if ontology is hidden
      if (!ontologyVisibility.get(ontology)) return;

      rawPoints.push({
        id: concept.concept_id,
        label: concept.label,
        x: concept.x,
        y: concept.y,
        z: concept.z,
        ontology,
        grounding: concept.grounding_strength,
        ontologyColor: ontologyColors.get(ontology) || '#888888',
        itemType: (concept.item_type as ProjectionItemType) || 'concept',
      });
    });

    if (rawPoints.length === 0) return [];

    // Compute bounds for position coloring
    const bounds = {
      minX: Math.min(...rawPoints.map(p => p.x)),
      maxX: Math.max(...rawPoints.map(p => p.x)),
      minY: Math.min(...rawPoints.map(p => p.y)),
      maxY: Math.max(...rawPoints.map(p => p.y)),
      minZ: Math.min(...rawPoints.map(p => p.z)),
      maxZ: Math.max(...rawPoints.map(p => p.z)),
    };

    // Apply color scheme
    return rawPoints.map(p => {
      let color: string;

      switch (colorScheme) {
        case 'grounding':
          color = groundingToColor(p.grounding, groundingScale, groundingRamp);
          break;
        case 'position':
          color = positionToColor(p.x, p.y, p.z, bounds);
          break;
        case 'ontology':
        default:
          color = p.ontologyColor;
          break;
      }

      return {
        id: p.id,
        label: p.label,
        x: p.x,
        y: p.y,
        z: p.z,
        ontology: p.ontology,
        grounding: p.grounding,
        color,
        itemType: p.itemType,
      };
    });
  }, [globalProjection, ontologyVisibility, ontologyColors, colorScheme, groundingScale, groundingRamp]);

  // Get list of ontologies for UI
  const ontologyList = useMemo(() => {
    return Array.from(ontologyVisibility.keys()).map(ont => ({
      ontology: ont,
      enabled: ontologyVisibility.get(ont) ?? true,
      color: ontologyColors.get(ont) || '#888888',
      count: globalProjection?.concepts.filter(c => c.ontology === ont).length || 0,
    }));
  }, [ontologyVisibility, ontologyColors, globalProjection]);

  // Calculate stats
  const stats = useMemo(() => {
    const enabledCount = ontologyList.filter(o => o.enabled).length;
    return {
      enabledOntologies: enabledCount,
      totalOntologies: ontologyList.length,
      totalConcepts: points.length,
      totalInProjection: globalProjection?.concepts.length || 0,
    };
  }, [ontologyList, points, globalProjection]);

  // Context menu handlers
  const handleContextMenu = useCallback((point: EmbeddingPoint, screenPos: { x: number; y: number }) => {
    setContextMenu({
      x: screenPos.x,
      y: screenPos.y,
      point,
    });
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Navigate to explorer with concept (similarity search)
  const examineAsConcept = useCallback((point: EmbeddingPoint, explorerType: '2d' | '3d') => {
    navigate(`/explore/${explorerType}?conceptId=${point.id}&mode=concept&similarity=0.5`);
    closeContextMenu();
  }, [navigate, closeContextMenu]);

  // Navigate to explorer with neighborhood (subgraph)
  const examineAsNeighborhood = useCallback((point: EmbeddingPoint, explorerType: '2d' | '3d') => {
    navigate(`/explore/${explorerType}?conceptId=${point.id}&mode=neighborhood&depth=2`);
    closeContextMenu();
  }, [navigate, closeContextMenu]);

  // Close context menu on outside click
  useEffect(() => {
    if (contextMenu) {
      const handleClick = () => closeContextMenu();
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [contextMenu, closeContextMenu]);

  return (
    <div className="flex h-full bg-background">
      {/* Sidebar — IconRailPanel with Ontologies + Settings tabs */}
      <IconRailPanel
        tabs={[
          {
            id: 'ontologies',
            icon: Layers,
            label: 'Ontologies',
            content: (
              <div className="flex flex-col h-full">
                <div className="flex-1 overflow-y-auto min-h-0 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-foreground">Ontologies</span>
                    <button
                      onClick={loadGlobalProjection}
                      disabled={loading}
                      className="p-1 text-muted-foreground hover:text-foreground rounded"
                      title="Reload projection"
                    >
                      <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                  </div>

                  {error && (
                    <div className="mb-4 p-2 bg-destructive/20 border border-destructive rounded text-sm text-destructive">
                      {error}
                    </div>
                  )}

                  {ontologyList.length === 0 && !loading && !error && (
                    <div className="text-sm text-muted-foreground text-center py-4">
                      No projection data. Use the regenerate action to generate.
                    </div>
                  )}

                  <div className="space-y-2">
                    {ontologyList.map(ont => (
                      <div
                        key={ont.ontology}
                        className={`p-3 rounded-lg border ${
                          ont.enabled
                            ? 'border-border bg-muted'
                            : 'border-border bg-card opacity-60'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => toggleOntology(ont.ontology)}
                            className="p-1 hover:bg-accent rounded"
                          >
                            {ont.enabled ? (
                              <Eye className="w-4 h-4 text-foreground" />
                            ) : (
                              <EyeOff className="w-4 h-4 text-muted-foreground" />
                            )}
                          </button>

                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: ont.color }}
                          />

                          <span className="text-sm text-foreground truncate flex-1">
                            {ont.ontology}
                          </span>

                          <span className="text-xs text-muted-foreground">
                            {ont.count}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Stats footer pinned at bottom */}
                <div className="flex-shrink-0 p-4 border-t border-border bg-muted/50">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">Ontologies</span>
                      <p className="text-foreground font-medium">
                        {stats.enabledOntologies}/{stats.totalOntologies}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Total Points</span>
                      <p className="text-foreground font-medium">{stats.totalConcepts}</p>
                    </div>
                  </div>
                </div>
              </div>
            ),
          },
          {
            id: 'settings',
            icon: SlidersHorizontal,
            label: 'Settings',
            content: (
              <div className="p-4">
                <div className="space-y-3">
                  {/* Color scheme selector */}
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-2">
                      Color Scheme
                    </label>
                    <div className="space-y-1">
                      {(Object.keys(COLOR_SCHEME_INFO) as ColorScheme[]).map(scheme => (
                        <button
                          key={scheme}
                          onClick={() => setColorScheme(scheme)}
                          className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                            colorScheme === scheme
                              ? 'bg-primary/20 text-primary border border-primary/30'
                              : 'bg-accent/50 text-foreground hover:bg-accent border border-transparent'
                          }`}
                        >
                          <div className="font-medium">{COLOR_SCHEME_INFO[scheme].label}</div>
                          <div className="text-muted-foreground mt-0.5">
                            {COLOR_SCHEME_INFO[scheme].description}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-border my-2" />

                  {/* Perplexity slider */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-foreground">
                        Perplexity
                      </label>
                      <span className="text-xs text-primary font-mono">{perplexity}</span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="100"
                      value={perplexity}
                      onChange={(e) => setPerplexity(Number(e.target.value))}
                      className="w-full h-1.5 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>Local (5)</span>
                      <span>Global (100)</span>
                    </div>
                    <p className="text-xs text-muted-foreground/70 mt-2">
                      Lower values emphasize local clusters, higher values reveal global patterns.
                    </p>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-border my-2" />

                  {/* Distance metric selector */}
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-2">
                      Distance Metric
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setMetric('cosine')}
                        className={`flex-1 px-3 py-2 rounded text-xs transition-colors ${
                          metric === 'cosine'
                            ? 'bg-primary/20 text-primary border border-primary/30'
                            : 'bg-accent/50 text-foreground hover:bg-accent border border-transparent'
                        }`}
                      >
                        <div className="font-medium">Cosine</div>
                        <div className="text-muted-foreground mt-0.5">Angular (semantic)</div>
                      </button>
                      <button
                        onClick={() => setMetric('euclidean')}
                        className={`flex-1 px-3 py-2 rounded text-xs transition-colors ${
                          metric === 'euclidean'
                            ? 'bg-primary/20 text-primary border border-primary/30'
                            : 'bg-accent/50 text-foreground hover:bg-accent border border-transparent'
                        }`}
                      >
                        <div className="font-medium">Euclidean</div>
                        <div className="text-muted-foreground mt-0.5">L2 distance</div>
                      </button>
                    </div>
                  </div>

                  {/* Refresh grounding toggle */}
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-xs font-medium text-foreground">
                        Refresh Grounding
                      </label>
                      <p className="text-xs text-muted-foreground/70">
                        Compute fresh values (slower)
                      </p>
                    </div>
                    <button
                      onClick={() => setRefreshGrounding(!refreshGrounding)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        refreshGrounding ? 'bg-primary' : 'bg-accent'
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                          refreshGrounding ? 'translate-x-4.5' : 'translate-x-0.5'
                        }`}
                        style={{ transform: refreshGrounding ? 'translateX(18px)' : 'translateX(2px)' }}
                      />
                    </button>
                  </div>

                  {/* Apply button */}
                  <button
                    onClick={regenerateGlobalProjection}
                    disabled={loading}
                    className="w-full py-2 px-3 bg-primary text-primary-foreground rounded text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Regenerating...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" />
                        Regenerate
                      </>
                    )}
                  </button>
                </div>
              </div>
            ),
          },
          {
            id: 'savedQueries',
            icon: FolderOpen,
            label: 'Saved Queries',
            content: (
              <SavedQueriesPanel
                onLoadQuery={replayQuery}
                definitionTypeFilter="exploration"
              />
            ),
          },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultExpanded={true}
        actions={[
          {
            id: 'regenerate',
            icon: RefreshCw,
            label: 'Regenerate Projection',
            onClick: regenerateGlobalProjection,
          },
        ]}
      />

      {/* Main visualization area */}
      <div className="flex-1 relative">
        {loading && points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin" />
              <span>Loading projections...</span>
            </div>
          </div>
        ) : points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <Layers className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No projections available</p>
              <p className="text-sm mt-1">Generate projections for ontologies to visualize</p>
            </div>
          </div>
        ) : (
          <EmbeddingScatter3D
            points={points}
            onSelectPoint={(point, screenPos) => {
              setSelectedConcept(point);
              setSelectedScreenPos(screenPos || null);
            }}
            onContextMenu={handleContextMenu}
            selectedPoint={selectedConcept}
          />
        )}

        {/* Color legend */}
        {points.length > 0 && (
          <div className="absolute top-4 right-4 p-3 bg-card/90 border border-border rounded-lg shadow-lg text-xs">
            <div className="font-medium text-foreground mb-2">
              {COLOR_SCHEME_INFO[colorScheme].label}
            </div>
            {colorScheme === 'ontology' && (
              <div className="space-y-1">
                {ontologyList.filter(o => o.enabled).map(ont => (
                  <div key={ont.ontology} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: ont.color }}
                    />
                    <span className="text-muted-foreground truncate max-w-[120px]">
                      {ont.ontology}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {colorScheme === 'grounding' && (
              <div className="space-y-2">
                {/* Scale selector */}
                <div className="flex gap-0.5 rounded overflow-hidden" style={{ width: '140px' }}>
                  {(['linear', 'sqrt', 'log'] as const).map((scale) => (
                    <button
                      key={scale}
                      onClick={() => setGroundingScale(scale)}
                      className={`flex-1 py-1 text-[10px] transition-colors ${
                        groundingScale === scale
                          ? 'bg-primary/30 text-primary'
                          : 'bg-accent/30 text-muted-foreground hover:bg-accent/50'
                      }`}
                    >
                      {scale === 'linear' ? 'Lin' : scale === 'sqrt' ? '√' : 'Log'}
                    </button>
                  ))}
                </div>
                {/* Clickable gradient bar to cycle color ramps */}
                <button
                  onClick={() => setGroundingRamp(getNextGroundingRamp(groundingRamp))}
                  className="h-4 rounded-full cursor-pointer hover:ring-2 hover:ring-primary/50 transition-all"
                  style={{
                    background: getGroundingGradient(groundingRamp, groundingScale),
                    width: '140px',
                  }}
                  title="Click to change colors"
                />
                {/* Labels */}
                <div className="flex justify-between text-[10px] text-muted-foreground" style={{ width: '140px' }}>
                  <span>-1</span>
                  <span>0</span>
                  <span>+1</span>
                </div>
                {/* Current ramp name */}
                <div className="text-[10px] text-muted-foreground/50 text-center" style={{ width: '140px' }}>
                  {GROUNDING_COLOR_RAMPS[groundingRamp].label}
                </div>
              </div>
            )}
            {colorScheme === 'position' && (
              <div className="space-y-2">
                {/* Color wheel for XZ plane */}
                <div className="flex items-center gap-3">
                  <div
                    className="w-12 h-12 rounded-full border border-border/50"
                    style={{
                      background: 'conic-gradient(from 180deg, hsl(0, 90%, 60%), hsl(60, 90%, 60%), hsl(120, 90%, 60%), hsl(180, 90%, 60%), hsl(240, 90%, 60%), hsl(300, 90%, 60%), hsl(360, 90%, 60%))',
                    }}
                  />
                  <div className="text-[10px] text-muted-foreground">
                    <div>XZ position</div>
                    <div className="text-muted-foreground/60">= hue angle</div>
                  </div>
                </div>
                {/* Lightness gradient for Y axis */}
                <div className="flex items-center gap-3">
                  <div
                    className="w-12 h-3 rounded"
                    style={{
                      background: 'linear-gradient(to right, hsl(200, 90%, 50%), hsl(200, 90%, 70%))',
                    }}
                  />
                  <div className="text-[10px] text-muted-foreground">
                    <div>Y height</div>
                    <div className="text-muted-foreground/60">= brightness</div>
                  </div>
                </div>
              </div>
            )}
            <div className="text-muted-foreground/60 mt-2 pt-2 border-t border-border">
              {stats.totalConcepts} points
            </div>
          </div>
        )}

        {/* Selected concept info - using shared NodeInfoBox */}
        {selectedConcept && selectedScreenPos && (
          <div className="absolute inset-0 pointer-events-none overflow-visible">
            <NodeInfoBox
              info={{
                nodeId: selectedConcept.id,
                label: selectedConcept.label,
                group: selectedConcept.ontology,
                degree: 0, // Not available in projection data
                x: selectedScreenPos.x,
                y: selectedScreenPos.y,
              }}
              onDismiss={() => {
                setSelectedConcept(null);
                setSelectedScreenPos(null);
              }}
            />
          </div>
        )}

        {/* Context menu for right-click actions */}
        {contextMenu && (
          <div
            className="absolute z-[9999] bg-card border border-border rounded-lg shadow-xl py-1 min-w-[220px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-3 py-2 border-b border-border">
              <div className="font-semibold text-sm text-card-foreground truncate">
                {contextMenu.point.label}
              </div>
              <div className="text-xs text-muted-foreground truncate">
                {contextMenu.point.ontology}
              </div>
            </div>
            <div className="py-1">
              {/* Concept Mode (Similarity Search) */}
              <div className="px-3 py-1.5">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Examine as Concept
                </div>
                <div className="text-xs text-muted-foreground mb-1">
                  Find similar concepts (~50% similarity)
                </div>
              </div>
              <button
                onClick={() => examineAsConcept(contextMenu.point, '2d')}
                className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent transition-colors text-card-foreground"
              >
                → 2D Force Graph
              </button>
              <button
                onClick={() => examineAsConcept(contextMenu.point, '3d')}
                className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent transition-colors text-card-foreground mb-2"
              >
                → 3D Force Graph
              </button>

              {/* Neighborhood Mode (Subgraph) */}
              <div className="px-3 py-1.5 border-t border-border">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Examine as Neighborhood
                </div>
                <div className="text-xs text-muted-foreground mb-1">
                  Explore connected concepts (2 hops)
                </div>
              </div>
              <button
                onClick={() => examineAsNeighborhood(contextMenu.point, '2d')}
                className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent transition-colors text-card-foreground"
              >
                → 2D Force Graph
              </button>
              <button
                onClick={() => examineAsNeighborhood(contextMenu.point, '3d')}
                className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent transition-colors text-card-foreground"
              >
                → 3D Force Graph
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
