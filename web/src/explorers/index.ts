/**
 * Explorers - Public API
 *
 * Exports all registered explorers and registry functions.
 */

export * from './registry';
export { ForceGraphExplorer } from './ForceGraph3D';
export { DocumentExplorerPlugin } from './DocumentExplorer';

// Import explorers to trigger auto-registration
import './ForceGraph3D';
import './DocumentExplorer';
