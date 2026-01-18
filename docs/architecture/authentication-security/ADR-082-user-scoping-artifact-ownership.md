# ADR-082: User Scoping and Artifact Ownership Model

**Status:** Accepted
**Date:** 2025-12-17
**Deciders:** @aaronsb, @claude
**Related ADRs:** ADR-028 (Dynamic RBAC), ADR-079 (Projection Storage)

## Context

The knowledge graph system currently has user authentication (ADR-028) but lacks:
1. **Ownership semantics** - Who is responsible for an ontology or artifact?
2. **Group membership** - Users can have roles, but not collaborative groups
3. **Resource-level permissions** - RBAC is role-based, not resource-specific
4. **Artifact tracking** - Computed reports (projections, polarity analyses) have no ownership

### The Satisficing Specialist Model

Consider a research group with multiple specialists:
- Specialists have **responsibility** for domains, not exclusive ownership
- Information flows freely between specialists (no strict isolation)
- Outside parties can interact with all specialists to form their own views
- Only in unusual scenarios (cognitohazard) would strict isolation apply

This system follows the same philosophy:
- **Sufficient controls** for coordination and accountability
- **Not security boundaries** - authenticated users are trusted collaborators
- **Responsibility over ownership** - "I maintain ontology X" not "I exclusively control X"

### Authentication as Accountability

Authentication serves:
1. **Accountability** - Who requested expensive operations?
2. **Resource allocation** - Per-user quotas, rate limiting
3. **Quality control** - Traceable modifications
4. **Coordination** - Knowing who maintains what

Anonymous access (if enabled) becomes a deployment decision at account creation, not a permission model concern.

### Artifact Freshness via Graph Epoch

The system tracks graph changes via `graph_change_counter` (Migration 033). This enables:
- Reports from a month ago are still valid if graph unchanged
- No redundant regeneration when data hasn't changed
- AI agents can recall stored artifacts without recomputation
- Temporal comparison: "What changed since this report?"

## Decision

### 1. Groups as First-Class Citizens

Create a groups system parallel to roles:

**Groups vs Roles:**
| Aspect | Roles | Groups |
|--------|-------|--------|
| Purpose | Permission bundles | Collaboration membership |
| Grants | Actions on resource types | Access to specific resources |
| Example | "curator can write vocabulary" | "research-team can access Ontology-X" |

**Special Groups:**
- `public` (ID 1) - All authenticated users are implicit members
- `admins` (ID 2) - Platform administrators

### 2. ID Ranges (Unix-style)

Reserve low IDs for system entities:

| Range | Purpose |
|-------|---------|
| 1-999 | System users and groups |
| 1000+ | Regular users and groups |

**Reserved Entities:**

| ID | User | Group |
|----|------|-------|
| 1 | `system` | `public` |
| 2 | - | `admins` |
| 1000 | First admin user | First user group |

### 3. Resource Ownership

Resources have an owner and optional grants:

```
Resource:
  owner_id: INTEGER      # User responsible (can transfer)
  grants: [              # Explicit access beyond owner
    {principal_type, principal_id, permission}
  ]
```

**Owned Resources:**
- Ontologies
- Reports (polarity, projections, etc.)
- Future: Saved queries, workspaces

### 4. Grant-Based Access Model

All access resolved through grants:

```python
def can_access(user_id, resource, permission):
    # Owner has full access
    if resource.owner_id == user_id:
        return True

    # Check explicit user grant
    if has_grant(resource, 'user', user_id, permission):
        return True

    # Check group grants (including 'public')
    for group_id in get_user_groups(user_id):
        if has_grant(resource, 'group', group_id, permission):
            return True

    # Public group - all authenticated users are members
    if has_grant(resource, 'group', PUBLIC_GROUP_ID, permission):
        return True

    return False
```

**Permission Levels:**
- `read` - View resource
- `write` - Modify resource (add to ontology, regenerate report)
- `admin` - Transfer ownership, manage grants

### 5. Artifact Metadata

All computed artifacts include:

```json
{
  "owner_id": 1000,
  "created_at": "2025-12-17T10:30:00Z",
  "graph_epoch": 15847,
  "parameters": { ... },
  "visibility": "grants"
}
```

**Freshness Check:**
```python
def is_fresh(artifact):
    current_epoch = get_graph_change_counter()
    return artifact.graph_epoch == current_epoch
```

