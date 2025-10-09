"""
Data integrity validation and assessment

Analyzes backup completeness and database integrity to detect:
- Cross-ontology dependencies
- Dangling relationship references
- Orphaned concepts
- Missing embeddings
- Torn ontological fabric from partial restores
"""

from typing import Dict, Any, List, Set, Optional
import sys
from pathlib import Path

# Add parent directory to path for AGEClient import
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.lib.age_client import AGEClient

from .console import Console, Colors


class BackupAssessment:
    """Assess backup completeness and dependencies"""

    @staticmethod
    def analyze_backup(backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a backup file for completeness and external dependencies

        Args:
            backup_data: Parsed backup JSON

        Returns:
            Assessment report with warnings and recommendations
        """
        report = {
            "backup_type": backup_data.get("type"),
            "ontology": backup_data.get("ontology"),
            "statistics": backup_data.get("statistics", {}),
            "issues": [],
            "warnings": [],
            "external_dependencies": {
                "concepts": set(),
                "sources": set()
            },
            "integrity_checks": {}
        }

        data = backup_data.get("data", {})

        # Build internal concept and source IDs
        internal_concept_ids = {c["concept_id"] for c in data.get("concepts", [])}
        internal_source_ids = {s["source_id"] for s in data.get("sources", [])}

        # Check for external concept references in relationships
        external_concepts = set()
        for rel in data.get("relationships", []):
            from_id = rel.get("from")
            to_id = rel.get("to")

            if from_id not in internal_concept_ids:
                external_concepts.add(from_id)
            if to_id not in internal_concept_ids:
                external_concepts.add(to_id)

        if external_concepts:
            report["warnings"].append(
                f"Found {len(external_concepts)} relationships pointing to external concepts "
                f"not included in this backup"
            )
            report["external_dependencies"]["concepts"] = list(external_concepts)

        # Check for missing embeddings
        concepts_without_embeddings = [
            c["concept_id"] for c in data.get("concepts", [])
            if not c.get("embedding") or len(c.get("embedding", [])) == 0
        ]
        if concepts_without_embeddings:
            report["issues"].append(
                f"{len(concepts_without_embeddings)} concepts missing embeddings"
            )
            report["integrity_checks"]["missing_embeddings"] = concepts_without_embeddings

        # Check for instances referencing external sources
        external_sources = set()
        for instance in data.get("instances", []):
            source_id = instance.get("source_id")
            if source_id not in internal_source_ids:
                external_sources.add(source_id)

        if external_sources:
            report["issues"].append(
                f"{len(external_sources)} instances reference sources not in this backup"
            )
            report["external_dependencies"]["sources"] = list(external_sources)

        # Check for orphaned concepts (no instances/sources)
        concepts_with_instances = {inst["concept_id"] for inst in data.get("instances", [])}
        orphaned_concepts = internal_concept_ids - concepts_with_instances

        if orphaned_concepts:
            report["warnings"].append(
                f"{len(orphaned_concepts)} concepts have no instances/evidence in this backup"
            )

        # Relationship integrity
        total_relationships = len(data.get("relationships", []))
        internal_relationships = sum(
            1 for rel in data.get("relationships", [])
            if rel["from"] in internal_concept_ids and rel["to"] in internal_concept_ids
        )
        external_relationships = total_relationships - internal_relationships

        report["integrity_checks"]["relationships"] = {
            "total": total_relationships,
            "internal": internal_relationships,
            "external": external_relationships,
            "external_percentage": (external_relationships / total_relationships * 100)
                                  if total_relationships > 0 else 0
        }

        if external_relationships > 0:
            report["warnings"].append(
                f"{external_relationships}/{total_relationships} "
                f"({report['integrity_checks']['relationships']['external_percentage']:.1f}%) "
                f"relationships point to external concepts"
            )

        return report

    @staticmethod
    def print_assessment(report: Dict[str, Any]):
        """Print assessment report to console"""
        Console.section("Backup Assessment")

        # Basic info
        Console.key_value("Backup Type", report["backup_type"])
        if report["ontology"]:
            Console.key_value("Ontology", report["ontology"])

        # Statistics
        Console.info("\nContents:")
        stats = report["statistics"]
        for key, value in stats.items():
            Console.key_value(f"  {key.title()}", str(value))

        # Relationship integrity
        rel_check = report["integrity_checks"].get("relationships", {})
        if rel_check:
            Console.info("\nRelationship Integrity:")
            Console.key_value("  Internal", f"{rel_check['internal']}/{rel_check['total']}",
                            Colors.BOLD, Colors.OKGREEN)
            if rel_check["external"] > 0:
                Console.key_value("  External", f"{rel_check['external']}/{rel_check['total']}",
                                Colors.BOLD, Colors.WARNING)
                Console.key_value("  External %", f"{rel_check['external_percentage']:.1f}%",
                                Colors.BOLD, Colors.WARNING)

        # Issues
        if report["issues"]:
            Console.warning("\n⚠ Issues Found:")
            for issue in report["issues"]:
                print(f"  • {issue}")

        # Warnings
        if report["warnings"]:
            Console.warning("\nWarnings:")
            for warning in report["warnings"]:
                print(f"  • {warning}")

        # External dependencies
        ext_deps = report["external_dependencies"]
        if ext_deps["concepts"] or ext_deps["sources"]:
            Console.warning("\nExternal Dependencies:")
            if ext_deps["concepts"]:
                print(f"  • {len(ext_deps['concepts'])} external concepts referenced")
            if ext_deps["sources"]:
                print(f"  • {len(ext_deps['sources'])} external sources referenced")

            Console.warning("\n⚠ Restoring this backup may create dangling references!")
            Console.info("  Consider one of these strategies:")
            print("    1. Restore into database that already has these dependencies")
            print("    2. Use --prune-external to skip external relationships")
            print("    3. Backup dependent ontologies together")


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

        # Check for orphaned concepts (no APPEARS_IN relationships)
        if ontology:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source {document: $ontology}))
                  AND EXISTS((c)-[:EVIDENCED_BY]->(:Instance)-[:FROM_SOURCE]->(:Source {document: $ontology}))
                RETURN count(c) as orphan_count, collect(c.concept_id)[..10] as sample_ids
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
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

            report["issues"].append(f"{orphan_count} orphaned concepts (no APPEARS_IN relationship)")
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
                MATCH (c:Concept)-[:APPEARS_IN]->(:Source {document: $ontology})
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
                MATCH (c1:Concept)-[:APPEARS_IN]->(:Source {document: $ontology})
                MATCH (c1)-[r]->(c2:Concept)
                WHERE NOT EXISTS((c2)-[:APPEARS_IN]->(:Source {document: $ontology}))
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
        Repair orphaned concepts by creating missing APPEARS_IN relationships

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            Number of relationships created
        """
        if ontology:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source {document: $ontology}))
                MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                WITH c, s
                MERGE (c)-[:APPEARS_IN]->(s)
                RETURN count(*) as repairs
            """
            result = client._execute_cypher(query, params={"ontology": ontology}, fetch_one=True)
        else:
            query = """
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
                MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
                WITH c, s
                MERGE (c)-[:APPEARS_IN]->(s)
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
                MATCH (c1:Concept)-[:APPEARS_IN]->(:Source {document: $ontology})
                MATCH (c1)-[r]->(c2:Concept)
                WHERE NOT EXISTS((c2)-[:APPEARS_IN]->(:Source))
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
                WHERE NOT EXISTS((c2)-[:APPEARS_IN]->(:Source))
                   OR NOT EXISTS((c1)-[:APPEARS_IN]->(:Source))
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
                    MATCH (c1:Concept)-[:APPEARS_IN]->(:Source {document: $ontology})
                    MATCH (c1)-[r]->(c2:Concept)
                    WHERE NOT EXISTS((c2)-[:APPEARS_IN]->(:Source))
                    DELETE r
                    RETURN count(r) as deleted
                """
                client._execute_cypher(delete_query, params={"ontology": ontology})
            else:
                delete_query = """
                    MATCH (c1:Concept)-[r]->(c2:Concept)
                    WHERE NOT EXISTS((c2)-[:APPEARS_IN]->(:Source))
                       OR NOT EXISTS((c1)-[:APPEARS_IN]->(:Source))
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
