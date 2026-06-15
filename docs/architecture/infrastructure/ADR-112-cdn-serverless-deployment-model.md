---
status: Proposed
date: 2025-11-03
deciders:
  - aaronsb
  - claude
related:
  - ADR-406
---

# ADR-112: CDN and Serverless Deployment Model

## Overview

Modern web applications face a deployment puzzle: how do you serve the same frontend code to development, staging, and production without rebuilding each time? If your app has hardcoded URLs pointing to `localhost:8000` for development, you can't deploy that same build to production pointing at `api.example.com`. The traditional solution is to rebuild for each environment, but that violates the principle of "build once, deploy many."

There's a deeper challenge too: serving web apps from Content Delivery Networks (CDNs) gives you global performance and scalability, but CDNs only serve static files. They can't run server-side code to render login forms or manage sessions. Yet modern OAuth security requires PKCE (a challenge-response protocol) and proper redirect URL validation. How do you reconcile stateless, static hosting with secure authentication?

The solution is runtime configuration and client-side OAuth flows. Instead of baking configuration into the build, the app loads it when it starts via a `config.js` file that's generated at deploy time. For authentication, the browser handles the entire OAuth flow client-side - no server-rendered HTML needed. This means you can build once, deploy the same files to CloudFlare or Vercel in multiple environments, and just swap out the config file to point each deployment at the right backend. It's like having a universal adapter that works anywhere once you plug in the right settings.

---

## Context

The knowledge graph system currently consists of:
- **API Server:** Python FastAPI backend (port 8000)
- **Visualization App:** React/TypeScript SPA (port 3000 in dev)
- **MCP Server:** TypeScript server for Claude Desktop integration
- **CLI:** TypeScript command-line client

Current deployment model assumes co-located services with local configuration (`.env` files). However, modern web architecture favors:

1. **CDN Deployment:** Static assets served from edge locations (CloudFlare, AWS CloudFront, Netlify)
2. **Serverless Backend:** API deployed as serverless functions (AWS Lambda, Vercel, CloudFlare Workers)
3. **Multi-Environment Support:** Same build artifacts deployed to dev/staging/prod without rebuilding
4. **OAuth Security:** Browser-based apps require PKCE, proper redirect URI validation
5. **Multiple Web Applications:** Future expansion (admin dashboard, public explorer, embedding playground)

### Problems with Current Architecture

1. **Build-Time Configuration:**
   ```typescript
   // ❌ Hardcoded at build time
   const API_URL = import.meta.env.VITE_API_URL;
   ```
   - Requires rebuilding for different environments
   - Cannot deploy same bundle to multiple domains
   - CDN deployment becomes environment-specific

2. **Server-Side OAuth Flow:**
   - Traditional OAuth requires server-rendered HTML for login forms
   - Not compatible with static CDN deployment
   - Requires session management on server

3. **Monolithic Frontend:**
   - Single React app for all use cases
   - Cannot selectively deploy features to different domains
   - Harder to scale team across multiple web projects

## Decision

### 1. Runtime Configuration via `window.APP_CONFIG`

**Frontend applications use runtime configuration injected at load time:**

```typescript
// Runtime config takes precedence over build-time env vars
declare global {
  interface Window {
    APP_CONFIG?: {
      apiUrl: string;
      oauth: {
        clientId: string;
        redirectUri?: string | null;
      };
      app?: {
        name?: string;
        version?: string;
      };
    };
  }
}

const API_BASE_URL = window.APP_CONFIG?.apiUrl ||
                     import.meta.env.VITE_API_URL ||
                     'http://localhost:8000';
```

**Implementation approaches:**

**Option A: `config.js` (Current Stub):**
```html
<!-- index.html -->
<script src="/config.js"></script>
<script type="module" src="/src/main.tsx"></script>
```

```javascript
// public/config.js - NOT committed, generated at deploy time
window.APP_CONFIG = {
  apiUrl: 'https://api.knowledge-graph.example.com',
  oauth: {
    clientId: 'kg-viz-prod',
    redirectUri: 'https://viz.knowledge-graph.example.com/callback'
  }
};
```

**Option B: Template Injection (Future):**
```html
<!-- index.html processed by server -->
<script>
  window.APP_CONFIG = <%= JSON.stringify(config) %>;
</script>
```

