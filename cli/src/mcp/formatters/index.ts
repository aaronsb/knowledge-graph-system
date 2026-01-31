/**
 * MCP Server Markdown Formatters
 *
 * Formats API responses as markdown-style text for AI agents.
 * Optimized for token efficiency - minimal Unicode, plain structure.
 *
 * Split by domain for maintainability (refactored from monolithic formatters.ts)
 */

// Shared utilities
export { formatGroundingStrength, formatGroundingWithConfidence } from './utils.js';

// Concept and search formatters
export {
  formatSearchResults,
  formatConceptDetails,
  formatConnectionPaths,
  formatRelatedConcepts,
} from './concept.js';

// Job formatters
export { formatJobList, formatJobStatus } from './job.js';

// Ingest formatters
export {
  formatInspectFileResult,
  formatIngestFileResult,
  formatIngestDirectoryResult,
} from './ingest.js';

// System and database formatters
export {
  formatDatabaseStats,
  formatDatabaseInfo,
  formatDatabaseHealth,
  formatSystemStatus,
  formatApiHealth,
  formatMcpAllowedPaths,
} from './system.js';

// Epistemic status formatters (ADR-065)
export {
  formatEpistemicStatusList,
  formatEpistemicStatusDetails,
  formatEpistemicStatusMeasurement,
} from './epistemic.js';

// Source and polarity formatters
export { formatSourceSearchResults, formatPolarityAxisResults } from './source.js';

// Document formatters (ADR-084)
export {
  formatDocumentSearchResults,
  formatDocumentList,
  formatDocumentContent,
  formatDocumentConcepts,
  formatDocumentConceptsDetailed,
} from './document.js';

// Graph CRUD formatters (ADR-089)
export {
  formatGraphConceptResult,
  formatGraphEdgeResult,
  formatGraphConceptList,
  formatGraphEdgeList,
  formatGraphBatchResult,
  formatGraphQueueResult,
} from './graph.js';

// Ontology formatters (ADR-200)
export {
  formatOntologyList,
  formatOntologyInfo,
  formatOntologyScores,
  formatOntologyEdges,
  formatOntologyAffinity,
  formatProposalList,
  formatProposalDetail,
  formatBreathingCycleResult,
} from './ontology.js';
