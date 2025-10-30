/**
 * Panel Stack Component
 *
 * Manages vertical stacking of panels on the right side of explorers.
 * Automatically positions panels based on their actual rendered heights,
 * allowing panels to collapse/expand and other panels to shift accordingly.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';

interface PanelStackProps {
  children: React.ReactNode;
  side?: 'left' | 'right';
  gap?: number; // Gap between panels in pixels
  initialTop?: number; // Starting top position
}

export const PanelStack: React.FC<PanelStackProps> = ({
  children,
  side = 'right',
  gap = 16,
  initialTop = 16,
}) => {
  const panelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [panelPositions, setPanelPositions] = useState<number[]>([]);

  // Filter out null/undefined children (from conditional rendering)
  const validChildren = React.Children.toArray(children).filter(
    (child) => child != null && React.isValidElement(child)
  );

  // Calculate panel positions based on actual rendered heights
  const updatePanelPositions = useCallback(() => {
    const positions: number[] = [];
    let currentTop = initialTop;

    panelRefs.current.forEach((panel) => {
      if (!panel) return;

      positions.push(currentTop);

      // Get actual height including any collapsed state
      const height = panel.getBoundingClientRect().height;
      currentTop += height + gap;
    });

    setPanelPositions(positions);
  }, [initialTop, gap]);

  // Update positions on mount and when children change
  useEffect(() => {
    // Small delay to ensure panels are rendered
    const timer = setTimeout(updatePanelPositions, 0);
    return () => clearTimeout(timer);
  }, [validChildren.length, updatePanelPositions]);

  // Use ResizeObserver to detect panel height changes (e.g., collapse/expand)
  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      updatePanelPositions();
    });

    // Observe all panel children
    panelRefs.current.forEach((panel) => {
      if (panel) resizeObserver.observe(panel);
    });

    return () => {
      resizeObserver.disconnect();
    };
  }, [validChildren.length, updatePanelPositions]);

  return (
    <>
      {validChildren.map((child, index) => {
        if (!React.isValidElement(child)) return null;

        const position = panelPositions[index] ?? initialTop;
        const positionStyle = side === 'right' ? { right: '1rem' } : { left: '1rem' };

        // Wrap child in a positioned div (don't clone)
        return (
          <div
            key={child.key || index}
            ref={(el) => {
              panelRefs.current[index] = el;
            }}
            style={{
              position: 'absolute',
              ...positionStyle,
              top: `${position}px`,
              zIndex: 10 - index,
              transition: 'all 300ms ease-in-out',
            }}
          >
            {child}
          </div>
        );
      })}
    </>
  );
};
