# ADR-001: Multi-Tier Agent Access Model

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related ADRs:** ADR-004 (Pure Graph Design)

## Overview

When multiple AI agents interact with a knowledge graph, you face a classic problem: how do you let helpful agents add knowledge while preventing damage from mistakes or malicious behavior? It's like running a library where some visitors can only browse books, others can suggest new acquisitions, and only trusted librarians can reorganize the shelves or remove duplicates.

The naive approach would be to trust each agent to declare its own permission level—"I'm a curator, let me delete things!" But that's like putting a suggestion box at the library entrance and blindly following every request. A compromised or poorly designed agent could claim administrator privileges and wreak havoc.

This decision establishes a multi-tier access control system where security happens at the database level, not the application level. Think of it as issuing library cards with different colors—the database checks your card before letting you into restricted sections, regardless of what you claim you're allowed to do. The application layer (our MCP server) just routes you to the right entrance; the real bouncer is the database itself.

The four tiers create a natural progression from casual readers to trusted curators, with each level unlocking new capabilities while preventing dangerous operations. This way, an AI agent helping you explore concepts can't accidentally delete your entire knowledge base, and even if someone hacks the application server, they can't escalate their database privileges.

---

## Context

The knowledge graph system needs to support multiple AI agents and human users interacting simultaneously. Different types of agents and users require different permission levels - some should only read data, while others need to contribute new concepts or perform administrative maintenance. Without proper access control, the system risks data corruption from unrestricted write access.

## Decision

Implement tiered access control via Neo4j user accounts and roles, not MCP server claims. The MCP server will route requests to appropriate Neo4j connections based on the agent's actual Neo4j credentials, ensuring that security is enforced at the database level.

### Access Tiers

#### Tier 1: Reader (Query-Only)
- **Neo4j Role:** `reader`
- **Permissions:** Read-only access to graph
- **Use Cases:** General purpose LLM agents, public web interface, text generation

#### Tier 2: Contributor (Controlled Write)
- **Neo4j Role:** `contributor`
- **Permissions:**
  - Read all nodes/relationships
  - Create Concept, Instance, Relationship nodes
  - Update fitness metrics (query_count, relevance_sum)
- **Restrictions:**
  - Cannot delete nodes
  - Cannot modify core properties of existing nodes
  - Cannot adjust manual_bias scores
- **Use Cases:** AI agents adding knowledge from conversations, automated ingestion

#### Tier 3: Librarian (Maintenance)
- **Neo4j Role:** `librarian`
- **Permissions:**
  - All Contributor permissions
  - Merge concepts (transfer relationships, delete duplicates)
  - Flag nodes for review
  - Set quality metadata (confidence, review flags)
- **Restrictions:**
  - Cannot adjust manual_bias
  - Cannot delete Source nodes
- **Use Cases:** Quality control agents, deduplication services

#### Tier 4: Curator (Structural)
- **Neo4j Role:** `curator`
- **Permissions:**
  - All Librarian permissions
  - Adjust manual_bias scores
  - Delete any node type
  - Bulk operations
  - Cross-graph operations (staging → production)
- **Use Cases:** Human administrators, CLI bulk operations

### Security Model

**Never trust MCP client claims:**
```
Agent claims role="curator" via MCP
  ↓
MCP server receives request
  ↓
MCP uses Neo4j connection with agent's actual credentials
  ↓
Neo4j enforces role-based permissions
  ↓
Operation succeeds/fails based on actual Neo4j role
```

**MCP Server Role:**
- Route requests to appropriate Neo4j connection
- Provide workflow hints and prerequisites (UX only, not security)
- Log operations for audit trail
- Return helpful error messages

**Neo4j Role Setup:**
```cypher
// Create roles
CREATE ROLE reader;
CREATE ROLE contributor;
CREATE ROLE librarian;
CREATE ROLE curator;

// Grant permissions (example for contributor)
GRANT TRAVERSE ON GRAPH * NODES * TO contributor;
GRANT READ {*} ON GRAPH * NODES * TO contributor;
GRANT CREATE ON GRAPH * NODES Concept, Instance TO contributor;
GRANT SET PROPERTY {query_count, relevance_sum, fitness_score} ON GRAPH * NODES Concept TO contributor;

// Create user with role
CREATE USER agent_gpt4o SET PASSWORD 'secure_password';
GRANT ROLE contributor TO agent_gpt4o;
```

## Consequences

### Positive
- Security enforced at database level, not application level
- Multiple MCP servers can exist without security concerns
- Compromised MCP server cannot escalate privileges
- Clear audit trail via Neo4j authentication logs
- Fine-grained control over different agent capabilities

### Negative
- Requires Neo4j Enterprise Edition for fine-grained role-based access control
- Additional complexity in managing Neo4j users and roles
- MCP server needs multiple Neo4j connection pools (one per role)

### Neutral
- Need to maintain documentation on which operations require which tier
- Migration path needed for existing agents to proper role assignments
