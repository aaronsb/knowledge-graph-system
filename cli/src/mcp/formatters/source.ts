/**
 * Source and polarity axis formatters
 */

import type { SourceSearchResponse } from '../../types/index.js';
import { formatGroundingStrength } from './utils.js';

/**
 * Format source search results as markdown (ADR-068 Phase 5)
 *
 * Optimized for MCP/AI consumption - shows matched chunks with offsets
 * and related concepts extracted from those sources.
 */
export function formatSourceSearchResults(result: SourceSearchResponse): string {
  let output = `# Source Search: "${result.query}"\n\n`;
  output += `Found ${result.count} source passage(s) (threshold: ${(result.threshold_used || 0.7) * 100}%)\n\n`;

  if (result.count === 0) {
    output += 'No source passages found matching this query.\n\n';
    output += '**Tips:**\n';
    output += '- Source search uses text embeddings, not concept embeddings\n';
    output += '- Try broader queries or lower similarity thresholds\n';
    output += '- Use concept search to find concepts, then view their evidence\n';
    return output;
  }

  result.results.forEach((source, i) => {
    output += `## ${i + 1}. ${source.document} (para ${source.paragraph})\n\n`;
    output += `- **Source ID:** ${source.source_id}\n`;
    output += `- **Similarity:** ${(source.similarity * 100).toFixed(1)}%\n`;

    if (source.is_stale) {
      output += `- **Status:** ⚠ Stale embedding (source text changed since embedding)\n`;
    }

    output += `\n**Matched Chunk** [offset ${source.matched_chunk.start_offset}:${source.matched_chunk.end_offset}]:\n\n`;
    output += `> ${source.matched_chunk.chunk_text}\n\n`;

    if (source.full_text) {
      const truncated = source.full_text.length > 300
        ? source.full_text.substring(0, 300) + '...'
        : source.full_text;
      output += `**Full Context:**\n\n${truncated}\n\n`;
    }

    if (source.concepts && source.concepts.length > 0) {
      output += `**Concepts Extracted** (${source.concepts.length}):\n\n`;
      source.concepts.slice(0, 5).forEach(concept => {
        output += `- **${concept.label}** (${concept.concept_id})\n`;
        if (concept.description) {
          output += `  ${concept.description}\n`;
        }
        output += `  Evidence: "${concept.instance_quote}"\n`;
      });

      if (source.concepts.length > 5) {
        output += `\n... and ${source.concepts.length - 5} more concepts\n`;
      }
      output += '\n';
    }
  });

  output += '**Next Steps:**\n';
  output += '- Use concept IDs with `concept` tool (action: "details") to explore further\n';
  output += '- Use `concept` tool (action: "connect") to find relationships between concepts\n';
  output += '- Adjust similarity threshold if results are too broad or too narrow\n';

  return output;
}

/**
 * Format polarity axis analysis results as markdown (ADR-070)
 *
 * Optimized for MCP/AI consumption - shows axis definition, projections,
 * statistics, and grounding correlation patterns.
 */