### 6. Schema Changes

**New Tables:**

```sql
-- Groups
CREATE TABLE kg_auth.groups (
    id INTEGER PRIMARY KEY,
    group_name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id)
);

-- Group Membership
CREATE TABLE kg_auth.user_groups (
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES kg_auth.groups(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by INTEGER REFERENCES kg_auth.users(id),
    PRIMARY KEY (user_id, group_id)
);

-- Resource Grants (for owned resources)
CREATE TABLE kg_auth.resource_grants (
    id SERIAL PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL,  -- 'ontology', 'report', 'projection'
    resource_id VARCHAR(200) NOT NULL,
    principal_type VARCHAR(20) NOT NULL CHECK (principal_type IN ('user', 'group')),
    principal_id INTEGER NOT NULL,
    permission VARCHAR(20) NOT NULL CHECK (permission IN ('read', 'write', 'admin')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by INTEGER REFERENCES kg_auth.users(id),
    UNIQUE(resource_type, resource_id, principal_type, principal_id, permission)
);

CREATE INDEX idx_resource_grants_resource ON kg_auth.resource_grants(resource_type, resource_id);
CREATE INDEX idx_resource_grants_principal ON kg_auth.resource_grants(principal_type, principal_id);
```

**Modifications:**

```sql
-- Add owner_id to ontologies (new table or graph property)
-- Add system user
INSERT INTO kg_auth.users (id, username, password_hash, primary_role, disabled)
VALUES (1, 'system', 'SYSTEM_NO_LOGIN', 'admin', true);

-- Add system groups
INSERT INTO kg_auth.groups (id, group_name, display_name, is_system)
VALUES
    (1, 'public', 'All Users', true),
    (2, 'admins', 'Administrators', true);

-- Reset sequences to start at 1000
ALTER SEQUENCE kg_auth.users_id_seq RESTART WITH 1000;
ALTER SEQUENCE kg_auth.groups_id_seq RESTART WITH 1000;
```

## Consequences

### Positive

1. **Clear ownership** - Know who maintains what
2. **Flexible sharing** - Private, team, or public resources
3. **Artifact reuse** - Stored reports available for recall
4. **AI agent support** - Agents can retrieve cached analyses
5. **Freshness awareness** - Know if reports are current via graph epoch
6. **Consistent model** - Same grant mechanism for all resource types
7. **Unix-familiar** - ID ranges follow established conventions

### Negative

1. **Schema migration** - Existing systems need migration
2. **Query complexity** - Access checks add overhead
3. **Admin burden** - Someone must manage grants (mitigated by sensible defaults)

### Neutral

1. **No strict security** - This is coordination, not isolation
2. **Public = authenticated** - No anonymous access at permission level
3. **Ownership transferable** - Resources can change hands

## What This ADR Does NOT Cover

1. **Anonymous access** - Deployment concern, not permission model
2. **Fine-grained permissions** - Read/write/admin is sufficient
3. **Specific artifact storage** - See ADR-083 for polarity reports
4. **Group hierarchies** - Flat groups for now, can extend later

## Implementation Plan

### Phase 1: Schema Foundation
1. Create migration for groups, user_groups, resource_grants tables
2. Add system user (ID 1) and system groups (ID 1, 2)
3. Alter sequences for 1000+ IDs
4. Update admin creation to use new sequence

### Phase 2: Ontology Ownership
1. Add owner_id tracking for ontologies (metadata in kg_api or graph property)
2. Default owner = user who created first ingestion
3. Add grant checking to ontology operations

### Phase 3: Artifact Ownership
1. Add ownership metadata to Garage storage schema
2. Update projection storage (ADR-079) to include owner
3. API endpoints for listing "my artifacts" vs "public artifacts"

### Phase 4: UI Integration
1. Show ownership in web UI
2. Grant management interface
3. "My ontologies" vs "Public ontologies" views

## Migration Notes

**Existing Ontologies:**
- Assign to `system` user (ID 1) by default
- Grant `public` group read access
- Admin can reassign ownership

**Sequence Reset:**
- Migration must handle existing users (if any with ID < 1000)
- Safe approach: only reset if max(id) < 1000

## References

- ADR-028: Dynamic RBAC (existing role system)
- ADR-079: Projection Artifact Storage (Garage pattern)
- Migration 033: Graph Change Triggers (epoch counter)
