---
status: Accepted
date: 2025-10-09
deciders:
  - Development Team
related:
  - ADR-013
  - ADR-018
---

# ADR-019: Type-Based Table Formatting System

## Overview

Terminal tables should be simple, but they're surprisingly tricky to get right. When you apply color codes to text and then try to truncate it to fit column widths, you end up cutting through the ANSI escape sequences—leaving broken formatting and misaligned columns. Unicode characters throw off width calculations. Every command reimplements its own table logic.

The problem gets worse when you realize tables appear everywhere in the CLI: job listings, search results, ontology information, and more. Each one was handling formatting slightly differently, with custom color logic applied before truncation, leading to the same bugs over and over.

This ADR introduces semantic column types—like `job_id`, `status`, or `timestamp`—that know how to format their content. The key insight: truncate plain text first, then apply colors and styling. This way, width calculations work correctly, formatting never breaks, and all tables across the entire CLI use consistent colors and formatting rules defined in one place.

---

## Context

The `kg` CLI displays tabular data in multiple commands (`kg jobs list`, `kg ontology list`, `kg search`, etc.). Initial implementations used custom formatting logic with ANSI color codes applied before truncation, which caused:

1. **Truncation corruption** - Truncating colored strings broke ANSI escape sequences
2. **Alignment issues** - Unicode characters and ANSI codes made width calculations incorrect
3. **Code duplication** - Each table re-implemented similar formatting logic
4. **Maintenance burden** - Changing color schemes required updating multiple files

Example of the problematic pattern:
```typescript
// BEFORE: Formatter returns colored string
formatter: (status) => colors.status.success('✓ completed')
// Then truncate colored string → broken ANSI codes
```

## Decision

Implement a **type-based table formatting system** that separates concerns:

1. **Semantic column types** - Define types like `job_id`, `status`, `timestamp`, `count`
2. **Format after truncate** - Apply colors/styles only after width calculations
3. **Reusable Table class** - Single implementation for all CLI tables
4. **Declarative API** - Simple column configuration with automatic formatting

### Architecture

```typescript
// Flow: Raw Data → Convert to String → Truncate → Apply Type Formatting → Pad

// Type formatters (centralized)
const typeFormatters: Record<ColumnType, (value: string, rawValue?: any) => string> = {
  job_id: (v) => colors.concept.id(v),
  status: (v, raw) => {
    switch (raw) {
      case 'completed': return colors.status.success('✓ completed');
      case 'failed': return colors.status.error('✗ failed');
      // ...
    }
  },
  timestamp: (v) => colors.status.dim(new Date(v).toLocaleString(...)),
  // ...
};

// Declarative column definition
const table = new Table<JobStatus>({
  columns: [
    {
      header: 'Job ID',
      field: 'job_id',
      type: 'job_id',        // Semantic type
      width: 'flex',
      priority: 2
    },
    {
      header: 'Status',
      field: 'status',
      type: 'status',        // Auto-formats with icons + colors
      width: 18
    }
  ]
});

table.print(jobs);  // That's it!
```

### Column Types

| Type | Purpose | Example Output |
|------|---------|----------------|
| `text` | Plain text, no formatting | `Some text` |
| `job_id` | Job/UUID identifiers | `job_abc123` (blue) |
| `concept_id` | Concept identifiers | `concept_xyz` (blue) |
| `user` | User/client names | `username` (purple) |
| `heading` | Section headings | `Ontology Name` (purple) |
| `status` | Job status with icons | `✓ completed` (green) |
| `timestamp` | Date/time values | `Jan 9, 10:30 AM` (dimmed) |
| `count` | Numeric counts | `42` (colored by magnitude) |
| `progress` | Progress percentages | `75%` (info color) |
| `value` | Generic values | `some_value` (yellow) |

### Processing Pipeline

