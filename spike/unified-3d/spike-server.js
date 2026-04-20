// Minimal drop-in replacement for atlassian-graph's explorer-server.js.
// Serves only the endpoints the 3D explorer UI needs to mount and render
// against a static kg data export.
//
// Run: node spike-server.js
// UI expects it on :4000 (vite dev proxies /api → :4000).

import express from 'express';
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_PATH = join(__dirname, 'data', 'kg-graph.json');
const data = JSON.parse(readFileSync(DATA_PATH, 'utf8'));

console.log(`[spike] loaded ${data.nodes.length} nodes, ${data.edges.length} edges from ${DATA_PATH}`);

const byName = new Map(data.nodes.map(n => [n.name, n]));

const app = express();
app.use(express.json());

app.get('/api/graph', (req, res) => {
  const cap = req.query.cap ? parseInt(req.query.cap, 10) : null;
  let nodes = data.nodes;
  let edges = data.edges;
  if (cap && Number.isFinite(cap) && cap < nodes.length) {
    const sorted = [...nodes].sort((a, b) => b.degree - a.degree).slice(0, cap);
    const keep = new Set(sorted.map(n => n.name));
    nodes = sorted;
    edges = edges.filter(e => keep.has(e.from) && keep.has(e.to));
  }
  res.json({
    nodes,
    edges,
    meta: {
      totalTypes: data.nodes.length,
      keptTypes: nodes.length,
      edgeCount: edges.length,
      kinds: ['OBJECT'],
      includeRelay: false,
    },
  });
});

app.get('/api/type/:name', (req, res) => {
  const n = byName.get(req.params.name);
  if (!n) return res.status(404).json({ error: 'not found' });
  // Synthesize a minimal type-detail response matching the shape the sidebar
  // expects. kg concepts don't have "fields" in the graphql sense; we adapt
  // the relationship set as pseudo-fields so the detail panel renders.
  const outgoing = data.edges.filter(e => e.from === n.name).map(e => ({
    name: e.field,
    type: e.to,
    description: '',
  }));
  res.json({
    name: n.name,
    kind: n.kind || 'OBJECT',
    label: n.label || '',
    description: n.label || '',
    category: n.category,
    degree: n.degree,
    fields: outgoing,
    interfaces: [],
    connectionOf: null,
    wrappedBy: [],
  });
});

app.get('/api/stats', (_req, res) => {
  const degByCategory = {};
  for (const n of data.nodes) {
    degByCategory[n.category] = (degByCategory[n.category] || 0) + 1;
  }
  res.json({
    totalTypes: data.nodes.length,
    totalFields: data.edges.length,
    topByDegree: [...data.nodes].sort((a, b) => b.degree - a.degree).slice(0, 10),
    categoryCounts: degByCategory,
  });
});

// Stubs for endpoints the sidebar / query panel may probe but we don't need.
app.get('/api/search', (_req, res) => res.json({ types: [], fields: [], descriptions: [] }));
app.get('/api/categories', (_req, res) => {
  const counts = {};
  for (const n of data.nodes) counts[n.category] = (counts[n.category] || 0) + 1;
  res.json(Object.entries(counts).map(([name, count]) => ({ name, count })));
});
app.get('/api/specs', (_req, res) => res.json({ specs: [] }));
app.get('/api/query-log', (_req, res) => res.json({ count: 0, entries: [] }));

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[spike] listening on http://localhost:${PORT}`);
});
