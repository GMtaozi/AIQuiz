"""Unit tests for ai_question service pure functions."""

import json

from app.services.ai_question import _sanitize_for_prompt, _try_parse_questions_json


class TestSanitizeForPrompt:
    def test_normal_text(self):
        assert "hello" in _sanitize_for_prompt("hello world")

    def test_script_tag_removed(self):
        result = _sanitize_for_prompt("<script>alert(1)</script>")
        assert "<script>" not in result

    def test_javascript_protocol_removed(self):
        result = _sanitize_for_prompt('click <a href="javascript:alert(1)">here</a>')
        assert "javascript:" not in result

    def test_on_event_removed(self):
        result = _sanitize_for_prompt('<div onclick="alert(1)">text</div>')
        assert "onclick" not in result

    def test_truncation(self):
        """_sanitize_for_prompt hard-truncates to 500 chars."""
        long = "a" * 1000
        result = _sanitize_for_prompt(long)
        assert len(result) <= 500


class TestTryParseQuestionsJson:
    def test_valid_json_array(self):
        data = [{"content": "Q1", "answer": "A", "question_type": "single_choice", "difficulty": 1}]
        result = _try_parse_questions_json(json.dumps(data))
        assert result is not None
        assert len(result) == 1

    def test_empty_list(self):
        result = _try_parse_questions_json("[]")
        assert result == []

    def test_invalid_json_returns_none(self):
        result = _try_parse_questions_json("not json at all")
        assert result is None

    def test_truncated_json_returns_none(self):
        """JSON truncated mid-string should return None, not raise."""
        truncated = '[{"content": "Q1", "answer": "A"'
        result = _try_parse_questions_json(truncated)
        assert result is None
