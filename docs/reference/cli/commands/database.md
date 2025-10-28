# kg database

> Auto-generated

## database (db)

Database operations and information. Provides read-only queries for PostgreSQL + Apache AGE database health, statistics, and connection details.

**Usage:**
```bash
kg database [options]
```

**Subcommands:**

- `stats` - Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.
- `info` - Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.
- `health` - Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.

---

### stats

Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.

**Usage:**
```bash
kg stats [options]
```

### info

Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.

**Usage:**
```bash
kg info [options]
```

### health

Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.

**Usage:**
```bash
kg health [options]
```
