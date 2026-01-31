"""
Unit tests for Breathing Evaluator (ADR-200 Phase 3b).

Tests LLM evaluation for ontology promotion and demotion decisions.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from api.app.lib.breathing_evaluator import (
    llm_evaluate_promotion,
    llm_evaluate_demotion,
    PromotionDecision,
    DemotionDecision,
    _call_llm,
)


@pytest.fixture
def mock_openai_provider():
    """Mock OpenAI provider that returns JSON responses."""
    provider = MagicMock()
    provider.get_provider_name.return_value = "openai"
    provider.extraction_model = "gpt-4o-mini"
    return provider


@pytest.fixture
def mock_anthropic_provider():
    """Mock Anthropic provider."""
    provider = MagicMock()
    provider.get_provider_name.return_value = "anthropic"
    provider.extraction_model = "claude-sonnet-4-20250514"
    return provider


@pytest.fixture
def mock_ollama_provider():
    """Mock Ollama provider."""
    provider = MagicMock()
    provider.get_provider_name.return_value = "ollama_local"
    provider.extraction_model = "mistral"
    provider.base_url = "http://localhost:11434"
    provider.session = MagicMock()
    return provider


def make_openai_response(content: str):
    """Create a mock OpenAI chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def make_anthropic_response(content: str):
    """Create a mock Anthropic message response."""
    message = MagicMock()
    message.content = [MagicMock()]
    message.content[0].text = content
    return message


@pytest.mark.unit
class TestPromotionDecision:
    """Tests for the PromotionDecision dataclass."""

    def test_default_fields(self):
        d = PromotionDecision(should_promote=True, reasoning="test")
        assert d.should_promote is True
        assert d.reasoning == "test"
        assert d.suggested_name is None
        assert d.suggested_description is None

    def test_full_fields(self):
        d = PromotionDecision(
            should_promote=True,
            reasoning="Strong nucleus",
            suggested_name="new-domain",
            suggested_description="A new domain"
        )
        assert d.suggested_name == "new-domain"


@pytest.mark.unit
class TestDemotionDecision:
    """Tests for the DemotionDecision dataclass."""

    def test_default_fields(self):
        d = DemotionDecision(should_demote=False, reasoning="Keep it")
        assert d.should_demote is False
        assert d.absorption_target is None

    def test_with_target(self):
        d = DemotionDecision(
            should_demote=True,
            reasoning="Too small",
            absorption_target="parent-domain"
        )
        assert d.absorption_target == "parent-domain"


