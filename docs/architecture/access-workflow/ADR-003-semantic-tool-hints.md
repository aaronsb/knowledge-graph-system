# ADR-003: Semantic Tool Hint Networks

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-001 (Multi-Tier Access)

## Overview

AI agents are powerful but not infallible—they can make workflow mistakes like creating duplicate concepts without searching first, or attempting operations they don't have permission for. The traditional solution is to hard-code strict rules: "You MUST search before creating." But this creates a rigid system that can't adapt when the agent has legitimate reasons to override the usual workflow.

Think of it like a text adventure game where examining objects gives you hints about what to do next. Instead of locking doors and forcing a linear path, the game suggests "You might want to search for traps before opening that chest" but still lets you proceed if you're confident. The hint system guides behavior without removing player agency.

This decision implements "conversational" tool hints in the MCP server that suggest best practices and prerequisites without enforcing them as hard rules. When an agent tries to create a concept, the system might respond: "Hey, you might want to search for similar concepts first to avoid duplicates. But if you're sure this is unique, go ahead." It's teaching through interaction rather than through prohibition.

The beauty of this approach is that well-designed agents learn the right patterns quickly, while still having the flexibility to break the rules when they have good reason. The hints create a natural conversation flow with the knowledge graph rather than a bureaucratic checklist. Security still happens at the database level (see ADR-001), but workflow guidance happens through friendly suggestions that make the system easier to use correctly.

---

## Context

AI agents using MCP tools can make workflow mistakes (e.g., creating duplicate concepts without searching first, attempting operations they lack permissions for). Hard-coding workflow constraints into the MCP server creates inflexibility and prevents agents from making informed decisions when they have additional context.

## Decision

Implement "text adventure" style tool hints in the MCP server, where tools suggest prerequisites and next actions. These hints guide agent behavior without enforcing strict workflow rules, allowing agents to override suggestions when they have good reason.

### Tool Hint Structure

```typescript
interface ToolHints {
  prerequisites?: string[];           // Tools that should be called first
  next_actions?: string[];            // Suggested tools to call after
  permission_level: AccessTier;       // Minimum required role
  error_hints: {
    [errorType: string]: string;      // Helpful messages for common errors
  };
  audit?: boolean;                    // Log this operation
}

const tools = {
  create_concept: {
    permission_level: "contributor",
    prerequisites: ["search_concepts"],
    error_hints: {
      duplicate_concept: "Similar concept found. Use create_relationship or merge_concepts instead.",
      no_search_performed: "Search for similar concepts first to avoid duplicates."
    },
    next_actions: ["create_relationship", "add_evidence"]
  },

  search_concepts: {
    permission_level: "reader",
    next_actions: ["create_concept", "create_relationship", "get_concept_details"]
  },

  merge_concepts: {
    permission_level: "librarian",
    prerequisites: ["flag_similar_concepts"],
    audit: true,
    error_hints: {
      insufficient_similarity: "Concepts must have similarity > 0.85 to merge",
      missing_flag: "Flag concepts for review before merging"
    }
  }
};
```

### Execution Flow (Text Adventure Pattern)

```typescript
async function executeWithHints(
  toolName: string,
  params: any,
  context: ExecutionContext,
  neo4jConnection: Neo4jDriver  // Uses agent's actual credentials
) {
  const tool = tools[toolName];

  // Check prerequisites (UX hint, not security)
  for (const prereq of tool.prerequisites || []) {
    if (!context.completed.includes(prereq)) {
      return {
        error: "PREREQUISITE_SUGGESTED",
        message: `Consider calling ${prereq} first`,
        hint: tool.error_hints[`missing_${prereq}`],
        can_proceed: true  // Suggestion, not enforcement
      };
    }
  }

  // Execute with agent's Neo4j credentials
  try {
    const result = await tool.execute(params, neo4jConnection);

    // Add to context
    context.completed.push(toolName);

    // Suggest next actions
    result.suggested_next_actions = tool.next_actions;

    return result;
  } catch (neo4jError) {
    // Neo4j permission error is the real enforcement
    return {
      error: "PERMISSION_DENIED",
      message: neo4jError.message,
      hint: "Your Neo4j role lacks permission for this operation"
    };
  }
}
```

### Example Interaction

```
Agent: create_concept({label: "Holacracy"})

MCP Response: {
  error: "PREREQUISITE_SUGGESTED",
  message: "Consider calling search_concepts first",
  hint: "Search for similar concepts to avoid creating duplicates",
  can_proceed: true
}

Agent: search_concepts({query: "Holacracy"})

MCP Response: {
  results: [...],
  suggested_next_actions: ["create_concept", "create_relationship"]
}

Agent: create_concept({label: "Holacracy"})

MCP Response: {
  success: true,
  concept_id: "holacracy-role-assignment",
  suggested_next_actions: ["create_relationship", "add_evidence"]
}
```

## Consequences

### Positive
- Guides agent behavior without hard constraints
- LLM learns proper workflow through interactive feedback
- Hints improve UX but don't replace Neo4j security enforcement
- Flexible - agents can ignore hints when they have additional context
- Prevents most common mistakes while allowing informed overrides
- Creates natural "conversation" flow with the knowledge graph

### Negative
- Agents might ignore hints and make mistakes anyway
- Requires maintaining hint metadata alongside tool definitions
- Context tracking adds complexity to MCP server
- Need to tune hint verbosity to avoid overwhelming agents

### Neutral
- Effectiveness depends on LLM following suggestions
- May need metrics to track how often hints are followed vs. ignored
- Tool hint network could become complex as system grows
