#!/usr/bin/env python3
"""
Extract git commit messages to markdown files for knowledge graph ingestion.

Reads config.json to get repository information and pointers.
Extracts commits to markdown files with frontmatter metadata.
Updates config.json with last processed commit.

Usage:
    python extract_commits.py
    python extract_commits.py --limit 50  # Extract only last 50 commits
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from git import Repo
except ImportError:
    print("Error: gitpython library not installed")
    print("Install with: pip install gitpython")
    sys.exit(1)


class CommitExtractor:
    """Extract git commits to markdown files."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.script_dir = Path(__file__).parent
        self.output_dir = self.script_dir / self.config.get("output_dir", "output")

    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def save_config(self):
        """Save configuration back to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_commits(self, repo_config: Dict, limit: Optional[int] = None, all_mode: bool = False) -> List:
        """
        Get commits from repository.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of commits to extract (windowed mode)
            all_mode: If True, ignore limit and get all remaining commits (YOLO mode)

        Returns:
            List of commit objects
        """
        repo_path = repo_config["path"]

        # Resolve relative path from script location
        if not os.path.isabs(repo_path):
            repo_path = (self.script_dir / repo_path).resolve()

        print(f"\nOpening repository: {repo_path}")
        repo = Repo(repo_path)

        # Get commits
        last_commit_hash = repo_config.get("last_commit")
        max_count = None if all_mode else (limit if limit else self.config.get("commit_limit"))

        if all_mode:
            print(f"  Mode: ALL (no limit)")
        elif max_count:
            print(f"  Mode: WINDOWED (limit: {max_count})")

        if last_commit_hash:
            # Get commits since last processed (incremental)
            print(f"  Extracting commits since: {last_commit_hash[:8]}")
            commits = list(repo.iter_commits(f"{last_commit_hash}..HEAD"))
            commits.reverse()  # Oldest first

            # Apply limit to incremental runs too (windowed mode)
            if max_count and len(commits) > max_count:
                print(f"  Limiting to next {max_count} of {len(commits)} remaining commits")
                commits = commits[:max_count]
        else:
            # Get commits from the BEGINNING (oldest first)
            print(f"  Extracting commits from the beginning...")

            # Get all commits, then take the oldest N
            all_commits = list(repo.iter_commits())
            all_commits.reverse()  # Now oldest first

            # Take only the first N commits (unless YOLO mode)
            if max_count:
                commits = all_commits[:max_count]
            else:
                commits = all_commits

        print(f"  Found {len(commits)} commits to process")
        return commits

    def commit_to_markdown(self, commit, repo_config: Dict) -> str:
        """
        Convert a commit to markdown format with frontmatter.

        Args:
            commit: GitPython commit object
            repo_config: Repository configuration dict

        Returns:
            Markdown string with frontmatter
        """
        # Extract commit metadata
        commit_hash = commit.hexsha
        short_hash = commit.hexsha[:7]
        author = commit.author.name
        email = commit.author.email
        date = datetime.fromtimestamp(commit.committed_date).strftime("%Y-%m-%d")
        time = datetime.fromtimestamp(commit.committed_date).strftime("%H:%M:%S")
        message = commit.message.strip()

        # Split message into subject and body
        lines = message.split('\n')
        subject = lines[0]
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""

        # Build frontmatter (use commits-specific ontology)
        commits_ontology = f"{repo_config['ontology']}-Commits"
        frontmatter = [
            "---",
            "type: commit",
            f"hash: {commit_hash}",
            f"short_hash: {short_hash}",
            f"author: {author}",
            f"email: {email}",
            f"date: {date}",
            f"time: {time}",
            f"repository: {repo_config['name']}",
            f"ontology: {commits_ontology}",
            "---",
            ""
        ]

        # Build document
        doc = frontmatter + [
            f"# Commit: {subject}",
            ""
        ]

        if body:
            doc.extend([
                body,
                ""
            ])

        return '\n'.join(doc)

    def extract_repository(self, repo_config: Dict, limit: Optional[int] = None, all_mode: bool = False, dry_run: bool = True):
        """
        Extract commits from a single repository.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of commits (windowed mode)
            all_mode: If True, ignore limit and get all remaining commits
            dry_run: If True, only preview what would be extracted (default: True)
        """
        if not repo_config.get("enabled", True):
            print(f"\nSkipping disabled repository: {repo_config['name']}")
            return

        # Use separate ontology for commits (appends "-Commits" to base ontology)
        commits_ontology = f"{repo_config['ontology']}-Commits"

        mode_str = "[DRY RUN] " if dry_run else ""
        print(f"\n{'='*60}")
        print(f"{mode_str}Repository: {repo_config['name']}")
        print(f"Ontology: {commits_ontology}")
        print(f"{'='*60}")

        # Get commits
        commits = self.get_commits(repo_config, limit, all_mode)

        if not commits:
            print("  No new commits to process")
            return

        if dry_run:
            # Preview mode - just list what would be extracted
            print(f"\n  Would extract {len(commits)} commits:")
            # Show first 10 and last 5 if more than 15
            if len(commits) > 15:
                for commit in commits[:10]:
                    subject = commit.message.split('\n')[0][:60]
                    print(f"    {commit.hexsha[:7]}: {subject}...")
                print(f"    ... ({len(commits) - 15} more) ...")
                for commit in commits[-5:]:
                    subject = commit.message.split('\n')[0][:60]
                    print(f"    {commit.hexsha[:7]}: {subject}...")
            else:
                for commit in commits:
                    subject = commit.message.split('\n')[0][:60]
                    print(f"    {commit.hexsha[:7]}: {subject}...")
            print(f"\n  Run with --confirm to actually extract")
            return

        # Create output directory
        commits_dir = self.output_dir / "commits" / repo_config['name']
        commits_dir.mkdir(parents=True, exist_ok=True)

        # Process each commit
        processed = 0
        for commit in commits:
            # Generate markdown
            markdown = self.commit_to_markdown(commit, repo_config)

            # Write to file (use short hash as filename)
            filename = f"{commit.hexsha[:7]}.md"
            filepath = commits_dir / filename

            with open(filepath, 'w') as f:
                f.write(markdown)

            processed += 1
            if processed % 10 == 0:
                print(f"  Processed {processed}/{len(commits)} commits...")

        print(f"  ✓ Processed {processed} commits")

        # Update pointer to latest commit
        if commits:
            repo_config["last_commit"] = commits[-1].hexsha
            print(f"  Updated pointer to: {commits[-1].hexsha[:8]}")

    def extract_all(self, limit: Optional[int] = None, all_mode: bool = False, dry_run: bool = True):
        """
        Extract commits from all enabled repositories.

        Args:
            limit: Optional limit on number of commits per repository (windowed mode)
            all_mode: If True, ignore limit and get all remaining commits (YOLO mode)
            dry_run: If True, only preview what would be extracted (default: True)
        """
        for repo_config in self.config["repositories"]:
            try:
                self.extract_repository(repo_config, limit, all_mode, dry_run)
            except Exception as e:
                print(f"\n✗ Error processing {repo_config['name']}: {e}")
                continue

        # Save updated config with pointers (only if not dry run)
        if not dry_run:
            self.save_config()
            print(f"\n✓ Config updated: {self.config_path}")
        else:
            print(f"\n[DRY RUN] Config not updated")


def main():
    parser = argparse.ArgumentParser(
        description="Extract git commit messages to markdown files"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Configuration file (default: config.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of commits per batch (windowed mode, default from config)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_mode",
        help="YOLO mode: extract ALL remaining commits, ignoring limit"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually extract commits (default is preview/what-if mode)"
    )

    args = parser.parse_args()

    # Extract commits
    extractor = CommitExtractor(config_path=args.config)
    dry_run = not args.confirm
    extractor.extract_all(limit=args.limit, all_mode=args.all_mode, dry_run=dry_run)

    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"\nOutput directory: {extractor.output_dir}/commits/")
    print(f"\nNext steps:")
    print(f"  1. Review generated markdown files")
    print(f"  2. Ingest: ./github.sh ingest")
    print(f"  3. Query: kg search query \"your search term\"")


if __name__ == "__main__":
    main()
