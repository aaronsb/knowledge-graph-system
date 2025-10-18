/**
 * Block Compiler - Converts visual blocks to executable openCypher queries
 *
 * Takes a flow of connected blocks and generates valid Apache AGE openCypher syntax.
 */

import type { Node, Edge } from 'reactflow';
import type {
  BlockData,
  SearchBlockParams,
  SelectConceptBlockParams,
  NeighborhoodBlockParams,
  PathToBlockParams,
  FilterBlockParams,
  LimitBlockParams,
  CompiledQuery,
} from '../types/blocks';

/**
 * Compile a flow of blocks into an executable openCypher query
 */
export function compileBlocksToOpenCypher(nodes: Node<BlockData>[], edges: Edge[]): CompiledQuery {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Validate we have blocks
  if (nodes.length === 0) {
    errors.push('No blocks in query');
    return { cypher: '', errors, warnings };
  }

  // Find the starting block (no incoming edges)
  const startingNodes = nodes.filter(node => {
    return !edges.some(edge => edge.target === node.id);
  });

  if (startingNodes.length === 0) {
    errors.push('No starting block found (every block has an input)');
    return { cypher: '', errors, warnings };
  }

  if (startingNodes.length > 1) {
    errors.push('Multiple starting blocks found - only one starting block is allowed');
    return { cypher: '', errors, warnings };
  }

  // Build execution chain by following edges
  const executionChain: Node<BlockData>[] = [];
  let currentNode = startingNodes[0];

  while (currentNode) {
    executionChain.push(currentNode);

    // Find next node
    const outgoingEdge = edges.find(edge => edge.source === currentNode.id);
    if (outgoingEdge) {
      const nextNode = nodes.find(node => node.id === outgoingEdge.target);
      if (!nextNode) {
        errors.push(`Broken connection: node ${outgoingEdge.target} not found`);
        break;
      }
      currentNode = nextNode;
    } else {
      break; // End of chain
    }
  }

  // Check for cycles
  if (executionChain.length !== new Set(executionChain.map(n => n.id)).size) {
    errors.push('Cycle detected in block flow');
    return { cypher: '', errors, warnings };
  }

  // Compile each block to openCypher
  const cypherParts: string[] = [];
  let variableCounter = 0;
  let currentVariable = 'start';

  for (let i = 0; i < executionChain.length; i++) {
    const block = executionChain[i];
    const isFirst = i === 0;

    try {
      const { cypher, outputVariable } = compileBlock(block, currentVariable, isFirst, variableCounter);
      cypherParts.push(cypher);
      currentVariable = outputVariable;
      variableCounter++;
    } catch (error: any) {
      errors.push(`Block "${block.data.label}": ${error.message}`);
      return { cypher: '', errors, warnings };
    }
  }

  // Add final RETURN statement
  cypherParts.push(`RETURN DISTINCT ${currentVariable}`);

  const finalCypher = cypherParts.join('\n');

  return {
    cypher: finalCypher,
    errors,
    warnings,
  };
}

/**
 * Compile a single block to openCypher
 * Returns the cypher clause and the output variable name
 */
function compileBlock(
  node: Node<BlockData>,
  inputVariable: string,
  isFirst: boolean,
  counter: number
): { cypher: string; outputVariable: string } {
  const { type, params } = node.data;

  switch (type) {
    case 'search':
      return compileSearchBlock(params as SearchBlockParams, isFirst, counter);

    case 'selectConcept':
      return compileSelectConceptBlock(params as SelectConceptBlockParams, isFirst);

    case 'neighborhood':
      return compileNeighborhoodBlock(params as NeighborhoodBlockParams, inputVariable, isFirst, counter);

    case 'pathTo':
      return compilePathToBlock(params as PathToBlockParams, inputVariable, counter);

    case 'filter':
      return compileFilterBlock(params as FilterBlockParams, inputVariable);

    case 'limit':
      return compileLimitBlock(params as LimitBlockParams);

    default:
      throw new Error(`Unknown block type: ${type}`);
  }
}

// ============================================================================
// Block Compilers
// ============================================================================

