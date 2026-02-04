# Knowledge Graph Visualizer - Deployment Guide

The viz-app is designed to support multiple deployment strategies with the same build artifacts.

## Architecture

The app uses **runtime configuration** (`config.js`) instead of build-time environment variables. This enables:
- ✅ Single build deployed to multiple environments (dev/staging/prod)
- ✅ CDN/serverless deployment without rebuilding
- ✅ Docker deployment with environment variables
- ✅ No secrets embedded in build artifacts

## Deployment Options

### 1. CDN Deployment (Recommended for Production)

Deploy to Netlify, Vercel, Cloudflare Pages, AWS S3+CloudFront, etc.

**Steps:**
```bash
# 1. Build the app
npm run build

# 2. Create production config
cp public/config.example.js dist/config.js

# 3. Edit dist/config.js with your production values
window.APP_CONFIG = {
  apiUrl: 'https://api.kg.example.com',
  oauth: {
    clientId: 'kg-viz',
    redirectUri: 'https://viz.kg.example.com/callback',
  },
  app: {
    name: 'Knowledge Graph Visualizer',
    version: '1.0.0',
  },
};

# 4. Deploy the dist/ folder to your CDN
# Netlify: drag dist/ folder to Netlify Drop
# Vercel: vercel --prod
# Cloudflare Pages: wrangler pages publish dist
# AWS S3: aws s3 sync dist/ s3://your-bucket --delete
```

**Important:**
- Always deploy the updated `config.js` along with static assets
- No rebuild required when changing API URL or OAuth config
- Update redirect URI in database: `UPDATE kg_auth.oauth_clients SET redirect_uris = ARRAY['https://viz.kg.example.com/callback'] WHERE client_id = 'kg-viz'`

### 2. Docker Deployment

Run as a container with nginx serving the static files.

**Steps:**
```bash
# 1. Build Docker image
docker build -t kg-viz-app .

# 2. Run with environment variables
docker run -d \
  --name kg-viz \
  -p 3000:80 \
  -e VITE_API_URL=http://api.example.com:8000 \
  -e VITE_OAUTH_CLIENT_ID=kg-viz \
  -e VITE_OAUTH_REDIRECT_URI=http://localhost:3000/callback \
  kg-viz-app
```

**With docker-compose** (to be added to main docker-compose.yml):
```yaml
services:
  viz-app:
    build: ./viz-app
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=${VITE_API_URL:-http://localhost:8000}
      - VITE_OAUTH_CLIENT_ID=${VITE_OAUTH_CLIENT_ID:-kg-viz}
      - VITE_OAUTH_REDIRECT_URI=${VITE_OAUTH_REDIRECT_URI:-http://localhost:3000/callback}
    depends_on:
      - postgres
      - api
    restart: unless-stopped
```

The `docker-entrypoint.sh` script automatically generates `config.js` from environment variables at startup.

### 3. Development

Run locally with Vite dev server.

**Steps:**
```bash
# 1. Create .env file (or use existing .env)
cp .env.example .env

# 2. Edit .env with local values
VITE_API_URL=http://localhost:8000
VITE_OAUTH_CLIENT_ID=kg-viz
VITE_OAUTH_REDIRECT_URI=http://localhost:3000/callback

# 3. Start dev server
npm run dev
```

**Note:** Development uses `public/config.js` for runtime config. Both `.env` and `config.js` work, but `config.js` takes precedence.

## Configuration Precedence

The app checks configuration sources in this order:
1. **Runtime config** (`window.APP_CONFIG` from `config.js`) - highest priority
2. **Build-time env vars** (`import.meta.env.VITE_*`) - fallback for backward compatibility
3. **Hardcoded defaults** - last resort

This means:
- CDN deployment: Only `config.js` matters
- Docker deployment: Environment variables generate `config.js` at startup
- Development: `config.js` is used (which can be replaced by `.env` for local dev)

## Security Considerations

### OAuth Redirect URIs

The OAuth client in the database must have the redirect URI whitelisted:

```sql
-- Check current redirect URIs
SELECT redirect_uris FROM kg_auth.oauth_clients WHERE client_id = 'kg-viz';

-- Update for production
UPDATE kg_auth.oauth_clients
SET redirect_uris = ARRAY[
  'http://localhost:3000/callback',        -- Development
  'https://viz.kg.example.com/callback'   -- Production
]
WHERE client_id = 'kg-viz';
```

### CORS Configuration

The API server must allow requests from the viz-app origin:

```python
# api/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",            # Development
        "https://viz.kg.example.com"       # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Troubleshooting

### Config not loading
- **CDN:** Check that `config.js` exists in deployed files
- **Docker:** Check `docker logs <container>` for config generation output
- **Dev:** Check browser console for `window.APP_CONFIG` object

### OAuth redirect mismatch
- Ensure `config.js` redirect URI matches database `redirect_uris`
- Check browser URL after login attempt for actual redirect URI
- Update database with correct production URL

### API CORS errors
- API server must allow viz-app origin in CORS middleware
- Check browser console for CORS error details
- Verify `VITE_API_URL` matches actual API server URL

## CI/CD Example

**GitHub Actions:**
```yaml
name: Deploy to CDN

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: cd viz-app && npm ci

      - name: Build
        run: cd viz-app && npm run build

      - name: Create production config
        run: |
          cat > viz-app/dist/config.js <<EOF
          window.APP_CONFIG = {
            apiUrl: '${{ secrets.API_URL }}',
            oauth: {
              clientId: 'kg-viz',
              redirectUri: '${{ secrets.OAUTH_REDIRECT_URI }}',
            },
            app: {
              name: 'Knowledge Graph Visualizer',
              version: '${{ github.sha }}',
            },
          };
          EOF

      - name: Deploy to Cloudflare Pages
        run: wrangler pages publish viz-app/dist
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```
