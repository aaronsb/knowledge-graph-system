# ADR-004: Pure Graph Design (Library Metaphor)

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related ADRs:** ADR-001 (Multi-Tier Access), ADR-002 (Node Fitness Scoring)

## Overview

When building software, there's a constant temptation to bundle everything together—put your access control in the database, your business logic in your API, your workflow rules in your UI, all tangled up in a mess that becomes impossible to change. Knowledge graphs are particularly vulnerable to this because they're so flexible: you can store anything in there, so why not store everything?

The problem is that tight coupling kills adaptability. If your graph contains not just knowledge but also the rules for how to access it, the tools for working with it, and the logic for managing it, then you can't query it with anything except your specific application. Want to add a web UI? Rebuild everything. Want to query it with a different tool? Can't do it—the graph only speaks one language.

This decision establishes a clean separation: the graph is a pure knowledge store, like a library's catalog system. All the stuff about how to access it, what workflows to follow, and what business rules apply lives outside the graph in the application layer, MCP server, or external services. The graph just holds concepts, relationships, sources, and provenance—period.

Using the library metaphor: the graph is the books on shelves, organized and cataloged. The MCP server is the librarian's desk where you ask questions and get guidance. Automated quality control agents are the librarians who periodically check for misplaced books or damaged items. This separation means anyone can walk into the library and browse (using any tool), while the librarians maintain order without physically altering the books themselves.

---

## Context

Early knowledge graph systems often conflate knowledge storage with access control, workflow logic, and business rules. This creates tight coupling that makes it difficult to add new access methods (web UI, API, different MCP servers) or query the graph using different tools.

## Decision

Keep the graph as a pure knowledge store, similar to a library's catalog system. All access control, workflow rules, and business logic live in the MCP server, API layer, or external services - not in the graph itself.

### Analogy: "The Library and the Librarian's Desk"

The graph is the library - books on shelves, organized and cataloged. The MCP server is the librarian's desk - where you ask questions, get guidance, and follow checkout procedures.

### Graph Responsibilities (The Library)
- Store concepts, relationships, instances, sources
- Maintain vector embeddings for semantic search
- Track provenance (who created, when, from where)
- Record usage metrics (fitness scores)
- Enforce data constraints via Neo4j schema

### Graph Does NOT Contain
- ❌ Access control logic (use Neo4j roles - see ADR-001)
- ❌ Workflow rules (use MCP hints - see ADR-003)
- ❌ Business logic (use application layer)
- ❌ Tool definitions (use MCP server)
- ❌ UI state (use client applications)

### MCP Server Responsibilities (The Librarian's Desk)
- Route requests to appropriate Neo4j connection
- Provide tool hints and workflow guidance
- Log operations for audit trail
- Translate between LLM and graph operations
- Return helpful error messages

### Quality Control Services (The Librarians)
Automated agents that maintain graph quality:
- Periodic quality assessments
- Duplicate detection
- Orphaned node cleanup
- Confidence scoring
- Relationship validation

### "Any Moron Can Enter the Library"

Just as anyone can walk into a library and potentially misfile a book, agents with write access can create problematic data. The solution is automated librarians that detect and flag issues:

**Example: The Comic Book in Medical Texts Problem**

```cypher
// Automated librarian finds suspicious placements
MATCH (c:Concept)-[r]-(neighbor:Concept)
WHERE c.created_at > datetime() - duration('P7D')
WITH c, collect(neighbor.label) as neighbors
CALL db.index.vector.queryNodes('concept-embeddings', 5, c.embedding)
  YIELD node, score
WITH c, neighbors, collect(node.label) as semantically_similar
WHERE none(n IN neighbors WHERE n IN semantically_similar)
SET c.flagged_for_review = true,
    c.flag_reason = "Linked to semantically distant concepts"
```

**Provenance Tracking for Quality Analysis:**

```cypher
(:Concept {
  created_by: "agent_gpt4o_session_abc123",
  created_at: "2025-10-04T20:15:00Z",
  source_type: "conversation"
})

// Query: Who created low-quality nodes?
MATCH (c:Concept)
WHERE c.confidence < 0.5 AND c.created_by STARTS WITH "agent_"
RETURN c.created_by, count(*) as low_quality_count
ORDER BY low_quality_count DESC
```

## Consequences

### Positive
- Clear separation of concerns between storage and logic
- Graph remains queryable by any tool/language
- Easy to add new access methods (web UI, API, different clients)
- Quality issues can be detected and fixed programmatically
- Scales to multiple MCP servers without data duplication
- Graph data can outlive specific application code

### Negative
- Requires discipline to avoid putting business logic in graph
- Quality control agents are essential (not optional)
- May need to educate contributors on the separation principle
- Some operations require coordination between graph and application layer

### Neutral
- Provenance tracking is crucial for identifying problematic data sources
- Need clear guidelines on what belongs in graph vs. application layer
- Quality control agents should run automatically, not on-demand
