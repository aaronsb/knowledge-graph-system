# Development Test Scripts

Tests run inside the `kg-api-dev` Docker container. Use the Makefile from the project root:

```bash
make test            # Full test suite
make test-unit       # Unit tests only
make test-api        # API route tests only
make test-verbose    # Full suite, verbose output
```

These translate to `docker exec kg-api-dev pytest ...` commands.

## Standalone Diagnostics

| Script | Purpose |
|--------|---------|
| `test_device_detection.py` | Device detection and cross-platform compatibility checks (MPS/CUDA/CPU) |

## Testing Specific Features

```bash
# Run inside the container directly
docker exec kg-api-dev pytest tests/ -k datetime    # Match pattern
docker exec kg-api-dev pytest tests/unit/ -v         # Verbose
docker exec kg-api-dev pytest tests/api/test_auth_utils.py  # Single file
```

## Related

- `make help` — all available developer targets
- `make lint` — static analysis (query linter + docstring coverage)