function compileSearchBlock(params: SearchBlockParams, _isFirst: boolean, counter: number): { cypher: string; outputVariable: string } {
  if (!params.query || params.query.trim() === '') {
    throw new Error('Search query is empty');
  }

  // Note: This generates a pattern match, but doesn't actually do semantic search
  // The semantic search would need to happen via the search endpoint first,
  // then we'd use the returned concept IDs here
  // For now, we do a simple CONTAINS match
  const outputVar = `c${counter}`;
  const cypher = `MATCH (${outputVar}:Concept)\nWHERE ${outputVar}.label CONTAINS '${escapeString(params.query)}'`;

  return { cypher, outputVariable: outputVar };
}

function compileSelectConceptBlock(params: SelectConceptBlockParams, _isFirst: boolean): { cypher: string; outputVariable: string } {
  if (!params.conceptId) {
    throw new Error('No concept selected');
  }

  const outputVar = 'start';
  const cypher = `MATCH (${outputVar}:Concept {concept_id: '${escapeString(params.conceptId)}'})`;

  return { cypher, outputVariable: outputVar };
}

function compileNeighborhoodBlock(
  params: NeighborhoodBlockParams,
  inputVariable: string,
  _isFirst: boolean,
  counter: number
): { cypher: string; outputVariable: string } {
  if (_isFirst) {
    throw new Error('Neighborhood block cannot be the first block');
  }

  const outputVar = `neighbor${counter}`;
  const relFilter = params.relationshipTypes && params.relationshipTypes.length > 0
    ? `:${params.relationshipTypes.join('|')}`
    : '';

  let pattern: string;
  if (params.direction === 'outgoing') {
    pattern = `(${inputVariable})-[${relFilter}*1..${params.depth}]->(${outputVar}:Concept)`;
  } else if (params.direction === 'incoming') {
    pattern = `(${inputVariable})<-[${relFilter}*1..${params.depth}]-(${outputVar}:Concept)`;
  } else {
    pattern = `(${inputVariable})-[${relFilter}*1..${params.depth}]-(${outputVar}:Concept)`;
  }

  const cypher = `MATCH ${pattern}`;

  return { cypher, outputVariable: outputVar };
}

function compilePathToBlock(
  params: PathToBlockParams,
  inputVariable: string,
  counter: number
): { cypher: string; outputVariable: string } {
  const targetVar = `target${counter}`;
  const pathVar = `path${counter}`;

  let targetMatch: string;

  if (params.targetType === 'concept') {
    if (!params.targetConceptId) {
      throw new Error('No target concept selected');
    }
    targetMatch = `MATCH (${targetVar}:Concept {concept_id: '${escapeString(params.targetConceptId)}'})`;
  } else {
    if (!params.targetQuery || params.targetQuery.trim() === '') {
      throw new Error('Target search query is empty');
    }
    targetMatch = `MATCH (${targetVar}:Concept)\nWHERE ${targetVar}.label CONTAINS '${escapeString(params.targetQuery)}'`;
  }

  const pathMatch = `MATCH ${pathVar} = shortestPath((${inputVariable})-[*1..${params.maxHops}]-(${targetVar}))`;

  const cypher = `${targetMatch}\n${pathMatch}`;

  return { cypher, outputVariable: pathVar };
}

function compileFilterBlock(params: FilterBlockParams, inputVariable: string): { cypher: string; outputVariable: string } {
  const conditions: string[] = [];

  if (params.ontologies && params.ontologies.length > 0) {
    const ontologyList = params.ontologies.map(o => `'${escapeString(o)}'`).join(', ');
    conditions.push(`${inputVariable}.ontology IN [${ontologyList}]`);
  }

  // Note: Relationship type filtering is better done in neighborhood blocks
  // but we can add it here too if needed

  if (params.minConfidence !== undefined && params.minConfidence > 0) {
    conditions.push(`${inputVariable}.confidence >= ${params.minConfidence}`);
  }

  if (conditions.length === 0) {
    throw new Error('Filter block has no conditions');
  }

  const cypher = `WHERE ${conditions.join(' AND ')}`;

  return { cypher, outputVariable: inputVariable };
}

function compileLimitBlock(params: LimitBlockParams): { cypher: string; outputVariable: string } {
  if (!params.count || params.count < 1) {
    throw new Error('Limit count must be at least 1');
  }

  // LIMIT doesn't change the variable, it just limits results
  // We'll use a placeholder variable that gets replaced by RETURN
  const cypher = `LIMIT ${params.count}`;

  return { cypher, outputVariable: '' }; // Empty because LIMIT doesn't produce a variable
}

// ============================================================================
// Utilities
// ============================================================================

function escapeString(str: string): string {
  return str.replace(/'/g, "\\'");
}
