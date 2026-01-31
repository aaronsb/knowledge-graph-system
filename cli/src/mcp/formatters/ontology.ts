/**
 * Ontology formatters (ADR-200)
 *
 * Formats ontology responses as markdown for AI agents.
 * - Core: Ontology list, info, scores
 * - Phase 3b/4: Proposal list, proposal details, proposal review
 * - Phase 5: Ontology edges, affinity
 */

// ========== Core Ontology Formatters ==========

/**
 * Format ontology list
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function formatOntologyList(data: any): string {
  let output = `# Ontologies\n\n`;
  output += `**Total:** ${data.count}\n\n`;

  if (data.count === 0) {
    output += `No ontologies found.\n`;
    return output;
  }

  output += `| Ontology | Concepts | Sources | Lifecycle | Epoch |\n`;
  output += `|----------|----------|---------|-----------|-------|\n`;

  for (const o of data.ontologies) {
    const lifecycle = o.lifecycle_state || 'active';
    const epoch = o.creation_epoch ?? '-';
    output += `| **${o.ontology}** | ${o.concept_count} | ${o.source_count} | ${lifecycle} | ${epoch} |\n`;
  }

  return output;
}

/**
 * Format ontology info (detail view)
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function formatOntologyInfo(data: any): string {
  let output = `# Ontology: ${data.ontology}\n\n`;

  if (!data.node) {
    output += `**Warning:** Ontology node not found in graph. Sources may exist with this document name but no Ontology node is registered.\n\n`;
  } else {
    output += `| Property | Value |\n|----------|-------|\n`;
    output += `| ID | \`${data.node.ontology_id}\` |\n`;
    if (data.node.description) {
      output += `| Description | ${data.node.description} |\n`;
    }
    output += `| Lifecycle | ${data.node.lifecycle_state} |\n`;
    output += `| Creation epoch | ${data.node.creation_epoch} |\n`;
    output += `| Has embedding | ${data.node.has_embedding} |\n`;
    if (data.node.created_by) {
      output += `| Created by | ${data.node.created_by} |\n`;
    }
    if (data.node.search_terms && data.node.search_terms.length > 0) {
      output += `| Search terms | ${data.node.search_terms.join(', ')} |\n`;
    }
    output += `\n`;
  }

  output += `## Statistics\n\n`;
  output += `| Metric | Count |\n|--------|-------|\n`;
  output += `| Concepts | ${data.statistics.concept_count} |\n`;
  output += `| Sources | ${data.statistics.source_count} |\n`;
  output += `| Files | ${data.statistics.file_count} |\n`;
  output += `| Instances | ${data.statistics.instance_count} |\n`;
  output += `| Relationships | ${data.statistics.relationship_count} |\n`;

  if (data.files.length > 0) {
    output += `\n## Files (${data.files.length})\n\n`;
    for (const f of data.files) {
      output += `- ${f}\n`;
    }
  }

  return output;
}

/**
 * Format ontology scores (single or all)
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function formatOntologyScores(data: any): string {
  // Single ontology score
  if (data.ontology && data.mass_score !== undefined) {
    const fmt = (v: number | null | undefined) => v != null ? v.toFixed(4) : '-';
    let output = `# Ontology Scores: ${data.ontology}\n\n`;
    output += `| Metric | Value |\n|--------|-------|\n`;
    output += `| Mass | ${fmt(data.mass_score)} |\n`;
    output += `| Coherence | ${fmt(data.coherence_score)} |\n`;
    output += `| Raw exposure | ${fmt(data.raw_exposure)} |\n`;
    output += `| Weighted exposure | ${fmt(data.weighted_exposure)} |\n`;
    output += `| **Protection** | **${fmt(data.protection_score)}** |\n`;
    output += `| Epoch | ${data.last_evaluated_epoch ?? '-'} |\n`;
    return output;
  }

  // All ontology scores
  let output = `# Ontology Scores\n\n`;
  output += `**Epoch:** ${data.global_epoch ?? '-'} | **Count:** ${data.count ?? 0}\n\n`;

  const scores = data.scores || [];
  if (scores.length === 0) {
    output += `No scores available.\n`;
    return output;
  }

  output += `| Ontology | Mass | Coherence | Exposure | Protection | Epoch |\n`;
  output += `|----------|------|-----------|----------|------------|-------|\n`;

  const fmt3 = (v: number | null | undefined) => v != null ? v.toFixed(3) : '-';
  for (const s of scores) {
    output += `| **${s.ontology}** | ${fmt3(s.mass_score)} | ${fmt3(s.coherence_score)} | ${fmt3(s.weighted_exposure)} | ${fmt3(s.protection_score)} | ${s.last_evaluated_epoch ?? '-'} |\n`;
  }

  return output;
}

// ========== Ontology Edge Formatters (ADR-200 Phase 5) ==========

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

// ========== Breathing Proposals (ADR-200 Phase 3b/4) ==========

interface BreathingProposal {
  id: number;
  proposal_type: string;
  ontology_name: string;
  anchor_concept_id?: string;
  target_ontology?: string;
  reasoning: string;
  mass_score?: number;
  coherence_score?: number;
  protection_score?: number;
  status: string;
  created_at: string;
  created_at_epoch: number;
  reviewed_at?: string;
  reviewed_by?: string;
  reviewer_notes?: string;
  executed_at?: string;
  execution_result?: Record<string, unknown>;
  suggested_name?: string;
  suggested_description?: string;
}

interface ProposalListResponse {
  proposals: BreathingProposal[];
  count: number;
}

function formatStatus(status: string): string {
  const icons: Record<string, string> = {
    pending: '[PENDING]',
    approved: '[APPROVED]',
    executing: '[EXECUTING]',
    executed: '[EXECUTED]',
    rejected: '[REJECTED]',
    failed: '[FAILED]',
    expired: '[EXPIRED]',
  };
  return icons[status] || `[${status.toUpperCase()}]`;
}

function formatScores(p: BreathingProposal): string {
  const parts: string[] = [];
  if (p.mass_score != null) parts.push(`mass: ${p.mass_score.toFixed(3)}`);
  if (p.coherence_score != null) parts.push(`coherence: ${p.coherence_score.toFixed(3)}`);
  if (p.protection_score != null) parts.push(`protection: ${p.protection_score.toFixed(3)}`);
  return parts.length > 0 ? parts.join(' | ') : '';
}

/**
 * Format a list of breathing proposals
 */
