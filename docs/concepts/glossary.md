# Glossary

Terms used in this system, explained in plain language.

---

## Concept

An idea extracted from a document. Not a keyword - a meaningful unit of thought.

Examples:
- "Climate change increases extreme weather events"
- "The mitochondria is the powerhouse of the cell"
- "Napoleon was defeated at Waterloo in 1815"

Concepts can be claims, definitions, events, entities, or other types. Each concept has a grounding score indicating how well-supported it is.

---

## Relationship

A connection between two concepts. The system discovers how ideas relate to each other.

Common relationship types:
- **Supports**: One concept provides evidence for another
- **Contradicts**: Two concepts are in tension or conflict
- **Implies**: If one is true, the other follows
- **Causes**: One concept leads to another
- **Is Part Of**: One concept belongs to a larger whole
- **Is Example Of**: One concept illustrates another

---

## Grounding

A measure of how well-supported a concept is. High grounding means many sources confirm the idea. Low grounding means few sources mention it.

Grounding considers:
- Number of sources mentioning the concept
- Whether sources agree or disagree
- Strength of the evidence in each source

A grounding score ranges from -1.0 (strongly contradicted) to +1.0 (strongly supported). Near zero means mixed or insufficient evidence.

---

## Source

A chunk of original text from a document. Sources are the evidence - they're what concepts are extracted from.

Each source preserves:
- The actual text
- Which document it came from
- Location information (for highlighting and reference)

When you want to verify a concept, you trace it back to its sources.

---

## Evidence

The link between a concept and a source. Evidence shows *which specific text* led to *which concept*.

Multiple sources can provide evidence for the same concept. When they do, the concept's grounding increases.

---

## Provenance

The chain of origin for any piece of knowledge. Provenance answers "where did this come from?"

For a concept, provenance traces:
Document → Chunk → Extraction → Concept

This matters because claims without provenance can't be verified.

---

## Ontology

A collection of related knowledge. Think of it as a named knowledge base.

You might create separate ontologies for:
- "Research Papers"
- "Company Documentation"
- "Meeting Notes"

Ontologies can be queried separately or together. They help organize knowledge into meaningful collections.

---

## Epistemic Status

The reliability classification of knowledge. Describes whether something is well-established, contested, or uncertain.

Possible statuses:
- **Affirmative**: Well-supported, high confidence
- **Contested**: Sources disagree
- **Contradictory**: Strong evidence against
- **Insufficient Data**: Not enough sources to judge
- **Historical**: Considered accurate for its time period

---

## Semantic Search

Finding concepts by meaning, not just matching keywords.

Search for "economic downturn" and find concepts about recessions, market crashes, and financial crises - even if none use those exact words.

This works because concepts are compared by what they mean, not just what words they contain.

---

## Contradiction

When sources disagree. The system tracks contradictions rather than hiding them.

Example: One paper says "coffee prevents heart disease" while another says "coffee increases heart disease risk." Both concepts are stored with their sources, and the contradiction is noted.

This lets you (or an AI) reason about disagreements rather than pretending they don't exist.

---

## Ingestion

The process of adding documents to the system. During ingestion:
1. Documents are stored
2. Text is split into chunks
3. Concepts are extracted from each chunk
4. Relationships are discovered
5. Grounding is calculated

---

## MCP (Model Context Protocol)

A standard way for AI assistants to use external tools. This system provides MCP tools so AI agents like Claude can:
- Search concepts
- Explore relationships
- Query grounding
- Ingest new documents

This is how AI assistants gain persistent memory.

---

## Chunk

A portion of a document, roughly page-sized. Documents are split into chunks for processing.

Chunks preserve context - they overlap slightly so ideas that span a page break aren't lost.

---

## Instance

A specific occurrence of a concept in a source. If the same concept appears in three documents, there are three instances but one concept.

Instances are the individual sightings. The concept is the aggregated understanding.

---

## Diversity Score

A measure of how broadly connected a concept is. High diversity means the concept connects to many different topics. Low diversity means it's narrowly focused.

Useful for finding concepts that bridge different domains.

---

Next: [Using the System](../using/README.md) - Getting started as a user
