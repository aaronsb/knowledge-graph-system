#!/usr/bin/env python3
"""
Extract GitHub pull requests to markdown files for knowledge graph ingestion.

Uses the gh CLI tool for GitHub API access.
Reads config.json to get repository and GitHub information.
Extracts PRs to markdown files with frontmatter metadata.
Updates config.json with last processed PR.

Usage:
    gh auth login  # First time setup
    python extract_prs.py
    python extract_prs.py --limit 20  # Extract only last 20 PRs
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class PRExtractor:
    """Extract GitHub pull requests using gh CLI."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.script_dir = Path(__file__).parent
        self.output_dir = self.script_dir / self.config.get("output_dir", "output")

        # Check gh CLI is available and authenticated
        self.check_gh_auth()

    def check_gh_auth(self):
        """Check if gh CLI is installed and authenticated."""
        # Check if gh is installed
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ gh CLI installed: {result.stdout.split()[2]}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: gh CLI not installed")
            print("Install with: brew install gh  # or your package manager")
            print("See: https://cli.github.com/manual/installation")
            sys.exit(1)

        # Check if authenticated
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ gh authenticated")
        except subprocess.CalledProcessError:
            print("Error: gh CLI not authenticated")
            print("Run: gh auth login")
            sys.exit(1)

    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def save_config(self):
        """Save configuration back to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_pull_requests(self, repo_config: Dict, limit: Optional[int] = None) -> List[Dict]:
        """
        Get pull requests from GitHub repository using gh CLI.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of PRs to extract

        Returns:
            List of PR dicts
        """
        github_repo_name = repo_config.get("github_repo")
        if not github_repo_name:
            print(f"  No github_repo configured, skipping")
            return []

        print(f"\nFetching PRs from: {github_repo_name}")

        last_pr = repo_config.get("last_pr", 0)
        max_prs = limit if limit else self.config.get("pr_limit", 100)

        # Fetch PRs using gh CLI
        # Strategy: Fetch newest first, filter to PRs > last_pr, then re-sort oldest first
        # This ensures we capture recent PRs even with a reasonable limit
        # Note: Avoid 'commits' field - causes GraphQL node explosion
        fetch_limit = max(200, max_prs * 3)  # Fetch enough to cover the window
        cmd = [
            "gh", "pr", "list",
            "--repo", github_repo_name,
            "--state", "all",
            "--search", "sort:created-desc",  # Newest first to get recent PRs
            "--limit", str(fetch_limit),
            "--json", "number,title,state,author,createdAt,updatedAt,mergedAt,mergedBy,body,url,labels,additions,deletions,changedFiles"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            all_prs = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error fetching PRs: {e.stderr}")
            return []

        # Filter to new PRs only (those after our last processed PR)
        prs = [pr for pr in all_prs if pr["number"] > (last_pr or 0)]

        # Sort by number (oldest first) for sequential processing
        prs.sort(key=lambda x: x["number"])

        # Limit
        if len(prs) > max_prs:
            prs = prs[:max_prs]

        print(f"  Found {len(prs)} new PRs to process")
        return prs

    def pr_to_markdown(self, pr: Dict, repo_config: Dict) -> str:
        """
        Convert a pull request to markdown format with frontmatter.

        Args:
            pr: PR dict from gh CLI
            repo_config: Repository configuration dict

        Returns:
            Markdown string with frontmatter
        """
        # Extract PR metadata
        number = pr["number"]
        title = pr["title"]
        author = pr["author"]["login"]
        state = pr["state"]
        created = pr["createdAt"]
        updated = pr["updatedAt"]
        merged_at = pr.get("mergedAt")
        merged = bool(merged_at)  # Derive from mergedAt
        merged_by = pr.get("mergedBy", {}).get("login") if pr.get("mergedBy") else None
        body = pr.get("body", "").strip()
        url = pr["url"]

        # Build frontmatter
        frontmatter = [
            "---",
            "type: pull_request",
            f"number: {number}",
            f"title: \"{title}\"",
            f"author: {author}",
            f"state: {state}",
            f"merged: {merged}",
            f"created: {created}",
            f"updated: {updated}",
        ]

        if merged_at:
            frontmatter.append(f"merged_at: {merged_at}")
        if merged_by:
            frontmatter.append(f"merged_by: {merged_by}")

        # Use PRs-specific ontology
        prs_ontology = f"{repo_config['ontology']}-PRs"
        frontmatter.extend([
            f"repository: {repo_config['name']}",
            f"ontology: {prs_ontology}",
            f"url: {url}",
            "---",
            ""
        ])

        # Build document
        doc = frontmatter + [
            f"# Pull Request #{number}: {title}",
            ""
        ]

        if body:
            doc.extend([
                "## Description",
                "",
                body,
                ""
            ])

        # Add labels if any
        if pr.get("labels"):
            doc.extend([
                "## Labels",
                ""
            ])
            for label in pr["labels"]:
                doc.append(f"- `{label['name']}`")
            doc.append("")

        # Add stats (note: 'commits' field omitted - causes GraphQL explosion)
        stats = []
        if "changedFiles" in pr:
            stats.append(f"**Files Changed:** {pr.get('changedFiles', 0)}")
        if "additions" in pr and "deletions" in pr:
            stats.append(f"**Changes:** +{pr.get('additions', 0)}/-{pr.get('deletions', 0)}")

        if stats:
            doc.extend(stats)
            doc.append("")

        return '\n'.join(doc)

    def extract_repository(self, repo_config: Dict, limit: Optional[int] = None, dry_run: bool = True):
        """
        Extract PRs from a single repository.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of PRs
            dry_run: If True, only preview what would be extracted (default: True)
        """
        if not repo_config.get("enabled", True):
            print(f"\nSkipping disabled repository: {repo_config['name']}")
            return

        if not repo_config.get("github_repo"):
            print(f"\nSkipping repository without github_repo: {repo_config['name']}")
            return

        # Use PRs-specific ontology
        prs_ontology = f"{repo_config['ontology']}-PRs"

        mode_str = "[DRY RUN] " if dry_run else ""
        print(f"\n{'='*60}")
        print(f"{mode_str}Repository: {repo_config['name']}")
        print(f"GitHub: {repo_config['github_repo']}")
        print(f"Ontology: {prs_ontology}")
        print(f"{'='*60}")

        # Get PRs
        prs = self.get_pull_requests(repo_config, limit)

        if not prs:
            print("  No new PRs to process")
            return

        if dry_run:
            # Preview mode - just list what would be extracted
            print(f"\n  Would extract {len(prs)} PRs:")
            for pr in prs:
                state = pr["state"].upper()
                # Only add merged indicator if state isn't already MERGED
                if pr.get("mergedAt") and state != "MERGED":
                    state = f"{state} [MERGED]"
                print(f"    PR #{pr['number']}: {pr['title'][:60]}... ({state})")
            print(f"\n  Run with --confirm to actually extract")
            return

        # Create output directory
        prs_dir = self.output_dir / "prs" / repo_config['name']
        prs_dir.mkdir(parents=True, exist_ok=True)

        # Process each PR
        processed = 0
        for pr in prs:
            # Generate markdown
            markdown = self.pr_to_markdown(pr, repo_config)

            # Write to file
            filename = f"pr-{pr['number']:04d}.md"
            filepath = prs_dir / filename

            with open(filepath, 'w') as f:
                f.write(markdown)

            processed += 1
            print(f"  Processed PR #{pr['number']}: {pr['title']}")

        print(f"  ✓ Processed {processed} PRs")

        # Update pointer to latest PR
        if prs:
            repo_config["last_pr"] = prs[-1]["number"]
            print(f"  Updated pointer to: PR #{prs[-1]['number']}")

    def extract_all(self, limit: Optional[int] = None, dry_run: bool = True):
        """
        Extract PRs from all enabled repositories.

        Args:
            limit: Optional limit on number of PRs per repository
            dry_run: If True, only preview what would be extracted (default: True)
        """
        for repo_config in self.config["repositories"]:
            try:
                self.extract_repository(repo_config, limit, dry_run)
            except Exception as e:
                print(f"\n✗ Error processing {repo_config['name']}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Save updated config with pointers (only if not dry run)
        if not dry_run:
            self.save_config()
            print(f"\n✓ Config updated: {self.config_path}")
        else:
            print(f"\n[DRY RUN] Config not updated")


def main():
    parser = argparse.ArgumentParser(
        description="Extract GitHub pull requests to markdown files using gh CLI"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Configuration file (default: config.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of PRs to extract per repository"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract ALL remaining PRs (YOLO mode, ignores limit)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually extract PRs (default is preview/what-if mode)"
    )

    args = parser.parse_args()

    # Extract PRs
    extractor = PRExtractor(config_path=args.config)
    dry_run = not args.confirm

    # In YOLO mode, use a very high limit to get everything
    limit = None if args.all else args.limit
    if args.all:
        print("YOLO MODE: Extracting ALL remaining PRs")

    extractor.extract_all(limit=limit, dry_run=dry_run)

    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"\nOutput directory: {extractor.output_dir}/prs/")
    print(f"\nNext steps:")
    print(f"  1. Review generated markdown files")
    print(f"  2. Ingest: ./github.sh ingest")
    print(f"  3. Query: kg search query \"your search term\"")


if __name__ == "__main__":
    main()
