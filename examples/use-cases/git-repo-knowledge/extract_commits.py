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

    def get_commits(self, repo_config: Dict, limit: Optional[int] = None) -> List:
        """
        Get commits from repository.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of commits to extract

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

        if last_commit_hash:
            # Get commits since last processed
            print(f"  Extracting commits since: {last_commit_hash[:8]}")
            commits = list(repo.iter_commits(f"{last_commit_hash}..HEAD"))
            commits.reverse()  # Oldest first
        else:
            # Get all commits (or limited number)
            print(f"  Extracting all commits...")
            max_count = limit if limit else self.config.get("commit_limit")
            commits = list(repo.iter_commits(max_count=max_count))
            commits.reverse()  # Oldest first

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

        # Build frontmatter
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
            f"ontology: {repo_config['ontology']}",
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

        doc.extend([
            "## Metadata",
            "",
            f"- **Commit Hash:** `{commit_hash}`",
            f"- **Short Hash:** `{short_hash}`",
            f"- **Author:** {author} <{email}>",
            f"- **Date:** {date} {time}",
            f"- **Repository:** {repo_config['name']}",
            ""
        ])

        return '\n'.join(doc)

    def extract_repository(self, repo_config: Dict, limit: Optional[int] = None):
        """
        Extract commits from a single repository.

        Args:
            repo_config: Repository configuration dict
            limit: Optional limit on number of commits
        """
        if not repo_config.get("enabled", True):
            print(f"\nSkipping disabled repository: {repo_config['name']}")
            return

        print(f"\n{'='*60}")
        print(f"Repository: {repo_config['name']}")
        print(f"Ontology: {repo_config['ontology']}")
        print(f"{'='*60}")

        # Get commits
        commits = self.get_commits(repo_config, limit)

        if not commits:
            print("  No new commits to process")
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

    def extract_all(self, limit: Optional[int] = None):
        """
        Extract commits from all enabled repositories.

        Args:
            limit: Optional limit on number of commits per repository
        """
        for repo_config in self.config["repositories"]:
            try:
                self.extract_repository(repo_config, limit)
            except Exception as e:
                print(f"\n✗ Error processing {repo_config['name']}: {e}")
                continue

        # Save updated config with pointers
        self.save_config()
        print(f"\n✓ Config updated: {self.config_path}")


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
        help="Limit number of commits to extract per repository"
    )

    args = parser.parse_args()

    # Extract commits
    extractor = CommitExtractor(config_path=args.config)
    extractor.extract_all(limit=args.limit)

    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"\nOutput directory: {extractor.output_dir}/commits/")
    print(f"\nNext steps:")
    print(f"  1. Review generated markdown files")
    print(f"  2. Run: ./ingest.sh")
    print(f"  3. Query: kg search query \"your search term\"")


if __name__ == "__main__":
    main()
