-- ================================================================
-- Semantic Path Gradient Analysis - PostgreSQL Extensions
-- ================================================================
--
-- Custom functions for gradient-based analysis of concept paths
-- Requires: pgvector extension
--
-- Usage:
--   psql -U admin -d knowledge_graph -f sql_functions.sql
--

-- ================================================================
-- Basic Gradient Operations
-- ================================================================

-- Semantic gradient (vector difference)
CREATE OR REPLACE FUNCTION semantic_gradient(emb1 vector, emb2 vector)
RETURNS vector AS $$
BEGIN
  RETURN emb2 - emb1;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION semantic_gradient IS
  'Calculate semantic gradient (directional derivative) between two embeddings';


-- Gradient magnitude (L2 distance)
CREATE OR REPLACE FUNCTION gradient_magnitude(emb1 vector, emb2 vector)
RETURNS float AS $$
BEGIN
  RETURN l2_distance(emb1, emb2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION gradient_magnitude IS
  'Calculate magnitude of semantic gradient between two embeddings';


-- ================================================================
-- Path Analysis Functions
-- ================================================================

-- Path coherence score
CREATE OR REPLACE FUNCTION path_coherence(embeddings vector[])
RETURNS float AS $$
DECLARE
  distances float[] := '{}';
  mean_dist float;
  variance float;
  coherence float;
BEGIN
  -- Need at least 2 embeddings
  IF array_length(embeddings, 1) < 2 THEN
    RETURN NULL;
  END IF;

  -- Calculate pairwise distances
  FOR i IN 1..array_length(embeddings, 1)-1 LOOP
    distances := distances || l2_distance(embeddings[i], embeddings[i+1]);
  END LOOP;

  -- Calculate statistics
  SELECT AVG(d), VARIANCE(d) INTO mean_dist, variance FROM unnest(distances) AS d;

  -- Coherence = 1 - normalized variance
  -- High coherence (near 1) = consistent spacing
  -- Low coherence (near 0) = erratic jumps
  coherence := 1.0 - (variance / (mean_dist + 0.0001));

  RETURN coherence;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION path_coherence IS
  'Calculate coherence score for a path (1 = perfectly consistent spacing, 0 = erratic)';


-- Find weak links in a reasoning path
CREATE OR REPLACE FUNCTION find_weak_links(
  concept_ids text[],
  threshold_sigma float DEFAULT 2.0
)
RETURNS TABLE(
  step_index int,
  source_id text,
  target_id text,
  source_label text,
  target_label text,
  semantic_gap float,
  severity_sigma float
) AS $$
DECLARE
  embeddings vector[];
  distances float[];
  mean_dist float;
  std_dist float;
BEGIN
  -- Fetch embeddings in order
  SELECT array_agg(c.embedding ORDER BY idx)
  INTO embeddings
  FROM unnest(concept_ids) WITH ORDINALITY AS t(id, idx)
  JOIN concepts c ON c.concept_id = t.id;

  -- Calculate distances between consecutive embeddings
  FOR i IN 1..array_length(embeddings, 1)-1 LOOP
    distances[i] := l2_distance(embeddings[i], embeddings[i+1]);
  END LOOP;

  -- Calculate statistics
  SELECT AVG(d), STDDEV(d) INTO mean_dist, std_dist FROM unnest(distances) AS d;

  -- Return outliers (distances > threshold_sigma * std_dev above mean)
  FOR i IN 1..array_length(distances, 1) LOOP
    IF distances[i] > mean_dist + threshold_sigma * std_dist THEN
      RETURN QUERY
      SELECT
        i::int,
        concept_ids[i],
        concept_ids[i+1],
        c1.label,
        c2.label,
        distances[i],
        (distances[i] - mean_dist) / (std_dist + 0.0001)
      FROM concepts c1, concepts c2
      WHERE c1.concept_id = concept_ids[i]
        AND c2.concept_id = concept_ids[i+1];
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_weak_links IS
  'Identify weak links (large semantic gaps) in a reasoning path';


-- ================================================================
-- Relationship Quality Analysis
-- ================================================================

-- Score all relationships by semantic gap
CREATE OR REPLACE VIEW relationship_quality AS
SELECT
  r.relationship_type,
  c1.label as source_label,
  c2.label as target_label,
  l2_distance(c1.embedding, c2.embedding) as semantic_gap,
  CASE
    WHEN l2_distance(c1.embedding, c2.embedding) < 0.3 THEN 'Strong'
    WHEN l2_distance(c1.embedding, c2.embedding) < 0.5 THEN 'Moderate'
    ELSE 'Weak'
  END as strength,
  r.source_concept_id,
  r.target_concept_id
FROM relationships r
JOIN concepts c1 ON r.source_concept_id = c1.concept_id
JOIN concepts c2 ON r.target_concept_id = c2.concept_id
WHERE c1.embedding IS NOT NULL
  AND c2.embedding IS NOT NULL;

COMMENT ON VIEW relationship_quality IS
  'Score all relationships by semantic distance (smaller = stronger)';


-- ================================================================
-- Example Queries
-- ================================================================

/*

-- Example 1: Find weak relationships
SELECT * FROM relationship_quality
WHERE strength = 'Weak'
ORDER BY semantic_gap DESC
LIMIT 20;


-- Example 2: Analyze a specific path
WITH path AS (
  SELECT ARRAY[
    'concept-id-1',
    'concept-id-2',
    'concept-id-3',
    'concept-id-4'
  ] as concept_ids
)
SELECT
  array_to_string(
    array_agg(c.label ORDER BY idx),
    ' → '
  ) as reasoning_path,
  path_coherence(array_agg(c.embedding ORDER BY idx)) as coherence_score
FROM path,
  unnest(concept_ids) WITH ORDINALITY AS t(id, idx)
  JOIN concepts c ON c.concept_id = t.id;


-- Example 3: Find weak links in a path
SELECT *
FROM find_weak_links(ARRAY[
  'concept-id-1',
  'concept-id-2',
  'concept-id-3',
  'concept-id-4'
], 2.0);


-- Example 4: Compare relationship types by average semantic gap
SELECT
  relationship_type,
  COUNT(*) as count,
  AVG(semantic_gap) as avg_gap,
  STDDEV(semantic_gap) as std_gap,
  MIN(semantic_gap) as min_gap,
  MAX(semantic_gap) as max_gap
FROM relationship_quality
GROUP BY relationship_type
ORDER BY avg_gap ASC;


-- Example 5: Find concepts that could bridge large gaps
WITH weak_relationships AS (
  SELECT
    source_concept_id,
    target_concept_id,
    semantic_gap
  FROM relationship_quality
  WHERE semantic_gap > 0.6
  LIMIT 10
)
SELECT
  wr.source_concept_id,
  wr.target_concept_id,
  wr.semantic_gap as direct_gap,
  c.concept_id as bridge_id,
  c.label as bridge_label,
  (
    l2_distance(c1.embedding, c.embedding) +
    l2_distance(c.embedding, c2.embedding)
  ) as detour_distance,
  wr.semantic_gap - (
    l2_distance(c1.embedding, c.embedding) +
    l2_distance(c.embedding, c2.embedding)
  ) as improvement
FROM weak_relationships wr
JOIN concepts c1 ON wr.source_concept_id = c1.concept_id
JOIN concepts c2 ON wr.target_concept_id = c2.concept_id
CROSS JOIN concepts c
WHERE c.concept_id NOT IN (wr.source_concept_id, wr.target_concept_id)
  AND c.embedding IS NOT NULL
  -- Detour must be better than direct path
  AND (
    l2_distance(c1.embedding, c.embedding) +
    l2_distance(c.embedding, c2.embedding)
  ) < wr.semantic_gap * 1.2
ORDER BY improvement DESC
LIMIT 50;

*/

-- ================================================================
-- Cleanup (if needed)
-- ================================================================

/*
-- To remove these functions:
DROP FUNCTION IF EXISTS semantic_gradient(vector, vector);
DROP FUNCTION IF EXISTS gradient_magnitude(vector, vector);
DROP FUNCTION IF EXISTS path_coherence(vector[]);
DROP FUNCTION IF EXISTS find_weak_links(text[], float);
DROP VIEW IF EXISTS relationship_quality;
*/
