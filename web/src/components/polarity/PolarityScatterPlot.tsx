/**
 * Polarity Axis Scatter Plot Visualization
 *
 * 2D bubble chart showing concept distribution across polarity axis:
 * - X-axis: Position on axis (-1 to +1)
 * - Y-axis: Grounding strength
 * - Color: Direction (positive/neutral/negative)
 * - Size: Inverse of axis distance (larger = better fit)
 */

import React, { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Label,
} from 'recharts';
import type { PolarityAxisResponse, ProjectedConcept } from '../../types/polarity';

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

export const PolarityScatterPlot: React.FC<PolarityScatterPlotProps> = ({
  analysisResult,
  onConceptClick,
}) => {
  const navigate = useNavigate();
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(['positive', 'negative', 'neutral'])
  );
  const [hoveredConcept, setHoveredConcept] = useState<ProjectedConcept | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    concept: ProjectedConcept;
  } | null>(null);

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

  // Transform data for visualization
  const chartData = useMemo(() => {
    return analysisResult.projections
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
      }));
  }, [analysisResult.projections, activeFilters]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload[0]) return null;

    const concept: ProjectedConcept & { size: number; color: string } = payload[0].payload;

    return (
      <div className="bg-card dark:bg-gray-800 border border-border dark:border-gray-600 rounded-lg p-3 shadow-lg">
        <div className="font-semibold text-sm mb-2 text-card-foreground dark:text-gray-100">
          {concept.label}
        </div>
        <div className="space-y-1 text-xs text-muted-foreground dark:text-gray-400">
          <div>
            <span className="font-medium">Position:</span> {concept.position.toFixed(3)}
          </div>
          <div>
            <span className="font-medium">Grounding:</span> {concept.grounding.toFixed(3)}
          </div>
          <div>
            <span className="font-medium">Direction:</span>{' '}
            <span className={`font-medium`} style={{ color: concept.color }}>
              {concept.direction}
            </span>
          </div>
          <div>
            <span className="font-medium">Axis Distance:</span> {concept.axis_distance.toFixed(3)}
          </div>
        </div>
      </div>
    );
  };

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

  // Generate regression line points
  const regressionPoints = useMemo(() => {
    if (!regressionLine) return [];
    const { slope, intercept } = regressionLine;
    return [
      { x: -1, y: slope * -1 + intercept },
      { x: 1, y: slope * 1 + intercept },
    ];
  }, [regressionLine]);

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
    <div className="flex flex-col gap-4" onClick={closeContextMenu}>
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

      {/* Filter Controls */}
      <div className="flex items-center gap-3 px-4">
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

      {/* Scatter Plot */}
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart
          margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
        >
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

          {/* Tooltip */}
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />

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

          {/* Regression line */}
          {regressionLine && (
            <ReferenceLine
              segment={regressionPoints.map(p => ({ x: p.x, y: p.y }))}
              stroke="#6366F1"
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: `y = ${regressionLine.slope.toFixed(2)}x + ${regressionLine.intercept.toFixed(2)}`,
                position: 'insideTopRight',
                className: 'text-xs fill-indigo-500 font-mono',
              }}
            />
          )}

          {/* Data points (bubbles with direction indicators) */}
          <Scatter
            name="Concepts"
            data={chartData}
            onClick={(data) => onConceptClick?.(data)}
            onMouseEnter={(data) => setHoveredConcept(data)}
            onMouseLeave={() => setHoveredConcept(null)}
            cursor="pointer"
            shape={(props: any) => {
              const { cx, cy, fill, payload } = props;
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
              const indicatorLength = radius + 4 + (vectorMagnitude * 8); // Scales with strength

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

              return (
                <g>
                  {/* Direction indicator (flow telltale) - shows trend direction for each concept */}
                  <line
                    x1={lineStartX}
                    y1={lineStartY}
                    x2={lineEndX}
                    y2={lineEndY}
                    stroke={fill}
                    strokeWidth={isHovered ? 2 : 1.5}
                    strokeOpacity={isHovered ? 0.9 : 0.6}
                    strokeLinecap="round"
                    pointerEvents="none"
                  />

                  {/* Bubble */}
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
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleContextMenu(e as any, payload);
                    }}
                  />
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

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-muted-foreground dark:text-gray-400">
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
        <div className="flex items-center gap-2">
          <div className="w-8 h-0.5 bg-indigo-500" style={{ backgroundImage: 'linear-gradient(to right, #6366F1 50%, transparent 50%)', backgroundSize: '8px 2px' }} />
          <span>Regression line (correlation trend)</span>
        </div>
      </div>
    </div>
  );
};
