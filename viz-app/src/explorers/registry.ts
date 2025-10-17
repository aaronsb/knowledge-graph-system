/**
 * Explorer Registry
 *
 * Centralized registry for all explorer types following ADR-034.
 * Each explorer implements the ExplorerPlugin interface.
 */

import type { VisualizationType, ExplorerPlugin } from '../types/explorer';

/**
 * Global registry of all available explorers
 */
export const EXPLORER_REGISTRY: Map<VisualizationType, ExplorerPlugin> = new Map();

/**
 * Register an explorer plugin
 */
export function registerExplorer(explorer: ExplorerPlugin): void {
  EXPLORER_REGISTRY.set(explorer.config.type, explorer);
}

/**
 * Get a specific explorer by type
 */
export function getExplorer(type: VisualizationType): ExplorerPlugin | undefined {
  return EXPLORER_REGISTRY.get(type);
}

/**
 * Get all registered explorers
 */
export function getAllExplorers(): ExplorerPlugin[] {
  return Array.from(EXPLORER_REGISTRY.values());
}

/**
 * Check if an explorer is registered
 */
export function hasExplorer(type: VisualizationType): boolean {
  return EXPLORER_REGISTRY.has(type);
}

/**
 * Get explorers filtered by data shape requirement
 */
export function getExplorersByDataShape(
  dataShape: 'graph' | 'tree' | 'flow' | 'matrix' | 'temporal'
): ExplorerPlugin[] {
  return getAllExplorers().filter(
    (explorer) => explorer.config.requiredDataShape === dataShape
  );
}
