#!/usr/bin/env python3
"""
Simple PDF to Images Converter

Converts a PDF file to a directory of ordered PNG images at reasonable DPI.
This is a pre-processing tool for the multimodal image ingestion pipeline.

Usage:
    python convert.py input.pdf [output_directory] [--dpi DPI]

Requirements:
    - pdf2image (pip install pdf2image)
    - poppler-utils (system package: apt install poppler-utils on Debian/Ubuntu)
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    from pdf2image import convert_from_path
except ImportError:
    print("Error: pdf2image library not found.")
    print("Install with: pip install pdf2image")
    print("Also install system dependency: sudo apt install poppler-utils")
    sys.exit(1)


def convert_pdf_to_images(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    dpi: int = 300,
) -> None:
    """
    Convert PDF pages to PNG images.

    Args:
        pdf_path: Path to input PDF file
        output_dir: Output directory for images (default: pdf_path.stem + "_images")
        dpi: DPI resolution for output images (default: 300)
    """
    # Validate input
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    if not pdf_path.suffix.lower() == '.pdf':
        print(f"Error: Input file must be a PDF: {pdf_path}")
        sys.exit(1)

    # Set output directory
    if output_dir is None:
        output_dir = pdf_path.parent / f"{pdf_path.stem}_images"

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting PDF: {pdf_path}")
    print(f"Output directory: {output_dir}")
    print(f"DPI: {dpi}")
    print()

    try:
        # Convert PDF to images
        print("Converting pages...")
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt='png',
            output_folder=output_dir,
            paths_only=False,  # Return PIL Image objects
        )

        # Save images with ordered filenames (page-001.png, page-002.png, etc.)
        num_digits = len(str(len(images)))

        for i, image in enumerate(images, start=1):
            page_num = str(i).zfill(num_digits)
            output_path = output_dir / f"page-{page_num}.png"

            print(f"  Saving page {i}/{len(images)}: {output_path.name}")
            image.save(output_path, 'PNG')

        print()
        print(f"✓ Converted {len(images)} pages successfully")
        print(f"✓ Images saved to: {output_dir}")

    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF to ordered PNG images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert PDF to images in default output directory
  python convert.py document.pdf

  # Specify custom output directory
  python convert.py document.pdf /path/to/output

  # Use higher DPI for better quality (larger files)
  python convert.py document.pdf --dpi 600

  # Use lower DPI for smaller files (faster processing)
  python convert.py document.pdf --dpi 150

Recommended DPI settings:
  - 150 DPI: Quick preview, smaller files
  - 300 DPI: Standard quality (default, recommended)
  - 600 DPI: High quality, larger files
        """
    )

    parser.add_argument(
        'pdf_path',
        type=Path,
        help='Path to input PDF file'
    )

    parser.add_argument(
        'output_dir',
        type=Path,
        nargs='?',
        default=None,
        help='Output directory for images (default: <pdf_name>_images/)'
    )

    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help='DPI resolution for output images (default: 300)'
    )

    args = parser.parse_args()

    convert_pdf_to_images(
        pdf_path=args.pdf_path,
        output_dir=args.output_dir,
        dpi=args.dpi,
    )


if __name__ == '__main__':
    main()
