"""
Text file parser for document ingestion.

Splits documents into paragraphs for processing.
"""

from typing import List
from pathlib import Path


def parse_text_file(filepath: str) -> List[str]:
    """
    Parse a text file into paragraphs.

    Args:
        filepath: Path to the text file to parse

    Returns:
        List of paragraph strings, with whitespace stripped and empty paragraphs filtered

    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise IOError(f"Error reading file {filepath}: {e}")

    # Split on double newlines to get paragraphs
    paragraphs = content.split('\n\n')

    # Strip whitespace and filter empty paragraphs
    processed = []
    for para in paragraphs:
        cleaned = para.strip()
        if cleaned:  # Only include non-empty paragraphs
            processed.append(cleaned)

    return processed
