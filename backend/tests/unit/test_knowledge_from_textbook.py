"""Unit tests for textbook knowledge generation feature."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.knowledge import TextbookKnowledgeRequest, TextbookKnowledgeResponse
from app.services.ai_knowledge_extractor import generate_knowledge_from_textbook, AIKnowledgeExtractor


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_textbook_response():
    """Sample AI response for textbook knowledge generation."""
    return json.dumps({
        "knowledge_points": [
            {
                "name": "中华文明的起源",
                "description": "了解中华文明的早期形态，包括原始农耕文化和早期国家的形成",
                "excerpt": "中华文明起源于黄河流域和长江流域，距今约5000年前",
                "children": [
                    {
                        "name": "原始农业",
                        "description": "原始农耕文化的发展，包括水稻和粟的栽培",
                        "excerpt": "河姆渡居民种植水稻，半坡居民种植粟",
                        "children": []
                    },
                    {
                        "name": "早期国家",
                        "description": "早期国家的形成，包括夏朝的建立",
                        "excerpt": "约公元前2070年，禹建立夏朝",
                        "children": []
                    }
                ]
            },
            {
                "name": "夏商周的更替",
                "description": "掌握夏商周三个朝代的兴衰和更替过程",
                "excerpt": "夏朝灭亡后，商朝建立，后又周朝取代",
                "children": []
            }
        ]
    })


@pytest.fixture
def mock_ai_provider(sample_textbook_response):
    """Mock AI provider that returns sample textbook knowledge."""
    mock_response = MagicMock()
    mock_response.content = sample_textbook_response
    mock_response.input_tokens = 100
    mock_response.output_tokens = 500
    mock_response.total_tokens = 600
    mock_response.error_message = None
    return mock_response


# ---------------------------------------------------------------------------
# TextbookKnowledgeRequest validation tests
# ---------------------------------------------------------------------------

class TestTextbookKnowledgeRequestValidation:
    """Test request model validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        req = TextbookKnowledgeRequest(
            grade="初中七年级",
            subject="历史",
            version="人教版",
            max_points=80
        )
        assert req.grade == "初中七年级"
        assert req.subject == "历史"
        assert req.version == "人教版"
        assert req.max_points == 80
        assert req.chapter is None

    def test_default_version(self):
        """Test default version is 人教版."""
        req = TextbookKnowledgeRequest(grade="初中七年级", subject="历史")
        assert req.version == "人教版"
        assert req.max_points == 80

    def test_with_chapter(self):
        """Test request with specific chapter."""
        req = TextbookKnowledgeRequest(
            grade="初中七年级",
            subject="历史",
            chapter="第一单元"
        )
        assert req.chapter == "第一单元"

    def test_max_points_boundary_min(self):
        """Test max_points minimum boundary."""
        req = TextbookKnowledgeRequest(
            grade="初中七年级",
            subject="历史",
            max_points=1
        )
        assert req.max_points == 1

    def test_max_points_boundary_max(self):
        """Test max_points maximum boundary."""
        req = TextbookKnowledgeRequest(
            grade="初中七年级",
            subject="历史",
            max_points=200
        )
        assert req.max_points == 200

    def test_max_points_exceeds_limit(self):
        """Test max_points exceeding limit raises error."""
        with pytest.raises(Exception):
            TextbookKnowledgeRequest(
                grade="初中七年级",
                subject="历史",
                max_points=201
            )

    def test_empty_grade_raises_error(self):
        """Test empty grade raises validation error."""
        with pytest.raises(Exception):
            TextbookKnowledgeRequest(grade="", subject="历史")

    def test_empty_subject_raises_error(self):
        """Test empty subject raises validation error."""
        with pytest.raises(Exception):
            TextbookKnowledgeRequest(grade="初中七年级", subject="")


# ---------------------------------------------------------------------------
# generate_knowledge_from_textbook function tests
# ---------------------------------------------------------------------------

