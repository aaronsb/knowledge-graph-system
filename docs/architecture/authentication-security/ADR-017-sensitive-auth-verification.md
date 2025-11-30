# Architecture Decision Record: Client-Initiated Token Revocation for Elevated Operations

**Status:** Proposed

**Date:** 2025-10-09

**Deciders:** [Engineering Team]

**Technical Story:** Implement a secure authentication flow for destructive administrative operations (database wipe, restore, configuration changes) that balances security with operational robustness.

---

## Context

Our application consists of:
- **Client:** TypeScript-based CLI (potential future GUI applications)
- **API Layer:** Python REST API
- **Backend:** PostgreSQL with Apache AGE graph extension
- **Operations:** Administrative actions that substantially modify, destroy, or alter data in a way that is not deterministic and could result in corruption

We need to protect destructive operations beyond standard authentication. Standard auth tokens are long-lived (hours/days) and cached client-side. If stolen, they provide extensive access. We need a mechanism for users to re-authenticate for sensitive operations while maintaining a robust, retry-friendly client experience.

### Requirements

1. **Security:** Prevent unauthorized destructive operations
2. **Usability:** Don't break legitimate retries due to network failures
3. **Auditability:** Detect potential token theft or replay attacks
4. **Standards Compliance:** Follow industry-standard security practices
5. **Defense in Depth:** Multiple security layers

### Constraints

- CLI clients may have unreliable network connections
- Operations should be idempotent where possible
- Must support future GUI clients (web, mobile, desktop)
- Cannot store passwords client-side
- Must maintain detailed audit logs for compliance

---

## Decision

We will implement **Time-Bound Elevated Tokens with Client-Initiated Revocation and Post-Revocation Monitoring**, combining three established security patterns:

1. **Step-Up Authentication** (RFC 6749 - OAuth 2.0)
2. **Client-Initiated Token Revocation** (RFC 7009 - OAuth 2.0 Token Revocation)
3. **Post-Revocation Security Monitoring** (NIST SP 800-53 AU-6)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Client (TypeScript CLI)                                     │
│  1. Request elevation with password                         │
│  2. Receive time-bound elevated token (5 min TTL)           │
│  3. Perform protected operation(s)                          │
│  4. Voluntarily revoke token on success                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Python REST API                                             │
│  • Validate password against salted hash                    │
│  • Issue short-lived elevated tokens                        │
│  • Accept client-initiated revocation                       │
│  • Monitor for post-revocation use                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL + Apache AGE                                     │
│  • Store elevated_tokens table                              │
│  • Store audit_log table                                    │
│  • Archive old tokens for security analysis                 │
└─────────────────────────────────────────────────────────────┘
```

### Security Layers

| Layer | Mechanism | Standard | Purpose |
|-------|-----------|----------|---------|
| **1** | Time-bound expiration (5 min) | OWASP ASVS 2.7 | Primary security control |
| **2** | Client-initiated revocation | RFC 7009 | Voluntary single-use behavior |
| **3** | Post-revocation monitoring | NIST SP 800-53 AU-6 | Attack detection |
| **4** | Rate limiting (5 uses max) | OWASP API Security | Abuse prevention |
| **5** | Operation scoping | Principle of Least Privilege | Limit blast radius |
| **6** | Dual token requirement | Defense in Depth | Regular + elevated |

---

## Implementation

### Database Schema

```sql
-- Elevated tokens table
CREATE TABLE elevated_tokens (
    token VARCHAR(64) PRIMARY KEY,
    identity VARCHAR(255) NOT NULL,
    allowed_operations TEXT[] NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    state VARCHAR(50) NOT NULL, -- 'active', 'client_invalidated', 'expired'
    use_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP NULL,
    invalidated_at TIMESTAMP NULL,
    invalidated_by_client_ip VARCHAR(45) NULL,
    
    INDEX idx_identity (identity),
    INDEX idx_state_expires (state, expires_at)
);

-- Security events table
CREATE TABLE security_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    identity VARCHAR(255) NOT NULL,
    elevated_token VARCHAR(64) NULL,
    seconds_after_invalidation INTEGER NULL,
    request_ip VARCHAR(45) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    details JSONB
);

