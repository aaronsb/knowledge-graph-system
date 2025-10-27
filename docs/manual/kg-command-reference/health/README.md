# kg health

Check API server health and retrieve service information.

## Usage

```bash
kg health [options]
```

## Description

The `health` command performs a health check on the Knowledge Graph API server and returns detailed service information including version, job queue status, and available endpoints.

This is typically the first command to run when troubleshooting connectivity issues or verifying that the API server is running and accessible.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Behavior

The command:
1. Connects to the API server (using configured URL or default `http://localhost:8000`)
2. Calls the health check endpoint
3. Displays a simple status message
4. Returns detailed service information including:
   - Service name and version
   - Current health status
   - Job queue statistics (pending, approved, processing, etc.)
   - API documentation URL
   - Key endpoint information

## Output

### Success

When the API is healthy:

```bash
Checking API health...
✓ API is healthy
{
  "status": "healthy"
}

API Info:
{
  "service": "Knowledge Graph API",
  "version": "0.1.0 (ADR-024: PostgreSQL Job Queue)",
  "status": "healthy",
  "queue": {
    "type": "postgresql",
    "pending": 0,
    "awaiting_approval": 0,
    "approved": 0,
    "queued": 0,
    "processing": 0
  },
  "docs": "/docs",
  "endpoints": {
    "ingest": "POST /ingest (upload file) or POST /ingest/text (raw text)",
    "jobs": "GET /jobs/{job_id} for status, POST /jobs/{job_id}/approve to start processing"
  }
}
```

### Failure

When the API is unreachable or unhealthy:

```bash
Checking API health...
✗ API health check failed: Connection refused
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | API is healthy and reachable |
| 1 | API is unreachable or unhealthy |

## Examples

### Basic Health Check

```bash
kg health
```

### Check Custom API URL

```bash
kg health --api-url https://api.example.com
```

## Common Use Cases

1. **Initial Setup Verification**: Confirm the API server is running after installation
2. **Troubleshooting**: First step when other commands fail
3. **Monitoring**: Periodic checks in scripts or monitoring systems
4. **Job Queue Status**: Quick view of current job queue state

## Related Commands

- [`kg config`](../config/) - Configure API URL and connection settings
- [`kg admin status`](../admin/#status) - More detailed system status information
- [`kg database stats`](../database/#stats) - Database-specific statistics

## Implementation Notes

- Calls `GET /` and `GET /health` endpoints
- Does not require authentication
- Timeout is based on standard HTTP client settings
- Can be used in automated monitoring/health check scripts

## See Also

- [API Documentation](../../06-reference/01-API.md)
- [Configuration Guide](../../02-configuration/)
- [Troubleshooting Guide](../../05-maintenance/troubleshooting.md)
