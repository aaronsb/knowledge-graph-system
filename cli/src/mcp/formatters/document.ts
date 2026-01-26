/**
 * Document formatters (ADR-084)
 */

import { formatGroundingStrength } from './utils.js';

/**
 * Format document search results (ADR-084)
 */
export function formatDocumentSearchResults(result: any): string {
  let output = `# Document Search: "${result.query || 'documents'}"\n\n`;
  output += `Found ${result.total_matches} document(s)\n\n`;

  if (result.documents.length === 0) {
    output += 'No documents found matching this query.\n';
    return output;
  }

  result.documents.forEach((doc: any, i: number) => {
    output += `## ${i + 1}. ${doc.filename}\n\n`;
    output += `Document ID: ${doc.document_id}\n`;
    output += `Ontology: ${doc.ontology}\n`;
    output += `Similarity: ${(doc.best_similarity * 100).toFixed(1)}%\n`;
    output += `Source Chunks: ${doc.source_count}\n`;

    if (doc.concept_ids && doc.concept_ids.length > 0) {
      const conceptPreview = doc.concept_ids.slice(0, 5).join(', ');
      const more = doc.concept_ids.length > 5 ? ` (+${doc.concept_ids.length - 5} more)` : '';
      output += `Concepts: ${conceptPreview}${more}\n`;
    }

    output += '\n';
  });

  // Usage hints
  output += '## Next Steps\n\n';
  output += '- Use `document` tool with action "show" to view document content\n';
  output += '- Use `document` tool with action "concepts" to see all extracted concepts\n';
  output += '- Use `concept` tool to explore individual concepts in detail\n';

  return output;
}

/**
 * Format document list (ADR-084)
 */
export function formatDocumentList(result: any): string {
  let output = `# Documents\n\n`;
  output += `Showing ${result.documents.length} of ${result.total} documents\n\n`;

  if (result.documents.length === 0) {
    output += 'No documents found.\n';
    return output;
  }

  result.documents.forEach((doc: any, i: number) => {
    output += `${i + 1}. **${doc.filename}**\n`;
    output += `   - ID: ${doc.document_id.substring(0, 50)}...\n`;
    output += `   - Ontology: ${doc.ontology}\n`;
    output += `   - Type: ${doc.content_type || 'document'}\n`;
    output += `   - Sources: ${doc.source_count}, Concepts: ${doc.concept_count}\n`;
    output += '\n';
  });

  if (result.total > result.documents.length) {
    output += `Use offset=${result.offset + result.documents.length} to see more.\n`;
  }

  return output;
}

/**
 * Format document content (ADR-084)
 */
export function formatDocumentContent(result: any): string {
  let output = `# Document Content\n\n`;
  output += `Type: ${result.content_type}\n`;
  output += `Chunks: ${result.chunks.length}\n\n`;

  if (result.content_type === 'image') {
    if (result.content.prose) {
      output += '## Image Description\n\n';
      output += result.content.prose + '\n\n';
    }
    if (result.content.image) {
      output += `[Image data: ${result.content.image.length} bytes base64]\n`;
    }
  } else {
    if (result.content.document) {
      output += '## Content\n\n';
      output += result.content.document + '\n';
    } else if (result.content.error) {
      output += `Error: ${result.content.error}\n`;
    } else {
      output += 'No content available.\n';
    }
  }

  return output;
}

/**
 * Format document concepts (ADR-084)
 */
export function formatDocumentConcepts(result: any): string {
  let output = `# Concepts: ${result.filename}\n\n`;
  output += `Document: ${result.document_id}\n`;
  output += `Total: ${result.total} concept(s)\n\n`;

  if (result.concepts.length === 0) {
    output += 'No concepts found for this document.\n';
    return output;
  }

  result.concepts.forEach((concept: any, i: number) => {
    output += `${i + 1}. **${concept.name}**\n`;
    output += `   - ID: ${concept.concept_id}\n`;
    output += `   - Source: ${concept.source_id}\n`;
    output += `   - Instances: ${concept.instance_count}\n`;
    output += '\n';
  });

  // Usage hints
  output += '## Next Steps\n\n';
  output += '- Use `concept` tool with action "details" for full concept information\n';
  output += '- Use `concept` tool with action "connect" to find relationships between concepts\n';
  output += '- Or use `include_details: true` to get full details in one call\n';

  return output;
}

/**
 * Format document concepts with full details (ADR-084)
 * Used when include_details=true - fetches all concept info in one call
 */
export function formatDocumentConceptsDetailed(docResult: any, conceptDetails: any[]): string {
  let output = `# Concepts: ${docResult.filename}\n\n`;
  output += `Document: ${docResult.document_id}\n`;
  output += `Total: ${conceptDetails.length} unique concept(s)\n\n`;

  if (conceptDetails.length === 0) {
    output += 'No concepts found for this document.\n';
    return output;
  }

  conceptDetails.forEach((concept: any, i: number) => {
    if (concept.error) {
      output += `## ${i + 1}. ${concept.label}\n\n`;
      output += `ID: ${concept.concept_id}\n`;
      output += `Status: Failed to load\n\n`;
      return;
    }

    output += `## ${i + 1}. ${concept.label}\n\n`;

    if (concept.description) {
      output += `${concept.description}\n\n`;
    }

    output += `ID: ${concept.concept_id}\n`;
    output += `Documents: ${concept.documents?.join(', ') || 'Unknown'}\n`;
    output += `Evidence: ${concept.instances?.length || 0} instances\n`;

    // Grounding with confidence
    if (concept.grounding_strength !== undefined || concept.grounding_display) {
      const grounding = concept.grounding_display || formatGroundingStrength(concept.grounding_strength);
      output += `Grounding: ${grounding}\n`;
    }

    // Sample evidence (max 2)
    if (concept.instances && concept.instances.length > 0) {
      output += `\n### Evidence Samples\n\n`;
      concept.instances.slice(0, 2).forEach((inst: any, idx: number) => {
        const truncated = inst.quote.length > 120 ? inst.quote.substring(0, 120) + '...' : inst.quote;
        output += `${idx + 1}. ${inst.document} (para ${inst.paragraph}):\n`;
        output += `   "${truncated}"\n`;
      });
      if (concept.instances.length > 2) {
        output += `   ... and ${concept.instances.length - 2} more\n`;
      }
    }

    // Relationships (max 5)
    if (concept.relationships && concept.relationships.length > 0) {
      output += `\n### Relationships (${concept.relationships.length})\n\n`;
      concept.relationships.slice(0, 5).forEach((rel: any) => {
        const confidence = rel.confidence ? ` (${(rel.confidence * 100).toFixed(0)}%)` : '';
        output += `${rel.rel_type} -> ${rel.to_label}${confidence}\n`;
      });
      if (concept.relationships.length > 5) {
        output += `... and ${concept.relationships.length - 5} more\n`;
      }
    }

    output += '\n---\n\n';
  });

  return output;
}
