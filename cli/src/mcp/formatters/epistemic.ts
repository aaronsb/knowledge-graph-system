/**
 * Epistemic status formatters (ADR-065)
 */

/**
 * Format epistemic status interpretation hint
 */
function formatEpistemicStatusInterpretation(status: string): string {
  const interpretations: { [key: string]: string } = {
    'WELL_GROUNDED': 'Well-established knowledge with strong evidence support (avg grounding >0.8). Highly reliable for reasoning.',
    'MIXED_GROUNDING': 'Variable validation - grounding ranges 0.15-0.8 (15-80% net support). Represents mixed evidence or evolving understanding.',
    'WEAK_GROUNDING': 'Weak positive grounding 0.0-0.15 (0-15% net support). Developing evidence, emerging knowledge. Use for exploratory reasoning.',
    'POORLY_GROUNDED': 'Weak negative grounding -0.5-0.0 (0-50% net contradiction). Uncertain, liminal knowledge. Unclear epistemic status.',
    'CONTRADICTED': 'Strong negative grounding <-0.5 (>50% net contradiction). Refuted claims, contradicted by evidence.',
    'HISTORICAL': 'Temporal vocabulary with past-tense markers. Important for understanding evolution of concepts over time.',
    'INSUFFICIENT_DATA': 'Less than 3 measurements available. Need more graph data to establish epistemic status.',
  };
  return interpretations[status] || 'Unknown epistemic status classification.';
}

/**
 * Format epistemic status list (ADR-065)
 */
export function formatEpistemicStatusList(result: any): string {
  let output = '# Epistemic Status Classification\n\n';
  output += `Total vocabulary types: ${result.total}\n\n`;

  if (!result.types || result.types.length === 0) {
    output += '**No epistemic status data available.**\n\n';
    output += 'Run measurement first using the "measure" action to calculate epistemic status for all vocabulary types.\n\n';
    output += '**What This Means:** Epistemic status reflects how well-established each relationship type is based on evidence grounding. ';
    output += 'Without measurement, you cannot filter relationships by reliability or identify contested knowledge areas.\n';
    return output;
  }

  // Add staleness header (ADR-065 Phase 2 counter-based tracking)
  if (result.last_measurement_at) {
    const measurementDate = new Date(result.last_measurement_at).toLocaleString();
    output += `**Last Measurement:** ${measurementDate}\n`;

    const delta = result.vocabulary_changes_since_measurement ?? 0;
    let stalenessText = '';

    if (delta === 0) {
      stalenessText = 'No changes since measurement (fresh)';
    } else if (delta < 5) {
      stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
    } else if (delta < 10) {
      stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
    } else {
      stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
    }

    output += `**Staleness:** ${stalenessText}\n\n`;
  }

  // Summary by classification
  const classificationCounts: { [key: string]: number } = {};
  result.types.forEach((type: any) => {
    const status = type.epistemic_status || 'UNKNOWN';
    classificationCounts[status] = (classificationCounts[status] || 0) + 1;
  });

  output += '## Classification Summary\n\n';
  Object.entries(classificationCounts)
    .sort((a, b) => b[1] - a[1])  // Sort by count descending
    .forEach(([status, count]) => {
      output += `- **${status}**: ${count} types\n`;
    });
  output += '\n';

  // Detailed table (removed "Measured At" column - all types measured together)
  output += '## Vocabulary Types\n\n';
  output += '| Relationship Type | Status | Avg Grounding | Sampled Edges |\n';
  output += '|-------------------|--------|---------------|---------------|\n';

  result.types.forEach((type: any) => {
    const avgGrounding = type.stats?.avg_grounding !== undefined
      ? type.stats.avg_grounding.toFixed(3)
      : '--';
    const sampledEdges = type.stats?.sampled_edges !== undefined
      ? type.stats.sampled_edges.toString()
      : '--';

    output += `| ${type.relationship_type} | ${type.epistemic_status} | ${avgGrounding} | ${sampledEdges} |\n`;
  });

  output += '\n## Interpretation Guide\n\n';
  output += '**How to use this data:**\n';
  output += '- **WELL_GROUNDED types** → Use for high-confidence reasoning and reliable knowledge extraction (>80% net support)\n';
  output += '- **MIXED_GROUNDING types** → Variable validation (15-80% net support), explore dialectical patterns or uncertainty\n';
  output += '- **WEAK_GROUNDING types** → Emerging evidence (0-15% net support), use for exploratory reasoning\n';
  output += '- **POORLY_GROUNDED types** → Uncertain knowledge (0-50% net contradiction), unclear epistemic status\n';
  output += '- **CONTRADICTED types** → Refuted claims (>50% net contradiction), contradicted by evidence\n';
  output += '- **INSUFFICIENT_DATA types** → Need more document ingestion to establish epistemic patterns\n\n';
  output += '**Next Steps:**\n';
  output += '- Use `epistemic_status` with action "show" to get detailed statistics for a specific type\n';
  output += '- Filter concept searches by epistemic status to curate high-confidence vs exploratory subgraphs\n';
  output += '- Ingest more documents to move types from INSUFFICIENT_DATA to measurable classifications\n';

  return output;
}

