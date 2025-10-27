#!/usr/bin/env python3
"""
Quick verification script for Phase 3 vocabulary graph migration.
Checks that :VocabType and :VocabCategory nodes were created successfully.
"""

import psycopg2
import os

# Database connection
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    database=os.getenv("POSTGRES_DB", "knowledge_graph"),
    user=os.getenv("POSTGRES_USER", "admin"),
    password=os.getenv("POSTGRES_PASSWORD", "password123")
)

cursor = conn.cursor()

# Load AGE extension
cursor.execute("LOAD 'age'")
cursor.execute("SET search_path = ag_catalog, public")

print("=" * 60)
print("Phase 3 Vocabulary Graph Verification")
print("=" * 60)
print()

# Count VocabType nodes
cursor.execute("""
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (v:VocabType)
        RETURN count(v) as total
    $$) as (total agtype)
""")
vocab_type_count = cursor.fetchone()[0]
print(f"✓ VocabType nodes: {vocab_type_count}")

# Count VocabCategory nodes
cursor.execute("""
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (c:VocabCategory)
        RETURN count(c) as total
    $$) as (total agtype)
""")
vocab_cat_count = cursor.fetchone()[0]
print(f"✓ VocabCategory nodes: {vocab_cat_count}")

# Count IN_CATEGORY relationships
cursor.execute("""
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH ()-[r:IN_CATEGORY]->()
        RETURN count(r) as total
    $$) as (total agtype)
""")
rel_count = cursor.fetchone()[0]
print(f"✓ IN_CATEGORY relationships: {rel_count}")

print()

# Compare with SQL
cursor.execute("SELECT COUNT(*) FROM kg_api.relationship_vocabulary")
sql_count = cursor.fetchone()[0]
print(f"SQL vocabulary table has {sql_count} types")

print()
print("=" * 60)
if int(str(vocab_type_count)) == sql_count:
    print("✅ SUCCESS: Graph vocabulary matches SQL vocabulary!")
else:
    print(f"⚠️  WARNING: Mismatch - Graph has {vocab_type_count}, SQL has {sql_count}")
print("=" * 60)

cursor.close()
conn.close()