**Benefits:**
- Same build deployed to dev/staging/prod
- CDN-compatible (config.js served from origin)
- Easy to update configuration without rebuild
- Fallback to build-time env vars for local dev

### 2. Hybrid OAuth Flow for Browser-Based Apps

**Traditional server-rendered OAuth flow:**
```
User → GET /oauth/authorize (login form)
     → POST /oauth/authorize (credentials)
     → Redirect with code
     → Frontend exchanges code for token
```

**Our hybrid approach (ADR-406 implementation):**
```
User → Client-side LoginModal (React component)
     → POST /auth/oauth/login-and-authorize (credentials + PKCE)
     → Returns authorization code (JSON response, not redirect)
     → Client redirects to /callback with code
     → POST /auth/oauth/token (exchange code for tokens)
     → Store in localStorage, fetch user info
```

**Key characteristics:**
- **PKCE Required:** `code_challenge` and `code_verifier` for public clients
- **No Server-Side HTML:** API returns JSON, not HTML forms
- **Client-Side Routing:** React Router handles `/callback` route
- **Stateless Server:** No sessions, all state in tokens
- **First-Party Only:** Simplified flow for same-origin apps

**Implementation (viz-app/src/lib/auth/authorization-code-flow.ts:44-96):**
```typescript
export async function startAuthorizationFlow(
  username: string,
  password: string,
  config: AuthorizationFlowConfig = {}
): Promise<void> {
  // Generate PKCE parameters
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);

  // Store verifier for callback
  storePKCEVerifier(codeVerifier);

  // Call combined login-and-authorize endpoint
  const response = await axios.post(
    `${API_BASE_URL}/auth/oauth/login-and-authorize`,
    new URLSearchParams({
      username,
      password,
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      scope: config.scope || 'read:* write:*',
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
    })
  );

  const { code, state } = response.data;

  // Client-side redirect to callback
  window.location.href = `${REDIRECT_URI}?code=${code}&state=${state}`;
}
```

### 3. Client-Side Routing with React Router

**All web applications use React Router for client-side navigation:**

