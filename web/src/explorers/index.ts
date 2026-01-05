/**
 * Explorers - Public API
 *
 * Exports all registered explorers and registry functions.
 */

export * from './registry';
export { ForceGraph2DExplorer } from './ForceGraph2D';
export { ForceGraph3DExplorer } from './ForceGraph3D';
export { DocumentExplorerPlugin } from './DocumentExplorer';

// Import explorers to trigger auto-registration
import './ForceGraph2D';
import './ForceGraph3D';
import './DocumentExplorer';
