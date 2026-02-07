/**
 * GraphProgram AST Types (ADR-500)
 *
 * TypeScript mirror of Python models in api/app/models/program.py.
 * These types define the canonical JSON AST for graph query programs.
 *
 * @verified 0000000
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Set-algebra operator for a statement. */
export type Operator = '+' | '-' | '&' | '?' | '!';

/** Allowed API endpoints for ApiOp statements. */
export const API_ENDPOINT_ALLOWLIST = [
  '/search/concepts',
  '/search/sources',
  '/vocabulary/status',
  '/concepts/batch',
  '/concepts/details',
  '/concepts/related',
] as const;

export type AllowedEndpoint = typeof API_ENDPOINT_ALLOWLIST[number];

// ---------------------------------------------------------------------------
// Conditions (for ConditionalOp)
// ---------------------------------------------------------------------------

export interface HasResultsCondition {
  test: 'has_results';
}

export interface EmptyCondition {
  test: 'empty';
}

export interface CountGteCondition {
  test: 'count_gte';
  value: number;
}

export interface CountLteCondition {
  test: 'count_lte';
  value: number;
}

export interface HasOntologyCondition {
  test: 'has_ontology';
  ontology: string;
}

export interface HasRelationshipCondition {
  test: 'has_relationship';
  type: string;
}

export type Condition =
  | HasResultsCondition
  | EmptyCondition
  | CountGteCondition
  | CountLteCondition
  | HasOntologyCondition
  | HasRelationshipCondition;

// ---------------------------------------------------------------------------
// Operations
// ---------------------------------------------------------------------------

/** Execute a read-only openCypher query against the source graph H. */
export interface CypherOp {
  type: 'cypher';
  query: string;
  limit?: number;
}

/** Call a REST API endpoint (smart block). */
export interface ApiOp {
  type: 'api';
  endpoint: string;
  params?: Record<string, unknown>;
}

/** Conditional branching based on working graph W state. */
export interface ConditionalOp {
  type: 'conditional';
  condition: Condition;
  then: Statement[];
  else?: Statement[];
}

export type Operation = CypherOp | ApiOp | ConditionalOp;

// ---------------------------------------------------------------------------
// Block annotations (decompilation support)
// ---------------------------------------------------------------------------

/** Source block type and params for round-trip decompilation. */
export interface BlockAnnotation {
  blockType: string;
  params?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Statement
// ---------------------------------------------------------------------------

/** A single step in a GraphProgram. */
export interface Statement {
  op: Operator;
  operation: Operation;
  label?: string;
  block?: BlockAnnotation;
}

// ---------------------------------------------------------------------------
// Metadata and parameters
// ---------------------------------------------------------------------------

/** Program-level metadata. */
export interface ProgramMetadata {
  name?: string;
  description?: string;
  author?: 'human' | 'agent' | 'system';
  created?: string;
}

/** A program parameter declaration. */
export interface ParamDeclaration {
  name: string;
  type: 'string' | 'number';
  default?: string | number;
}

// ---------------------------------------------------------------------------
// GraphProgram (top-level AST)
// ---------------------------------------------------------------------------

/**
 * The canonical AST for a graph query program (ADR-500).
 *
 * A finite, bounded sequence of set-algebraic operations over openCypher
 * queries and REST API calls.
 */
export interface GraphProgram {
  version: 1;
  metadata?: ProgramMetadata;
  params?: ParamDeclaration[];
  statements: Statement[];
}

// ---------------------------------------------------------------------------
// Validation types (from program_validator.py)
// ---------------------------------------------------------------------------

/** A single validation error or warning. */
export interface ValidationIssue {
  rule_id: string;
  severity: 'error' | 'warning';
  statement?: number | null;
  field?: string | null;
  message: string;
}

/** Result of validating a GraphProgram. */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

// ---------------------------------------------------------------------------
// API request/response types (ADR-500 Phase 2b)
// ---------------------------------------------------------------------------

/** Request body for POST /programs and POST /programs/validate. */
export interface ProgramSubmission {
  name?: string;
  program: Record<string, unknown>;
}

/** Response from POST /programs (notarize + store). */
export interface ProgramCreateResponse {
  id: number;
  name: string;
  program: GraphProgram;
  valid: boolean;
  created_at: string;
  updated_at: string;
}

/** Response from GET /programs/{id}. */
export interface ProgramReadResponse {
  id: number;
  name: string;
  program: GraphProgram;
  owner_id: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Execution types (ADR-500 Phase 3)
// ---------------------------------------------------------------------------

/** A node in the WorkingGraph, identity-keyed by concept_id. */
export interface ProgramRawNode {
  concept_id: string;
  label: string;
  ontology?: string | null;
  description?: string | null;
  properties: Record<string, unknown>;
}

/** A link in the WorkingGraph, identity-keyed by (from_id, relationship_type, to_id). */
export interface ProgramRawLink {
  from_id: string;
  to_id: string;
  relationship_type: string;
  category?: string | null;
  confidence?: number | null;
  properties: Record<string, unknown>;
}

/** The mutable in-memory graph built during program execution. */
export interface WorkingGraph {
  nodes: ProgramRawNode[];
  links: ProgramRawLink[];
}

/** Per-statement execution log record. */
export interface StepLogEntry {
  statement: number;
  op: string;
  operation_type: 'cypher' | 'api' | 'conditional';
  branch_taken?: 'then' | 'else' | null;
  nodes_affected: number;
  links_affected: number;
  w_size: { nodes: number; links: number };
  duration_ms: number;
}

/** Complete execution result from POST /programs/execute. */
export interface ProgramResult {
  result: WorkingGraph;
  log: StepLogEntry[];
  aborted?: { statement: number; reason: string } | null;
}

/** A single entry in a program chain (deck). */
export interface DeckEntry {
  program_id?: number;
  program?: Record<string, unknown>;
  params?: Record<string, string | number>;
}

/** Result from chained program execution (deck mode). */
export interface BatchProgramResult {
  result: WorkingGraph;
  programs: ProgramResult[];
  aborted?: { statement: number; reason: string } | null;
}

/** Lightweight program summary for list endpoints. */
export interface ProgramListItem {
  id: number;
  name: string;
  description?: string | null;
  statement_count: number;
  created_at: string;
}
