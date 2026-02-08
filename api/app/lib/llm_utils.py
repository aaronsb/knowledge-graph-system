"""
Shared LLM dispatch utility for vocabulary and ontology management.

Provides a single call_llm_sync() function that handles provider-specific
branching (OpenAI, Anthropic, Ollama) so callers don't duplicate dispatch
logic.  @verified 638bd880

All three provider SDKs are synchronous.  Callers that need async should
wrap with ``asyncio.to_thread(call_llm_sync, ...)``.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def call_llm_sync(
    ai_provider: Any,
    prompt: str,
    system_msg: str = "You are a knowledge graph expert. Respond with valid JSON only.",
    max_tokens: int = 300,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """
    Synchronous LLM call dispatching to OpenAI, Anthropic, or Ollama.

    Single source of truth for provider-branching logic used by vocabulary
    consolidation (pruning_strategies) and ontology annealing
    (annealing_evaluator).

    Args:
        ai_provider: AI provider instance with get_provider_name(), client
            (OpenAI/Anthropic) or session/base_url (Ollama).
        prompt: User prompt to send.
        system_msg: System message for context.
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.
        json_mode: Request structured JSON output.  Enables OpenAI
            response_format and Ollama format:"json".  Anthropic has no
            JSON mode; the system_msg should request JSON instead.

    Returns:
        Raw response text from the LLM, stripped of whitespace.

    Raises:
        ValueError: If provider type is unsupported.
    """
    provider_name = ai_provider.get_provider_name().lower()

    if provider_name == "openai":
        kwargs: dict = dict(
            model=ai_provider.extraction_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = ai_provider.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    elif provider_name == "anthropic":
        message = ai_provider.client.messages.create(
            model=ai_provider.extraction_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    elif "ollama" in provider_name:
        options: dict = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        if hasattr(ai_provider, "top_p"):
            options["top_p"] = ai_provider.top_p

        payload: dict = {
            "model": ai_provider.extraction_model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"

        response = ai_provider.session.post(
            f"{ai_provider.base_url}/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    else:
        raise ValueError(f"Unsupported AI provider: {provider_name}")