/**
 * Format epistemic status details for a specific type (ADR-065)
 */
export function formatEpistemicStatusDetails(result: any): string {
  const relType = result.relationship_type || 'Unknown';
  const status = result.epistemic_status || 'UNKNOWN';

  let output = `# Epistemic Status: ${relType}\n\n`;
  output += `**Classification:** ${status}\n\n`;
  output += `**Interpretation:** ${formatEpistemicStatusInterpretation(status)}\n\n`;

  if (result.stats) {
    output += '## Grounding Statistics\n\n';
    output += `- **Average Grounding:** ${result.stats.avg_grounding.toFixed(3)} `;
    if (result.stats.avg_grounding > 0.8) {
      output += '(Strong support - well-established)\n';
    } else if (result.stats.avg_grounding > 0.15) {
      output += '(Mixed validation - debated or uncertain)\n';
    } else if (result.stats.avg_grounding >= 0) {
      output += '(Weak support - emerging or poorly grounded)\n';
    } else {
      output += '(Contradicted - refuted or historical)\n';
    }

    if (result.stats.std_grounding !== undefined) {
      output += `- **Standard Deviation:** ${result.stats.std_grounding.toFixed(3)} `;
      if (result.stats.std_grounding > 0.3) {
        output += '(High variance - highly contested)\n';
      } else if (result.stats.std_grounding > 0.15) {
        output += '(Moderate variance - some disagreement)\n';
      } else {
        output += '(Low variance - consistent validation)\n';
      }
    }

    output += `- **Range:** ${result.stats.min_grounding.toFixed(3)} to ${result.stats.max_grounding.toFixed(3)}\n`;
    output += `- **Measurements:** ${result.stats.measured_concepts} concepts sampled\n`;
    output += `- **Sampled Edges:** ${result.stats.sampled_edges} of ${result.stats.total_edges} total\n`;
  }

  // Add measurement context with staleness (ADR-065 Phase 2)
  output += '\n## Measurement Context\n\n';
  if (result.status_measured_at) {
    output += `- **Measured At:** ${new Date(result.status_measured_at).toLocaleString()}\n`;
  }

  const delta = result.vocabulary_changes_since_measurement ?? 0;
  let stalenessText = '';

  if (delta === 0) {
    stalenessText = 'No changes since measurement (fresh)';
  } else if (delta < 5) {
    stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
  } else if (delta < 10) {
    stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
  } else {
    stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
  }

  output += `- **Staleness:** ${stalenessText}\n`;
  output += `- **Note:** Results are temporal - rerun measurement as graph evolves\n`;

  if (result.rationale) {
    output += `\n## Classification Rationale\n\n${result.rationale}\n`;
  }

  output += '\n## Practical Implications\n\n';
  if (status === 'WELL_GROUNDED') {
    output += '**This relationship type is highly reliable.**\n';
    output += '- Use in high-confidence reasoning chains\n';
    output += '- Good candidate for automated inference\n';
    output += '- Represents well-established domain knowledge\n';
  } else if (status === 'MIXED_GROUNDING') {
    output += '**This relationship type has variable validation.**\n';
    output += '- Represents mixed evidence or evolving understanding\n';
    output += '- Explore both supporting and contradicting evidence\n';
    output += '- Good for identifying knowledge gaps or areas of uncertainty\n';
  } else if (status === 'WEAK_GROUNDING') {
    output += '**This relationship type has emerging evidence.**\n';
    output += '- Weak positive grounding (0.0-0.15) indicates developing knowledge\n';
    output += '- May strengthen with more document ingestion\n';
    output += '- Use for exploratory reasoning, but verify claims\n';
  } else if (status === 'POORLY_GROUNDED') {
    output += '**This relationship type has uncertain validation.**\n';
    output += '- Weak negative grounding (-0.5-0.0) indicates unclear support\n';
    output += '- May represent liminal or contested knowledge\n';
    output += '- Use cautiously - verify before using in reasoning\n';
  } else if (status === 'CONTRADICTED') {
    output += '**This relationship type is contradicted by evidence.**\n';
    output += '- May represent refuted claims or historical misconceptions\n';
    output += '- Use cautiously - validate before using in reasoning\n';
    output += '- Useful for understanding evolution of knowledge\n';
  } else if (status === 'INSUFFICIENT_DATA') {
    output += '**Not enough data to establish epistemic pattern.**\n';
    output += '- Need more documents using this relationship type\n';
    output += '- Current measurements: <3 successful samples\n';
    output += '- Re-measure after ingesting more content\n';
  }

  return output;
}

