#!/usr/bin/env node
/**
 * Generate version info from git at build time
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function getGitInfo() {
  const info = { tag: 'dev', commit: undefined };

  try {
    // Get short commit hash
    info.commit = execSync('git rev-parse --short HEAD', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore']
    }).trim();
  } catch {
    // Not in a git repo or git not available
  }

  try {
    // Try to get exact tag first
    info.tag = execSync('git describe --tags --exact-match', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore']
    }).trim();
  } catch {
    // Not on a tag, try to get nearest tag
    try {
      info.tag = execSync('git describe --tags', {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'ignore']
      }).trim();
    } catch {
      // No tags available - use 'dev' as default
      info.tag = 'dev';
    }
  }

  return info;
}

const gitInfo = getGitInfo();
const buildTime = new Date().toISOString();

const content = `/**
 * Auto-generated version info
 * Generated at build time - DO NOT EDIT
 */

export const VERSION_INFO = {
  tag: '${gitInfo.tag}',
  commit: ${gitInfo.commit ? `'${gitInfo.commit}'` : 'undefined'},
  buildTime: '${buildTime}',
} as const;
`;

const outputPath = path.join(__dirname, '../src/version.ts');
fs.writeFileSync(outputPath, content, 'utf8');

console.log(`Generated version info: ${gitInfo.tag} ${gitInfo.commit || '(no commit)'}`);