```typescript
// viz-app/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<ForceDirected2D />} />
          <Route path="3d" element={<ForceDirected3D />} />
          <Route path="callback" element={<OAuthCallback />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

**CDN Configuration (CloudFlare Pages / Netlify / Vercel):**
```toml
# _redirects (Netlify) or netlify.toml
/*    /index.html    200
```

```json
// vercel.json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

**Benefits:**
- Deep linking support (`/3d`, `/callback`, etc.)
- Works with CDN (all routes serve index.html)
- No server-side routing needed
- Shareable URLs for specific visualizations

### 4. Multi-Application Architecture (Future)

**Proposed structure for multiple web applications:**

```
web-apps/
├── viz-app/              # Main visualization explorer (current)
│   ├── src/
│   ├── public/
│   │   └── config.js     # Runtime config (not committed)
│   └── package.json
│
├── admin-dashboard/      # Admin management UI (future)
│   ├── src/
│   ├── public/
│   │   └── config.js
│   └── package.json
│
├── public-explorer/      # Read-only public graph viewer (future)
│   ├── src/
│   ├── public/
│   │   └── config.js
│   └── package.json
│
└── shared/               # Shared components, auth, API client
    ├── components/
    ├── lib/
    │   ├── auth/         # OAuth flow logic
    │   ├── api/          # API client
    │   └── config/       # Runtime config utilities
    └── package.json
```

**Each app:**
- Independent deployment to different CDN routes/domains
- Shared authentication via OAuth (same authorization server)
- Shared API client and components (via `shared/` package)
- Independent versioning and feature flags
- Different OAuth clients (kg-viz, kg-admin, kg-public)

**Deployment examples:**
```
https://viz.kg.example.com      → viz-app (authenticated, full features)
https://admin.kg.example.com    → admin-dashboard (admin-only)
https://explore.kg.example.com  → public-explorer (read-only, no auth)
```

### 5. OAuth Client Registration Strategy

**Each deployment environment gets unique OAuth clients:**

```sql
-- Development
INSERT INTO kg_auth.oauth_clients (
  client_id, client_name, client_type, redirect_uris, scopes
) VALUES (
  'kg-viz-dev',
  'KG Viz (Development)',
  'public',
  ARRAY['http://localhost:3000/callback'],
  ARRAY['read:*', 'write:*']
);

-- Production (CDN)
INSERT INTO kg_auth.oauth_clients (
  client_id, client_name, client_type, redirect_uris, scopes
) VALUES (
  'kg-viz-prod',
  'KG Viz (Production)',
  'public',
  ARRAY['https://viz.kg.example.com/callback'],
  ARRAY['read:*', 'write:*']
);

-- Admin Dashboard
INSERT INTO kg_auth.oauth_clients (
  client_id, client_name, client_type, redirect_uris, scopes
) VALUES (
  'kg-admin-prod',
  'KG Admin Dashboard',
  'public',
  ARRAY['https://admin.kg.example.com/callback'],
  ARRAY['read:*', 'write:*', 'admin:*']
);
```

**Runtime configuration per deployment:**
```javascript
// viz.kg.example.com/config.js
window.APP_CONFIG = {
  apiUrl: 'https://api.kg.example.com',
  oauth: {
    clientId: 'kg-viz-prod',
    redirectUri: 'https://viz.kg.example.com/callback'
  }
};

// admin.kg.example.com/config.js
window.APP_CONFIG = {
  apiUrl: 'https://api.kg.example.com',
  oauth: {
    clientId: 'kg-admin-prod',
    redirectUri: 'https://admin.kg.example.com/callback'
  }
};
```

### 6. Serverless Backend Considerations

**API deployment options:**

**Option A: Traditional (Current):**
- Single FastAPI server
- Deployed to VM/container (DigitalOcean, AWS EC2, Railway)
- All endpoints in one process
- Good for: MVP, development, small-medium scale

**Option B: Serverless Functions (Future):**
- Separate functions per route group
- Deployed to AWS Lambda, Vercel Functions, CloudFlare Workers
- Auto-scaling, pay-per-request
- Requires: Cold start optimization, stateless design

**Current architecture is serverless-ready:**
- ✅ Stateless JWT/OAuth tokens (no server sessions)
- ✅ PostgreSQL connection pooling (works with serverless)
- ✅ No in-memory state (job queue is DB-backed)
- ⚠️ Cold start concern: Sentence transformers model loading (~2-3s)

**Serverless optimization path:**
1. Separate embedding service (always-on or pre-warmed)
2. Route groups as separate functions:
   - `/auth/*` - Auth service (fast cold start, no ML models)
   - `/query/*` - Query service (shares embedding pool)
   - `/ingest/*` - Ingestion service (async, can cold start)
   - `/admin/*` - Admin service (low traffic, can cold start)

### 7. Multi-Shard Architecture (Future Scalability)

**Shard Definition (ADR-405):**

A **shard** is a single deployment instance with its own:
- PostgreSQL + Apache AGE database
- API server (FastAPI backend)
- LLM API keys and embedding models
- Isolated ontology collections
- Independent user management

**Why Sharding?**

As the knowledge graph scales, a single database instance hits limits:
- Storage capacity (TB+ of graph data)
- Query performance (complex graph traversals)
- Concurrent user load
- Ingestion throughput

**Sharding Strategy (Future):**

```
                    ┌─────────────────────┐
                    │   Shard Router      │
                    │  (CloudFlare Worker)│
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
      ┌─────▼─────┐      ┌─────▼─────┐     ┌─────▼─────┐
      │  Shard 1  │      │  Shard 2  │     │  Shard 3  │
      │           │      │           │     │           │
      │ DB + API  │      │ DB + API  │     │ DB + API  │
      │ us-west   │      │ us-east   │     │ eu-west   │
      └───────────┘      └───────────┘     └───────────┘
```

**Routing Strategies:**

1. **Ontology-based sharding:**
   ```
   ontology "CompanyCorp" → Shard 1
   ontology "PublicDocs"  → Shard 2
   ```

2. **Geographic sharding:**
   ```
   User in US   → us-west shard (low latency)
   User in EU   → eu-west shard (GDPR compliance)
   ```

3. **Semantic sharding (ADR-907 - Future):**
   ```
   FENNEL-style clustering:
   - "ML/AI concepts"     → Shard A
   - "Business concepts"  → Shard B
   - Cross-shard queries via shard router
   ```

**How CDN/Serverless Enables Sharding:**

**Traditional architecture (hard to shard):**
```
User → viz-app (localhost:3000) → API (localhost:8000) → DB (localhost:5432)
```
- Hardcoded API URL in build
- Cannot route to multiple backends
- Would need separate builds per shard

**CDN/Serverless architecture (shard-ready):**
```
User → CDN (viz.kg.com) → Shard Router → Shard 1/2/3
                            ↓
                       config.js
                    {apiUrl: router_url}
```
- Same frontend build for all shards
- Shard router determines backend
- Runtime config points to router or direct shard
- OAuth clients per shard

**Shard Router Implementation (Future):**

```typescript
// CloudFlare Worker - shard-router.js
export default {
  async fetch(request) {
    const url = new URL(request.url);

    // Extract routing hint from request
    const ontology = url.searchParams.get('ontology');
    const userId = await getUserIdFromToken(request);

    // Determine shard
    const shard = await routeRequest({
      ontology,
      userId,
      path: url.pathname
    });

    // Proxy to shard
    const shardUrl = `https://${shard.apiUrl}${url.pathname}${url.search}`;
    return fetch(shardUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
  }
};

async function routeRequest({ ontology, userId, path }) {
  // Strategy 1: Ontology-based routing
  if (ontology) {
    const shardMapping = await kv.get(`ontology:${ontology}:shard`);
    if (shardMapping) return SHARDS[shardMapping];
  }

  // Strategy 2: User-based routing (sticky sessions)
  const userShard = await kv.get(`user:${userId}:shard`);
  if (userShard) return SHARDS[userShard];

  // Strategy 3: Geographic routing
  const geo = request.cf?.country;
  if (geo === 'US') return SHARDS.us_west;
  if (geo === 'GB' || geo === 'DE') return SHARDS.eu_west;

  // Default: Round-robin or least-loaded
  return await getLeastLoadedShard();
}
```

**Benefits of Serverless for Sharding:**

1. **Independent Scaling:**
   - Each shard's API can scale independently
   - High-traffic shards get more resources
   - Low-traffic shards cost less

2. **Cross-Shard Queries:**
   - Shard router can fan-out queries
   - Aggregate results from multiple shards
   - Serverless functions handle parallelization

3. **Easy Shard Migration:**
   - Move ontology from Shard 1 → Shard 2
   - Update KV mapping in router
   - No frontend changes needed

4. **Gradual Rollout:**
   - Start with single shard (current)
   - Add shard router when needed
   - Migrate ontologies incrementally
   - Frontend stays compatible

**Serverless + Sharding Trade-offs:**

✅ **Pros:**
- Horizontal scalability (add shards as needed)
- Geographic distribution (low latency worldwide)
- Cost efficiency (pay per shard usage)
- Fault isolation (one shard down doesn't affect others)

⚠️ **Cons:**
- Cross-shard queries are slower (network hops)
- Shard router becomes single point of failure
- More complex deployment and monitoring
- Ontology placement strategy needed

**Migration Path:**

```
Phase 1 (Current):     Single shard, monolithic deployment
Phase 2 (ADR-112):     Serverless API, CDN frontend (shard-ready)
Phase 3 (Future):      Add shard router, create Shard 2 for testing
Phase 4 (Future):      Migrate high-traffic ontologies to dedicated shards
Phase 5 (Future):      Geographic sharding for EU/Asia regions
Phase 6 (Future):      Semantic sharding (FENNEL + HNSW, ADR-907)
```

**When to Shard?**

Don't shard prematurely. Shard when:
- Single DB exceeds 1TB+ (storage limit)
- Query latency >1s for common operations
- Concurrent users >10,000 (load limit)
- Geographic distribution needed (EU data residency)
- Multi-tenancy isolation required (enterprise customers)

**Current Status:** Single shard sufficient for MVP and early adoption. Serverless architecture keeps sharding option open for future.

## Implementation Status

### ✅ Completed (Stubs/Foundation)

1. **Runtime Configuration:**
   - `window.APP_CONFIG` support in viz-app (src/lib/auth/authorization-code-flow.ts:37-42)
   - Fallback to build-time env vars
   - Ready for config.js injection

2. **Hybrid OAuth Flow:**
   - `POST /auth/oauth/login-and-authorize` endpoint (api/app/routes/oauth.py:961-1131)
   - Client-side LoginModal component (viz-app/src/components/auth/LoginModal.tsx)
   - PKCE implementation (viz-app/src/lib/auth/oauth-utils.ts)
   - Token exchange and refresh (viz-app/src/lib/auth/authorization-code-flow.ts)

3. **Client-Side Routing:**
   - React Router v7 installed
   - `/callback` route for OAuth handling
   - Browser history routing

4. **Timezone-Aware Datetimes:**
   - Fixed `datetime.utcnow()` → `datetime.now(timezone.utc)` (api/app/lib/oauth_utils.py:10, 253)
   - OAuth tokens now compatible with PostgreSQL timezone-aware columns

### 🚧 In Progress / Needed

1. **Multi-App Structure:**
   - [ ] Refactor into `web-apps/` monorepo structure
   - [ ] Extract shared code to `web-apps/shared/`
   - [ ] Create separate admin-dashboard and public-explorer apps

2. **Deployment Tooling:**
   - [ ] `config.js` generation scripts per environment
   - [ ] CDN deployment configs (Netlify, Vercel, CloudFlare Pages)
   - [ ] CI/CD pipelines for multi-app deployments

3. **OAuth Client Management:**
   - [ ] CLI command to register clients per environment
   - [ ] Documentation for redirect URI configuration
   - [ ] Wildcard redirect support for preview deployments

4. **Serverless Backend:**
   - [ ] Separate embedding service
   - [ ] Function-per-route-group architecture
   - [ ] Connection pooling optimization for serverless
   - [ ] Cold start benchmarks and optimizations

## Consequences

### Benefits

1. **CDN Deployment:**
   - ✅ Same build bundle for all environments
   - ✅ Edge caching for static assets
   - ✅ Global low-latency access
   - ✅ No rebuild required for config changes

2. **OAuth Security:**
   - ✅ PKCE protects public clients (browser apps)
   - ✅ No server-side sessions (stateless, scales horizontally)
   - ✅ Proper redirect URI validation per environment
   - ✅ Token refresh for long-lived sessions

3. **Developer Experience:**
   - ✅ Local dev uses build-time env vars (no config.js needed)
   - ✅ Production uses runtime config (deploy-time injection)
   - ✅ Clear separation of build vs deploy configuration
   - ✅ Easy to add new environments

4. **Multi-App Future:**
   - ✅ Independent deployment schedules
   - ✅ Shared authentication (same OAuth server)
   - ✅ Code reuse via shared packages
   - ✅ Team scalability (parallel development)

### Trade-offs

1. **Complexity:**
   - ⚠️ Runtime config adds deployment step (generate config.js)
   - ⚠️ Multi-app requires monorepo tooling (Turborepo, Nx, or pnpm workspaces)
   - ⚠️ More OAuth clients to manage per environment

2. **Security Considerations:**
   - ⚠️ config.js must be served from same origin (CORS)
   - ⚠️ Client secrets cannot be used (public clients only)
   - ⚠️ Redirect URIs must be strictly validated server-side

3. **Testing:**
   - ⚠️ Need to test runtime config injection
   - ⚠️ Each app needs separate OAuth client for testing
   - ⚠️ Multi-environment testing more complex

4. **Serverless Limitations:**
   - ⚠️ Cold start latency for ML models (embedding generation)
   - ⚠️ Function size limits (sentence transformers ~500MB)
   - ⚠️ Connection pool management in serverless context

## Alternatives Considered

### Alternative 1: Server-Side Rendered OAuth

**Traditional flow with HTML templates:**
- Server renders login form at `GET /oauth/authorize`
- Form posts to `POST /oauth/authorize`
- Server redirects with authorization code

**Rejected because:**
- ❌ Requires server-side HTML templating (FastAPI Jinja2)
- ❌ Not compatible with static CDN deployment
- ❌ Requires session management for CSRF tokens
- ❌ Couples frontend to backend deployment

### Alternative 2: Build-Time Configuration Only

**Separate builds for each environment:**
```bash
# Build for production
VITE_API_URL=https://api.kg.example.com npm run build

# Build for staging
VITE_API_URL=https://staging-api.kg.example.com npm run build
```

**Rejected because:**
- ❌ Violates "build once, deploy many" principle
- ❌ Harder to deploy to multiple domains from same build
- ❌ Configuration changes require full rebuild
- ❌ Preview deployments need unique builds

### Alternative 3: Environment Detection at Runtime

**Auto-detect API URL from current domain:**
```typescript
const API_URL = window.location.hostname === 'viz.kg.example.com'
  ? 'https://api.kg.example.com'
  : window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : 'https://staging-api.kg.example.com';
```

**Rejected because:**
- ❌ Hardcodes environment logic in application code
- ❌ Doesn't support arbitrary deployments (preview URLs, forks)
- ❌ Makes testing harder (need to mock window.location)
- ❌ Configuration not externalized

### Alternative 4: Backend Proxy for Authentication

**All OAuth handled by backend, frontend just calls `/api/login`:**
```typescript
// Frontend
await axios.post('/api/login', { username, password });
// Backend sets HTTP-only cookie
```

**Rejected because:**
- ❌ Requires backend deployment on same domain (no CDN)
- ❌ Cookie-based auth harder to use with mobile/desktop apps
- ❌ Less flexible for future third-party OAuth (GitHub, Google)
- ❌ Doesn't work with serverless edge functions (need state)

## Migration Plan

### Phase 1: Current State (ADR-406 + ADR-112 Foundation)

**Status:** ✅ Complete

- Hybrid OAuth flow working in viz-app
- Runtime config support (fallback to env vars)
- Client-side routing with React Router
- Timezone-aware datetime handling

**No breaking changes needed**

### Phase 2: Multi-App Refactor

1. Create `web-apps/` monorepo structure
2. Move current viz-app → `web-apps/viz-app/`
3. Extract shared code → `web-apps/shared/`
4. Set up monorepo tooling (pnpm workspaces or Turborepo)

**Breaking changes:**
- Import paths change (use workspace references)
- Separate build commands per app

### Phase 3: CDN Deployment

1. Create config.js generation scripts
2. Document deployment process per CDN provider
3. Set up production OAuth clients
4. Deploy viz-app to CDN (CloudFlare Pages or Vercel)

**No code changes needed** (runtime config already supported)

### Phase 4: Additional Web Apps

1. Build admin-dashboard app
2. Build public-explorer app
3. Register OAuth clients for each app
4. Deploy to separate domains/routes

**Benefits become clear:** Shared auth, independent deployments

### Phase 5: Serverless Backend

1. Benchmark cold starts with current architecture
2. Separate embedding service (always-on or pre-warmed)
3. Split routes into function groups
4. Deploy to AWS Lambda / Vercel Functions
5. Optimize connection pooling for serverless

**Optional:** Can stay on traditional deployment if serverless doesn't provide value

## Open Questions

1. **Monorepo Tooling:** Turborepo vs Nx vs pnpm workspaces?
   - Turborepo: Simple, good DX, popular for React monorepos
   - Nx: More powerful, steeper learning curve, better for large teams
   - pnpm workspaces: Minimal, just package management

2. **CDN Provider:** CloudFlare Pages vs Vercel vs Netlify?
   - CloudFlare: Best global edge network, serverless workers
   - Vercel: Best React/Next.js integration, preview deployments
   - Netlify: Good balance, easy redirects, form handling

3. **Embedding Service Architecture:**
   - Always-on VM (simple, current model)
   - Pre-warmed Lambda (serverless, higher complexity)
   - Dedicated GPU instance (best performance, higher cost)

4. **Public Explorer Scope:**
   - Read-only graph viewer for unauthenticated users?
   - Curated public ontologies vs full database access?
   - Embedding options for third-party websites?

## References

- **OAuth 2.0 for Browser-Based Apps:** https://datatracker.ietf.org/doc/html/draft-ietf-oauth-browser-based-apps
- **PKCE (RFC 7636):** https://datatracker.ietf.org/doc/html/rfc7636
- **CDN Deployment Best Practices:** https://web.dev/articles/rendering-on-the-web
- **Serverless Architecture:** https://aws.amazon.com/serverless/
- **React Router v7:** https://reactrouter.com/
- **ADR-406:** OAuth Client Management (authentication foundation)

## Decision Log

- **2025-11-03:** ADR created after implementing hybrid OAuth flow
- **2025-11-03:** Runtime config pattern validated in viz-app
- **2025-11-03:** Timezone fix applied (datetime.now(timezone.utc) pattern)

---

**Next Actions:**

1. Update `docs/architecture/ARCHITECTURE_DECISIONS.md` with ADR-112 entry
2. Document runtime config generation in deployment guide
3. Create example `config.js` templates for each environment
4. Plan Phase 2 (multi-app refactor) scope and timeline
