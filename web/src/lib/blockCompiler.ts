/**
 * Block Compiler - Converts visual blocks to executable openCypher queries
 *
 * Takes a flow of connected blocks and generates valid Apache AGE openCypher syntax.
 */

import type { Node, Edge } from 'reactflow';
import type {
  BlockData,
  StartBlockParams,
  EndBlockParams,
  SearchBlockParams,
  SelectConceptBlockParams,
  NeighborhoodBlockParams,
  PathToBlockParams,
  OntologyFilterBlockParams,
  EdgeFilterBlockParams,
  NodeFilterBlockParams,
  AndBlockParams,
  OrBlockParams,
  NotBlockParams,
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

  // Find explicit Start blocks
  const startBlocks = nodes.filter(node => node.data.type === 'start');

  if (startBlocks.length === 0) {
    errors.push('No Start block found - add a Start block to begin your query');
    return { cypher: '', errors, warnings };
  }

  if (startBlocks.length > 1) {
    errors.push('Multiple Start blocks found - only one Start block is allowed');
    return { cypher: '', errors, warnings };
  }

  // Find explicit End blocks
  const endBlocks = nodes.filter(node => node.data.type === 'end');
  if (endBlocks.length === 0) {
    warnings.push('No End block found - consider adding an End block to mark query completion');
  }

  // Build execution chain by following edges from Start block
  const executionChain: Node<BlockData>[] = [];
  let currentNode = startBlocks[0];

  while (currentNode) {
    // Add to execution chain (skip Start/End blocks - they're flow markers only)
    if (currentNode.data.type !== 'start' && currentNode.data.type !== 'end') {
      executionChain.push(currentNode);
    }

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
  let limitValue: number | null = null;

  // Track all variables to return (nodes and paths)
  const returnVariables: string[] = [];

  for (let i = 0; i < executionChain.length; i++) {
    const block = executionChain[i];
    const isFirst = i === 0;

    // Special handling for LIMIT block - it must come after RETURN
    if (block.data.type === 'limit') {
      const params = block.data.params as LimitBlockParams;
      limitValue = params.count;
      continue; // Skip adding to cypherParts during loop
    }

    try {
      const { cypher, outputVariable, pathVariable } = compileBlock(block, currentVariable, isFirst, variableCounter);
      cypherParts.push(cypher);

      // Track variables to return
      if (isFirst && outputVariable) {
        returnVariables.push(outputVariable);
      }
      if (pathVariable) {
        returnVariables.push(pathVariable);
      }

      currentVariable = outputVariable;
      variableCounter++;
    } catch (error: any) {
      errors.push(`Block "${block.data.label}": ${error.message}`);
      return { cypher: '', errors, warnings };
    }
  }

  // Add final RETURN statement with all tracked variables
  // This ensures we get both nodes and relationships (via paths)
  const uniqueVars = [...new Set(returnVariables)];
  if (uniqueVars.length === 0) {
    uniqueVars.push(currentVariable);
  }
  cypherParts.push(`RETURN DISTINCT ${uniqueVars.join(', ')}`);

  // Add LIMIT after RETURN if present
  if (limitValue !== null) {
    cypherParts.push(`LIMIT ${limitValue}`);
  }

  const finalCypher = cypherParts.join('\n');

  return {
    cypher: finalCypher,
    errors,
    warnings,
  };
}

/**
 * Compile a single block to openCypher
 * Returns the cypher clause, output variable name, and optional path variable
 */
function compileBlock(
  node: Node<BlockData>,
  inputVariable: string,
  isFirst: boolean,
  counter: number
): { cypher: string; outputVariable: string; pathVariable?: string } {
  const { type, params } = node.data;

  switch (type) {
    case 'start':
    case 'end':
      // Flow control blocks - no Cypher generation
      return { cypher: '', outputVariable: inputVariable };

    case 'search':
      return compileSearchBlock(params as SearchBlockParams, isFirst, counter);

    case 'selectConcept':
      return compileSelectConceptBlock(params as SelectConceptBlockParams, isFirst);

    case 'neighborhood':
      return compileNeighborhoodBlock(params as NeighborhoodBlockParams, inputVariable, isFirst, counter);

    case 'pathTo':
      return compilePathToBlock(params as PathToBlockParams, inputVariable, counter);

    case 'filterOntology':
      return compileOntologyFilterBlock(params as OntologyFilterBlockParams, inputVariable);

    case 'filterEdge':
      return compileEdgeFilterBlock(params as EdgeFilterBlockParams, inputVariable);

    case 'filterNode':
      return compileNodeFilterBlock(params as NodeFilterBlockParams, inputVariable);

    case 'and':
    case 'or':
    case 'not':
      // Boolean logic blocks - not yet fully implemented
      // For now, pass through the input variable
      return { cypher: `// ${type.toUpperCase()} gate (not yet implemented in compiler)`, outputVariable: inputVariable };

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
  // For now, we do a case-insensitive CONTAINS match
  const outputVar = `c${counter}`;
  const limit = params.limit || 1;

  // Use WITH clause to limit results before subsequent operations
  const cypher = `MATCH (${outputVar}:Concept)\nWHERE toLower(${outputVar}.label) CONTAINS toLower('${escapeString(params.query)}')\nWITH ${outputVar} LIMIT ${limit}`;

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
  const pathVar = `p${counter}`;

  // ADR-065: Build relationship type filter
  // Priority: explicit relationshipTypes > epistemic filtering > all types
  let relTypes: string[] = [];

  if (params.relationshipTypes && params.relationshipTypes.length > 0) {
    // Explicit relationship types specified
    relTypes = params.relationshipTypes;
  } else if (params.includeEpistemicStatus || params.excludeEpistemicStatus) {
    // Need to resolve epistemic filters to relationship types
    // Note: This would require a VocabType query in the Cypher, which is complex
    // For now, we'll add a comment that this needs backend filtering
    // In practice, epistemic filtering should use the REST API, not raw Cypher
    throw new Error('Epistemic status filtering requires using the REST API (/query/related endpoint), not raw Cypher queries');
  }

  const relFilter = relTypes.length > 0
    ? `:${relTypes.join('|')}`
    : '';

  // Use path pattern to capture both nodes and relationships
  let pattern: string;
  if (params.direction === 'outgoing') {
    pattern = `${pathVar} = (${inputVariable})-[${relFilter}*1..${params.depth}]->(${outputVar}:Concept)`;
  } else if (params.direction === 'incoming') {
    pattern = `${pathVar} = (${inputVariable})<-[${relFilter}*1..${params.depth}]-(${outputVar}:Concept)`;
  } else {
    pattern = `${pathVar} = (${inputVariable})-[${relFilter}*1..${params.depth}]-(${outputVar}:Concept)`;
  }

  const cypher = `MATCH ${pattern}`;

  // Return both the neighbor node (for chaining) and path (for relationships)
  return { cypher, outputVariable: outputVar, pathVariable: pathVar };
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

function compileOntologyFilterBlock(params: OntologyFilterBlockParams, inputVariable: string): { cypher: string; outputVariable: string } {
  if (!params.ontologies || params.ontologies.length === 0) {
    throw new Error('Ontology filter block has no ontologies specified');
  }

  const conditions = params.ontologies.map(ont => {
    // Check if it looks like a regex pattern
    if (/[.*+?^${}()|[\]\\]/.test(ont)) {
      return `${inputVariable}.ontology =~ '${escapeString(ont)}'`;
    } else {
      return `${inputVariable}.ontology = '${escapeString(ont)}'`;
    }
  });

  const cypher = `WHERE ${conditions.join(' OR ')}`;
  return { cypher, outputVariable: inputVariable };
}

function compileEdgeFilterBlock(params: EdgeFilterBlockParams, inputVariable: string): { cypher: string; outputVariable: string } {
  if (!params.relationshipTypes || params.relationshipTypes.length === 0) {
    throw new Error('Edge filter block has no relationship types specified');
  }

  // Note: Edge filtering is complex in openCypher because we need to reference
  // relationships from a previous MATCH. This works best when used with neighborhood blocks.
  // For now, we'll generate a comment indicating this limitation.
  const cypher = `// Edge filter (relationship types: ${params.relationshipTypes.join(', ')}) - best used with Neighborhood block`;

  return { cypher, outputVariable: inputVariable };
}

function compileNodeFilterBlock(params: NodeFilterBlockParams, inputVariable: string): { cypher: string; outputVariable: string } {
  const conditions: string[] = [];

  if (params.nodeLabels && params.nodeLabels.length > 0) {
    const labelConditions = params.nodeLabels.map(label => {
      // Check if it looks like a regex pattern
      if (/[.*+?^${}()|[\]\\]/.test(label)) {
        return `${inputVariable}.label =~ '${escapeString(label)}'`;
      } else {
        return `${inputVariable}.label = '${escapeString(label)}'`;
      }
    });
    conditions.push(`(${labelConditions.join(' OR ')})`);
  }

  if (params.minConfidence !== undefined && params.minConfidence > 0) {
    conditions.push(`${inputVariable}.confidence >= ${params.minConfidence}`);
  }

  if (conditions.length === 0) {
    throw new Error('Node filter block has no conditions specified');
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