```typescript
// In Table.render():
for (const row of data) {
  const cells = columns.map((col, i) => {
    const rawValue = getCellValue(row, col);

    // Step 1: Convert to string (custom or default)
    let stringValue = col.customFormat
      ? col.customFormat(rawValue, row)
      : String(rawValue ?? '');

    // Step 2: Truncate plain string
    if (stringValue.length > columnWidths[i]) {
      stringValue = stringValue.substring(0, columnWidths[i] - 3) + '...';
    }

    // Step 3: Apply type formatting (adds colors)
    const formatted = col.type
      ? typeFormatters[col.type](stringValue, rawValue)
      : stringValue;

    // Step 4: Pad (handles ANSI codes via string-width)
    return padCell(formatted, columnWidths[i]);
  });
}
```

### Custom Formatting

For complex cases, use `customFormat` to transform **before** type formatting:

```typescript
{
  header: 'Progress',
  field: (job) => job.progress?.percent,
  type: 'progress',
  customFormat: (percent, job) => {
    // Custom logic returns RAW string
    if (job.status === 'completed') return '✓';
    return percent !== undefined ? String(percent) : '-';
  }
  // Type formatter applies colors after truncation
}
```

## Implementation

### Files Modified

- **`client/src/lib/table.ts`** (340 lines)
  - `ColumnType` enum with 10 semantic types
  - `typeFormatters` centralized formatting logic
  - `Table<T>` class with type-based rendering
  - Unicode-aware padding using `string-width` package

- **`client/src/cli/jobs.ts`**
  - Refactored `displayJobsList()` from 100+ lines to ~70 lines
  - Removed custom `colorizeStatus()` and `getProgressString()` helpers
  - Declarative column definitions using types

- **`client/src/lib/table-example.ts`**
  - Example patterns for jobs, ontologies, search results, backups

### Dependencies

- **`string-width`** (v8.1.0) - Unicode-aware string width calculation for proper padding

## Consequences

### Positive

✅ **No ANSI parsing needed** - Truncate plain strings, then apply colors
✅ **Consistent formatting** - All tables use same color scheme
✅ **Maintainable** - Change colors in one place
✅ **Reusable** - Single `Table` class for all CLI output
✅ **Type-safe** - TypeScript generics for row types
✅ **Responsive** - Dynamic column widths based on terminal size
✅ **Clean API** - Declarative column definitions

### Negative

⚠️ **Learning curve** - Developers must learn type system
⚠️ **Type constraints** - Adding new types requires updating central enum
⚠️ **Abstraction overhead** - Simple tables have slight overhead vs inline formatting

### Neutral

📋 **Migration path** - Existing tables must be refactored to use new system
📋 **Documentation** - Need examples for common table patterns

## Usage Examples

### Simple Table (Ontologies)
```typescript
const table = new Table({
  columns: [
    { header: 'Ontology', field: 'ontology', type: 'heading', width: 'flex' },
    { header: 'Concepts', field: 'concept_count', type: 'count', width: 10, align: 'right' }
  ]
});
table.print(ontologies);
```

### Complex Table (Search Results)
```typescript
const table = new Table({
  columns: [
    { header: 'Concept', field: 'label', type: 'value', width: 'flex', priority: 2 },
    { header: 'Similarity', field: 'score', width: 12, align: 'right',
      customFormat: (s) => `${(s * 100).toFixed(1)}%` }
  ]
});
table.print(results);
```

## Migration Guide

### Before (Old Pattern)
```typescript
import { formatters } from '../lib/table';

const table = new Table({
  columns: [
    {
      header: 'Status',
      field: 'status',
      width: 18,
      formatter: (status) => formatters.jobStatus(status)  // Returns colored string
    }
  ]
});
```

### After (New Pattern)
```typescript
const table = new Table({
  columns: [
    {
      header: 'Status',
      field: 'status',
      type: 'status',     // Semantic type
      width: 18
      // No formatter needed!
    }
  ]
});
```

## Future Enhancements

- [ ] Add `ontology` type for ontology names (distinct from `heading`)
- [ ] Add `path` type for file paths
- [ ] Add `url` type for URLs
- [ ] Support custom type formatters via config
- [ ] Add `align: 'auto'` to auto-detect alignment from type
- [ ] Table themes (compact, detailed, minimal)

## References

- Implementation: `client/src/lib/table.ts`
- Example usage: `client/src/cli/jobs.ts:76-134`
- Package: `string-width` v8.1.0 (Unicode width)
- Related: ADR-013 (Unified TypeScript Client)
