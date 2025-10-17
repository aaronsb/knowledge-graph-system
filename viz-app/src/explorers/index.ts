/**
 * Explorers - Public API
 *
 * Exports all registered explorers and registry functions.
 */

export * from './registry';
export { ForceGraph2DExplorer } from './ForceGraph2D';

// Import explorers to trigger auto-registration
import './ForceGraph2D';