/**
 * Format epistemic status measurement results (ADR-065)
 */
export function formatEpistemicStatusMeasurement(result: any): string {
  let output = '# Epistemic Status Measurement Results\n\n';
  output += `**Measured:** ${result.total_types} vocabulary types\n`;
  output += `**Stored:** ${result.stored_count} types updated in database\n\n`;

  if (result.classifications && Object.keys(result.classifications).length > 0) {
    output += '## Classification Distribution\n\n';
    Object.entries(result.classifications)
      .sort((a: any, b: any) => b[1] - a[1])  // Sort by count descending
      .forEach(([status, count]) => {
        output += `- **${status}**: ${count}\n`;
      });
    output += '\n';
  }

  if (result.sample_results && result.sample_results.length > 0) {
    output += '## Sample Results (Top 10)\n\n';
    output += '| Type | Status | Avg Grounding | Interpretation |\n';
    output += '|------|--------|---------------|----------------|\n';

    result.sample_results.forEach((sample: any) => {
      const avgGrounding = sample.stats?.avg_grounding !== undefined
        ? sample.stats.avg_grounding.toFixed(3)
        : '--';

      let interpretation = '';
      if (sample.epistemic_status === 'WELL_GROUNDED') {
        interpretation = '✓ Reliable';
      } else if (sample.epistemic_status === 'MIXED_GROUNDING') {
        interpretation = '⚠ Variable';
      } else if (sample.epistemic_status === 'WEAK_GROUNDING') {
        interpretation = '~ Emerging';
      } else if (sample.epistemic_status === 'POORLY_GROUNDED') {
        interpretation = '? Uncertain';
      } else if (sample.epistemic_status === 'CONTRADICTED') {
        interpretation = '✗ Refuted';
      } else if (sample.epistemic_status === 'INSUFFICIENT_DATA') {
        interpretation = '? Need data';
      } else {
        interpretation = '- Other';
      }

      output += `| ${sample.relationship_type} | ${sample.epistemic_status} | ${avgGrounding} | ${interpretation} |\n`;
    });
    output += '\n';
  }

  output += '## What This Means\n\n';
  output += 'Epistemic status measurement evaluates how well-established each vocabulary relationship type is based on:\n';
  output += '1. **Grounding strength** of target concepts (evidence support)\n';
  output += '2. **Consistency** across multiple samples (standard deviation)\n';
  output += '3. **Sample size** (measured vs total edges)\n\n';

  output += '**Key Insights:**\n';
  output += '- **WELL_GROUNDED types** represent well-established knowledge patterns (>80% net support)\n';
  output += '- **MIXED_GROUNDING types** show variable validation or mixed evidence (15-80% net support)\n';
  output += '- **WEAK_GROUNDING types** represent emerging knowledge (0-15% net support)\n';
  output += '- **POORLY_GROUNDED types** have uncertain validation (0-50% net contradiction)\n';
  output += '- **CONTRADICTED types** may represent refuted claims (>50% net contradiction)\n';
  output += '- **INSUFFICIENT_DATA types** need more document ingestion\n\n';

  output += '**Next Actions:**\n';
  output += '1. Review MIXED_GROUNDING types to identify knowledge gaps or dialectical patterns\n';
  output += '2. Use WELL_GROUNDED types for high-confidence reasoning and inference\n';
  output += '3. Investigate CONTRADICTED types to understand knowledge evolution\n';
  output += '4. Ingest more documents to move INSUFFICIENT_DATA types to measurable states\n';

  return output;
}
