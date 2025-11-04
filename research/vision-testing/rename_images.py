#!/usr/bin/env python3
"""
Image Renaming Script using GPT-4o Vision

Uses GPT-4o Vision to analyze images and generate descriptive filenames.

Usage:
    python rename_images.py /path/to/images/

Requirements:
    - OpenAI API key in /home/aaron/Projects/ai/data/images/.env
    - openai library (pip install openai)
    - Pillow (pip install Pillow)
"""

import argparse
import base64
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not found.")
    print("Install with: pip install openai")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library not found.")
    print("Install with: pip install Pillow")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv library not found.")
    print("Install with: pip install python-dotenv")
    sys.exit(1)


def load_api_key(env_path: Path) -> str:
    """Load OpenAI API key from .env file."""
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    load_dotenv(env_path)
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print(f"Error: OPENAI_API_KEY not found in {env_path}")
        sys.exit(1)

    return api_key


def encode_image_to_base64(image_path: Path) -> str:
    """Encode image to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_image_description(client: OpenAI, image_path: Path) -> Optional[str]:
    """Use GPT-4o Vision to get a brief description of the image."""
    try:
        # Encode image
        base64_image = encode_image_to_base64(image_path)

        # Determine MIME type
        extension = image_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(extension, 'image/jpeg')

        # Call GPT-4o Vision
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this image in exactly 3-5 words. Be concise and descriptive. Examples: 'red car on highway', 'black cat sleeping', 'mountain lake sunset'. Only return the description, nothing else."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=50,
            temperature=0.3
        )

        description = response.choices[0].message.content.strip()
        return description

    except Exception as e:
        print(f"  Error processing {image_path.name}: {e}")
        return None


def description_to_filename(description: str, extension: str) -> str:
    """Convert description to valid filename format."""
    # Convert to lowercase
    filename = description.lower()

    # Replace spaces with underscores
    filename = filename.replace(' ', '_')

    # Remove quotes and periods
    filename = filename.replace('"', '').replace("'", '').replace('.', '')

    # Remove special characters except underscores and hyphens
    filename = re.sub(r'[^a-z0-9_-]', '', filename)

    # Remove consecutive underscores
    filename = re.sub(r'_+', '_', filename)

    # Remove leading/trailing underscores
    filename = filename.strip('_')

    # Add extension
    return f"{filename}{extension}"


def rename_images(image_dir: Path, env_path: Path, dry_run: bool = False) -> Dict[str, str]:
    """Rename all images in directory using GPT-4o Vision descriptions."""
    # Load API key
    print(f"Loading OpenAI API key from: {env_path}")
    api_key = load_api_key(env_path)
    client = OpenAI(api_key=api_key)

    # Find all images
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    image_files = [
        f for f in sorted(image_dir.iterdir())
        if f.suffix.lower() in image_extensions and f.is_file()
    ]

    if not image_files:
        print(f"Error: No images found in {image_dir}")
        return {}

    print(f"\nFound {len(image_files)} images to process")
    print()

    # Process each image
    rename_mapping = {}
    for i, image_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] Processing: {image_path.name}")

        # Get description from GPT-4o
        description = get_image_description(client, image_path)

        if description:
            print(f"  Description: \"{description}\"")

            # Convert to filename
            new_filename = description_to_filename(description, image_path.suffix)
            new_path = image_dir / new_filename

            # Handle naming conflicts
            counter = 1
            original_new_filename = new_filename
            while new_path.exists() and new_path != image_path:
                stem = Path(original_new_filename).stem
                ext = Path(original_new_filename).suffix
                new_filename = f"{stem}_{counter}{ext}"
                new_path = image_dir / new_filename
                counter += 1

            print(f"  New filename: {new_filename}")

            # Store mapping
            rename_mapping[image_path.name] = new_filename

            # Rename file (unless dry run)
            if not dry_run:
                try:
                    image_path.rename(new_path)
                    print(f"  ✓ Renamed successfully")
                except Exception as e:
                    print(f"  ✗ Rename failed: {e}")
            else:
                print(f"  [DRY RUN - would rename]")
        else:
            print(f"  ✗ Failed to get description")

        print()

    return rename_mapping


def print_summary(rename_mapping: Dict[str, str]):
    """Print summary of renames."""
    print()
    print("=" * 80)
    print("RENAME SUMMARY")
    print("=" * 80)
    print()

    if not rename_mapping:
        print("No files were renamed.")
        return

    # Print mapping
    print(f"Successfully processed {len(rename_mapping)} images:")
    print()

    max_old_len = max(len(old) for old in rename_mapping.keys())

    for old_name, new_name in rename_mapping.items():
        arrow = "→" if old_name != new_name else "="
        print(f"  {old_name:<{max_old_len}}  {arrow}  {new_name}")

    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Rename images using GPT-4o Vision descriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rename images in directory
  python rename_images.py /path/to/images/

  # Dry run (preview without renaming)
  python rename_images.py /path/to/images/ --dry-run

  # Use custom .env location
  python rename_images.py /path/to/images/ --env /path/to/.env

Description format:
  - GPT-4o generates 3-5 word descriptions
  - Converted to lowercase with underscores
  - Special characters removed
  - Original extension preserved
  - Example: "Black cat on couch" → "black_cat_on_couch.jpg"
        """
    )

    parser.add_argument(
        'image_dir',
        type=Path,
        help='Directory containing images to rename'
    )

    parser.add_argument(
        '--env',
        type=Path,
        default=Path('/home/aaron/Projects/ai/data/images/.env'),
        help='Path to .env file with OPENAI_API_KEY (default: /home/aaron/Projects/ai/data/images/.env)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview renames without actually renaming files'
    )

    args = parser.parse_args()

    # Validate directory
    if not args.image_dir.exists():
        print(f"Error: Directory not found: {args.image_dir}")
        sys.exit(1)

    if not args.image_dir.is_dir():
        print(f"Error: Not a directory: {args.image_dir}")
        sys.exit(1)

    print(f"Image directory: {args.image_dir}")
    if args.dry_run:
        print("[DRY RUN MODE - no files will be renamed]")

    # Rename images
    rename_mapping = rename_images(args.image_dir, args.env, dry_run=args.dry_run)

    # Print summary
    print_summary(rename_mapping)


if __name__ == '__main__':
    main()
