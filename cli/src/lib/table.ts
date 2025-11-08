/**
 * Reusable Table Utility for CLI Output
 *
 * Provides a flexible, responsive table formatter with:
 * - Dynamic column width distribution
 * - Unicode-aware text padding
 * - Priority-based column sizing
 * - Semantic type-based formatting
 * - Integrated color theming
 */

import stringWidth from 'string-width';
import * as colors from '../cli/colors';
import { separator } from '../cli/colors';

/**
 * Column width strategy
 * - number: fixed width in characters
 * - 'auto': fit to content
 * - 'flex': flexible, shares remaining space
 */
export type ColumnWidth = number | 'auto' | 'flex';

/**
 * Column alignment
 */
export type ColumnAlign = 'left' | 'right' | 'center';

/**
 * Semantic column types for consistent formatting
 */
export type ColumnType =
  | 'text'           // Plain text with default color
  | 'job_id'         // Job ID (blue, monospace-like)
  | 'concept_id'     // Concept ID (blue, monospace-like)
  | 'user'           // User/client ID (purple)
  | 'heading'        // Section heading (purple/bright)
  | 'status'         // Job status with icons
  | 'timestamp'      // Date/time (dimmed)
  | 'count'          // Numeric count (colored by magnitude)
  | 'progress'       // Progress percentage
  | 'value';         // Generic value (yellow/gold)

/**
 * Column definition
 */
export interface TableColumn<T = any> {
  /** Column header text */
  header: string;

  /** Field accessor - can be key name or function */
  field: keyof T | ((row: T) => any);

  /** Semantic type for formatting (applied after truncation) */
  type?: ColumnType;

  /** Column width strategy (default: 'auto') */
  width?: ColumnWidth;

  /** Minimum column width */
  minWidth?: number;

  /** Maximum column width (for flex columns) */
  maxWidth?: number;

  /** Priority for flex space distribution (higher = more space, default: 1) */
  priority?: number;

  /** Text alignment (default: 'left') */
  align?: ColumnAlign;

  /** Custom formatter for complex cases (receives raw value, returns RAW string - formatting applied after) */
  customFormat?: (value: any, row: T) => string;

  /** Truncate with ellipsis if exceeds width (default: true) */
  truncate?: boolean;
}

/**
 * Table configuration
 */
export interface TableConfig<T = any> {
  /** Column definitions */
  columns: TableColumn<T>[];

  /** Spacing between columns (default: 2) */
  spacing?: number;

  /** Show header row (default: true) */
  showHeader?: boolean;

  /** Show separator lines (default: true) */
  showSeparator?: boolean;

  /** Terminal width (auto-detected if not provided) */
  terminalWidth?: number;

  /** Empty message when no data (default: 'No data') */
  emptyMessage?: string;
}

/**
 * Type formatters - apply color/style to raw truncated strings
 */
const typeFormatters: Record<ColumnType, (value: string, rawValue?: any) => string> = {
  text: (v) => v,
  job_id: (v) => colors.concept.id(v),
  concept_id: (v) => colors.concept.id(v),
  user: (v) => colors.ui.value(v),
  heading: (v) => colors.ui.value(v),
  status: (v, raw) => {
    // Format job status with icons
    switch (raw) {
      case 'completed': return colors.status.success('✓ completed');
      case 'failed': return colors.status.error('✗ failed');
      case 'processing': return colors.status.info('⚙ processing');
      case 'approved': return colors.status.success('✓ approved');
      case 'awaiting_approval': return colors.status.warning('⏸ awaiting');
      case 'pending': return colors.status.dim('○ pending');
      case 'queued': return colors.status.info('⋯ queued');
      case 'cancelled': return colors.status.dim('⊗ cancelled');
      default: return colors.status.dim(v);
    }
  },
  timestamp: (v, raw) => {
    // Use rawValue (not truncated string) for date parsing
    const d = new Date(raw || v);
    if (isNaN(d.getTime())) {
      return colors.status.dim('Invalid Date');
    }
    return colors.status.dim(d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }));
  },
  count: (v) => colors.coloredCount(parseInt(v)),
  progress: (v, raw) => {
    // Handle empty/undefined
    if (raw === undefined || raw === null || raw === '') {
      return colors.status.dim('-');
    }
    // Handle special icons for terminal states (passed as string)
    if (v === '✓') return colors.status.success('✓');
    if (v === '✗') return colors.status.error('✗');
    if (v === '⊗') return colors.status.warning('⊗');
    // Handle numeric progress
    return colors.status.info(`${v}%`);
  },
  value: (v) => colors.ui.value(v)
};

/**
 * Reusable Table Builder
 */
export class Table<T = any> {
  private config: Required<TableConfig<T>>;

  constructor(config: TableConfig<T>) {
    this.config = {
      spacing: 2,
      showHeader: true,
      showSeparator: true,
      terminalWidth: process.stdout.columns || 120,
      emptyMessage: 'No data',
      ...config
    };
  }

