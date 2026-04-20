#!/usr/bin/env bash
# Export kg concepts + relationships in atlassian-graph shape:
#   node: { name, kind, category, degree }
#   edge: { from, field, to }
#
# kg.concept.concept_id → name
# kg.concept.label      → stored as 'label' field (ref UI tolerates extras)
# source-document hash prefix → category (synthesized; real kg ontology_category
#   is mostly 'uncategorized' in this dataset, so we group by source doc to
#   exercise the palette mapping)
# kg.relationship_type  → field (atlassian uses 'field' as the edge label)

set -euo pipefail

OUT_DIR="$(dirname "$0")/data"
mkdir -p "$OUT_DIR"

# AGE note: we cast agtype → text → jsonb. This works on the AGE image pinned
# in this repo (see CLAUDE.md). Across AGE versions this cast can emit numeric
# type annotations or unquoted keys that break jsonb parsing; if this script
# starts failing after an AGE upgrade, switch to the kg REST API as the data
# source instead of SQL.
# Degree uses an undirected match (c)-[r]-() — each relationship is counted
# twice (once from each endpoint) when summed across nodes, which matches how
# the reference renderer scales node size.
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph -qtA <<'SQL' > "$OUT_DIR/kg-raw.jsonl"
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT row_to_json(t) FROM (
  SELECT 'node' AS kind, (x.n::text)::jsonb AS data
  FROM cypher('knowledge_graph', $$
    MATCH (c:Concept)
    OPTIONAL MATCH (c)-[r]-()
    WITH c, count(r) AS degree
    RETURN {
      concept_id: c.concept_id,
      label: c.label,
      ontology: coalesce(c.ontology_category, c.category, 'uncategorized'),
      degree: degree
    } AS n
  $$) AS x(n agtype)
  UNION ALL
  SELECT 'edge' AS kind, (y.e::text)::jsonb AS data
  FROM cypher('knowledge_graph', $$
    MATCH (a:Concept)-[r]->(b:Concept)
    RETURN {
      from: a.concept_id,
      to: b.concept_id,
      type: type(r)
    } AS e
  $$) AS y(e agtype)
) t;
SQL

python3 - "$OUT_DIR/kg-raw.jsonl" "$OUT_DIR/kg-graph.json" <<'PY'
import json, sys, re, hashlib

src, dst = sys.argv[1], sys.argv[2]
nodes, edges = [], []

# atlassian-graph's palette.jsx has a fixed 16-category enum. Until we wire in
# kg's own palette, remap kg source-document buckets into these slots so we get
# color variety instead of every node falling to 'uncategorized'.
ATLASSIAN_CATEGORIES = [
    'core_products', 'identity_user', 'search_discovery', 'development_devops',
    'project_work', 'content_knowledge', 'ai_intelligence', 'apps_marketplace',
    'feeds_activity', 'analytics_insights', 'collaboration', 'administration',
    'specialized_tools', 'support_help', 'meta_system', 'uncategorized',
]

def source_bucket(cid, _seen={}):
    m = re.match(r'^sha256:([^_]+)', cid or '')
    if not m:
        return 'uncategorized'
    key = m.group(1)
    if key not in _seen:
        idx = len(_seen) % (len(ATLASSIAN_CATEGORIES) - 1)  # reserve last slot
        _seen[key] = ATLASSIAN_CATEGORIES[idx]
    return _seen[key]

with open(src) as f:
    raw_lines = f.readlines()
for line in raw_lines:
    line = line.strip()
    if not line:
        continue
    row = json.loads(line)
    d = row['data']
    if row['kind'] == 'node':
        # atlassian-graph shape. We promote source bucket to category so the
        # palette actually has variety; the real ontology_category is mostly
        # uncategorized in this dataset and that defeats the visual test.
        bucket = source_bucket(d.get('concept_id'))
        nodes.append({
            'name': d['concept_id'],
            'label': d.get('label', ''),
            'kind': 'OBJECT',
            'category': bucket,
            'ontology': d.get('ontology', 'uncategorized'),
            'degree': d.get('degree', 0),
        })
    else:
        edges.append({
            'from': d['from'],
            'field': d.get('type', 'RELATES'),
            'to': d['to'],
        })

# Build category index for /api/type responses
cat_counts = {}
for n in nodes:
    cat_counts[n['category']] = cat_counts.get(n['category'], 0) + 1

out = {
    'nodes': nodes,
    'edges': edges,
    'meta': {
        'totalTypes': len(nodes),
        'keptTypes': len(nodes),
        'edgeCount': len(edges),
        'categories': sorted(cat_counts.items(), key=lambda x: -x[1]),
    },
}
with open(dst, 'w') as f:
    json.dump(out, f, indent=2)
print(f"wrote {dst}: {len(nodes)} nodes, {len(edges)} edges, {len(cat_counts)} source buckets")
PY
