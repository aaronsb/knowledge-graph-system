"""
Database integrity validation and repair.

Runtime checks on the live graph (post-restore and on demand) to detect and
repair:
- Dangling relationship references
- Orphaned concepts
- Missing embeddings

(The v1 BackupAssessment static-analysis class was removed in ADR-102 P6 — backup
inspection now goes through KgBackupV2Reader / backup_integrity.check_backup_data.)
"""

from typing import Dict, Any, List, Set, Optional
import sys
from pathlib import Path

# Add parent directory to path for AGEClient import
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.app.lib.age_client import AGEClient

from .console import Console, Colors


class DatabaseIntegrity:
    """Validate database integrity after restore"""

    @staticmethod
    def check_integrity(client: AGEClient, ontology: Optional[str] = None) -> Dict[str, Any]:
        """
        Check database integrity

        Args:
            client: AGEClient instance
            ontology: Optional ontology to check (None = entire database)

        Returns:
            Integrity report
        """
        import json

        report = {
            "ontology": ontology,
            "checks": {},
            "issues": [],
            "warnings": []
        }

        # Check for orphaned concepts (no APPEARS relationships)
        if ontology:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS]->(:Source {document: $ontology}))
                  AND EXISTS((c)-[:EVIDENCED_BY]->(:Instance)-[:FROM_SOURCE]->(:Source {document: $ontology}))
                RETURN count(c) as orphan_count, collect(c.concept_id)[..10] as sample_ids
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS]->(:Source))
                RETURN count(c) as orphan_count, collect(c.concept_id)[..10] as sample_ids
            """
            result = client._execute_cypher(query, fetch_one=True)

        orphan_count = int(str(result.get("orphan_count", 0))) if result else 0
        if orphan_count > 0:
            # Parse sample_ids from agtype
            sample_ids_raw = str(result.get("sample_ids", "[]"))
            try:
                sample_ids = json.loads(sample_ids_raw)
            except json.JSONDecodeError:
                sample_ids = []

            report["issues"].append(f"{orphan_count} orphaned concepts (no APPEARS relationship)")
            report["checks"]["orphaned_concepts"] = {
                "count": orphan_count,
                "sample": sample_ids
            }

        # Check for dangling relationships (pointing to non-existent concepts)
        query = """
            MATCH (c1:Concept)-[r]->(c2:Concept)
            WHERE c1.concept_id IS NULL OR c2.concept_id IS NULL
            RETURN count(r) as dangling_count
        """
        result = client._execute_cypher(query, fetch_one=True)
        dangling_count = int(str(result.get("dangling_count", 0))) if result else 0
        if dangling_count > 0:
            report["issues"].append(f"{dangling_count} dangling relationships")
            report["checks"]["dangling_relationships"] = dangling_count

        # Check for concepts missing embeddings
        if ontology:
            query = """
                MATCH (c:Concept)-[:APPEARS]->(:Source {document: $ontology})
                WHERE c.embedding IS NULL OR size(c.embedding) = 0
                RETURN count(c) as missing_embedding_count, collect(c.concept_id)[..10] as sample_ids
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (c:Concept)
                WHERE c.embedding IS NULL OR size(c.embedding) = 0
                RETURN count(c) as missing_embedding_count, collect(c.concept_id)[..10] as sample_ids
            """
            result = client._execute_cypher(query, fetch_one=True)

        missing_emb_count = int(str(result.get("missing_embedding_count", 0))) if result else 0
        if missing_emb_count > 0:
            # Parse sample_ids from agtype
            sample_ids_raw = str(result.get("sample_ids", "[]"))
            try:
                sample_ids = json.loads(sample_ids_raw)
            except json.JSONDecodeError:
                sample_ids = []

            report["issues"].append(f"{missing_emb_count} concepts missing embeddings")
            report["checks"]["missing_embeddings"] = {
                "count": missing_emb_count,
                "sample": sample_ids
            }

        # Check for instances with missing concept or source references
        if ontology:
            query = """
                MATCH (i:Instance)-[:FROM_SOURCE]->(:Source {document: $ontology})
                WHERE NOT EXISTS((i)<-[:EVIDENCED_BY]-(:Concept))
                   OR NOT EXISTS((i)-[:FROM_SOURCE]->(:Source))
                RETURN count(i) as orphan_instance_count
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (i:Instance)
                WHERE NOT EXISTS((i)<-[:EVIDENCED_BY]-(:Concept))
                   OR NOT EXISTS((i)-[:FROM_SOURCE]->(:Source))
                RETURN count(i) as orphan_instance_count
            """
            result = client._execute_cypher(query, fetch_one=True)

        orphan_inst_count = int(str(result.get("orphan_instance_count", 0))) if result else 0
        if orphan_inst_count > 0:
            report["warnings"].append(f"{orphan_inst_count} instances with missing references")
            report["checks"]["orphan_instances"] = orphan_inst_count

        # Check for cross-ontology relationships (if checking specific ontology)
        if ontology:
            query = """
                MATCH (c1:Concept)-[:APPEARS]->(:Source {document: $ontology})
                MATCH (c1)-[r]->(c2:Concept)
                WHERE NOT EXISTS((c2)-[:APPEARS]->(:Source {document: $ontology}))
                RETURN count(r) as cross_ontology_rels,
                       collect(DISTINCT type(r)) as rel_types,
                       collect(DISTINCT c2.concept_id)[..10] as external_concepts
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
            cross_ont_count = int(str(result.get("cross_ontology_rels", 0))) if result else 0

            if cross_ont_count > 0:
                # Parse rel_types and external_concepts from agtype
                rel_types_raw = str(result.get("rel_types", "[]"))
                external_concepts_raw = str(result.get("external_concepts", "[]"))

                try:
                    rel_types = json.loads(rel_types_raw)
                    external_concepts = json.loads(external_concepts_raw)
                except json.JSONDecodeError:
                    rel_types = []
                    external_concepts = []

                report["warnings"].append(
                    f"{cross_ont_count} relationships to concepts in other ontologies"
                )
                report["checks"]["cross_ontology_relationships"] = {
                    "count": cross_ont_count,
                    "relationship_types": rel_types,
                    "external_concepts_sample": external_concepts
                }

        return report

    @staticmethod
    def print_integrity_report(report: Dict[str, Any]):
        """Print integrity report to console"""
        Console.section("Database Integrity Check")

        if report["ontology"]:
            Console.key_value("Ontology", report["ontology"])

        if not report["issues"] and not report["warnings"]:
            Console.success("\n✓ No integrity issues found")
            return

        # Issues (critical)
        if report["issues"]:
            Console.error("\n✗ Critical Issues:")
            for issue in report["issues"]:
                print(f"  • {issue}")

            # Show samples
            if "orphaned_concepts" in report["checks"]:
                check = report["checks"]["orphaned_concepts"]
                Console.warning(f"\n  Sample orphaned concepts:")
                for cid in check["sample"][:5]:
                    print(f"    - {cid}")

            if "missing_embeddings" in report["checks"]:
                check = report["checks"]["missing_embeddings"]
                Console.warning(f"\n  Sample concepts missing embeddings:")
                for cid in check["sample"][:5]:
                    print(f"    - {cid}")

        # Warnings (non-critical)
        if report["warnings"]:
            Console.warning("\n⚠ Warnings:")
            for warning in report["warnings"]:
                print(f"  • {warning}")

            # Cross-ontology relationships
            if "cross_ontology_relationships" in report["checks"]:
                check = report["checks"]["cross_ontology_relationships"]
                Console.info("\n  Cross-ontology relationships by type:")
                for rel_type in check["relationship_types"]:
                    print(f"    - {rel_type}")

        # Recommendations
        Console.warning("\n💡 Recommendations:")
        if report["issues"]:
            print("  • Run repair operation to fix critical issues")
            print("  • Consider re-importing from original sources")
        if report.get("checks", {}).get("cross_ontology_relationships"):
            print("  • Cross-ontology relationships are normal, but be aware when deleting ontologies")
            print("  • Deleting ontologies may orphan concepts referenced by other ontologies")

    @staticmethod
    def repair_orphaned_concepts(client: AGEClient, ontology: Optional[str] = None) -> int:
        """
        Repair orphaned concepts by creating missing APPEARS relationships

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            Number of relationships created
        """
        if ontology:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS]->(:Source {document: $ontology}))
                MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                WITH c, s
                MERGE (c)-[:APPEARS]->(s)
                RETURN count(*) as repairs
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS]->(:Source))
                MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
                WITH c, s
                MERGE (c)-[:APPEARS]->(s)
                RETURN count(*) as repairs
            """
            result = client._execute_cypher(query, fetch_one=True)

        return int(str(result.get("repairs", 0))) if result else 0

    @staticmethod
    def prune_dangling_relationships(
        client: AGEClient,
        ontology: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Remove dangling relationships that point to non-existent concepts

        This "trims the torn fabric" by removing relationships where either the
        source or target concept no longer exists in the database.

        Args:
            client: AGEClient instance
            ontology: Optional ontology to scope pruning
            dry_run: If True, only report what would be pruned

        Returns:
            Dictionary with pruning statistics and pruned relationships
        """
        result = {
            "dangling_relationships": [],
            "total_pruned": 0,
            "by_type": {}
        }

        # Find dangling relationships
        if ontology:
            # Find relationships from concepts in this ontology pointing to non-existent concepts
            query = """
                MATCH (c1:Concept)-[:APPEARS]->(:Source {document: $ontology})
                MATCH (c1)-[r]->(c2:Concept)
                WHERE NOT EXISTS((c2)-[:APPEARS]->(:Source))
                RETURN type(r) as rel_type,
                       c1.concept_id as from_id,
                       c1.label as from_label,
                       id(c2) as to_node_id,
                       c2.concept_id as to_id,
                       c2.label as to_label,
                       id(r) as rel_id
            """
            dangling = client._execute_cypher(query, params={"ontology": ontology})
        else:
            # Find all dangling relationships in database
            query = """
                MATCH (c1:Concept)-[r]->(c2:Concept)
                WHERE NOT EXISTS((c2)-[:APPEARS]->(:Source))
                   OR NOT EXISTS((c1)-[:APPEARS]->(:Source))
                RETURN type(r) as rel_type,
                       c1.concept_id as from_id,
                       c1.label as from_label,
                       c2.concept_id as to_id,
                       c2.label as to_label,
                       id(r) as rel_id
            """
            dangling = client._execute_cypher(query)

        # Collect dangling relationships
        for record in dangling:
            rel_info = {
                "type": str(record.get("rel_type", "")).strip('"'),
                "from_id": str(record.get("from_id", "")).strip('"'),
                "from_label": str(record.get("from_label", "")).strip('"'),
                "to_id": str(record.get("to_id", "")).strip('"'),
                "to_label": str(record.get("to_label", "")).strip('"'),
                "rel_id": int(str(record.get("rel_id", 0)))
            }
            result["dangling_relationships"].append(rel_info)

            # Count by type
            rel_type = rel_info["type"]
            if rel_type not in result["by_type"]:
                result["by_type"][rel_type] = 0
            result["by_type"][rel_type] += 1

        result["total_pruned"] = len(result["dangling_relationships"])

        # Delete if not dry-run
        if not dry_run and result["total_pruned"] > 0:
            if ontology:
                delete_query = """
                    MATCH (c1:Concept)-[:APPEARS]->(:Source {document: $ontology})
                    MATCH (c1)-[r]->(c2:Concept)
                    WHERE NOT EXISTS((c2)-[:APPEARS]->(:Source))
                    DELETE r
                    RETURN count(r) as deleted
                """
                client._execute_cypher(delete_query, params={"ontology": ontology})
            else:
                delete_query = """
                    MATCH (c1:Concept)-[r]->(c2:Concept)
                    WHERE NOT EXISTS((c2)-[:APPEARS]->(:Source))
                       OR NOT EXISTS((c1)-[:APPEARS]->(:Source))
                    DELETE r
                    RETURN count(r) as deleted
                """
                client._execute_cypher(delete_query)

        return result

    @staticmethod
    def print_pruning_report(pruning_result: Dict[str, Any], dry_run: bool = False):
        """Print pruning report to console"""
        if dry_run:
            Console.section("Pruning Preview (Dry-Run)")
        else:
            Console.section("Pruning Results")

        total = pruning_result["total_pruned"]
        if total == 0:
            Console.success("✓ No dangling relationships found")
            return

        Console.warning(f"Found {total} dangling relationships")

        # By type
        Console.info("\nBy relationship type:")
        for rel_type, count in pruning_result["by_type"].items():
            Console.key_value(f"  {rel_type}", str(count), Colors.BOLD, Colors.WARNING)

        # Sample
        Console.info("\nSample dangling relationships:")
        for i, rel in enumerate(pruning_result["dangling_relationships"][:5], 1):
            print(f"\n  {i}. {Colors.OKCYAN}{rel['from_label']}{Colors.ENDC}")
            print(f"     --[{Colors.WARNING}{rel['type']}{Colors.ENDC}]-->")
            print(f"     {Colors.FAIL}{rel['to_label']} (DANGLING){Colors.ENDC}")

        if total > 5:
            Console.info(f"\n  ... and {total - 5} more")

        if dry_run:
            Console.warning("\n[DRY-RUN] No changes applied")
            Console.info("  Run without --dry-run to prune these relationships")
        else:
            Console.success(f"\n✓ Pruned {total} dangling relationships")
            Console.info("  Graph is now clean - no broken traversal paths")
