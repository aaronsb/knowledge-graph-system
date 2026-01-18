# Quick Start

Get the knowledge graph running locally in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- 8GB RAM available
- Git

## Steps

### 1. Clone the Repository

```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
```

### 2. Initialize

```bash
./operator.sh init
```

This starts an interactive wizard that:
- Generates secure secrets
- Detects your GPU (if any)
- Starts the containers
- Creates an admin user

Follow the prompts. For defaults, just press Enter.

### 3. Access the System

Once initialization completes:

- **Web interface**: http://localhost:3000
- **API**: http://localhost:8000
- **Login**: Use the admin credentials you set during init

### 4. Verify It Works

```bash
./operator.sh status
```

You should see all containers running and healthy.

## Optional: Install the CLI

The `kg` CLI provides command-line access to the knowledge graph:

```bash
cd cli
npm install
npm run build
./install.sh
```

Then test it:

```bash
kg health
kg search "test query"
```

## What's Next?

**Try ingesting a document:**
```bash
kg ingest /path/to/document.pdf
```

**Or via the web interface:**
1. Go to http://localhost:3000
2. Log in with your admin credentials
3. Navigate to Ingest
4. Upload a document

**Learn more:**
- [Production Deployment](production.md) - For real use
- [Configuration](configuration.md) - All the settings
- [Using the System](../using/README.md) - How to use it

## Troubleshooting

**Containers won't start:**
```bash
./operator.sh logs         # Check for errors
docker ps -a               # See container status
```

**Port already in use:**
Edit `.env` and change the port mappings, or stop whatever's using ports 3000/8000.

**Out of memory:**
The API container needs memory for ML models. Ensure 8GB+ available.

**GPU not detected:**
Run `./operator.sh init` again and check GPU detection, or manually set `GPU_MODE=cpu` in `.operator.conf`.

See [Troubleshooting](troubleshooting.md) for more.
