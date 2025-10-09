"""
Semantic Re-stitching - Intelligently reconnect dangling relationships

When restoring partial backups, external concept references can be reconnected
to similar concepts in the target database using vector similarity matching.

This uses the same concept matching algorithm as ingestion:
1. Detect external concept references (not in backup)
2. Check if similar concepts exist in target database
3. Offer to reconnect relationships to matched concepts
4. Optionally create placeholder concepts for unmatched references
"""

from typing import Dict, Any, List, Tuple, Optional
import json
import numpy as np

from .console import Console, Colors
from .age_ops import AGEConnection
from .age_client import AGEClient


class ConceptMatcher:
    """Match external concepts to similar concepts in target database"""

    def __init__(self, conn: AGEConnection, similarity_threshold: float = 0.85):
        """
        Initialize concept matcher

        Args:
            conn: AGE connection
            similarity_threshold: Minimum similarity for matching (default: 0.85)
        """
        self.conn = conn
        self.threshold = similarity_threshold

    def find_external_concepts(self, backup_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all external concept references in backup

        Args:
            backup_data: Parsed backup JSON

        Returns:
            List of external concept references with metadata
        """
        data = backup_data.get("data", {})
        internal_concept_ids = {c["concept_id"] for c in data.get("concepts", [])}

        external_refs = {}

        # Scan relationships for external concepts
        for rel in data.get("relationships", []):
            from_id = rel.get("from")
            to_id = rel.get("to")

            # Check 'from' concept
            if from_id not in internal_concept_ids:
                if from_id not in external_refs:
                    external_refs[from_id] = {
                        "concept_id": from_id,
                        "referencing_relationships": [],
                        "label": None,  # Will try to infer
                        "embedding": None
                    }
                external_refs[from_id]["referencing_relationships"].append({
                    "from": from_id,
                    "to": to_id,
                    "type": rel["type"],
                    "direction": "outgoing"
                })

            # Check 'to' concept
            if to_id not in internal_concept_ids:
                if to_id not in external_refs:
                    external_refs[to_id] = {
                        "concept_id": to_id,
                        "referencing_relationships": [],
                        "label": None,
                        "embedding": None
                    }
                external_refs[to_id]["referencing_relationships"].append({
                    "from": from_id,
                    "to": to_id,
                    "type": rel["type"],
                    "direction": "incoming"
                })

        return list(external_refs.values())

    def match_concept_in_database(
        self,
        external_concept: Dict[str, Any],
        client: AGEClient
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar concept in target database using vector similarity

        Args:
            external_concept: External concept metadata
            client: AGE client

        Returns:
            Matched concept with similarity score, or None if no match
        """
        # If we have an embedding for the external concept, use it
        if external_concept.get("embedding"):
            embedding = external_concept["embedding"]
        elif external_concept.get("label"):
            # Generate embedding from label
            embedding = self.conn.generate_embedding(external_concept["label"])
        else:
            # Can't match without label or embedding
            return None

        # Fetch all concepts with embeddings
        query = """
            MATCH (c:Concept)
            WHERE c.embedding IS NOT NULL
            RETURN c.concept_id as concept_id,
                   c.label as label,
                   c.embedding as embedding
        """
        results = client._execute_cypher(query)

        if not results:
            return None

        # Compute cosine similarity in Python
        embedding_vec = np.array(embedding)
        best_match = None
        best_score = self.threshold

        for record in results:
            concept_id = str(record.get("concept_id", "")).strip('"')
            label = str(record.get("label", "")).strip('"')
            embedding_str = str(record.get("embedding", "[]"))

            try:
                candidate_embedding = json.loads(embedding_str)
                candidate_vec = np.array(candidate_embedding)

                # Cosine similarity
                similarity = float(np.dot(embedding_vec, candidate_vec) /
                                 (np.linalg.norm(embedding_vec) * np.linalg.norm(candidate_vec)))

                if similarity > best_score:
                    best_score = similarity
                    best_match = {
                        "concept_id": concept_id,
                        "label": label,
                        "similarity": similarity
                    }
            except (json.JSONDecodeError, ValueError):
                continue

        return best_match

    def create_restitch_plan(
        self,
        external_concepts: List[Dict[str, Any]],
        client: AGEClient
    ) -> Dict[str, Any]:
        """
        Create re-stitching plan for external concepts

        Args:
            external_concepts: List of external concept references
            client: AGE client

        Returns:
            Re-stitching plan with matches and recommendations
        """
        plan = {
            "total_external": len(external_concepts),
            "matched": [],
            "unmatched": [],
            "statistics": {
                "high_confidence": 0,  # > 0.95
                "medium_confidence": 0,  # 0.85-0.95
                "no_match": 0
            }
        }

        Console.info(f"Analyzing {len(external_concepts)} external concept references...")

        for ext_concept in external_concepts:
            match = self.match_concept_in_database(ext_concept, client)

            if match:
                similarity = match["similarity"]
                restitch_info = {
                    "external_id": ext_concept["concept_id"],
                    "target_id": match["concept_id"],
                    "target_label": match["label"],
                    "similarity": similarity,
                    "relationship_count": len(ext_concept["referencing_relationships"]),
                    "relationships": ext_concept["referencing_relationships"]
                }

                plan["matched"].append(restitch_info)

                if similarity > 0.95:
                    plan["statistics"]["high_confidence"] += 1
                else:
                    plan["statistics"]["medium_confidence"] += 1
            else:
                plan["unmatched"].append({
                    "external_id": ext_concept["concept_id"],
                    "relationship_count": len(ext_concept["referencing_relationships"]),
                    "relationships": ext_concept["referencing_relationships"]
                })
                plan["statistics"]["no_match"] += 1

        return plan

    def print_restitch_plan(self, plan: Dict[str, Any]):
        """Print re-stitching plan to console"""
        Console.section("Semantic Re-stitching Plan")

        Console.info(f"Found {plan['total_external']} external concept references")

        # Statistics
        stats = plan["statistics"]
        Console.info("\nMatching Results:")
        Console.key_value("  High confidence (>95%)", str(stats["high_confidence"]),
                        Colors.BOLD, Colors.OKGREEN)
        Console.key_value("  Medium confidence (85-95%)", str(stats["medium_confidence"]),
                        Colors.BOLD, Colors.WARNING)
        Console.key_value("  No match", str(stats["no_match"]),
                        Colors.BOLD, Colors.FAIL)

        # Show matches
        if plan["matched"]:
            Console.warning("\nProposed Re-stitching:")
            for i, match in enumerate(plan["matched"][:5], 1):
                color = Colors.OKGREEN if match["similarity"] > 0.95 else Colors.WARNING
                print(f"\n  {i}. External: {match['external_id']}")
                print(f"     → Connect to: {color}{match['target_label']}{Colors.ENDC}")
                print(f"     Similarity: {color}{match['similarity']:.1%}{Colors.ENDC}")
                print(f"     Affects {match['relationship_count']} relationship(s)")

            if len(plan["matched"]) > 5:
                Console.info(f"\n  ... and {len(plan['matched']) - 5} more matches")

        # Show unmatched
        if plan["unmatched"]:
            Console.warning(f"\nUnmatched ({len(plan['unmatched'])}):")
            for i, unmatch in enumerate(plan["unmatched"][:5], 1):
                print(f"  {i}. {unmatch['external_id']} ({unmatch['relationship_count']} relationships)")

            if len(plan["unmatched"]) > 5:
                Console.info(f"  ... and {len(plan['unmatched']) - 5} more")

            Console.warning("\n  Options for unmatched concepts:")
            print("    1. Leave relationships dangling (skip)")
            print("    2. Create placeholder concepts")
            print("    3. Manual review required")

    def execute_restitch(
        self,
        plan: Dict[str, Any],
        client: AGEClient,
        create_placeholders: bool = False
    ) -> Dict[str, int]:
        """
        Execute re-stitching plan

        Args:
            plan: Re-stitching plan from create_restitch_plan()
            client: AGE client
            create_placeholders: If True, create placeholder concepts for unmatched

        Returns:
            Statistics: restitched_count, placeholder_count
        """
        stats = {
            "restitched": 0,
            "placeholders": 0,
            "skipped": 0
        }

        # Re-stitch matched concepts
        Console.info("\nRe-stitching matched concepts...")
        for match in plan["matched"]:
            for rel in match["relationships"]:
                # Determine which concept to update
                if rel["direction"] == "incoming":
                    # External concept is the 'to' side
                    # Update relationship: (from)-[type]->(external) → (from)-[type]->(target)
                    query = """
                        MATCH (from_concept:Concept {concept_id: $from_id})
                        MATCH (target_concept:Concept {concept_id: $target_id})
                        MERGE (from_concept)-[r:""" + rel["type"] + """]->(target_concept)
                        RETURN count(r) as created
                    """
                    client._execute_cypher(query, params={"from_id": rel["from"], "target_id": match["target_id"]})
                else:
                    # External concept is the 'from' side
                    # Update relationship: (external)-[type]->(to) → (target)-[type]->(to)
                    query = """
                        MATCH (to_concept:Concept {concept_id: $to_id})
                        MATCH (target_concept:Concept {concept_id: $target_id})
                        MERGE (target_concept)-[r:""" + rel["type"] + """]->(to_concept)
                        RETURN count(r) as created
                    """
                    client._execute_cypher(query, params={"to_id": rel["to"], "target_id": match["target_id"]})

            stats["restitched"] += len(match["relationships"])
            Console.progress(stats["restitched"],
                           sum(len(m["relationships"]) for m in plan["matched"]),
                           "Re-stitching")

        # Handle unmatched
        if create_placeholders and plan["unmatched"]:
            Console.info("\nCreating placeholder concepts for unmatched references...")
            for unmatch in plan["unmatched"]:
                # Create placeholder concept (no embedding, marked as placeholder)
                query = """
                    MERGE (c:Concept {concept_id: $concept_id})
                    ON CREATE SET c.label = 'Placeholder: ' + $concept_id,
                                  c.placeholder = true,
                                  c.search_terms = []
                    RETURN c
                """
                client._execute_cypher(query, params={"concept_id": unmatch["external_id"]})
                stats["placeholders"] += 1
        else:
            stats["skipped"] = len(plan["unmatched"])

        return stats
