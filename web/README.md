# Knowledge Graph Visualizer

Web-based visualization interface for the Knowledge Graph System. Explore concepts, relationships, and evidence in an interactive graph visualization.

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure login with PKCE flow
- 📊 **Multiple Explorers** - 2D force graph, 3D visualization, and more
- 🔍 **Advanced Search** - Find concepts by semantic similarity
- 🎨 **Category Colors** - Visual categorization of relationship types
- 🌐 **CDN-Ready** - Deploy to serverless platforms without rebuilding

## Quick Start

### Development

```bash
# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local development)

# 3. Start API server (in parent directory)
cd .. && ./scripts/start-api.sh

# 4. Start dev server
npm run dev

# 5. Open browser
# http://localhost:3000
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build locally
npm run preview
```

## Deployment

The viz-app supports multiple deployment strategies. See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

### CDN Deployment (Netlify, Vercel, Cloudflare Pages)

```bash
npm run build
cp public/config.example.js dist/config.js
# Edit dist/config.js with production values
# Deploy dist/ folder to your CDN
```

### Docker Deployment

```bash
docker build -t kg-viz-app .
docker run -d -p 3000:80 \
  -e VITE_API_URL=http://api.example.com:8000 \
  -e VITE_OAUTH_REDIRECT_URI=http://localhost:3000/callback \
  kg-viz-app
```

## Configuration

The app uses **runtime configuration** for deployment flexibility:

1. **Runtime config** (`public/config.js`) - highest priority
2. **Build-time env vars** (`.env`) - fallback
3. **Hardcoded defaults** - last resort

See [.env.example](./.env.example) for available configuration options.

## Architecture

- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **State Management:** Zustand
- **Data Fetching:** TanStack Query (React Query)
- **Routing:** React Router v7
- **Auth:** OAuth 2.0 with PKCE
- **Styling:** Tailwind CSS
- **Visualization:** D3.js, Force-Graph, Three.js

## Project Structure

```
viz-app/
├── public/
│   ├── config.js         # Runtime configuration
│   └── config.example.js # Config template
├── src/
│   ├── api/              # API client
│   ├── components/       # React components
│   │   ├── auth/         # OAuth callback
│   │   ├── layout/       # App layout
│   │   └── shared/       # Reusable components
│   ├── explorers/        # Visualization explorers
│   │   ├── ForceGraph2D/
│   │   ├── ForceGraph3D/
│   │   └── common/
│   ├── hooks/            # React hooks
│   ├── lib/              # Utilities
│   │   └── auth/         # OAuth utilities
│   ├── store/            # Zustand stores
│   ├── types/            # TypeScript types
│   └── main.tsx          # App entry point
├── Dockerfile            # Multi-stage Docker build
├── nginx.conf            # Nginx config for SPA routing
├── docker-entrypoint.sh  # Runtime config generation
└── DEPLOYMENT.md         # Deployment guide
```

## Development

### Prerequisites

- Node.js 20+
- API server running on http://localhost:8000
- OAuth client `kg-viz` configured in database

### Available Scripts

- `npm run dev` - Start dev server (hot reload)
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript compiler check

### Adding a New Explorer

1. Create explorer directory: `src/explorers/MyExplorer/`
2. Implement explorer component and settings panel
3. Register in `src/explorers/index.ts`
4. Add data transformer for your visualization library

See existing explorers (ForceGraph2D, ForceGraph3D) for examples.

## OAuth Configuration

The viz-app uses the `kg-viz` OAuth client (public client with PKCE).

**Database Configuration:**
```sql
SELECT * FROM kg_auth.oauth_clients WHERE client_id = 'kg-viz';

-- Update redirect URIs for production:
UPDATE kg_auth.oauth_clients
SET redirect_uris = ARRAY[
  'http://localhost:3000/callback',
  'https://viz.example.com/callback'
]
WHERE client_id = 'kg-viz';
```

**API CORS Configuration:**
```python
# api/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://viz.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Troubleshooting

### OAuth Redirect Mismatch
- Ensure redirect URI in `config.js` matches database `redirect_uris`
- Check browser console for actual redirect URI in error message

### API Connection Failed
- Verify API server is running: `curl http://localhost:8000/health`
- Check `VITE_API_URL` in config.js or .env
- Check API CORS allows viz-app origin

### Config Not Loading
- Development: Check `window.APP_CONFIG` in browser console
- Docker: Check `docker logs <container>` for config generation
- CDN: Verify `config.js` exists in deployed files

## License

MIT - see parent project LICENSE file
