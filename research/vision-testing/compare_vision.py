#!/usr/bin/env python3
"""
Vision Model Comparison: Granite vs OpenAI

Compare Granite Vision 3.3 2B (local) against OpenAI GPT-4o Vision (cloud)
for image description quality and performance.

Usage:
    python compare_vision.py image.png
    python compare_vision.py image.png --env-file /path/to/.env

Requirements:
    - Ollama with granite3.3-vision:2b
    - OpenAI API key in .env file (OPENAI_API_KEY=sk-...)
    - openai Python library (pip install openai)
"""

import argparse
import base64
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict

try:
    import ollama
except ImportError:
    print("Error: ollama library not found.")
    print("Install with: pip install ollama")
    sys.exit(1)

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


# Literal, exhaustive prompt - no interpretation, just describe everything
LITERAL_PROMPT = """Describe everything visible in this image literally and exhaustively.

Do NOT summarize or interpret. Do NOT provide analysis or conclusions.

Instead, describe:
- Every piece of text you see, word for word
- Every visual element (boxes, arrows, shapes, colors)
- The exact layout and positioning of elements
- Any diagrams, charts, or graphics in detail
- Relationships between elements (what connects to what, what's above/below)
- Any logos, branding, or page numbers

Be thorough and literal. If you see text, transcribe it exactly. If you see a box with an arrow pointing to another box, describe that precisely."""


def load_api_key(env_file: Optional[Path] = None) -> str:
    """Load OpenAI API key from .env file."""
    if env_file and env_file.exists():
        load_dotenv(env_file)
    else:
        # Try loading from current directory or parent directories
        load_dotenv()

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        print("Create a .env file with: OPENAI_API_KEY=sk-...")
        sys.exit(1)

    return api_key


def describe_with_granite(
    image_path: Path,
    prompt: str,
    model: str = "ibm/granite3.3-vision:2b",
    ollama_host: str = "http://localhost:11434",
) -> Dict:
    """Describe image using Granite Vision via Ollama."""
    print("Testing Granite Vision 3.3 2B...")

    try:
        client = ollama.Client(host=ollama_host)

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

        return {
            'description': response['message']['content'],
            'elapsed_time': elapsed_time,
            'model': model,
            'provider': 'ollama',
        }

    except Exception as e:
        print(f"  Error: {e}")
        return None


def describe_with_openai(
    image_path: Path,
    prompt: str,
    api_key: str,
    model: str = "gpt-4o",
) -> Dict:
    """Describe image using OpenAI GPT-4o Vision."""
    print("Testing OpenAI GPT-4o Vision...")

    try:
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine image format
        ext = image_path.suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(ext, 'image/png')

        client = OpenAI(api_key=api_key)

        start_time = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
        )
        elapsed_time = time.time() - start_time

        return {
            'description': response.choices[0].message.content,
            'elapsed_time': elapsed_time,
            'model': model,
            'provider': 'openai',
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens,
            }
        }

    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Compare Granite Vision vs OpenAI GPT-4o Vision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare both models on an image
  python compare_vision.py image.png

  # Specify .env file location
  python compare_vision.py image.png --env-file /path/to/.env

  # Save outputs to files
  python compare_vision.py image.png --save-outputs

Output files:
  - image-granite.txt: Granite Vision description
  - image-openai.txt: OpenAI GPT-4o description
  - image-comparison.txt: Side-by-side comparison
        """
    )

    parser.add_argument(
        'image_path',
        type=Path,
        help='Path to image file'
    )

    parser.add_argument(
        '--env-file',
        type=Path,
        default=None,
        help='.env file with OPENAI_API_KEY (default: search current/parent dirs)'
    )

    parser.add_argument(
        '--save-outputs',
        action='store_true',
        help='Save descriptions to separate files'
    )

    parser.add_argument(
        '--granite-only',
        action='store_true',
        help='Test only Granite Vision (skip OpenAI)'
    )

    parser.add_argument(
        '--openai-only',
        action='store_true',
        help='Test only OpenAI (skip Granite)'
    )

    args = parser.parse_args()

    # Validate image
    if not args.image_path.exists():
        print(f"Error: Image file not found: {args.image_path}")
        sys.exit(1)

    # Get image info
    try:
        with Image.open(args.image_path) as img:
            image_size = img.size
            image_format = img.format
            file_size_kb = args.image_path.stat().st_size / 1024
    except Exception as e:
        print(f"Error opening image: {e}")
        sys.exit(1)

    print(f"Image: {args.image_path}")
    print(f"  Size: {image_size[0]}x{image_size[1]} ({image_format})")
    print(f"  File size: {file_size_kb:.1f} KB")
    print()

    # Load API key (only if testing OpenAI)
    api_key = None
    if not args.granite_only:
        api_key = load_api_key(args.env_file)

    # Test models
    granite_result = None
    openai_result = None

    if not args.openai_only:
        granite_result = describe_with_granite(args.image_path, LITERAL_PROMPT)
        print()

    if not args.granite_only:
        openai_result = describe_with_openai(args.image_path, LITERAL_PROMPT, api_key)
        print()

    # Print results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    if granite_result:
        print("--- GRANITE VISION 3.3 2B ---")
        print(f"Time: {granite_result['elapsed_time']:.2f}s")
        print()
        print(granite_result['description'])
        print()
        print()

    if openai_result:
        print("--- OPENAI GPT-4o VISION ---")
        print(f"Time: {openai_result['elapsed_time']:.2f}s")
        if 'usage' in openai_result:
            print(f"Tokens: {openai_result['usage']['total_tokens']} "
                  f"(prompt: {openai_result['usage']['prompt_tokens']}, "
                  f"completion: {openai_result['usage']['completion_tokens']})")
        print()
        print(openai_result['description'])
        print()
        print()

    # Comparison metrics
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()

    if granite_result and openai_result:
        print(f"Speed:  Granite {granite_result['elapsed_time']:.2f}s  vs  "
              f"OpenAI {openai_result['elapsed_time']:.2f}s")
        print(f"Length: Granite {len(granite_result['description'])} chars  vs  "
              f"OpenAI {len(openai_result['description'])} chars")
        print()

    # Save outputs if requested
    if args.save_outputs:
        base_name = args.image_path.stem

        if granite_result:
            granite_file = args.image_path.parent / f"{base_name}-granite.txt"
            granite_file.write_text(granite_result['description'])
            print(f"✓ Granite output saved to: {granite_file}")

        if openai_result:
            openai_file = args.image_path.parent / f"{base_name}-openai.txt"
            openai_file.write_text(openai_result['description'])
            print(f"✓ OpenAI output saved to: {openai_file}")

        if granite_result and openai_result:
            comparison_file = args.image_path.parent / f"{base_name}-comparison.txt"
            comparison_text = f"""Image: {args.image_path}
Size: {image_size[0]}x{image_size[1]} ({image_format})
File size: {file_size_kb:.1f} KB

{"=" * 80}
GRANITE VISION 3.3 2B
{"=" * 80}
Time: {granite_result['elapsed_time']:.2f}s

{granite_result['description']}

{"=" * 80}
OPENAI GPT-4o VISION
{"=" * 80}
Time: {openai_result['elapsed_time']:.2f}s
Tokens: {openai_result['usage']['total_tokens']} (prompt: {openai_result['usage']['prompt_tokens']}, completion: {openai_result['usage']['completion_tokens']})

{openai_result['description']}
"""
            comparison_file.write_text(comparison_text)
            print(f"✓ Comparison saved to: {comparison_file}")


if __name__ == '__main__':
    main()
