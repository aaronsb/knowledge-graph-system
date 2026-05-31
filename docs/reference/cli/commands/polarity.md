# kg polarity

> Auto-generated

## polarity

Analyze bidirectional semantic dimensions between concept poles

**Usage:**
```bash
kg polarity [options]
```

**Subcommands:**

- `analyze` - Project concepts onto axis formed by two opposing poles (e.g., Modern ↔ Traditional)

---

### analyze

Project concepts onto axis formed by two opposing poles (e.g., Modern ↔ Traditional)

**Usage:**
```bash
kg analyze [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--positive <concept-id>` | Positive pole concept ID | - |
| `--negative <concept-id>` | Negative pole concept ID | - |
| `--candidates <ids...>` | Specific concept IDs to project (space-separated) | - |
| `--no-auto-discover` | Disable auto-discovery of related concepts | - |
| `--max-candidates <number>` | Maximum candidates for auto-discovery | `"20"` |
| `--max-hops <number>` | Maximum graph hops for auto-discovery (1-3) | `"1"` |
| `--discovery-mode <mode>` | Discovery strategy: conservative (pure degree), balanced (80/20 - DEFAULT), novelty (pure random) | `"balanced"` |
| `--discovery-pct <number>` | Custom discovery percentage (0.0-1.0, overrides --discovery-mode) | - |
| `--max-workers <number>` | Maximum parallel workers for 2-hop queries | `"8"` |
| `--chunk-size <number>` | Concepts per worker chunk | `"20"` |
| `--timeout <number>` | Wall-clock timeout in seconds | `"120"` |
| `--save-artifact` | Save result as persistent artifact (uses async job) | - |
| `--json` | Output raw JSON instead of formatted text | - |
