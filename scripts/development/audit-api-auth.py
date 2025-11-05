#!/usr/bin/env python3
"""
API Endpoint Authentication Audit Script

Scans all FastAPI routes and identifies:
- Which endpoints require authentication
- Which endpoints are public
- Which endpoints have role/permission requirements
- Which endpoints lack auth but probably should have it

Usage:
    python scripts/audit/audit_api_endpoints.py [--verbose] [--format=json|table|markdown]
"""

import sys
import os
import inspect
from pathlib import Path
from typing import List, Dict, Any, Optional, get_origin, get_args
import argparse
import json
from tabulate import tabulate

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Now we can import from the API
from fastapi import FastAPI, Depends
from src.api.main import app


def extract_dependency_names(dependencies: List) -> List[str]:
    """Extract names of dependency functions from depends list"""
    names = []
    for dep in dependencies:
        if hasattr(dep, 'dependency'):
            func = dep.dependency
            if hasattr(func, '__name__'):
                names.append(func.__name__)
            elif hasattr(func, '__class__'):
                names.append(func.__class__.__name__)
    return names


def analyze_endpoint(route) -> Dict[str, Any]:
    """Analyze a single endpoint for auth requirements"""

    endpoint_info = {
        "path": route.path,
        "method": ",".join(route.methods) if hasattr(route, 'methods') else "N/A",
        "name": route.name,
        "has_auth": False,
        "auth_type": "none",
        "dependencies": [],
        "requires_role": None,
        "requires_permission": None,
    }

    # Check route dependencies
    if hasattr(route, 'dependencies'):
        dep_names = extract_dependency_names(route.dependencies)
        endpoint_info["dependencies"] = dep_names

        # Check for auth dependencies
        auth_deps = [
            'get_current_user',
            'get_current_active_user',
            'get_api_key_user',
            'require_role',
            'require_permission'
        ]

        for auth_dep in auth_deps:
            if any(auth_dep in dep for dep in dep_names):
                endpoint_info["has_auth"] = True

                if 'require_role' in auth_dep:
                    endpoint_info["auth_type"] = "role"
                elif 'require_permission' in auth_dep:
                    endpoint_info["auth_type"] = "permission"
                elif 'get_current_user' in auth_dep or 'get_current_active_user' in auth_dep:
                    endpoint_info["auth_type"] = "user"
                elif 'get_api_key' in auth_dep:
                    endpoint_info["auth_type"] = "api_key"

    # Check endpoint function signature
    if hasattr(route, 'endpoint'):
        sig = inspect.signature(route.endpoint)
        for param_name, param in sig.parameters.items():
            # ADR-060: Check for CurrentUser type annotation (FastAPI template pattern)
            if param.annotation != inspect.Parameter.empty:
                annotation_str = str(param.annotation)
                # Check for CurrentUser type alias (ADR-060)
                # Could be "CurrentUser" or "typing.Annotated[UserInDB, ...]"
                if 'CurrentUser' in annotation_str:
                    endpoint_info["has_auth"] = True
                    endpoint_info["auth_type"] = "user"
                    endpoint_info["dependencies"].append("CurrentUser")
                # Also check for Annotated types that contain Depends
                elif hasattr(param.annotation, '__origin__'):
                    # This is a generic type (like Annotated)
                    args = get_args(param.annotation)
                    for arg in args:
                        arg_str = str(arg)
                        if 'Depends' in arg_str and ('current_user' in arg_str.lower() or 'get_current' in arg_str):
                            endpoint_info["has_auth"] = True
                            endpoint_info["auth_type"] = "user"
                            break

            if param.default != inspect.Parameter.empty:
                # Check if parameter has Depends with auth
                if isinstance(param.default, type(Depends())):
                    func_name = param.default.dependency.__name__ if hasattr(param.default.dependency, '__name__') else str(param.default.dependency)

                    if any(auth in func_name for auth in ['current_user', 'api_key', 'require_role', 'require_permission', 'check_role']):
                        endpoint_info["has_auth"] = True

                        # ADR-060: Upgrade to role-based if require_role dependency found
                        if 'require_role' in func_name or 'check_role' in func_name:
                            endpoint_info["auth_type"] = "role"
                        elif 'require_permission' in func_name:
                            endpoint_info["auth_type"] = "permission"
                        elif 'current_user' in func_name:
                            endpoint_info["auth_type"] = "user"
                        elif 'api_key' in func_name:
                            endpoint_info["auth_type"] = "api_key"

    return endpoint_info


