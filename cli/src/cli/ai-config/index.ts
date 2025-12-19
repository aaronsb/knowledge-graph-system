/**
 * AI Configuration Commands (ADR-039, ADR-041)
 *
 * Manages AI provider configuration:
 * - Embedding models (local/API-based)
 * - Extraction models (GPT-4, Claude)
 * - API keys with validation
 *
 * Command structure:
 *   kg admin embedding config   - Show embedding configuration
 *   kg admin embedding set      - Update embedding configuration
 *   kg admin extraction config  - Show extraction configuration
 *   kg admin extraction set     - Update extraction configuration
 *   kg admin keys list          - List API keys with status
 *   kg admin keys set           - Set API key for provider
 *   kg admin keys delete        - Delete API key
 */

export { createEmbeddingCommand } from './embedding';
export { createExtractionCommand } from './extraction';
export { createKeysCommand } from './keys';
