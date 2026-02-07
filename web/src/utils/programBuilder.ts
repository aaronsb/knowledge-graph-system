/**
 * Program Builder Utilities
 *
 * Helpers to construct GraphProgram ASTs from web app actions.
 * Used when rerouting raw Cypher execution through the notarized
 * GraphProgram execution pipeline (ADR-500).
 */

import type { GraphProgram, Statement, Operator } from '../types/program';

/**
 * Wrap a single Cypher query as a GraphProgram Statement.
 */
export function cypherToStatement(
  cypher: string,
  op: '+' | '-',
  label?: string,
): Statement {
  return {
    op: op as Operator,
    operation: { type: 'cypher', query: cypher },
    ...(label ? { label } : {}),
  };
}

/**
 * Convert an array of +/- Cypher statements to a full GraphProgram.
 *
 * This is the bridge between the web app's existing exploration model
 * (ordered +/- statements) and the GraphProgram AST.
 */
export function statementsToProgram(
  stmts: Array<{ op: '+' | '-'; cypher: string; label?: string }>,
): GraphProgram {
  return {
    version: 1,
    metadata: { author: 'human' },
    statements: stmts.map((s) => cypherToStatement(s.cypher, s.op, s.label)),
  };
}