def categorize_endpoints(endpoints: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize endpoints by auth requirements"""

    categories = {
        "public": [],  # No auth required
        "authenticated": [],  # Requires authentication
        "role_based": [],  # Requires specific role
        "permission_based": [],  # Requires specific permission
        "unclear": [],  # Should probably have auth but doesn't
    }

    # Patterns that indicate endpoints should be public
    public_patterns = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/auth/login",
        "/auth/device/authorize",
        "/oauth/",
        "/database/",  # Database stats/info (read-only informational)
        "/embedding/config",  # Public config summary
        "/extraction/config",  # Public config summary
        "/sources/",  # Source retrieval (read-only)
    ]

    # Patterns for PUBLIC vocabulary read endpoints (informational)
    public_vocabulary_patterns = [
        ("GET", "/vocabulary/status"),
        ("GET", "/vocabulary/types"),
        ("GET", "/vocabulary/category-scores/"),
        ("GET", "/vocabulary/similar/"),
        ("GET", "/vocabulary/analyze/"),
        ("GET", "/vocabulary/config"),
    ]

    # Patterns that indicate endpoints should require auth
    protected_patterns = [
        "/admin/",
        "/ingest",
        "/jobs/",
        "/ontology/",
        "/users/",
        "/roles/",
        "/permissions/",
    ]

    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]

        # Check public vocabulary read endpoints first (before general patterns)
        is_public_vocab = any(
            method.upper().startswith(vocab_method) and vocab_pattern in path
            for vocab_method, vocab_pattern in public_vocabulary_patterns
        )

        # Public endpoints (including public vocabulary reads)
        if is_public_vocab or any(pattern in path for pattern in public_patterns):
            categories["public"].append(endpoint)

        # Authenticated endpoints
        elif endpoint["has_auth"]:
            if endpoint["auth_type"] == "role":
                categories["role_based"].append(endpoint)
            elif endpoint["auth_type"] == "permission":
                categories["permission_based"].append(endpoint)
            else:
                categories["authenticated"].append(endpoint)

        # Endpoints that should probably be protected
        elif any(pattern in path for pattern in protected_patterns):
            categories["unclear"].append(endpoint)

        # Everything else is public
        else:
            categories["public"].append(endpoint)

    return categories


def print_summary(categories: Dict[str, List[Dict]], verbose: bool = False):
    """Print summary of endpoint audit"""

    print("\n" + "="*80)
    print("API ENDPOINT AUTHENTICATION AUDIT")
    print("="*80 + "\n")

    total = sum(len(endpoints) for endpoints in categories.values())
    print(f"Total endpoints: {total}\n")

    # Summary counts
    summary_data = [
        ["Public (no auth)", len(categories["public"])],
        ["Authenticated (user)", len(categories["authenticated"])],
        ["Role-based", len(categories["role_based"])],
        ["Permission-based", len(categories["permission_based"])],
        ["⚠️  Unclear/Missing Auth", len(categories["unclear"])],
    ]

    print(tabulate(summary_data, headers=["Category", "Count"], tablefmt="grid"))
    print()

    if verbose:
        # Detailed breakdown
        for category, endpoints in categories.items():
            if not endpoints:
                continue

            print(f"\n{'='*80}")
            print(f"{category.upper().replace('_', ' ')} ENDPOINTS ({len(endpoints)})")
            print('='*80)

            table_data = []
            for ep in endpoints:
                table_data.append([
                    ep["method"],
                    ep["path"],
                    ep["auth_type"],
                    ", ".join(ep["dependencies"][:2]) if ep["dependencies"] else "none"
                ])

            print(tabulate(
                table_data,
                headers=["Method", "Path", "Auth Type", "Dependencies"],
                tablefmt="grid"
            ))

    # Highlight unclear/missing auth
    if categories["unclear"]:
        print(f"\n{'='*80}")
        print("⚠️  ENDPOINTS WITH UNCLEAR/MISSING AUTHENTICATION")
        print('='*80)
        print("\nThese endpoints may need authentication but don't appear to have it:\n")

        table_data = []
        for ep in categories["unclear"]:
            table_data.append([
                ep["method"],
                ep["path"],
                ep["name"],
                "❌ NO AUTH" if not ep["has_auth"] else "✓ Has Auth"
            ])

        print(tabulate(
            table_data,
            headers=["Method", "Path", "Name", "Status"],
            tablefmt="grid"
        ))
        print()


def export_json(categories: Dict[str, List[Dict]], output_file: str):
    """Export audit results to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(categories, f, indent=2)
    print(f"\n✅ Results exported to: {output_file}")


def export_markdown(categories: Dict[str, List[Dict]], output_file: str):
    """Export audit results to Markdown file"""

    with open(output_file, 'w') as f:
        f.write("# API Endpoint Authentication Audit\n\n")
        f.write(f"**Generated:** {os.popen('date').read().strip()}\n\n")

        total = sum(len(endpoints) for endpoints in categories.values())
        f.write(f"**Total Endpoints:** {total}\n\n")

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Category | Count |\n")
        f.write("|----------|-------|\n")
        for category, endpoints in categories.items():
            f.write(f"| {category.replace('_', ' ').title()} | {len(endpoints)} |\n")

        # Detailed breakdown
        for category, endpoints in categories.items():
            if not endpoints:
                continue

            f.write(f"\n## {category.replace('_', ' ').title()} Endpoints ({len(endpoints)})\n\n")
            f.write("| Method | Path | Auth Type | Name |\n")
            f.write("|--------|------|-----------|------|\n")

            for ep in endpoints:
                f.write(f"| {ep['method']} | `{ep['path']}` | {ep['auth_type']} | {ep['name']} |\n")

        # Highlight missing auth
        if categories["unclear"]:
            f.write("\n## ⚠️ Endpoints Requiring Review\n\n")
            f.write("These endpoints may need authentication:\n\n")
            f.write("| Method | Path | Current Status |\n")
            f.write("|--------|------|----------------|\n")

            for ep in categories["unclear"]:
                status = "❌ NO AUTH" if not ep["has_auth"] else "✓ Has Auth"
                f.write(f"| {ep['method']} | `{ep['path']}` | {status} |\n")

    print(f"\n✅ Results exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit API endpoints for authentication requirements"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed breakdown of all endpoints"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        help="Export to file format (optional)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: auth_audit.json or auth_audit.md)"
    )

    args = parser.parse_args()

    # Collect all endpoints
    print("Scanning API endpoints...")
    endpoints = []

    for route in app.routes:
        if hasattr(route, 'path'):
            endpoint_info = analyze_endpoint(route)
            endpoints.append(endpoint_info)

    # Categorize endpoints
    categories = categorize_endpoints(endpoints)

    # Always print summary to terminal
    print_summary(categories, verbose=args.verbose)

    # Optionally export to file
    if args.format == "json":
        output_file = args.output or "auth_audit.json"
        export_json(categories, output_file)

    elif args.format == "markdown":
        output_file = args.output or "auth_audit.md"
        export_markdown(categories, output_file)


if __name__ == "__main__":
    main()
