/**
 * Shared D3 zoom behavior for SVG visualizations.
 *
 * Attaches pan (drag) and zoom (scroll-wheel) to an SVG element and applies
 * the resulting transform to a nested <g> element.  Uses D3's direct DOM
 * manipulation to avoid React re-renders on every zoom tick.
 *
 * Usage:
 *   const svgRef = useRef<SVGSVGElement>(null);
 *   const zoomRef = useRef<SVGGElement>(null);
 *   const { resetZoom } = useSvgPanZoom(svgRef, zoomRef);
 *
 *   <svg ref={svgRef}>
 *     <g ref={zoomRef}>
 *       ...content...
 *     </g>
 *   </svg>
 */

import { useEffect, useCallback, useRef, type RefObject } from 'react';
import * as d3 from 'd3';

interface PanZoomOptions {
  /** Minimum zoom scale (default: 0.25) */
  minZoom?: number;
  /** Maximum zoom scale (default: 4) */
  maxZoom?: number;
}

interface PanZoomResult {
  /** Reset zoom to identity transform */
  resetZoom: () => void;
}

export function useSvgPanZoom(
  svgRef: RefObject<SVGSVGElement | null>,
  zoomGroupRef: RefObject<SVGGElement | null>,
  options: PanZoomOptions = {},
): PanZoomResult {
  const { minZoom = 0.25, maxZoom = 4 } = options;
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    const group = zoomGroupRef.current;
    if (!svg || !group) return;

    const svgSelection = d3.select(svg);
    const groupSelection = d3.select(group);

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([minZoom, maxZoom])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        groupSelection.attr('transform', event.transform.toString());
      });

    svgSelection.call(zoom);
    zoomBehaviorRef.current = zoom;

    return () => {
      svgSelection.on('.zoom', null);
      zoomBehaviorRef.current = null;
    };
  }, [svgRef, zoomGroupRef, minZoom, maxZoom]);

  const resetZoom = useCallback(() => {
    const svg = svgRef.current;
    if (!svg || !zoomBehaviorRef.current) return;
    d3.select(svg)
      .transition()
      .duration(300)
      .call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
  }, [svgRef]);

  return { resetZoom };
}
