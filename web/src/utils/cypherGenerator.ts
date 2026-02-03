/**
 * Cypher Generator — serializer/deserializer for the unified query program.
 *
 * All three query modes (smart search, block editor, Cypher editor) compile
 * to the same intermediate representation: { op: '+' | '-', cypher: string }[].
 * This module converts between that IR and the human-readable text format.
 *
 * Text format:
 *   - Each statement is prefixed with + (add to graph) or - (subtract from graph)
 *   - Statements execute in order, applying set algebra to the graph
 *   - Comments (--) and blank lines are ignored during parsing
 *   - Unprefixed statements default to + (additive)
 *
 * Functions:
 *   - stepToCypher()            — single semantic action → Cypher statement
 *   - generateCypher(session)   — exploration session → text script (serializer)
 *   - parseCypherStatements(text) — text script → { op, cypher }[] (deserializer)
 *
 * @example
 * ```
 * -- Exploration: My Graph Query
 * -- Step 1: explore "Way"
 * + MATCH (c:Concept)-[r]-(n:Concept) WHERE c.label = 'Way' RETURN c, r, n;
 * -- Step 2: add-adjacent "Enterprise Operating Model"
 * + MATCH (c:Concept)-[r]-(n:Concept) WHERE c.label = 'Enterprise Operating Model' RETURN c, r, n;
 * -- Step 3: subtract "Noise"
 * - MATCH (c:Concept)-[r]-(n:Concept) WHERE c.label = 'Noise' RETURN c, r, n;
 * ```
 */

import type { ExplorationStep, ExplorationSession, ExplorationAction } from '../store/graphStore';

/**
 * Escape a string for safe use in Cypher WHERE clauses.
 * Handles single quotes which would break string literals.
 */
function escapeCypher(label: string): string {
  return label.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

/**
 * Generate a Cypher statement for a single exploration step.
 *
 * Maps each action type to its equivalent Cypher pattern:
 * - explore/follow/add-adjacent: MATCH neighborhood at given depth
 * - load-path: MATCH variable-length path between two concepts
 *
 * @param step - The exploration step to convert
 * @returns A Cypher MATCH...RETURN statement
 */
export function stepToCypher(step: {
  action: ExplorationAction;
  conceptLabel: string;
  depth: number;
  destinationConceptLabel?: string;
  maxHops?: number;
}): string {
  switch (step.action) {
    case 'explore':
    case 'follow':
    case 'add-adjacent': {
      if (step.depth <= 1) {
        return [
          `MATCH (c:Concept)-[r]-(n:Concept)`,
          `WHERE c.label = '${escapeCypher(step.conceptLabel)}'`,
          `RETURN c, r, n`,
        ].join('\n');
      }
      return [
        `MATCH (c:Concept)-[r*1..${step.depth}]-(n:Concept)`,
        `WHERE c.label = '${escapeCypher(step.conceptLabel)}'`,
        `RETURN c, r, n`,
      ].join('\n');
    }

    case 'load-path': {
      const hops = step.maxHops || 5;
      return [
        `MATCH path = (a:Concept)-[*..${hops}]-(b:Concept)`,
        `WHERE a.label = '${escapeCypher(step.conceptLabel)}'`,
        `  AND b.label = '${escapeCypher(step.destinationConceptLabel || '')}'`,
        `RETURN path`,
      ].join('\n');
    }

    default:
      return `-- Unknown action: ${step.action}`;
  }
}

/**
 * Generate a complete Cypher script from an exploration session.
 *
 * Each step becomes a +/- prefixed statement. The output is formatted
 * as a semicolon-delimited script with comments showing the exploration
 * narrative (action type, concept name, timestamp).
 *
 * @param session - The exploration session to convert
 * @returns A multi-statement Cypher script with +/- operator prefixes
 */
export function generateCypher(session: ExplorationSession): string {
  const { steps } = session;
  if (steps.length === 0) return '-- No exploration steps recorded';

  const lines: string[] = [];

  // Header
  lines.push(`-- Exploration: ${session.name || 'Untitled'}`);
  lines.push(`-- Generated: ${new Date().toISOString()}`);
  lines.push(`-- Steps: ${steps.length}`);
  lines.push('');

  // Each step as an operator-prefixed statement
  steps.forEach((step, idx) => {
    let actionLabel: string;
    if (step.action === 'cypher') {
      // Raw cypher steps — show truncated query as label
      const snippet = step.cypher.replace(/\n/g, ' ').substring(0, 60);
      actionLabel = `cypher "${snippet}${step.cypher.length > 60 ? '...' : ''}"`;
    } else if (step.action === 'load-path') {
      actionLabel = `${step.action} "${step.conceptLabel}" → "${step.destinationConceptLabel}"`;
    } else {
      actionLabel = `${step.action} "${step.conceptLabel}"`;
    }

    lines.push(`-- Step ${idx + 1}: ${actionLabel}`);
    lines.push(`${step.op} ${step.cypher};`);
    lines.push('');
  });

  return lines.join('\n').trimEnd();
}

/**
 * Parse a +/- prefixed Cypher script back into individual statements.
 *
 * This is the inverse of generateCypher — it takes the editor text and
 * extracts the operator and Cypher for each statement. Comments are ignored.
 *
 * @param script - The Cypher script text (from the editor)
 * @returns Array of { op, cypher } pairs
 */
export function parseCypherStatements(
  script: string
): Array<{ op: '+' | '-'; cypher: string }> {
  const results: Array<{ op: '+' | '-'; cypher: string }> = [];
  const lines = script.split('\n');

  let currentOp: '+' | '-' | null = null;
  let currentLines: string[] = [];

  const flush = () => {
    if (currentOp && currentLines.length > 0) {
      const cypher = currentLines.join('\n').replace(/;\s*$/, '').trim();
      if (cypher) {
        results.push({ op: currentOp, cypher });
      }
    }
    currentOp = null;
    currentLines = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();

    // Skip comments and blank lines between statements
    if (trimmed.startsWith('--') || trimmed === '') {
      // If we're accumulating a statement and hit a blank line, flush
      if (currentOp && currentLines.length > 0 && trimmed === '') {
        flush();
      }
      continue;
    }

    // Check for operator prefix at start of a new statement
    if (trimmed.startsWith('+ ') || trimmed.startsWith('- ')) {
      flush();
      currentOp = trimmed[0] as '+' | '-';
      currentLines.push(trimmed.slice(2));
    } else if (currentOp) {
      // Continuation of current statement
      currentLines.push(trimmed);
    } else {
      // No operator prefix — treat as additive by default
      currentOp = '+';
      currentLines.push(trimmed);
    }
  }

  flush();
  return results;
}
