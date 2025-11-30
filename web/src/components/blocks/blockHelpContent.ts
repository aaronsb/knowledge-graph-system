/**
 * Help content definitions for each block type
 */

import type { BlockType } from '../../types/blocks';

export interface BlockHelpContent {
  title: string;
  tag: 'FLOW' | 'CYPHER' | 'LOGIC' | 'SMART';
  tagColor: string;
  description: string;
  parameters?: {
    name: string;
    description: string;
  }[];
  tips?: string[];
  example?: string;
}

export const blockHelpContent: Record<BlockType, BlockHelpContent> = {
  start: {
    title: 'Start',
    tag: 'FLOW',
    tagColor: 'green',
    description: 'Entry point for your query flow. Every query must begin with a Start block.',
    tips: [
      'Only one Start block is allowed per query',
      'Connect to your first query block (Search, Vector Search, etc.)',
    ],
  },

  end: {
    title: 'End',
    tag: 'FLOW',
    tagColor: 'red',
    description: 'Exit point marking the end of your query flow. Optional but recommended for clarity.',
    tips: [
      'Helps visualize where your query terminates',
      'Multiple branches can connect to End',
    ],
  },

  search: {
    title: 'Text Search',
    tag: 'CYPHER',
    tagColor: 'blue',
    description: 'Find concepts by exact text matching. Searches for concepts whose labels contain your search term.',
    parameters: [
      { name: 'Query', description: 'Text to search for in concept labels' },
      { name: 'Max Results', description: 'Maximum number of concepts to return' },
    ],
    tips: [
      'Case-insensitive substring matching',
      'Use for finding specific terms you know exist',
      'For semantic/meaning-based search, use Vector Search instead',
    ],
    example: 'Search "payment" finds "payment processing", "payment gateway"',
  },

  vectorSearch: {
    title: 'Vector Search',
    tag: 'SMART',
    tagColor: 'indigo',
    description: 'Semantic search using AI embeddings. Finds concepts by meaning, not just text matching.',
    parameters: [
      { name: 'Query', description: 'Natural language phrase to search for' },
      { name: 'Similarity', description: 'How closely concepts must match (50-100%)' },
      { name: 'Max Results', description: 'Maximum number of concepts to return' },
    ],
    tips: [
      'Finds semantically related concepts even with different wording',
      'Higher similarity = more precise but fewer results',
      'Lower similarity = broader exploration',
    ],
    example: 'Search "payment" might find "transaction", "billing", "invoice"',
  },

  sourceSearch: {
    title: 'Source Search',
    tag: 'SMART',
    tagColor: 'amber',
    description: 'Search source text passages directly using embeddings. Finds original document chunks where concepts were extracted from (ADR-068).',
    parameters: [
      { name: 'Query', description: 'Natural language phrase to search for in source text' },
      { name: 'Ontology', description: 'Optional filter by ontology/document name' },
      { name: 'Similarity', description: 'How closely passages must match (50-100%)' },
      { name: 'Max Results', description: 'Maximum number of passages to return' },
    ],
    tips: [
      'Searches actual source documents, not concept descriptions',
      'Returns text chunks with character offsets for highlighting',
      'Useful for finding original context and evidence',
      'Shows which concepts were extracted from each passage',
    ],
    example: 'Search "authentication flow" finds source passages discussing auth, not just concepts',
  },

  selectConcept: {
    title: 'Select Concept',
    tag: 'CYPHER',
    tagColor: 'blue',
    description: 'Select a specific concept by its ID. Useful for starting from a known concept.',
    parameters: [
      { name: 'Concept ID', description: 'The unique identifier of the concept' },
    ],
  },

  neighborhood: {
    title: 'Neighborhood',
    tag: 'CYPHER',
    tagColor: 'purple',
    description: 'Expand outward from current concepts to find connected neighbors. Explores the graph structure.',
    parameters: [
      { name: 'Depth', description: 'Number of hops to traverse (1-5)' },
      { name: 'Direction', description: 'Outgoing, incoming, or both directions' },
    ],
    tips: [
      'Higher depth = exponentially more results',
      'Start with depth 1-2 for focused exploration',
      'Use with filters to narrow results',
    ],
  },

  pathTo: {
    title: 'Path To',
    tag: 'CYPHER',
    tagColor: 'blue',
    description: 'Find the shortest path between concepts. Discovers how concepts are connected.',
    parameters: [
      { name: 'Target', description: 'Destination concept (by search or ID)' },
      { name: 'Max Hops', description: 'Maximum path length to search' },
    ],
  },

  filterOntology: {
    title: 'Filter Ontology',
    tag: 'CYPHER',
    tagColor: 'orange',
    description: 'Filter concepts by their source ontology (document collection). Narrow results to specific knowledge domains.',
    parameters: [
      { name: 'Ontologies', description: 'List of ontology names to include' },
    ],
    tips: [
      'Useful for focusing on specific document sources',
      'Supports regex patterns for flexible matching',
    ],
  },

  filterEdge: {
    title: 'Filter Edge',
    tag: 'CYPHER',
    tagColor: 'blue',
    description: 'Filter by relationship types between concepts.',
    parameters: [
      { name: 'Relationship Types', description: 'Types to include (IMPLIES, SUPPORTS, etc.)' },
    ],
  },

  filterNode: {
    title: 'Filter Node',
    tag: 'CYPHER',
    tagColor: 'purple',
    description: 'Filter concepts by label patterns or confidence scores.',
    parameters: [
      { name: 'Label Patterns', description: 'Text patterns to match' },
      { name: 'Min Confidence', description: 'Minimum confidence threshold' },
    ],
  },

  and: {
    title: 'AND',
    tag: 'LOGIC',
    tagColor: 'amber',
    description: 'Intersection of multiple input branches. Returns concepts that appear in ALL connected inputs.',
    tips: [
      'Requires multiple input connections for full effect',
      'Use to find concepts that match multiple criteria',
    ],
  },

  or: {
    title: 'OR',
    tag: 'LOGIC',
    tagColor: 'cyan',
    description: 'Union of multiple input branches. Returns concepts that appear in ANY connected input.',
    tips: [
      'Requires multiple input connections for full effect',
      'Use to combine alternative search paths',
    ],
  },

  not: {
    title: 'Exclude (NOT)',
    tag: 'CYPHER',
    tagColor: 'rose',
    description: 'Exclude concepts matching a pattern. Removes unwanted results from your query.',
    parameters: [
      { name: 'Exclude By', description: 'Property to match (label or ontology)' },
      { name: 'Pattern', description: 'Text pattern to exclude' },
    ],
    tips: [
      'Place after other blocks to filter their results',
      'Case-insensitive matching',
    ],
    example: 'Exclude "deprecated" removes concepts with "deprecated" in label',
  },

  limit: {
    title: 'Limit',
    tag: 'CYPHER',
    tagColor: 'gray',
    description: 'Limit the number of results returned. Prevents overwhelming result sets.',
    parameters: [
      { name: 'Count', description: 'Maximum number of results to return' },
    ],
    tips: [
      'Apply at the end of your query',
      'Use presets for common values',
    ],
  },

  epistemicFilter: {
    title: 'Epistemic Filter',
    tag: 'SMART',
    tagColor: 'indigo',
    description: 'Filter relationships by their epistemic status - the reliability classification of knowledge based on grounding measurements.',
    parameters: [
      { name: 'Include Only', description: 'Only show relationships with these statuses' },
      { name: 'Exclude', description: 'Hide relationships with these statuses' },
    ],
    tips: [
      'AFFIRMATIVE = well-established, high confidence',
      'CONTESTED = debated, mixed evidence',
      'CONTRADICTORY = contradicted by evidence',
      'Use to focus on reliable knowledge or explore uncertain areas',
    ],
    example: 'Include AFFIRMATIVE to see only well-supported relationships',
  },

  enrich: {
    title: 'Enrich',
    tag: 'SMART',
    tagColor: 'teal',
    description: 'Fetch full concept details from the database. Adds ontology colors, grounding scores, and search terms for rich visualization.',
    parameters: [
      { name: 'Ontology', description: 'Fetch source document for color-coding' },
      { name: 'Grounding', description: 'Fetch confidence/reliability score' },
      { name: 'Search Terms', description: 'Fetch alternative labels' },
    ],
    tips: [
      'Add before visualization for full detail',
      'Required to see ontology colors like Smart Search',
      'May slow down queries with many results',
    ],
  },
};
