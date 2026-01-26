/**
 * Graph CRUD formatters (ADR-089 Phase 3a)
 */

/**
 * Format a created/updated concept for MCP output
 */
export function formatGraphConceptResult(result: any, action: string): string {
  let output = `# ${action === 'create' ? 'Created' : action === 'edit' ? 'Updated' : 'Deleted'} Concept\n\n`;

  if (action === 'delete') {
    output += `Concept deleted successfully.\n`;
    return output;
  }

  output += `**Label:** ${result.label}\n`;
  output += `**ID:** ${result.concept_id}\n`;
  output += `**Ontology:** ${result.ontology || 'N/A'}\n`;

  if (result.description) {
    output += `**Description:** ${result.description}\n`;
  }

  if (result.search_terms && result.search_terms.length > 0) {
    output += `**Search Terms:** ${result.search_terms.join(', ')}\n`;
  }

  output += `**Creation Method:** ${result.creation_method || 'mcp'}\n`;
  output += `**Has Embedding:** ${result.has_embedding ? 'Yes' : 'Pending'}\n`;

  if (result.matched_existing) {
    output += `\n⚠️ **Matched Existing Concept** - no new concept created\n`;
  }

  return output;
}

/**
 * Format a created/updated edge for MCP output
 */
export function formatGraphEdgeResult(result: any, action: string): string {
  let output = `# ${action === 'create' ? 'Created' : action === 'edit' ? 'Updated' : 'Deleted'} Edge\n\n`;

  if (action === 'delete') {
    output += `Edge deleted successfully.\n`;
    return output;
  }

  output += `**Relationship:** ${result.from_label || result.from_concept_id} → [${result.relationship_type}] → ${result.to_label || result.to_concept_id}\n\n`;
  output += `**From Concept:** ${result.from_concept_id}\n`;
  output += `**To Concept:** ${result.to_concept_id}\n`;
  output += `**Type:** ${result.relationship_type}\n`;
  output += `**Category:** ${result.category}\n`;
  output += `**Confidence:** ${(result.confidence * 100).toFixed(0)}%\n`;
  output += `**Source:** ${result.source}\n`;

  if (result.created_at) {
    output += `**Created:** ${result.created_at}\n`;
  }

  return output;
}

/**
 * Format concept list for MCP output
 */
export function formatGraphConceptList(result: any): string {
  let output = `# Concepts\n\n`;
  output += `Showing ${result.concepts.length} of ${result.total} concepts\n\n`;

  if (result.concepts.length === 0) {
    output += 'No concepts found matching the filters.\n';
    return output;
  }

  result.concepts.forEach((concept: any, i: number) => {
    output += `${i + 1}. **${concept.label}**\n`;
    output += `   - ID: ${concept.concept_id}\n`;
    if (concept.ontology) {
      output += `   - Ontology: ${concept.ontology}\n`;
    }
    if (concept.description) {
      const truncated = concept.description.length > 80
        ? concept.description.substring(0, 80) + '...'
        : concept.description;
      output += `   - Description: ${truncated}\n`;
    }
    output += `   - Method: ${concept.creation_method || 'unknown'}\n`;
    output += `   - Embedding: ${concept.has_embedding ? '✓' : '⏳'}\n`;
    output += '\n';
  });

  if (result.total > result.offset + result.concepts.length) {
    output += `Use offset=${result.offset + result.limit} to see more.\n`;
  }

  return output;
}

/**
 * Format edge list for MCP output
 */
export function formatGraphEdgeList(result: any): string {
  let output = `# Edges\n\n`;
  output += `Showing ${result.edges.length} of ${result.total} edges\n\n`;

  if (result.edges.length === 0) {
    output += 'No edges found matching the filters.\n';
    return output;
  }

  result.edges.forEach((edge: any, i: number) => {
    output += `${i + 1}. **${edge.relationship_type}**\n`;
    output += `   - From: ${edge.from_concept_id}\n`;
    output += `   - To: ${edge.to_concept_id}\n`;
    output += `   - Category: ${edge.category}\n`;
    output += `   - Confidence: ${(edge.confidence * 100).toFixed(0)}%\n`;
    output += `   - Source: ${edge.source}\n`;
    output += '\n';
  });

  if (result.total > result.offset + result.edges.length) {
    output += `Use offset=${result.offset + result.limit} to see more.\n`;
  }

  return output;
}

/**
 * Format batch create response for MCP output
 */