  /**
   * Render table to string array (one line per array element)
   */
  render(data: T[]): string[] {
    if (data.length === 0) {
      return [colors.status.dim(`\n${this.config.emptyMessage}\n`)];
    }

    const lines: string[] = [];
    const columnWidths = this.calculateColumnWidths(data);
    const columnSpacing = ' '.repeat(this.config.spacing);
    const sepWidth = this.config.terminalWidth - 4;

    // Header
    if (this.config.showHeader) {
      if (this.config.showSeparator) {
        lines.push('\n' + separator(sepWidth));
      }

      const headerRow = this.config.columns.map((col, i) =>
        this.padCell(colors.ui.header(col.header), columnWidths[i], col.align || 'left')
      ).join(columnSpacing);

      lines.push(headerRow);

      if (this.config.showSeparator) {
        lines.push(separator(sepWidth));
      }
    }

    // Data rows
    for (const row of data) {
      const cells = this.config.columns.map((col, i) => {
        const rawValue = this.getCellValue(row, col);

        // Step 1: Convert to string (custom format or default)
        let stringValue = col.customFormat
          ? col.customFormat(rawValue, row)
          : String(rawValue ?? '');

        // Step 2: Truncate if needed (working with plain strings)
        if (col.truncate !== false && stringValue.length > columnWidths[i]) {
          stringValue = stringValue.substring(0, columnWidths[i] - 3) + '...';
        }

        // Step 3: Apply type-based formatting (adds color/style)
        const formatted = col.type
          ? typeFormatters[col.type](stringValue, rawValue)
          : stringValue;

        // Step 4: Pad to column width (handles ANSI codes properly)
        return this.padCell(formatted, columnWidths[i], col.align || 'left');
      });

      lines.push(cells.join(columnSpacing));
    }

    // Footer separator
    if (this.config.showSeparator) {
      lines.push(separator(sepWidth));
      lines.push(colors.status.dim(`\nShowing ${data.length} row(s)\n`));
    }

    return lines;
  }

  /**
   * Print table directly to console
   */
  print(data: T[]): void {
    const lines = this.render(data);
    console.log(lines.join('\n'));
  }

  /**
   * Get cell value from row
   */
  private getCellValue(row: T, col: TableColumn<T>): any {
    if (typeof col.field === 'function') {
      return col.field(row);
    }
    return row[col.field];
  }

  /**
   * Calculate optimal column widths based on data and terminal size
   */
  private calculateColumnWidths(data: T[]): number[] {
    const { columns, spacing, terminalWidth } = this.config;

    // Step 1: Determine fixed-width columns
    const fixedWidths: (number | null)[] = columns.map(col => {
      if (typeof col.width === 'number') {
        return col.width;
      }
      return null;
    });

    // Step 2: Calculate auto-fit columns (fit to content)
    const autoWidths: (number | null)[] = columns.map((col, i) => {
      if (col.width === 'auto') {
        // Find max content width for this column (using raw strings before formatting)
        const headerWidth = stringWidth(col.header);
        const maxContentWidth = Math.max(
          headerWidth,
          ...data.map(row => {
            const rawValue = this.getCellValue(row, col);
            const stringValue = col.customFormat
              ? col.customFormat(rawValue, row)
              : String(rawValue ?? '');
            return stringValue.length;
          })
        );

        const constrainedWidth = Math.min(
          col.maxWidth || Infinity,
          Math.max(col.minWidth || 0, maxContentWidth)
        );

        return constrainedWidth;
      }
      return null;
    });

    // Step 3: Calculate total fixed space used
    const totalSpacing = spacing * (columns.length - 1);
    const usedWidth = fixedWidths.reduce((sum: number, w) => sum + (w || 0), 0) +
                      autoWidths.reduce((sum: number, w) => sum + (w || 0), 0) +
                      totalSpacing + 4; // 4 for margins

    const remainingWidth = Math.max(0, terminalWidth - usedWidth);

    // Step 4: Distribute remaining width to flex columns
    const flexColumns = columns
      .map((col, i) => ({ col, i }))
      .filter(({ col }) => col.width === 'flex' || col.width === undefined);

    if (flexColumns.length === 0) {
      // No flex columns, use fixed + auto widths
      return columns.map((col, i) => fixedWidths[i] ?? autoWidths[i] ?? 10);
    }

    // Calculate total priority
    const totalPriority = flexColumns.reduce((sum, { col }) => sum + (col.priority || 1), 0);

    // Distribute remaining width by priority
    const flexWidths: number[] = columns.map(() => 0);
    flexColumns.forEach(({ col, i }) => {
      const priority = col.priority || 1;
      const share = Math.floor((remainingWidth * priority) / totalPriority);
      const constrainedShare = Math.min(
        col.maxWidth || Infinity,
        Math.max(col.minWidth || 0, share)
      );
      flexWidths[i] = constrainedShare;
    });

    // Combine all widths
    return columns.map((col, i) =>
      fixedWidths[i] ?? autoWidths[i] ?? flexWidths[i] ?? 10
    );
  }

  /**
   * Pad cell text to width with alignment
   */
  private padCell(text: string, width: number, align: ColumnAlign): string {
    const visualWidth = stringWidth(text);
    const padding = Math.max(0, width - visualWidth);

    switch (align) {
      case 'right':
        return ' '.repeat(padding) + text;
      case 'center':
        const leftPad = Math.floor(padding / 2);
        const rightPad = padding - leftPad;
        return ' '.repeat(leftPad) + text + ' '.repeat(rightPad);
      case 'left':
      default:
        return text + ' '.repeat(padding);
    }
  }
}
