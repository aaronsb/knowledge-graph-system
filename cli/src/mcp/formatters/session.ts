/**
 * Session context and ingest formatters
 */

export interface SessionConcept {
  label: string;
  concept_id: string;
  ontology: string | null;
  created_at_epoch: number;
}

/**
 * Format session context results as markdown
 */
export function formatSessionContext(concepts: SessionConcept[], summary: string): string {
  if (concepts.length === 0) {
    return summary + '\n';
  }

  let output = `# Session Context\n\n`;
  output += `${summary}\n\n`;

  // Group by epoch for readability
  let currentEpoch: number | null = null;
  for (const c of concepts) {
    if (c.created_at_epoch !== currentEpoch) {
      currentEpoch = c.created_at_epoch;
      output += `\n**Epoch ${currentEpoch}**\n`;
    }
    const ont = c.ontology ? ` [${c.ontology}]` : '';
    output += `- ${c.label} (${c.concept_id})${ont}\n`;
  }

  return output;
}

/**
 * Format session ingest result as markdown.
 * Deliberately minimal — the agent should fire and forget.
 */
export function formatSessionIngest(result: any): string {
  if (result.job_id) {
    return 'Session summary saved to knowledge graph.';
  }
  return `Session ingest failed: ${result.detail || result.message || 'unknown error'}`;
}
