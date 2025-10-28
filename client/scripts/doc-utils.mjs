/**
 * Documentation Generation Utilities
 *
 * Shared utilities for CLI and MCP doc generators.
 */

import fs from 'fs';
import crypto from 'crypto';

/**
 * Normalize content by removing timestamps and dynamic content
 * for comparison purposes
 */
function normalizeContent(content) {
  return content
    // Remove ISO dates (e.g., "2025-10-28")
    .replace(/\d{4}-\d{2}-\d{2}/g, 'DATE')
    // Remove "Last updated:" lines
    .replace(/Last updated:.*$/gm, 'Last updated: DATE')
    // Remove "Generated:" lines
    .replace(/Generated:.*$/gm, 'Generated: DATE')
    // Normalize whitespace
    .replace(/\s+$/gm, '')  // Trim trailing whitespace
    .trim();
}

/**
 * Calculate content hash (excluding dynamic parts)
 */
function contentHash(content) {
  const normalized = normalizeContent(content);
  return crypto.createHash('md5').update(normalized).digest('hex');
}

/**
 * Smart write - only write if content actually changed
 * Returns true if file was written, false if skipped
 */
export function smartWrite(filePath, newContent) {
  // If file doesn't exist, write it
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, newContent);
    return { written: true, reason: 'new file' };
  }

  // Read existing content
  const existingContent = fs.readFileSync(filePath, 'utf-8');

  // Compare hashes (normalized to ignore timestamps)
  const existingHash = contentHash(existingContent);
  const newHash = contentHash(newContent);

  if (existingHash === newHash) {
    return { written: false, reason: 'unchanged' };
  }

  // Content changed, write it
  fs.writeFileSync(filePath, newContent);
  return { written: true, reason: 'updated' };
}

/**
 * Smart write with stats tracking
 */
export class DocWriter {
  constructor() {
    this.stats = {
      new: 0,
      updated: 0,
      unchanged: 0,
      total: 0
    };
  }

  write(filePath, content) {
    const result = smartWrite(filePath, content);
    this.stats.total++;

    if (!result.written) {
      this.stats.unchanged++;
    } else if (result.reason === 'new file') {
      this.stats.new++;
    } else {
      this.stats.updated++;
    }

    return result;
  }

  getStats() {
    return this.stats;
  }

  printStats() {
    const s = this.stats;
    console.log(`\n📊 Documentation Stats:`);
    console.log(`   Total files: ${s.total}`);
    console.log(`   ✅ New: ${s.new}`);
    console.log(`   ✏️  Updated: ${s.updated}`);
    console.log(`   ⏭️  Unchanged: ${s.unchanged}`);

    if (s.unchanged > 0) {
      console.log(`   (Skipped ${s.unchanged} files to avoid git churn)`);
    }
  }
}
