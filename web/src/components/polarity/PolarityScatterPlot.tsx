/**
 * Polarity Axis Scatter Plot Visualization
 *
 * 2D bubble chart showing concept distribution across polarity axis:
 * - X-axis: Position on axis (-1 to +1)
 * - Y-axis: Grounding strength
 * - Color: Direction (positive/neutral/negative)
 * - Size: Inverse of axis distance (larger = better fit)
 */

import React, { useState, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  ReferenceArea,
  Label,
  Area,
} from 'recharts';
import type { PolarityAxisResponse, ProjectedConcept } from '../../types/polarity';
import { NodeInfoBox } from '../../explorers/common/NodeInfoBox';

interface PolarityScatterPlotProps {
  analysisResult: PolarityAxisResponse;
  onConceptClick?: (concept: ProjectedConcept) => void;
}

// Color constants matching existing polarity explorer
const DIRECTION_COLORS = {
  positive: '#3B82F6',    // blue-500
  negative: '#F97316',    // orange-500
  neutral: '#9CA3AF',     // gray-400
} as const;

// Inferno heatmap color scheme (pure function, computed once)
// Black/dark purple → Red → Orange → Yellow
const getHeatColor = (intensity: number): string => {
  if (intensity < 0.25) {
    // Black to dark purple
    const t = intensity / 0.25;
    return `rgba(${0 + t * 50}, ${0 + t * 10}, ${0 + t * 70}, ${0.2 + t * 0.3})`;
  } else if (intensity < 0.5) {
    // Dark purple to red
    const t = (intensity - 0.25) / 0.25;
    return `rgba(${50 + t * 140}, ${10 + t * 10}, ${70 - t * 60}, ${0.5 + t * 0.15})`;
  } else if (intensity < 0.75) {
    // Red to orange
    const t = (intensity - 0.5) / 0.25;
    return `rgba(${190 + t * 40}, ${20 + t * 100}, ${10 + t * 0}, ${0.65 + t * 0.15})`;
  } else {
    // Orange to yellow/white
    const t = (intensity - 0.75) / 0.25;
    return `rgba(${230 + t * 25}, ${120 + t * 135}, ${10 + t * 230}, ${0.8 + t * 0.2})`;
  }
};

