"""
Golden fidelity check for the #457 vision facade collapse (ADR-802 §4, ADR-305).

LLM output at temperature 0.1 is near-deterministic but NOT byte-identical
run-to-run, so a text diff would be noisy even comparing old-vs-old. The
deterministic, meaningful fidelity proof is the REQUEST PAYLOAD the provider
SDK receives: if the collapsed AIProvider.describe_image sends the same request
the old vision_providers path sent, image->prose behaviour is preserved (modulo
provider nondeterminism, which is out of our control).

Part 1 (deterministic): capture the new path's outgoing Anthropic request and
assert it equals the reconstructed old vision_providers request, for the same
(image, prompt, model, temperature, detail=None) the ingestion worker uses.

Part 2 (live, optional): run the real worker path (resolve_vision_selection →
get_provider → describe_image) against the configured Anthropic provider on a
real ADR-305 research image, and print the description so quality is eyeballable.

Run inside the API container:
    docker exec kg-api-dev python scripts/development/diagnostics/golden_describe_image.py
"""

import base64
import copy
import sys
from unittest.mock import MagicMock

from api.app.lib.ai_providers import AnthropicProvider, _anthropic_drops_sampling_params
from api.app.lib.vision_providers import LITERAL_DESCRIPTION_PROMPT, resolve_vision_selection

import os
# Default to an ADR-305 research image; override with GOLDEN_IMAGE for an
# ad-hoc article (e.g. the Old Town Wichita cowtown photos).
IMAGE_PATH = os.getenv("GOLDEN_IMAGE", "docs/research/vision-testing/test-images/old_western_town_scene.jpg")
MODEL = "claude-sonnet-4-6"  # representative active vision model


def _old_vision_providers_anthropic_request(image_bytes, prompt, model):
    """Reconstruct EXACTLY the request the deleted
    vision_providers.AnthropicVisionProvider.describe_image built, for a
    png/jpeg image (the ADR-305-validated formats)."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = "image/png" if image_bytes.startswith(b"\x89PNG") else "image/jpeg"
    request_kwargs = {
        "model": model,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    if not _anthropic_drops_sampling_params(model):
        request_kwargs["temperature"] = 0.1
    return request_kwargs


def _capture_new_request(image_bytes, prompt, model):
    """Capture the request the NEW AIProvider.describe_image sends, using the
    worker's exact args (model threaded, detail=None, temperature=0.1)."""
    p = object.__new__(AnthropicProvider)
    p.client = MagicMock()
    captured = {}

    def _record(**kwargs):
        captured.update(kwargs)
        msg = MagicMock()
        msg.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "ok"
        msg.content = [block]
        msg.usage.input_tokens = 1
        msg.usage.output_tokens = 1
        return msg

    p.client.messages.create.side_effect = _record
    p.describe_image(image_bytes, prompt, model=model, detail=None, temperature=0.1)
    return captured


def part1_request_equivalence(image_bytes):
    old = _old_vision_providers_anthropic_request(image_bytes, LITERAL_DESCRIPTION_PROMPT, MODEL)
    new = _capture_new_request(image_bytes, LITERAL_DESCRIPTION_PROMPT, MODEL)
    # Compare the SDK-facing payloads.
    if copy.deepcopy(old) == copy.deepcopy(new):
        print("✅ PART 1 — request payloads IDENTICAL (old vision_providers ≡ new AIProvider)")
        print(f"   model={new['model']} max_tokens={new['max_tokens']} "
              f"temperature={new.get('temperature')} "
              f"content_order={[c['type'] for c in new['messages'][0]['content']]} "
              f"media_type={new['messages'][0]['content'][0]['source']['media_type']}")
        return True
    print("❌ PART 1 — request payloads DIFFER")
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            # Don't dump the base64 image; summarize.
            if k == "messages":
                print(f"   messages differ (content structure / media_type / order)")
            else:
                print(f"   {k}: old={old.get(k)!r} new={new.get(k)!r}")
    return False


async def _ensure_embedding_manager():
    """Initialize the embedding model manager singleton.

    get_embedding_provider() builds a LocalEmbeddingProvider, which needs the
    manager the API server initializes at startup. A bare script doesn't have
    it, so get_provider() would wrongly fail with "requires an embedding
    provider" — a harness artifact, not a real regression. Initialize it here
    so PART 2 reproduces the actual worker runtime.
    """
    from api.app.lib.embedding_model_manager import init_embedding_model_manager
    await init_embedding_model_manager()


def part2_live(image_bytes, label):
    import asyncio
    print(f"\n--- PART 2 — live worker path (real provider call) [{label}] ---")
    try:
        asyncio.run(_ensure_embedding_manager())
    except Exception as e:
        print(f"   ⚠️  embedding manager init failed (live call may fail): {e}")
    try:
        provider_name, vision_model = resolve_vision_selection()
        print(f"   resolved vision slot: provider={provider_name} model={vision_model}")
    except Exception as e:
        print(f"   ⚠️  resolve_vision_selection failed: {e}")
        return
    try:
        from api.app.lib.ai_providers import get_provider
        provider = get_provider(provider_name)
        out = provider.describe_image(
            image_bytes, LITERAL_DESCRIPTION_PROMPT,
            model=vision_model, detail=None, temperature=0.1,
        )
        text = out["text"]
        print(f"   ✅ described: {len(text)} chars, tokens={out['tokens']}, "
              f"model={out['model']}, provider={out['provider']}")
        print("   --- first 400 chars ---")
        print("   " + text[:400].replace("\n", "\n   "))
    except Exception as e:
        print(f"   ⚠️  live call failed: {e}")


def _iter_images(path):
    """Yield (label, bytes) for a file or every image in a directory."""
    if os.path.isdir(path):
        names = sorted(
            n for n in os.listdir(path)
            if n.lower().endswith((".png", ".jpg", ".jpeg"))
        )
        for n in names:
            with open(os.path.join(path, n), "rb") as f:
                yield n, f.read()
    else:
        with open(path, "rb") as f:
            yield os.path.basename(path), f.read()


def main():
    # PART1_ONLY skips the live (token-spending) calls — useful to prove
    # request-payload equivalence across a whole image set for free.
    part1_only = os.getenv("GOLDEN_PART1_ONLY") == "1"
    all_ok = True
    for label, image_bytes in _iter_images(IMAGE_PATH):
        print(f"\n========== {label} ({len(image_bytes)} bytes) ==========")
        ok = part1_request_equivalence(image_bytes)
        all_ok = all_ok and ok
        if not part1_only:
            part2_live(image_bytes, label)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