export function formatGraphBatchResult(result: any): string {
  let output = `# Batch Create Results\n\n`;

  output += `## Summary\n\n`;
  output += `- **Concepts Created:** ${result.concepts_created}\n`;
  output += `- **Concepts Matched:** ${result.concepts_matched}\n`;
  output += `- **Edges Created:** ${result.edges_created}\n`;

  if (result.errors && result.errors.length > 0) {
    output += `- **Errors:** ${result.errors.length}\n`;
  }

  if (result.concept_results && result.concept_results.length > 0) {
    output += `\n## Concept Results\n\n`;
    result.concept_results.forEach((item: any, i: number) => {
      const statusIcon = item.status === 'created' ? '✓' : item.status === 'matched' ? '⊘' : '✗';
      output += `${i + 1}. ${statusIcon} **${item.label}** - ${item.status}`;
      if (item.id) {
        output += ` (${item.id})`;
      }
      if (item.error) {
        output += ` - ${item.error}`;
      }
      output += '\n';
    });
  }

  if (result.edge_results && result.edge_results.length > 0) {
    output += `\n## Edge Results\n\n`;
    result.edge_results.forEach((item: any, i: number) => {
      const statusIcon = item.status === 'created' ? '✓' : item.status === 'error' ? '✗' : '⊘';
      output += `${i + 1}. ${statusIcon} **${item.label}** - ${item.status}`;
      if (item.id) {
        output += ` (${item.id})`;
      }
      if (item.error) {
        output += ` - ${item.error}`;
      }
      output += '\n';
    });
  }

  if (result.errors && result.errors.length > 0) {
    output += `\n## Errors\n\n`;
    result.errors.forEach((error: string, i: number) => {
      output += `${i + 1}. ${error}\n`;
    });
  }

  return output;
}

/**
 * Queue operation result type for formatter
 */
interface QueueOperationResult {
  index: number;
  status: 'ok' | 'error';
  op: string;
  entity: string;
  label?: string;
  id?: string;
  relationship?: string;
  count?: number;
  total?: number;
  matched_existing?: boolean;
  concepts?: Array<{ id: string; label: string }>;
  edges?: Array<{ from: string; type: string; to: string }>;
  error?: string;
}

/**
 * Queue execution result type for formatter
 */
interface QueueExecutionResult {
  results: QueueOperationResult[];
  stopIndex: number;
  successCount: number;
  errorCount: number;
}

/**
 * Format queue execution results for MCP output
 */
export function formatGraphQueueResult(
  queueResult: QueueExecutionResult,
  totalOperations: number
): string {
  const { results, stopIndex, successCount, errorCount } = queueResult;

  let output = `# Queue Results\n\n`;
  output += `**Executed:** ${results.length} of ${totalOperations} operations\n`;
  output += `**Success:** ${successCount} | **Errors:** ${errorCount}\n`;
  if (stopIndex >= 0) {
    output += `**Stopped at:** operation ${stopIndex + 1} (error)\n`;
  }
  output += '\n## Operations\n\n';

  results.forEach((r) => {
    const icon = r.status === 'ok' ? '✓' : '✗';
    output += `${r.index}. ${icon} **${r.op} ${r.entity}**`;
    if (r.status === 'ok') {
      if (r.label) output += ` - ${r.label}`;
      if (r.id) output += ` (${r.id})`;
      if (r.relationship) output += ` - ${r.relationship}`;
      if (r.count !== undefined) output += ` - ${r.count}/${r.total} results`;
      if (r.matched_existing) output += ' ⚠️ matched existing';
    } else {
      output += ` - ${r.error}`;
    }
    output += '\n';
  });

  // Include list results inline for convenience
  const listResults = results.filter((r) => r.status === 'ok' && r.op === 'list');
  if (listResults.length > 0) {
    output += '\n## List Results\n\n';
    listResults.forEach((r) => {
      output += `### Operation ${r.index}: ${r.entity} list\n\n`;
      if (r.entity === 'concept' && r.concepts) {
        r.concepts.slice(0, 10).forEach((c, i) => {
          output += `${i + 1}. ${c.label} (${c.id})\n`;
        });
        if (r.concepts.length > 10) {
          output += `... and ${r.concepts.length - 10} more\n`;
        }
      } else if (r.entity === 'edge' && r.edges) {
        r.edges.slice(0, 10).forEach((e, i) => {
          output += `${i + 1}. ${e.from} -[${e.type}]-> ${e.to}\n`;
        });
        if (r.edges.length > 10) {
          output += `... and ${r.edges.length - 10} more\n`;
        }
      }
      output += '\n';
    });
  }

  return output;
}