-- Archive table (retain for 90 days for security analysis)
CREATE TABLE elevated_tokens_archive (
    LIKE elevated_tokens INCLUDING ALL,
    archived_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### API Endpoints

#### 1. Request Elevation (Step-Up Authentication)

```python
# POST /auth/elevate
@app.post("/auth/elevate")
async def elevate_privileges(
    identity: str,
    password: str,
    operations: List[str],
    request: Request
):
    """
    RFC 6749 - OAuth 2.0 step-up authentication pattern
    User re-authenticates with password to receive elevated token
    """
    # Verify password against salted hash in database
    if not verify_password_hash(identity, password):
        await rate_limit_failed_attempt(identity)
        raise AuthenticationError("Invalid credentials")
    
    # Generate cryptographically secure token
    elevated_token = secrets.token_urlsafe(32)
    
    # Create time-bound token (5 minutes)
    token_data = {
        "token": elevated_token,
        "identity": identity,
        "allowed_operations": operations,  # Scope to specific operations
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=5),
        "state": "active",
        "use_count": 0
    }
    
    await store_elevated_token(token_data)
    await audit_log("elevated_token_issued", identity, operations)
    
    return {
        "elevated_token": elevated_token,
        "expires_at": token_data["expires_at"].isoformat(),
        "expires_in": 300,
        "allowed_operations": operations
    }
```

#### 2. Client-Initiated Revocation (RFC 7009)

```python
# DELETE /auth/elevate/{token}
@app.delete("/auth/elevate/{token}")
async def revoke_elevated_token(
    token: str,
    regular_token: str = Header(...),
    request: Request
):
    """
    RFC 7009 - OAuth 2.0 Token Revocation
    Client signals completion and voluntarily invalidates token
    
    IMPORTANT: This endpoint is idempotent per RFC 7009:
    "The revocation endpoint returns HTTP 200 whether the token 
    was valid or not" (prevents information leakage)
    """
    identity = await verify_regular_token(regular_token)
    token_data = await get_elevated_token(token)
    
    # Idempotent: Always return 200, never reveal if token exists
    if not token_data:
        return {"status": "revoked"}
    
    if token_data["identity"] != identity:
        # Log but don't reveal mismatch to prevent enumeration
        await audit_log("token_revocation_identity_mismatch", identity)
        return {"status": "revoked"}
    
    if token_data["state"] == "client_invalidated":
        # Already revoked - idempotent behavior
        return {"status": "revoked"}
    
    # Mark as client-invalidated (distinct from natural expiration)
    await update_token({
        "token": token,
        "state": "client_invalidated",
        "invalidated_at": datetime.utcnow(),
        "invalidated_by_client_ip": request.client.host
    })
    
    await audit_log("elevated_token_client_invalidated", 
                   identity=identity,
                   use_count=token_data["use_count"])
    
    return {"status": "revoked"}
```

#### 3. Protected Operation with Post-Revocation Monitoring

```python
# POST /admin/database/wipe
@app.post("/admin/database/wipe")
async def wipe_database(
    regular_token: str = Header(...),
    elevated_token: str = Header(..., alias="X-Elevated-Token"),
    request: Request
):
    """
    Protected operation with multi-layer security validation
    """
    identity = await verify_regular_token(regular_token)
    token_data = await get_elevated_token(elevated_token)
    
    if not token_data:
        raise AuthorizationError("Invalid elevated token")
    
    now = datetime.utcnow()
    
    # CRITICAL: Check for post-revocation use (NIST SP 800-53 AU-6)
    if token_data["state"] == "client_invalidated":
        seconds_since = (now - token_data["invalidated_at"]).seconds
        
        # Determine severity
        severity = "CRITICAL" if seconds_since < 5 else "HIGH"
        
        # Log security event
        await create_security_event({
            "event_type": "post_invalidation_token_use",
            "severity": severity,
            "identity": identity,
            "elevated_token": elevated_token[:8],
            "seconds_after_invalidation": seconds_since,
            "request_ip": request.client.host,
            "details": {
                "invalidated_by_ip": token_data["invalidated_by_client_ip"],
                "operation": "database:wipe",
                "message": f"Token used {seconds_since}s after client revocation"
            }
        })
        
        # Critical case: immediate reuse suggests replay attack
        if seconds_since < 5:
            await alert_security_team(
                "CRITICAL: Possible replay attack detected",
                identity, elevated_token[:8]
            )
        
        raise AuthorizationError("Token has been invalidated")
    
    # Check natural expiration
    if token_data["expires_at"] < now:
        await update_token({"token": elevated_token, "state": "expired"})
        raise AuthorizationError("Token expired")
    
    # Verify operation permission (principle of least privilege)
    if "database:wipe" not in token_data["allowed_operations"]:
        raise AuthorizationError("Operation not permitted")
    
    # Rate limiting within valid window (OWASP API Security)
    use_count = await increment_token_use_count(elevated_token)
    if use_count > 5:
        await create_security_event({
            "event_type": "elevated_token_rate_limit_exceeded",
            "severity": "MEDIUM",
            "identity": identity
        })
        raise AuthorizationError("Token use limit exceeded")
    
    # Alert on multiple uses (low severity, but worth tracking)
    if use_count > 1:
        await audit_log("elevated_token_reused", 
                       identity=identity, 
                       use_count=use_count,
                       severity="LOW")
    
    # Idempotency check (prevent duplicate operations)
    existing_job = await get_active_wipe_job(identity)
    if existing_job:
        return {"status": "already_in_progress", "job_id": existing_job.id}
    
    # Perform protected operation
    job_id = await initiate_database_wipe(initiated_by=identity)
    
    await audit_log("database_wipe_initiated", identity=identity)
    
    return {"status": "initiated", "job_id": job_id}
```

### Client Implementation (TypeScript CLI)

```typescript
// cli/auth/elevated-operation.ts
export class ElevatedOperation {
  private elevatedToken: string | null = null;
  private expiresAt: Date | null = null;
  
  constructor(private apiClient: APIClient) {}
  
  /**
   * Request elevation with password re-authentication
   * Implements step-up authentication (RFC 6749)
   */
  async elevate(password: string, operations: string[]): Promise<void> {
    const response = await this.apiClient.post('/auth/elevate', {
      identity: this.apiClient.identity,
      password: password,
      operations: operations
    });
    
    this.elevatedToken = response.elevated_token;
    this.expiresAt = new Date(response.expires_at);
    
    console.log(`✅ Elevated privileges granted for ${operations.join(', ')}`);
    console.log(`⏱️  Valid for 5 minutes`);
  }
  
  /**
   * Execute protected operation with automatic token cleanup
   * Voluntarily revokes token on success (RFC 7009)
   */
  async execute<T>(operationFn: (token: string) => Promise<T>): Promise<T> {
    if (!this.elevatedToken) {
      throw new Error('Must call elevate() first');
    }
    
    try {
      // Perform operation (retries handled naturally by HTTP client)
      const result = await operationFn(this.elevatedToken);
      
      // Success! Voluntarily revoke token (RFC 7009)
      await this.revoke();
      
      return result;
      
    } catch (error) {
      // Operation failed - token remains valid for retry
      console.error('Operation failed, you may retry:', error.message);
      throw error;
    }
  }
  
  /**
   * RFC 7009 compliant token revocation
   * Idempotent - safe to call multiple times
   */
  async revoke(): Promise<void> {
    if (!this.elevatedToken) return;
    
    const token = this.elevatedToken;
    this.elevatedToken = null;
    this.expiresAt = null;
    
    try {
      await this.apiClient.delete(`/auth/elevate/${token}`);
      console.log('✅ Elevated privileges revoked');
    } catch (error) {
      // Per RFC 7009: revocation should not fail
      // Token will expire naturally
      console.warn('Token revocation request failed (will expire naturally)');
    }
  }
  
  /**
   * Cleanup on process exit
   */
  async cleanup(): Promise<void> {
    await this.revoke();
  }
}

// cli/commands/database.ts
export async function wipeDatabaseCommand(options: CommandOptions) {
  const elevatedOp = new ElevatedOperation(apiClient);
  
  // Ensure cleanup on exit
  process.on('exit', () => elevatedOp.cleanup());
  process.on('SIGINT', () => elevatedOp.cleanup());
  
  try {
    // Prompt for password (step-up authentication)
    const password = await promptPassword(
      'This will PERMANENTLY DELETE all data. Enter password to confirm:'
    );
    
    // Request elevated privileges
    await elevatedOp.elevate(password, ['database:wipe']);
    
    // Execute protected operation
    const result = await elevatedOp.execute(async (token) => {
      return await apiClient.post('/admin/database/wipe', null, {
        headers: { 
          'Authorization': `Bearer ${apiClient.regularToken}`,
          'X-Elevated-Token': token 
        }
      });
    });
    
    console.log('✅ Database wipe initiated:', result.job_id);
    
  } catch (error) {
    console.error('❌ Failed to wipe database:', error.message);
    process.exit(1);
  }
}
```

---

## Consequences

### Positive

1. **Standards Compliance**
   - Follows RFC 7009 (OAuth 2.0 Token Revocation)
   - Aligns with NIST SP 800-53 (Audit Review & Analysis)
   - Implements OWASP ASVS 2.7 (Token Management)
   - Meets PCI-DSS 8.1.4 (Credential Monitoring)

2. **Security Benefits**
   - Multiple layers of defense (time-bound + revocation + monitoring)
   - Strong signal for attack detection (post-revocation use)
   - Limited blast radius (operation-scoped tokens)
   - Detailed audit trail for compliance

3. **Operational Robustness**
   - Network failures don't burn tokens
   - Natural retry behavior works correctly
   - Idempotent operations supported
   - Graceful degradation (expiration fallback)

4. **Developer Experience**
   - Simple client-side patterns
   - Clear success/failure semantics
   - Testable components
   - Future-proof for GUI clients

### Negative

1. **Complexity**
   - More code than simple single-use tokens
   - Additional database tables and indexes
   - Background cleanup jobs required
   - Security monitoring infrastructure needed

2. **Operational Overhead**
   - Must monitor security events dashboard
   - Need alerting for post-revocation use
   - Archive retention policy management
   - Token cleanup maintenance

3. **Slight Security Trade-off**
   - Tokens can be reused within 5-minute window (vs. single-use)
   - Mitigated by: rate limiting, monitoring, short TTL, operation scoping

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Token theft within 5-min window | Multiple security layers, rate limiting, alerts on multiple use |
| Post-revocation use not detected | Security events table with automated alerting |
| Client forgets to revoke | Natural expiration ensures cleanup |
| Database table growth | Automated archival and cleanup jobs |
| False positive alerts | Severity scoring based on timing and IP |

---

## Security Event Monitoring

### Alert Severity Matrix

```python
def calculate_severity(seconds_since_invalidation: int, 
                       request_ip: str, 
                       invalidated_by_ip: str) -> str:
    """
    Post-revocation use severity calculation
    Based on MITRE ATT&CK T1550 (Use Alternate Authentication Material)
    """
    if seconds_since_invalidation < 5:
        return "CRITICAL"  # Immediate replay attack
    
    if seconds_since_invalidation < 30 and request_ip != invalidated_by_ip:
        return "CRITICAL"  # Stolen token from different IP
    
    if seconds_since_invalidation < 300 and request_ip != invalidated_by_ip:
        return "HIGH"      # Suspicious cross-IP usage
    
    if request_ip == invalidated_by_ip:
        return "MEDIUM"    # Same IP, possible client bug
    
    return "LOW"           # Old token, likely automated scanner
```

### Required Dashboards

1. **Active Elevated Sessions** - Who has elevated privileges right now?
2. **Post-Revocation Events** - Potential attacks in progress
3. **High Use Count Tokens** - Tokens approaching rate limit
4. **Failed Elevation Attempts** - Password brute force attempts

---

## References

### Standards & RFCs

- **RFC 6749** - The OAuth 2.0 Authorization Framework (Step-up authentication)
  https://datatracker.ietf.org/doc/html/rfc6749

- **RFC 7009** - OAuth 2.0 Token Revocation (Client-initiated revocation)
  https://datatracker.ietf.org/doc/html/rfc7009

- **NIST SP 800-53** - Security and Privacy Controls (AU-6: Audit Review)
  https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final

- **NIST SP 800-63B** - Digital Identity Guidelines (Token lifecycle)
  https://pages.nist.gov/800-63-3/sp800-63b.html

### Security Frameworks

- **OWASP ASVS v4.0** - Section 2.7: Token-based Session Management
  https://owasp.org/www-project-application-security-verification-standard/

- **OWASP API Security Top 10** - API2:2023 Broken Authentication
  https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/

- **MITRE ATT&CK** - T1550: Use Alternate Authentication Material
  https://attack.mitre.org/techniques/T1550/

- **PCI-DSS 3.2.1** - Requirement 8: Identify and authenticate access
  https://www.pcisecuritystandards.org/

### Industry Examples

- **Google OAuth 2.0** - Token revocation endpoint
  https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke

- **GitHub Apps** - Token management and revocation
  https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-api-tokens-for-your-github-app

- **Auth0** - Token revocation
  https://auth0.com/docs/secure/tokens/token-best-practices

---

## Alternatives Considered

### 1. Single-Use Tokens Only
**Rejected:** Too fragile to network failures, poor developer experience

### 2. Long-Lived Elevated Tokens (15+ minutes)
**Rejected:** Increases attack window significantly

### 3. Password in Every Request
**Rejected:** Password transmitted repeatedly, poor UX

### 4. TOTP/MFA Codes
**Deferred:** Good enhancement for future, but requires MFA enrollment infrastructure

---

## Implementation Notes

- Token storage should use indexed queries on `(state, expires_at)` for cleanup efficiency
- Security events table should be partitioned by month for query performance
- Client libraries should implement automatic cleanup on process exit
- Consider rate limiting the elevation endpoint itself (5 attempts/hour per identity)
- Archive retention: 90 days recommended for security analysis, then hard delete

---

## Approval

- [ ] Security Team Review
- [ ] Architecture Team Review
- [ ] Engineering Lead Approval
- [ ] Compliance Review (if applicable)
