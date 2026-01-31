/**
 * Ontology formatters (ADR-200 Phase 5)
 *
 * Formats ontology responses as markdown for AI agents.
 */

interface OntologyEdge {
  from_ontology: string;
  to_ontology: string;
  edge_type: string;
  score: number;
  shared_concept_count: number;
  computed_at_epoch: number;
  source: string;
  direction: string;
}

interface OntologyEdgesResponse {
  ontology: string;
  count: number;
  edges: OntologyEdge[];
}

/**
 * Format ontology-to-ontology edges
 */
export function formatOntologyEdges(data: OntologyEdgesResponse): string {
  let output = `# Ontology Edges: ${data.ontology}\n\n`;

  if (data.count === 0) {
    output += `No edges found. Edges are derived during breathing cycles when ontologies share concepts.\n`;
    return output;
  }

  output += `**Total:** ${data.count} edges\n\n`;

  // Group by edge type
  const byType: Record<string, OntologyEdge[]> = {};
  for (const edge of data.edges) {
    const type = edge.edge_type;
    if (!byType[type]) byType[type] = [];
    byType[type].push(edge);
  }

  for (const [type, edges] of Object.entries(byType)) {
    output += `## ${type} (${edges.length})\n\n`;

    for (const edge of edges) {
      const arrow = edge.direction === 'outgoing' ? '->' : '<-';
      const other = edge.direction === 'outgoing' ? edge.to_ontology : edge.from_ontology;
      const scorePercent = (edge.score * 100).toFixed(1);

      output += `- ${data.ontology} ${arrow} **${other}**`;
      output += ` | score: ${scorePercent}%`;
      output += ` | shared: ${edge.shared_concept_count}`;
      output += ` | source: ${edge.source}`;
      if (edge.computed_at_epoch > 0) {
        output += ` | epoch: ${edge.computed_at_epoch}`;
      }
      output += `\n`;
    }
    output += `\n`;
  }

  return output;
}

interface OntologyAffinity {
  other_ontology: string;
  shared_concept_count: number;
  total_concepts: number;
  affinity_score: number;
}

interface OntologyAffinityResponse {
  ontology: string;
  count: number;
  affinities: OntologyAffinity[];
}

/**
 * Format ontology affinity (cross-ontology concept overlap)
 */
export function formatOntologyAffinity(data: OntologyAffinityResponse): string {
  let output = `# Ontology Affinity: ${data.ontology}\n\n`;

  if (data.count === 0) {
    output += `No shared concepts with other ontologies.\n`;
    return output;
  }

  output += `**Compared against:** ${data.count} ontologies\n\n`;

  for (const aff of data.affinities) {
    const scorePercent = (aff.affinity_score * 100).toFixed(1);
    output += `- **${aff.other_ontology}** | ${scorePercent}% affinity | ${aff.shared_concept_count} shared of ${aff.total_concepts} total\n`;
  }

  return output;
}
