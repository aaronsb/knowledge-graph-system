/**
 * Explorers - Public API
 *
 * Exports all registered explorers and registry functions.
 */

export * from './registry';
export { ForceGraphExplorer } from './ForceGraph';
export { DocumentExplorerPlugin } from './DocumentExplorer';

// Import explorers to trigger auto-registration
import './ForceGraph';
import './DocumentExplorer';