export const PolarityScatterPlot: React.FC<PolarityScatterPlotProps> = ({
  analysisResult,
  onConceptClick,
}) => {
  const navigate = useNavigate();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(['positive', 'negative', 'neutral'])
  );
  const [hoveredConcept, setHoveredConcept] = useState<ProjectedConcept | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    concept: ProjectedConcept;
  } | null>(null);

  // Selected concept for NodeInfoBox (left-click)
  const [selectedConcept, setSelectedConcept] = useState<{
    nodeId: string;
    label: string;
    group: string; // direction as group
    degree: number; // use 0 since we don't have this in polarity view
    x: number;
    y: number;
  } | null>(null);

  // Visualization layer toggles
  const [visualLayers, setVisualLayers] = useState({
    showBubbles: true,
    labels: false,
    regressionLine: true,
    confidenceBand: false,
    centroid: false,
    heatmap: false,
  });

  const toggleLayer = (layer: keyof typeof visualLayers) => {
    setVisualLayers(prev => ({ ...prev, [layer]: !prev[layer] }));
  };

  // Calculate regression line parameters
  const regressionLine = useMemo(() => {
    const { projections, grounding_correlation } = analysisResult;
    if (projections.length < 2) return null;

    // Simple linear regression: y = mx + b
    // Using Pearson r to calculate slope
    const positions = projections.map(p => p.position);
    const groundings = projections.map(p => p.grounding);

    const meanX = positions.reduce((a, b) => a + b, 0) / positions.length;
    const meanY = groundings.reduce((a, b) => a + b, 0) / groundings.length;

    const r = grounding_correlation.pearson_r;
    const stdX = Math.sqrt(
      positions.reduce((sum, x) => sum + Math.pow(x - meanX, 2), 0) / positions.length
    );
    const stdY = Math.sqrt(
      groundings.reduce((sum, y) => sum + Math.pow(y - meanY, 2), 0) / groundings.length
    );

    const slope = r * (stdY / stdX);
    const intercept = meanY - slope * meanX;

    return { slope, intercept };
  }, [analysisResult]);

  // Calculate fixed Y-axis domain based on ALL concepts (not just visible)
  // This prevents the chart from rescaling when filters change
  const yAxisDomain = useMemo(() => {
    const groundings = analysisResult.projections.map(p => p.grounding);
    const minGrounding = Math.min(...groundings);
    const maxGrounding = Math.max(...groundings);
    // Add 10% padding
    const padding = (maxGrounding - minGrounding) * 0.1;
    return [minGrounding - padding, maxGrounding + padding];
  }, [analysisResult.projections]);

  // Transform data for visualization
  const chartData = useMemo(() => {
    const filtered = analysisResult.projections
      .filter(p => activeFilters.has(p.direction))
      .map(projection => ({
        ...projection,
        // Calculate bubble size (inverse of axis distance)
        // Scale: distance 0-0.5 -> size 400-200, distance 0.5-1.0 -> size 200-100, >1.0 -> size 100-50
        size: projection.axis_distance < 0.5
          ? 400 - projection.axis_distance * 400
          : projection.axis_distance < 1.0
          ? 200 - (projection.axis_distance - 0.5) * 200
          : Math.max(50, 100 - (projection.axis_distance - 1.0) * 50),
        color: DIRECTION_COLORS[projection.direction],
        visible: true, // Mark as visible
      }));

    // If all filters are off, add an invisible dummy point to maintain chart coordinate system
    // This allows heatmap and other layers to still render
    if (filtered.length === 0 && analysisResult.projections.length > 0) {
      const firstConcept = analysisResult.projections[0];
      return [{
        ...firstConcept,
        size: 1,
        color: 'transparent',
        visible: false, // Mark as invisible dummy
      }];
    }

    return filtered;
  }, [analysisResult.projections, activeFilters]);


  // Toggle filter
  const toggleFilter = (direction: 'positive' | 'negative' | 'neutral') => {
    setActiveFilters(prev => {
      const newFilters = new Set(prev);
      if (newFilters.has(direction)) {
        newFilters.delete(direction);
      } else {
        newFilters.add(direction);
      }
      return newFilters;
    });
  };

  // Handle right-click on concept
  const handleContextMenu = useCallback((event: React.MouseEvent, concept: ProjectedConcept) => {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      concept,
    });
  }, []);

  // Close context menu
  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Navigate to explorer with concept (similarity search)
  const examineAsConcept = useCallback((concept: ProjectedConcept, explorerType: '2d' | '3d') => {
    navigate(`/explore/${explorerType}?conceptId=${concept.concept_id}&mode=concept&similarity=0.5`);
    closeContextMenu();
  }, [navigate, closeContextMenu]);

  // Navigate to explorer with neighborhood (subgraph)
  const examineAsNeighborhood = useCallback((concept: ProjectedConcept, explorerType: '2d' | '3d') => {
    navigate(`/explore/${explorerType}?conceptId=${concept.concept_id}&mode=neighborhood&depth=2`);
    closeContextMenu();
  }, [navigate, closeContextMenu]);

  // Filter button tooltips
  const filterTooltips = {
    positive: 'Show concepts aligned with the positive pole',
    negative: 'Show concepts aligned with the negative pole',
    neutral: 'Show concepts balanced between both poles',
  };

  // Generate regression line points as a tuple for ReferenceLineSegment
  const regressionPoints = useMemo((): [{ x: number; y: number }, { x: number; y: number }] | null => {
    if (!regressionLine) return null;
    const { slope, intercept } = regressionLine;
    return [
      { x: -1, y: slope * -1 + intercept },
      { x: 1, y: slope * 1 + intercept },
    ];
  }, [regressionLine]);

  // Determine regression line color based on p-value
  const regressionLineColor = useMemo(() => {
    const p = analysisResult.grounding_correlation.p_value;
    if (p < 0.05) return '#10B981'; // green-500 - significant
    if (p < 0.1) return '#F59E0B'; // amber-500 - marginal
    return '#9CA3AF'; // gray-400 - not significant
  }, [analysisResult.grounding_correlation.p_value]);

  // Calculate confidence band width based on correlation strength
  // Stronger correlation (higher |r|) = narrower band
  const confidenceBandWidth = useMemo(() => {
    const r = analysisResult.grounding_correlation.pearson_r;
    // Width inversely proportional to |r|: weak correlation = wide band
    // r=0: width=0.3, r=0.5: width=0.15, r=1.0: width=0.03
    return 0.3 * (1 - Math.abs(r));
  }, [analysisResult.grounding_correlation.pearson_r]);

  // Generate confidence band boundary points
  const confidenceBandPoints = useMemo(() => {
    if (!regressionLine || confidenceBandWidth === 0) return [];
    const { slope, intercept } = regressionLine;

    // Upper and lower bounds
    const upperBound = [
      { x: -1, y: (slope * -1 + intercept) + confidenceBandWidth },
      { x: 1, y: (slope * 1 + intercept) + confidenceBandWidth },
    ];
    const lowerBound = [
      { x: 1, y: (slope * 1 + intercept) - confidenceBandWidth },
      { x: -1, y: (slope * -1 + intercept) - confidenceBandWidth },
    ];

    return [...upperBound, ...lowerBound];
  }, [regressionLine, confidenceBandWidth]);

  // Calculate centroid (center of mass) of all concepts
  // This shows where the concept cloud converges
  const centroid = useMemo(() => {
    const projections = analysisResult.projections;
    if (projections.length === 0) return null;

    const sumPosition = projections.reduce((sum, p) => sum + p.position, 0);
    const sumGrounding = projections.reduce((sum, p) => sum + p.grounding, 0);

    return {
      position: sumPosition / projections.length,
      grounding: sumGrounding / projections.length,
    };
  }, [analysisResult.projections]);

  // Memoized heatmap rendering - only recreates when data or visibility changes
  const heatmapLayer = useMemo(() => {
    const projections = analysisResult.projections;
    if (projections.length === 0 || !visualLayers.heatmap) return null;

    const gridSize = 40; // 40x40 grid for smoother gradients

    // Calculate dynamic bounds based on actual data
    const positions = projections.map(p => p.position);
    const groundings = projections.map(p => p.grounding);
    const xMin = Math.min(...positions);
    const xMax = Math.max(...positions);
    const yMin = Math.min(...groundings);
    const yMax = Math.max(...groundings);

    // Add 15% padding to bounds for smoother edges
    const xPadding = (xMax - xMin) * 0.15;
    const yPadding = (yMax - yMin) * 0.15;
    const xMinPadded = xMin - xPadding;
    const xMaxPadded = xMax + xPadding;
    const yMinPadded = yMin - yPadding;
    const yMaxPadded = yMax + yPadding;

    const cellWidth = (xMaxPadded - xMinPadded) / gridSize;
    const cellHeight = (yMaxPadded - yMinPadded) / gridSize;

    // Initialize grid with smoothing (include neighboring cells)
    const grid: number[][] = Array(gridSize).fill(0).map(() => Array(gridSize).fill(0));

    // Count concepts in each cell with slight spreading to neighbors
    projections.forEach(p => {
      const xIndex = Math.floor((p.position - xMinPadded) / cellWidth);
      const yIndex = Math.floor((p.grounding - yMinPadded) / cellHeight);

      // Add to cell and immediate neighbors for smoothing effect
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const xi = xIndex + dx;
          const yi = yIndex + dy;
          if (xi >= 0 && xi < gridSize && yi >= 0 && yi < gridSize) {
            // Weight: center cell gets 1.0, immediate neighbors get 0.5, diagonals get 0.25
            const weight = (dx === 0 && dy === 0) ? 1.0 : (dx === 0 || dy === 0) ? 0.5 : 0.25;
            grid[yi][xi] += weight;
          }
        }
      }
    });

    // Find max density for normalization
    const maxDensity = Math.max(...grid.flat());
    if (maxDensity === 0) return null;

    // Render cells directly as React elements (cached)
    const cells: React.ReactElement[] = [];
    for (let y = 0; y < gridSize; y++) {
      for (let x = 0; x < gridSize; x++) {
        const density = grid[y][x];
        const intensity = density / maxDensity;

        // Only render cells with some density
        if (intensity > 0.05) {
          const cellX = xMinPadded + x * cellWidth;
          const cellY = yMinPadded + y * cellHeight;
          cells.push(
            <ReferenceArea
              key={`heat-${y}-${x}`}
              x1={cellX}
              x2={cellX + cellWidth}
              y1={cellY}
              y2={cellY + cellHeight}
              fill={getHeatColor(intensity)}
              fillOpacity={1}
              stroke="none"
              ifOverflow="hidden"
              style={{ pointerEvents: 'none' }}
            />
          );
        }
      }
    }

    return cells;
  }, [analysisResult.projections, visualLayers.heatmap]);

  // Custom tick formatter for color-coded axis labels
  const formatAxisTick = (value: number) => {
    return value;
  };

  // Close context menu when clicking outside
  React.useEffect(() => {
    if (contextMenu) {
      const handleClick = () => closeContextMenu();
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [contextMenu, closeContextMenu]);

  return (
    <div className="flex flex-col gap-4 relative" ref={chartContainerRef} onClick={(e) => {
      closeContextMenu();
      // Dismiss NodeInfoBox on click outside (unless clicking on a concept)
      if (selectedConcept && !(e.target as HTMLElement).closest('.recharts-scatter-symbol')) {
        setSelectedConcept(null);
      }
    }}>
      {/* NodeInfoBox for selected concept (left-click) */}
      {selectedConcept && (
        <NodeInfoBox
          info={selectedConcept}
          onDismiss={() => setSelectedConcept(null)}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="fixed z-[9999] bg-card dark:bg-gray-800 border border-border dark:border-gray-600 rounded-lg shadow-xl py-1 min-w-[220px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-3 py-2 border-b border-border dark:border-gray-700">
            <div className="font-semibold text-sm text-card-foreground dark:text-gray-100 truncate">
              {contextMenu.concept.label}
            </div>
          </div>
          <div className="py-1">
            {/* Concept Mode (Similarity Search) */}
            <div className="px-3 py-1.5">
              <div className="text-xs font-medium text-muted-foreground dark:text-gray-500 uppercase tracking-wide">
                Examine as Concept
              </div>
              <div className="text-xs text-muted-foreground dark:text-gray-500 mb-1">
                Find similar concepts (~50% similarity)
              </div>
            </div>
            <button
              onClick={() => examineAsConcept(contextMenu.concept, '2d')}
              className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent dark:hover:bg-gray-700 transition-colors text-card-foreground dark:text-gray-200"
            >
              → 2D Force Graph
            </button>
            <button
              onClick={() => examineAsConcept(contextMenu.concept, '3d')}
              className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent dark:hover:bg-gray-700 transition-colors text-card-foreground dark:text-gray-200 mb-2"
            >
              → 3D Force Graph
            </button>

            {/* Neighborhood Mode (Subgraph) */}
            <div className="px-3 py-1.5 border-t border-border dark:border-gray-700">
              <div className="text-xs font-medium text-muted-foreground dark:text-gray-500 uppercase tracking-wide">
                Examine as Neighborhood
              </div>
              <div className="text-xs text-muted-foreground dark:text-gray-500 mb-1">
                Explore connected concepts (2 hops)
              </div>
            </div>
            <button
              onClick={() => examineAsNeighborhood(contextMenu.concept, '2d')}
              className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent dark:hover:bg-gray-700 transition-colors text-card-foreground dark:text-gray-200"
            >
              → 2D Force Graph
            </button>
            <button
              onClick={() => examineAsNeighborhood(contextMenu.concept, '3d')}
              className="w-full px-6 py-1.5 text-left text-sm hover:bg-accent dark:hover:bg-gray-700 transition-colors text-card-foreground dark:text-gray-200"
            >
              → 3D Force Graph
            </button>
          </div>
        </div>
      )}

      {/* Filter and Visualization Controls */}
      <div className="flex flex-col gap-3 px-4">
        {/* Concept Filters */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-muted-foreground dark:text-gray-400">
            Show:
          </span>
          <div className="flex gap-2">
            {(['positive', 'negative', 'neutral'] as const).map(direction => (
              <button
                key={direction}
                onClick={() => toggleFilter(direction)}
                title={filterTooltips[direction]}
                className={`px-3 py-1 rounded text-sm font-medium transition-all ${
                  activeFilters.has(direction)
                    ? 'opacity-100'
                    : 'opacity-30 hover:opacity-50'
                }`}
                style={{
                  backgroundColor: activeFilters.has(direction)
                    ? `${DIRECTION_COLORS[direction]}20`
                    : 'transparent',
                  color: DIRECTION_COLORS[direction],
                  border: `1px solid ${DIRECTION_COLORS[direction]}`,
                }}
              >
                {direction.charAt(0).toUpperCase() + direction.slice(1)}
              </button>
            ))}
          </div>
          <div className="ml-auto text-xs text-muted-foreground dark:text-gray-500">
            r = {analysisResult.grounding_correlation.pearson_r.toFixed(3)}, p = {analysisResult.grounding_correlation.p_value.toFixed(4)}
          </div>
        </div>

        {/* Visualization Layer Toggles */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-muted-foreground dark:text-gray-400">
            Layers:
          </span>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => toggleLayer('showBubbles')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.showBubbles
                  ? 'bg-blue-500/20 text-blue-500 border-blue-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show concept bubbles (size = relevance to axis)"
            >
              Bubbles
            </button>
            <button
              onClick={() => toggleLayer('labels')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.labels
                  ? 'bg-cyan-500/20 text-cyan-500 border-cyan-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show concept name labels"
            >
              Labels
            </button>
            <button
              onClick={() => toggleLayer('regressionLine')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.regressionLine
                  ? 'bg-indigo-500/20 text-indigo-500 border-indigo-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show regression line (correlation trend)"
            >
              Regression
            </button>
            <button
              onClick={() => toggleLayer('confidenceBand')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.confidenceBand
                  ? 'bg-indigo-500/20 text-indigo-500 border-indigo-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show confidence band (correlation strength)"
            >
              Confidence
            </button>
            <button
              onClick={() => toggleLayer('centroid')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.centroid
                  ? 'bg-purple-500/20 text-purple-500 border-purple-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show centroid (center of mass)"
            >
              Centroid
            </button>
            <button
              onClick={() => toggleLayer('heatmap')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                visualLayers.heatmap
                  ? 'bg-red-500/20 text-red-500 border-red-500'
                  : 'bg-transparent text-muted-foreground border-muted-foreground/30'
              } border`}
              title="Show density heatmap"
            >
              Heatmap
            </button>
            <button
              onClick={() => setVisualLayers({ showBubbles: true, labels: true, regressionLine: true, confidenceBand: true, centroid: true, heatmap: true })}
              className="px-2 py-1 rounded text-xs font-medium bg-muted-foreground/10 text-muted-foreground border border-muted-foreground/30 hover:bg-muted-foreground/20 transition-all"
              title="Show all visualization layers"
            >
              All
            </button>
          </div>
        </div>
      </div>

      {/* Scatter Plot - responsive with aspect ratio constraint */}
      {/* [&_*] selector removes focus outlines from all nested elements to prevent white rectangle on click */}
      <div className="w-full aspect-[4/3] [&_.recharts-wrapper]:outline-none [&_.recharts-surface]:outline-none [&_*:focus]:outline-none [&_*]:focus-visible:outline-none">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart
          margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
        >
          {/* Density heatmap (background layer - render first so it's behind everything) */}
          {heatmapLayer}

          <CartesianGrid strokeDasharray="3 3" className="stroke-muted dark:stroke-gray-700" />

          {/* X-axis: Position on polarity axis */}
          <XAxis
            type="number"
            dataKey="position"
            name="Position"
            domain={[-1, 1]}
            ticks={[-1, -0.5, 0, 0.5, 1]}
            tick={(props) => {
              const { x, y, payload } = props;
              const value = payload.value;
              const color = value < 0 ? '#EF4444' : value > 0 ? '#10B981' : '#9CA3AF';
              return (
                <text
                  x={x}
                  y={y}
                  dy={16}
                  textAnchor="middle"
                  fill={color}
                  fontSize={12}
                >
                  {value}
                </text>
              );
            }}
          >
            <Label
              value="Position on Axis (Negative ← → Positive)"
              position="bottom"
              offset={20}
              className="text-sm font-medium fill-card-foreground dark:fill-gray-100"
            />
          </XAxis>

          {/* Y-axis: Grounding strength */}
          <YAxis
            type="number"
            dataKey="grounding"
            name="Grounding"
            domain={yAxisDomain}
            tick={(props) => {
              const { x, y, payload } = props;
              const value = payload.value;
              const color = value < 0 ? '#EF4444' : value > 0 ? '#10B981' : '#9CA3AF';
              return (
                <text
                  x={x}
                  y={y}
                  dx={-8}
                  textAnchor="end"
                  fill={color}
                  fontSize={12}
                >
                  {value.toFixed(1)}
                </text>
              );
            }}
          >
            <Label
              value="Grounding Strength"
              angle={-90}
              position="left"
              offset={20}
              className="text-sm font-medium fill-card-foreground dark:fill-gray-100"
            />
          </YAxis>

          {/* Tooltip disabled - use labels layer and click for NodeInfoBox instead */}

          {/* Zero reference lines */}
          <ReferenceLine
            x={0}
            stroke="#9CA3AF"
            strokeDasharray="3 3"
            strokeWidth={1}
            label={{ value: 'Neutral', position: 'top', className: 'text-xs fill-muted-foreground dark:fill-gray-500' }}
          />
          <ReferenceLine
            y={0}
            stroke="#9CA3AF"
            strokeDasharray="3 3"
            strokeWidth={1}
          />

          {/* Confidence band (shows correlation strength via width) */}
          {visualLayers.confidenceBand && regressionLine && confidenceBandWidth > 0 && (
            <>
              <ReferenceLine
                y={(regressionLine.slope * -1 + regressionLine.intercept) + confidenceBandWidth}
                stroke={regressionLineColor}
                strokeWidth={1}
                strokeOpacity={0.3}
                strokeDasharray="2 2"
              />
              <ReferenceLine
                y={(regressionLine.slope * -1 + regressionLine.intercept) - confidenceBandWidth}
                stroke={regressionLineColor}
                strokeWidth={1}
                strokeOpacity={0.3}
                strokeDasharray="2 2"
              />
            </>
          )}

          {/* Regression line (color shows significance via p-value) */}
          {visualLayers.regressionLine && regressionLine && regressionPoints && (
            <ReferenceLine
              segment={regressionPoints}
              stroke={regressionLineColor}
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: `y = ${regressionLine.slope.toFixed(2)}x + ${regressionLine.intercept.toFixed(2)}`,
                position: 'insideTopRight',
                style: { fill: regressionLineColor, fontSize: '11px', fontFamily: 'monospace' },
              }}
            />
          )}

          {/* Centroid marker (center of mass) */}
          {visualLayers.centroid && centroid && (
            <Scatter
              data={[{ position: centroid.position, grounding: centroid.grounding }]}
              fill="none"
              isAnimationActive={false}
              shape={(props: any) => {
                const { cx, cy } = props;
                return (
                  <g style={{ pointerEvents: 'none' }}>
                    {/* Outer circle */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={12}
                      fill="none"
                      stroke="#A855F7"
                      strokeWidth={2}
                      strokeOpacity={0.8}
                    />
                    {/* Inner circle */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={6}
                      fill="none"
                      stroke="#A855F7"
                      strokeWidth={2}
                      strokeOpacity={0.8}
                    />
                    {/* Crosshair */}
                    <line x1={cx - 15} y1={cy} x2={cx + 15} y2={cy} stroke="#A855F7" strokeWidth={1.5} strokeOpacity={0.6} />
                    <line x1={cx} y1={cy - 15} x2={cx} y2={cy + 15} stroke="#A855F7" strokeWidth={1.5} strokeOpacity={0.6} />
                  </g>
                );
              }}
            />
          )}

          {/* Data points (bubbles with direction indicators) */}
          <Scatter
            name="Concepts"
            data={chartData}
            onMouseEnter={(data) => setHoveredConcept(data)}
            onMouseLeave={() => setHoveredConcept(null)}
            cursor="pointer"
            shape={(props: any) => {
              const { cx, cy, fill, payload } = props;

              // Don't render invisible dummy points (used to maintain coordinate system)
              if (payload.visible === false) {
                return null;
              }

              const radius = Math.sqrt(payload.size / Math.PI);
              const isHovered = hoveredConcept?.concept_id === payload.concept_id;

              // Calculate direction indicator (flow telltale)
              // Shows the concept's trend direction in position-grounding space
              // Like yarn on a wing, shows the "flow" direction for this specific concept

              // Calculate vector magnitude (distance from origin)
              // Strong concepts (far from origin) get longer telltales
              const vectorMagnitude = Math.sqrt(
                payload.position ** 2 + payload.grounding ** 2
              );
              // Increased scale factor to make length differences more visible
              const indicatorLength = radius + 4 + (vectorMagnitude * 20); // Scales with strength

              // Calculate angle from origin to concept point (position, grounding)
              // This shows each concept's individual trend direction
              const angle = Math.atan2(payload.grounding, payload.position);

              const lineEndX = cx + Math.cos(angle) * indicatorLength;
              const lineEndY = cy - Math.sin(angle) * indicatorLength; // Negative because SVG Y increases downward
              const lineStartX = cx + Math.cos(angle) * radius;
              const lineStartY = cy - Math.sin(angle) * radius;

              // Visual distinction by direction
              const strokeDasharray = payload.direction === 'neutral' ? '2,2' : 'none';
              const strokeWidth = isHovered ? 2.5 : (payload.direction === 'neutral' ? 1.5 : 2);

              // Click handler for showing NodeInfoBox
              const handleClick = (e: React.MouseEvent) => {
                e.stopPropagation();
                const containerRect = chartContainerRef.current?.getBoundingClientRect();
                if (containerRect) {
                  const x = e.clientX - containerRect.left;
                  const y = e.clientY - containerRect.top;
                  setSelectedConcept({
                    nodeId: payload.concept_id,
                    label: payload.label,
                    group: payload.direction,
                    degree: 0,
                    x,
                    y,
                  });
                }
                onConceptClick?.(payload);
              };

              return (
                <g>
                  {/* Direction indicator (flow telltale) - shows trend direction for each concept */}
                  <line
                    x1={visualLayers.showBubbles ? lineStartX : cx}
                    y1={visualLayers.showBubbles ? lineStartY : cy}
                    x2={lineEndX}
                    y2={lineEndY}
                    stroke={fill}
                    strokeWidth={isHovered ? 2.5 : (visualLayers.showBubbles ? 1.5 : 2)}
                    strokeOpacity={isHovered ? 0.95 : (visualLayers.showBubbles ? 0.6 : 0.8)}
                    strokeLinecap="round"
                    pointerEvents="none"
                  />

                  {/* Bubble (conditionally rendered) */}
                  {visualLayers.showBubbles && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={radius}
                      fill={fill}
                      fillOpacity={isHovered ? 0.9 : 0.6}
                      stroke={fill}
                      strokeWidth={strokeWidth}
                      strokeDasharray={strokeDasharray}
                      strokeOpacity={isHovered ? 1 : 0.8}
                      style={{ cursor: 'pointer', pointerEvents: 'all' }}
                      onMouseDown={(e) => {
                        if (e.button === 0) { // Left click only
                          handleClick(e);
                        }
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        handleContextMenu(e as any, payload);
                      }}
                    />
                  )}

                  {/* Small dot at telltale origin when bubbles hidden (for hover/click target) */}
                  {!visualLayers.showBubbles && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 4 : 3}
                      fill={fill}
                      fillOpacity={isHovered ? 0.9 : 0.7}
                      stroke={fill}
                      strokeWidth={1}
                      style={{ cursor: 'pointer', pointerEvents: 'all' }}
                      onMouseDown={(e) => {
                        if (e.button === 0) { // Left click only
                          handleClick(e);
                        }
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        handleContextMenu(e as any, payload);
                      }}
                    />
                  )}

                  {/* Label (conditionally rendered) */}
                  {visualLayers.labels && (
                    <text
                      x={cx + radius + 4}
                      y={cy}
                      fontSize={10}
                      fill={fill}
                      fillOpacity={0.9}
                      dominantBaseline="middle"
                      pointerEvents="none"
                      style={{ userSelect: 'none' }}
                    >
                      {payload.label.length > 15 ? payload.label.substring(0, 15) + '…' : payload.label}
                    </text>
                  )}
                </g>
              );
            }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.color}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-3 px-4">
        <div className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide">
          Legend
        </div>

        {/* Concept visualization */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground dark:text-gray-400">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: DIRECTION_COLORS.positive }} />
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: DIRECTION_COLORS.positive }} />
              <div className="w-4 h-4 rounded-full" style={{ backgroundColor: DIRECTION_COLORS.positive }} />
            </div>
            <span>Bubble size = Relevance to axis (larger = better fit)</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="32" height="16" className="inline-block">
              {/* Short telltale */}
              <circle cx="6" cy="8" r="4" fill={DIRECTION_COLORS.neutral} fillOpacity="0.5" stroke={DIRECTION_COLORS.neutral} strokeWidth="1" />
              <line x1="10" y1="8" x2="13" y2="8" stroke={DIRECTION_COLORS.neutral} strokeWidth="1" strokeOpacity="0.5" strokeLinecap="round" />
              {/* Long telltale */}
              <circle cx="20" cy="8" r="4" fill={DIRECTION_COLORS.positive} fillOpacity="0.6" stroke={DIRECTION_COLORS.positive} strokeWidth="2" />
              <line x1="24" y1="8" x2="31" y2="8" stroke={DIRECTION_COLORS.positive} strokeWidth="1.5" strokeOpacity="0.6" strokeLinecap="round" />
            </svg>
            <span>Flow telltale = Trend direction (angle) & signal strength (length)</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="20" height="16" className="inline-block">
              <circle cx="10" cy="8" r="6" fill={DIRECTION_COLORS.neutral} fillOpacity="0.6" stroke={DIRECTION_COLORS.neutral} strokeWidth="1.5" strokeDasharray="2,2" />
            </svg>
            <span>Dashed border = Neutral (balanced)</span>
          </div>
        </div>

        {/* Statistical layers */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground dark:text-gray-400">
          <div className="flex items-center gap-2">
            <svg width="32" height="16" className="inline-block">
              <line x1="0" y1="8" x2="32" y2="8" stroke="#10B981" strokeWidth="2" strokeDasharray="5 5" />
            </svg>
            <span>Regression line color: <span className="text-green-500">Green</span> (p&lt;0.05), <span className="text-amber-500">Amber</span> (p&lt;0.1), <span className="text-gray-400">Gray</span> (p≥0.1)</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="32" height="16" className="inline-block">
              <line x1="0" y1="5" x2="32" y2="5" stroke="#10B981" strokeWidth="1" strokeOpacity="0.3" strokeDasharray="2 2" />
              <line x1="0" y1="8" x2="32" y2="8" stroke="#10B981" strokeWidth="2" strokeDasharray="5 5" />
              <line x1="0" y1="11" x2="32" y2="11" stroke="#10B981" strokeWidth="1" strokeOpacity="0.3" strokeDasharray="2 2" />
            </svg>
            <span>Confidence band width = Correlation strength (narrow = strong |r|, wide = weak |r|)</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="20" height="16" className="inline-block">
              <circle cx="10" cy="8" r="5" fill="none" stroke="#A855F7" strokeWidth="1.5" strokeOpacity="0.8" />
              <circle cx="10" cy="8" r="2.5" fill="none" stroke="#A855F7" strokeWidth="1.5" strokeOpacity="0.8" />
              <line x1="5" y1="8" x2="15" y2="8" stroke="#A855F7" strokeWidth="1" strokeOpacity="0.6" />
              <line x1="10" y1="3" x2="10" y2="13" stroke="#A855F7" strokeWidth="1" strokeOpacity="0.6" />
            </svg>
            <span>Centroid (purple crosshair) = Center of mass of concept cloud</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="60" height="16" className="inline-block">
              <rect x="0" y="0" width="12" height="16" fill="rgba(50, 10, 70, 0.5)" />
              <rect x="12" y="0" width="12" height="16" fill="rgba(140, 20, 60, 0.65)" />
              <rect x="24" y="0" width="12" height="16" fill="rgba(220, 80, 10, 0.75)" />
              <rect x="36" y="0" width="12" height="16" fill="rgba(245, 180, 50, 0.85)" />
              <rect x="48" y="0" width="12" height="16" fill="rgba(255, 240, 200, 0.95)" />
            </svg>
            <span>Heatmap (Inferno): Dark → <span className="text-red-500">Red</span> → <span className="text-orange-500">Orange</span> → <span className="text-yellow-400">Yellow</span> (low to high density)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