class TestGenerateKnowledgeFromTextbook:
    """Test generate_knowledge_from_textbook function."""

    @pytest.mark.asyncio
    async def test_basic_generation(self, mock_ai_provider):
        """Test basic textbook knowledge generation."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史",
                version="人教版"
            )

        assert result["success"] is True
        assert "knowledge_points" in result
        assert result["total"] > 0
        assert result["ria_enabled"] is True
        assert result["validation_enabled"] is True

    @pytest.mark.asyncio
    async def test_with_chapter(self, mock_ai_provider):
        """Test generation with specific chapter."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史",
                chapter="第一单元"
            )

        assert result["success"] is True
        assert "knowledge_points" in result

    @pytest.mark.asyncio
    async def test_different_version(self, mock_ai_provider):
        """Test generation with different textbook version."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史",
                version="北师大版"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_different_subject(self, mock_ai_provider):
        """Test generation for different subject."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="高中一年级",
                subject="数学",
                version="人教版"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_quality_validation_applied(self, mock_ai_provider):
        """Test that quality validation is applied to results."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史"
            )

        # Check validation results are present
        assert "validation_results" in result
        assert "triple_validation" in result["validation_results"]
        assert "hierarchy_validation" in result["validation_results"]
        assert "deduplication" in result["validation_results"]

    @pytest.mark.asyncio
    async def test_ai_failure_handling(self):
        """Test handling when AI call fails."""
        mock_call_ai = AsyncMock(side_effect=Exception("API timeout"))
        with patch.object(AIKnowledgeExtractor, '_call_ai', mock_call_ai):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史"
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_custom_max_points(self, mock_ai_provider):
        """Test generation with custom max_points."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史",
                max_points=50
            )

        assert result["success"] is True


# ---------------------------------------------------------------------------
# _build_textbook_prompt function tests
# ---------------------------------------------------------------------------

class TestBuildTextbookPrompt:
    """Test _build_textbook_prompt function."""

    def test_prompt_contains_grade(self):
        """Test prompt includes grade information."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "人教版", None, 80)
        assert "初中七年级" in prompt

    def test_prompt_contains_subject(self):
        """Test prompt includes subject information."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "人教版", None, 80)
        assert "历史" in prompt

    def test_prompt_contains_version(self):
        """Test prompt includes version information."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "北师大版", None, 80)
        assert "北师大版" in prompt

    def test_prompt_contains_chapter(self):
        """Test prompt includes chapter when specified."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "人教版", "第一单元", 80)
        assert "第一单元" in prompt

    def test_prompt_shows_full_book_without_chapter(self):
        """Test prompt shows '全册' when no chapter specified."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "人教版", None, 80)
        assert "全册" in prompt

    def test_prompt_contains_max_points(self):
        """Test prompt includes max_points limit."""
        from app.services.ai_knowledge_extractor import _build_textbook_prompt

        prompt = _build_textbook_prompt("初中七年级", "历史", "人教版", None, 50)
        assert "50" in prompt


# ---------------------------------------------------------------------------
# RIA++ validation integration tests
# ---------------------------------------------------------------------------

class TestRIAValidationIntegration:
    """Test that RIA++ validation is properly applied."""

    @pytest.mark.asyncio
    async def test_triple_validation_runs(self, mock_ai_provider):
        """Test that triple validation is executed."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史"
            )

        validation_results = result.get("validation_results", {})
        assert validation_results.get("triple_validation", {}).get("status") == "completed"

    @pytest.mark.asyncio
    async def test_hierarchy_validation_runs(self, mock_ai_provider):
        """Test that hierarchy validation is executed."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史"
            )

        validation_results = result.get("validation_results", {})
        assert validation_results.get("hierarchy_validation", {}).get("status") == "completed"

    @pytest.mark.asyncio
    async def test_deduplication_runs(self, mock_ai_provider):
        """Test that deduplication is executed."""
        with patch.object(
            AIKnowledgeExtractor,
            '_call_ai',
            new_callable=AsyncMock,
            return_value=mock_ai_provider
        ):
            result = await generate_knowledge_from_textbook(
                grade="初中七年级",
                subject="历史"
            )

        validation_results = result.get("validation_results", {})
        assert validation_results.get("deduplication", {}).get("status") == "completed"


# ---------------------------------------------------------------------------
# Response model tests
# ---------------------------------------------------------------------------

class TestTextbookKnowledgeResponse:
    """Test TextbookKnowledgeResponse model."""

    def test_success_response(self):
        """Test successful response creation."""
        resp = TextbookKnowledgeResponse(
            success=True,
            knowledge_points=[{"name": "test", "description": "test", "children": []}],
            total=1
        )
        assert resp.success is True
        assert resp.total == 1
        assert resp.ria_enabled is True
        assert resp.validation_enabled is True
        assert resp.quality_warnings == []

    def test_response_with_warnings(self):
        """Test response with quality warnings."""
        resp = TextbookKnowledgeResponse(
            success=True,
            knowledge_points=[],
            total=0,
            quality_warnings=["warning1", "warning2"]
        )
        assert len(resp.quality_warnings) == 2