@pytest.mark.unit
class TestCallLLM:
    """Tests for the _call_llm helper with different providers."""

    @pytest.mark.asyncio
    async def test_openai_provider(self, mock_openai_provider):
        """OpenAI provider returns parsed JSON."""
        response_json = json.dumps({"should_promote": True, "reasoning": "Good nucleus"})
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(response_json)
        )

        result = await _call_llm(
            prompt="test prompt",
            ai_provider=mock_openai_provider,
            parse_fn=lambda r: PromotionDecision(
                should_promote=r.get("should_promote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=PromotionDecision(should_promote=False, reasoning="fallback"),
        )

        assert result.should_promote is True
        assert result.reasoning == "Good nucleus"

    @pytest.mark.asyncio
    async def test_anthropic_provider(self, mock_anthropic_provider):
        """Anthropic provider returns parsed JSON."""
        response_json = json.dumps({"should_demote": True, "reasoning": "Too small"})
        mock_anthropic_provider.client.messages.create.return_value = (
            make_anthropic_response(response_json)
        )

        result = await _call_llm(
            prompt="test prompt",
            ai_provider=mock_anthropic_provider,
            parse_fn=lambda r: DemotionDecision(
                should_demote=r.get("should_demote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=DemotionDecision(should_demote=False, reasoning="fallback"),
        )

        assert result.should_demote is True

    @pytest.mark.asyncio
    async def test_json_in_markdown_block(self, mock_openai_provider):
        """Handles JSON wrapped in markdown code blocks."""
        content = '```json\n{"should_promote": false, "reasoning": "Crossroads concept"}\n```'
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(content)
        )

        result = await _call_llm(
            prompt="test",
            ai_provider=mock_openai_provider,
            parse_fn=lambda r: PromotionDecision(
                should_promote=r.get("should_promote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=PromotionDecision(should_promote=False, reasoning="fallback"),
        )

        assert result.should_promote is False
        assert "Crossroads" in result.reasoning

    @pytest.mark.asyncio
    async def test_invalid_json_returns_fallback(self, mock_openai_provider):
        """Invalid JSON response returns fallback decision."""
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response("This is not JSON at all")
        )

        fallback = PromotionDecision(should_promote=False, reasoning="LLM failed")
        result = await _call_llm(
            prompt="test",
            ai_provider=mock_openai_provider,
            parse_fn=lambda r: PromotionDecision(
                should_promote=r.get("should_promote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=fallback,
        )

        assert result.should_promote is False
        assert result.reasoning == "LLM failed"

    @pytest.mark.asyncio
    async def test_provider_exception_returns_fallback(self, mock_openai_provider):
        """Provider exception returns fallback decision."""
        mock_openai_provider.client.chat.completions.create.side_effect = Exception("API error")

        fallback = DemotionDecision(should_demote=False, reasoning="LLM evaluation failed")
        result = await _call_llm(
            prompt="test",
            ai_provider=mock_openai_provider,
            parse_fn=lambda r: DemotionDecision(
                should_demote=r.get("should_demote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=fallback,
        )

        assert result.should_demote is False

    @pytest.mark.asyncio
    async def test_unsupported_provider_returns_fallback(self):
        """Unsupported provider returns fallback."""
        provider = MagicMock()
        provider.get_provider_name.return_value = "unknown_provider"

        fallback = PromotionDecision(should_promote=False, reasoning="unsupported")
        result = await _call_llm(
            prompt="test",
            ai_provider=provider,
            parse_fn=lambda r: PromotionDecision(
                should_promote=r.get("should_promote", False),
                reasoning=r.get("reasoning", ""),
            ),
            fallback=fallback,
        )

        assert result.reasoning == "unsupported"


@pytest.mark.unit
class TestLLMEvaluatePromotion:
    """Tests for llm_evaluate_promotion."""

    @pytest.mark.asyncio
    async def test_promotion_approved(self, mock_openai_provider):
        """LLM approves promotion for nucleus concept."""
        response_json = json.dumps({
            "should_promote": True,
            "reasoning": "PostgreSQL is a coherent sub-domain",
            "suggested_name": "postgresql",
            "suggested_description": "PostgreSQL database concepts"
        })
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(response_json)
        )

        result = await llm_evaluate_promotion(
            concept_label="PostgreSQL",
            concept_description="Relational database system",
            degree=25,
            ontology_name="database-architecture",
            ontology_concept_count=100,
            top_neighbors=["SQL", "Indexing", "Query Planning"],
            affinity_targets=[],
            ai_provider=mock_openai_provider,
        )

        assert result.should_promote is True
        assert result.suggested_name == "postgresql"

    @pytest.mark.asyncio
    async def test_promotion_rejected(self, mock_openai_provider):
        """LLM rejects promotion for crossroads concept."""
        response_json = json.dumps({
            "should_promote": False,
            "reasoning": "Management is too generic, would create a grab-bag ontology"
        })
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(response_json)
        )

        result = await llm_evaluate_promotion(
            concept_label="Management",
            concept_description="Generic management term",
            degree=30,
            ontology_name="business",
            ontology_concept_count=50,
            top_neighbors=[],
            affinity_targets=[],
            ai_provider=mock_openai_provider,
        )

        assert result.should_promote is False


@pytest.mark.unit
class TestLLMEvaluateDemotion:
    """Tests for llm_evaluate_demotion."""

    @pytest.mark.asyncio
    async def test_demotion_approved(self, mock_openai_provider):
        """LLM approves demotion for low-quality ontology."""
        response_json = json.dumps({
            "should_demote": True,
            "reasoning": "Very low mass, content belongs in target",
            "absorption_target": "distributed-systems"
        })
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(response_json)
        )

        result = await llm_evaluate_demotion(
            ontology_name="tiny-domain",
            mass_score=0.05,
            coherence_score=0.3,
            protection_score=-0.1,
            concept_count=3,
            affinity_targets=[{"other_ontology": "distributed-systems", "shared_concept_count": 2, "affinity_score": 0.8}],
            ai_provider=mock_openai_provider,
        )

        assert result.should_demote is True
        assert result.absorption_target == "distributed-systems"

    @pytest.mark.asyncio
    async def test_demotion_rejected(self, mock_openai_provider):
        """LLM rejects demotion for young but focused ontology."""
        response_json = json.dumps({
            "should_demote": False,
            "reasoning": "Young domain with good coherence, needs more content"
        })
        mock_openai_provider.client.chat.completions.create.return_value = (
            make_openai_response(response_json)
        )

        result = await llm_evaluate_demotion(
            ontology_name="emerging-topic",
            mass_score=0.1,
            coherence_score=0.85,
            protection_score=0.08,
            concept_count=8,
            affinity_targets=[],
            ai_provider=mock_openai_provider,
        )

        assert result.should_demote is False