export function formatProposalList(data: ProposalListResponse): string {
  let output = `# Breathing Proposals\n\n`;

  if (data.count === 0) {
    output += `No proposals found.\n`;
    return output;
  }

  output += `**Total:** ${data.count}\n\n`;

  for (const p of data.proposals) {
    const typeIcon = p.proposal_type === 'promotion' ? 'PROMOTE' : 'DEMOTE';
    output += `### #${p.id} ${typeIcon}: ${p.ontology_name} ${formatStatus(p.status)}\n\n`;
    output += `${p.reasoning}\n\n`;

    if (p.proposal_type === 'promotion' && p.anchor_concept_id) {
      output += `- **Anchor concept:** ${p.anchor_concept_id}\n`;
      if (p.suggested_name) output += `- **Suggested name:** ${p.suggested_name}\n`;
    }
    if (p.proposal_type === 'demotion' && p.target_ontology) {
      output += `- **Absorption target:** ${p.target_ontology}\n`;
    }

    const scores = formatScores(p);
    if (scores) output += `- **Scores:** ${scores}\n`;
    output += `- **Epoch:** ${p.created_at_epoch} | **Created:** ${p.created_at}\n`;

    if (p.reviewed_at) {
      output += `- **Reviewed:** ${p.reviewed_at} by ${p.reviewed_by || 'unknown'}\n`;
    }
    if (p.execution_result) {
      const r = p.execution_result;
      if (r.ontology_created) output += `- **Created ontology:** ${r.ontology_created}\n`;
      if (r.absorbed_into) output += `- **Absorbed into:** ${r.absorbed_into}\n`;
      if (r.sources_reassigned !== undefined) output += `- **Sources reassigned:** ${r.sources_reassigned}\n`;
      if (r.error) output += `- **Error:** ${r.error}\n`;
    }

    output += `\n`;
  }

  return output;
}

/**
 * Format a single proposal (detail view or review result)
 */
