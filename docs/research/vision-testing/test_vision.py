#!/usr/bin/env python3
"""
Granite Vision Model Quality Testing

Test Granite Vision 3.3 2B's ability to describe images with detail.
This is a scratch space for evaluating local vision model quality before
integrating into the main ingestion pipeline.

Usage:
    python test_vision.py image.png
    python test_vision.py image.png --save-description
    python test_vision.py image.png --prompt "Describe this diagram in detail"

Requirements:
    - Ollama running with granite3.3-vision:2b model
    - ollama Python library (pip install ollama)
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import ollama
except ImportError:
    print("Error: ollama library not found.")
    print("Install with: pip install ollama")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library not found.")
    print("Install with: pip install Pillow")
    sys.exit(1)


DEFAULT_PROMPT = """Analyze this image and describe it in markdown format with detail.

Include:
- All visible text verbatim
- Diagrams, charts, and visual elements
- Relationships between elements
- Structure (headings, lists, tables)
- Layout and organization

Output pure markdown."""


def describe_image(
    image_path: Path,
    model: str = "ibm/granite3.3-vision:2b",
    prompt: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
) -> dict:
    """
    Send image to Granite Vision and get description.

    Args:
        image_path: Path to image file
        model: Ollama model name
        prompt: Custom prompt (uses default if None)
        ollama_host: Ollama server URL

    Returns:
        dict with keys: description, elapsed_time, image_size, model
    """
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    # Get image info
    try:
        with Image.open(image_path) as img:
            image_size = img.size
            image_format = img.format
    except Exception as e:
        print(f"Error opening image: {e}")
        sys.exit(1)

    # Use default prompt if not provided
    if prompt is None:
        prompt = DEFAULT_PROMPT

    print(f"Image: {image_path}")
    print(f"  Size: {image_size[0]}x{image_size[1]} ({image_format})")
    print(f"  File size: {image_path.stat().st_size / 1024:.1f} KB")
    print()
    print(f"Model: {model}")
    print(f"Ollama host: {ollama_host}")
    print()
    print("Sending to vision model...")
    print()

    try:
        # Configure Ollama client
        client = ollama.Client(host=ollama_host)

        # Send image to model
        start_time = time.time()

        response = client.chat(
            model=model,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                    'images': [str(image_path)]
                }
            ]
        )

        elapsed_time = time.time() - start_time

        description = response['message']['content']

        return {
            'description': description,
            'elapsed_time': elapsed_time,
            'image_size': image_size,
            'image_format': image_format,
            'file_size_kb': image_path.stat().st_size / 1024,
            'model': model,
        }

    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        print()
        print("Make sure Ollama is running and the model is available:")
        print(f"  docker exec kg-ollama ollama list")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Test Granite Vision model quality on images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Describe a single image
  python test_vision.py page-001.png

  # Use custom prompt
  python test_vision.py page-001.png --prompt "Extract all text from this slide"

  # Save description to file
  python test_vision.py page-001.png --save-description

  # Use different Ollama host
  python test_vision.py page-001.png --host http://localhost:11434

Testing workflow:
  1. Convert PDF to images: python convert.py document.pdf
  2. Test vision on sample pages: python test_vision.py document_images/page-001.png
  3. Evaluate description quality and performance
  4. Adjust DPI/prompt if needed
        """
    )

    parser.add_argument(
        'image_path',
        type=Path,
        help='Path to image file'
    )

    parser.add_argument(
        '--prompt',
        type=str,
        default=None,
        help='Custom prompt for vision model (uses default if not specified)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='ibm/granite3.3-vision:2b',
        help='Ollama model name (default: ibm/granite3.3-vision:2b)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='http://localhost:11434',
        help='Ollama server URL (default: http://localhost:11434)'
    )

    parser.add_argument(
        '--save-description',
        action='store_true',
        help='Save description to .txt file alongside image'
    )

    args = parser.parse_args()

    # Get description
    result = describe_image(
        image_path=args.image_path,
        model=args.model,
        prompt=args.prompt,
        ollama_host=args.host,
    )

    # Print results
    print("=" * 80)
    print("DESCRIPTION")
    print("=" * 80)
    print()
    print(result['description'])
    print()
    print("=" * 80)
    print("METRICS")
    print("=" * 80)
    print(f"Elapsed time: {result['elapsed_time']:.2f}s")
    print(f"Image size: {result['image_size'][0]}x{result['image_size'][1]} ({result['image_format']})")
    print(f"File size: {result['file_size_kb']:.1f} KB")
    print(f"Model: {result['model']}")

    # Save description if requested
    if args.save_description:
        output_path = args.image_path.with_suffix('.txt')
        output_path.write_text(result['description'])
        print()
        print(f"✓ Description saved to: {output_path}")


if __name__ == '__main__':
    main()