export function formatPolarityAxisResults(result: any): string {
  let output = `# Polarity Axis Analysis\n\n`;

  // Axis definition
  output += `## Polarity Axis: ${result.axis.positive_pole.label} ↔ ${result.axis.negative_pole.label}\n\n`;

  output += `**Positive Pole:** ${result.axis.positive_pole.label}\n`;
  output += `  Grounding: ${formatGroundingStrength(result.axis.positive_pole.grounding)}\n`;
  output += `  ID: ${result.axis.positive_pole.concept_id}\n\n`;

  output += `**Negative Pole:** ${result.axis.negative_pole.label}\n`;
  output += `  Grounding: ${formatGroundingStrength(result.axis.negative_pole.grounding)}\n`;
  output += `  ID: ${result.axis.negative_pole.concept_id}\n\n`;

  output += `**Axis Magnitude:** ${result.axis.magnitude.toFixed(4)}\n`;

  const qualityLabel = result.axis.axis_quality === 'strong'
    ? '✓ Strong (poles are semantically distinct)'
    : '⚠ Weak (poles may be too similar)';
  output += `**Axis Quality:** ${qualityLabel}\n\n`;

  // Statistics
  output += `## Statistics\n\n`;
  output += `- **Total Concepts:** ${result.statistics.total_concepts}\n`;
  output += `- **Position Range:** [${result.statistics.position_range[0].toFixed(3)}, ${result.statistics.position_range[1].toFixed(3)}]\n`;
  output += `- **Mean Position:** ${result.statistics.mean_position.toFixed(3)} `;

  if (result.statistics.mean_position > 0.2) {
    output += '(skewed toward positive pole)\n';
  } else if (result.statistics.mean_position < -0.2) {
    output += '(skewed toward negative pole)\n';
  } else {
    output += '(balanced)\n';
  }

  output += `- **Mean Axis Distance:** ${result.statistics.mean_axis_distance.toFixed(3)} (orthogonal spread)\n\n`;

  // Direction distribution
  output += `**Direction Distribution:**\n`;
  output += `- Positive (>0.3): ${result.statistics.direction_distribution.positive} concepts\n`;
  output += `- Neutral (-0.3 to 0.3): ${result.statistics.direction_distribution.neutral} concepts\n`;
  output += `- Negative (<-0.3): ${result.statistics.direction_distribution.negative} concepts\n\n`;

  // Grounding correlation
  output += `## Grounding Correlation\n\n`;
  output += `**Pearson r:** ${result.grounding_correlation.pearson_r.toFixed(3)}\n`;
  output += `**p-value:** ${result.grounding_correlation.p_value.toFixed(4)}\n`;
  output += `**Interpretation:** ${result.grounding_correlation.interpretation}\n\n`;

  // Add practical interpretation
  const r = result.grounding_correlation.pearson_r;
  if (Math.abs(r) < 0.1) {
    output += `→ No correlation: Position and grounding are independent\n\n`;
  } else if (r > 0.3) {
    output += `→ Positive correlation: Concepts near positive pole tend to have higher grounding\n\n`;
  } else if (r < -0.3) {
    output += `→ Negative correlation: Concepts near negative pole tend to have higher grounding\n\n`;
  } else {
    output += `→ Weak correlation: Position and grounding are loosely related\n\n`;
  }

  // Projections (top concepts for each direction)
  if (result.projections && result.projections.length > 0) {
    output += `## Concept Projections (${result.projections.length} total)\n\n`;

    // Sort by position
    const sorted = [...result.projections].sort((a: any, b: any) => b.position - a.position);

    // Show top 5 positive
    const positive = sorted.filter((p: any) => p.direction === 'positive').slice(0, 5);
    if (positive.length > 0) {
      output += `### Positive Direction (toward ${result.axis.positive_pole.label})\n\n`;
      positive.forEach((proj: any, i: number) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }

    // Show neutral concepts (if any)
    const neutral = sorted.filter((p: any) => p.direction === 'neutral').slice(0, 3);
    if (neutral.length > 0) {
      output += `### Neutral (balanced between poles)\n\n`;
      neutral.forEach((proj: any, i: number) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }

    // Show top 5 negative
    const negative = sorted.filter((p: any) => p.direction === 'negative').slice(-5).reverse();
    if (negative.length > 0) {
      output += `### Negative Direction (toward ${result.axis.negative_pole.label})\n\n`;
      negative.forEach((proj: any, i: number) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }
  }

  output += `## How to Use This Analysis\n\n`;
  output += `**Understanding Positions:**\n`;
  output += `- Position closer to +1.0 → More aligned with "${result.axis.positive_pole.label}"\n`;
  output += `- Position closer to -1.0 → More aligned with "${result.axis.negative_pole.label}"\n`;
  output += `- Position near 0.0 → Balanced or orthogonal to this dimension\n\n`;

  output += `**Axis Distance (orthogonality):**\n`;
  output += `- Low distance → Concept lies close to the axis (well-explained by this dimension)\n`;
  output += `- High distance → Concept is orthogonal (other dimensions more relevant)\n\n`;

  output += `**Next Steps:**\n`;
  output += `- Use concept IDs with \`concept\` tool (action: "details") to explore individual concepts\n`;
  output += `- Use \`concept\` tool (action: "connect") to find paths between concepts on the axis\n`;
  output += `- Try different pole pairs to explore other semantic dimensions\n`;
  output += `- Compare grounding patterns across positions to identify reliability trends\n`;

  return output;
}