export function formatProposalDetail(p: BreathingProposal): string {
  const typeIcon = p.proposal_type === 'promotion' ? 'PROMOTE' : 'DEMOTE';
  let output = `# Proposal #${p.id}: ${typeIcon} ${p.ontology_name}\n\n`;
  output += `**Status:** ${formatStatus(p.status)}\n\n`;
  output += `## Reasoning\n\n${p.reasoning}\n\n`;

  output += `## Details\n\n`;
  if (p.proposal_type === 'promotion') {
    if (p.anchor_concept_id) output += `- **Anchor concept:** ${p.anchor_concept_id}\n`;
    if (p.suggested_name) output += `- **Suggested name:** ${p.suggested_name}\n`;
    if (p.suggested_description) output += `- **Suggested description:** ${p.suggested_description}\n`;
  }
  if (p.proposal_type === 'demotion' && p.target_ontology) {
    output += `- **Absorption target:** ${p.target_ontology}\n`;
  }

  const scores = formatScores(p);
  if (scores) output += `- **Scores:** ${scores}\n`;
  output += `- **Epoch:** ${p.created_at_epoch}\n`;
  output += `- **Created:** ${p.created_at}\n`;

  if (p.reviewed_at) {
    output += `\n## Review\n\n`;
    output += `- **Reviewed:** ${p.reviewed_at} by ${p.reviewed_by || 'unknown'}\n`;
    if (p.reviewer_notes) output += `- **Notes:** ${p.reviewer_notes}\n`;
  }

  if (p.executed_at || p.execution_result) {
    output += `\n## Execution\n\n`;
    if (p.executed_at) output += `- **Executed:** ${p.executed_at}\n`;
    if (p.execution_result) {
      const r = p.execution_result;
      if (r.ontology_created) output += `- **Created ontology:** ${r.ontology_created}\n`;
      if (r.ontology_id) output += `- **Ontology ID:** ${r.ontology_id}\n`;
      if (r.absorbed_into) output += `- **Absorbed into:** ${r.absorbed_into}\n`;
      if (r.sources_reassigned !== undefined) output += `- **Sources reassigned:** ${r.sources_reassigned}\n`;
      if (r.sources_found !== undefined) output += `- **Sources found:** ${r.sources_found}\n`;
      if (r.parent_ontology) output += `- **Parent ontology:** ${r.parent_ontology}\n`;
      if (r.ontology_node_deleted !== undefined) output += `- **Node deleted:** ${r.ontology_node_deleted}\n`;
      if (r.error) output += `- **Error:** ${r.error}\n`;
    }
  }

  if (p.status === 'pending') {
    output += `\n---\n*Use proposal_review action with status "approved" or "rejected" to review.*\n`;
  }

  return output;
}

/**
 * Format a breathing cycle result
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function formatBreathingCycleResult(data: any): string {
  let output = `# Breathing Cycle Result\n\n`;

  if (data.dry_run) output += `**Mode:** Dry run (no proposals stored)\n\n`;

  output += `| Metric | Value |\n|--------|-------|\n`;
  output += `| Proposals generated | ${data.proposals_generated ?? 0} |\n`;
  output += `| Demotion candidates | ${data.demotion_candidates ?? 0} |\n`;
  output += `| Promotion candidates | ${data.promotion_candidates ?? 0} |\n`;
  output += `| Ontologies scored | ${data.scores_updated ?? 0} |\n`;
  output += `| Centroids updated | ${data.centroids_updated ?? 0} |\n`;
  output += `| Edges created | ${data.edges_created ?? 0} |\n`;
  output += `| Edges deleted | ${data.edges_deleted ?? 0} |\n`;
  output += `| Cycle epoch | ${data.cycle_epoch ?? 0} |\n`;

  if (data.candidates && typeof data.candidates === 'object') {
    const c = data.candidates as Record<string, unknown[]>;
    if (c.demotions && Array.isArray(c.demotions) && c.demotions.length > 0) {
      output += `\n## Demotion Candidates\n\n`;
      for (const d of c.demotions as Record<string, unknown>[]) {
        output += `- **${d.ontology}** (protection: ${d.protection})\n`;
      }
    }
    if (c.promotions && Array.isArray(c.promotions) && c.promotions.length > 0) {
      output += `\n## Promotion Candidates\n\n`;
      for (const p of c.promotions as Record<string, unknown>[]) {
        output += `- **${p.concept}** in ${p.ontology} (degree: ${p.degree})\n`;
      }
    }
  }

  return output;
}
