"""Unit tests for hybrid_question_generator pure functions."""

import random

import pytest

from app.services.hybrid_question_generator import (
    KP_DEFINITION,
    KP_GENERAL,
    KP_NORMATIVE,
    KP_PENALTY,
    KP_PROCEDURAL,
    KP_PROHIBITIVE,
    KP_SCOPE,
    KnowledgePointInfo,
    build_question_plans,
    classify_knowledge_point,
    rule_generate_essay,
    rule_generate_multiple_choice,
    rule_generate_single_choice,
    rule_generate_true_false,
)

# ---------------------------------------------------------------------------
# classify_knowledge_point
# ---------------------------------------------------------------------------


class TestClassifyKnowledgePoint:
    @pytest.mark.parametrize(
        "name,desc,expected",
        [
            ("禁止性规定", "不得擅自修改", KP_PROHIBITIVE),
            ("处罚条款", "罚款并撤销", KP_PENALTY),
            ("应当遵守", "必须依法", KP_NORMATIVE),
            ("审批程序", "经批准后", KP_PROCEDURAL),
            ("定义", "是指...", KP_DEFINITION),
            ("适用范围", "适用于...", KP_SCOPE),
            ("普通知识点", "一般内容", KP_GENERAL),
        ],
    )
    def test_classify(self, name, desc, expected):
        assert classify_knowledge_point(name, desc) == expected


# ---------------------------------------------------------------------------
# build_question_plans
# ---------------------------------------------------------------------------


class TestBuildQuestionPlans:
    def test_empty_kps(self):
        plans = build_question_plans([], 10, ["single_choice"])
        assert plans == []

    def test_basic_plan(self):
        kps = [KnowledgePointInfo(id=1, name="X", description="X的描述")]
        plans = build_question_plans(kps, 4, ["single_choice"])
        assert len(plans) >= 1
        assert sum(p.total_count for p in plans) >= 4

    def test_count_zero(self):
        kps = [KnowledgePointInfo(id=1, name="X", description="")]
        plans = build_question_plans(kps, 0, ["single_choice"])
        assert all(p.total_count == 0 for p in plans)


# ---------------------------------------------------------------------------
# rule_generate_* (seed-randomness for deterministic output)
# ---------------------------------------------------------------------------


def _make_kp(name: str, desc: str, kp_type: str = KP_GENERAL) -> KnowledgePointInfo:
    return KnowledgePointInfo(id=1, name=name, description=desc, kp_type=kp_type)


class TestRuleGenerate:
    def test_single_choice_deterministic(self):
        random.seed(42)
        kp = _make_kp("测试定义", "是指一种明确的定义描述", KP_DEFINITION)
        q = rule_generate_single_choice(kp, [kp])
        assert q is not None
        assert q["question_type"] == "single_choice"
        assert len(q["options"]) >= 2

    def test_true_false_deterministic(self):
        random.seed(42)
        kp = _make_kp("测试规范", "应当遵守相关规定，必须严格执行", KP_NORMATIVE)
        q = rule_generate_true_false(kp, [kp])
        assert q is not None
        assert q["question_type"] == "true_false"
        assert q["answer"] in ("true", "false")

    def test_multiple_choice_deterministic(self):
        random.seed(42)
        kp = _make_kp("测试范围", "适用于考试情形，招聘情形，审核情形", KP_SCOPE)
        q = rule_generate_multiple_choice(kp, [kp])
        assert q is not None
        assert q["question_type"] == "multiple_choice"
        assert len(q["options"]) >= 2

    def test_essay_deterministic(self):
        random.seed(42)
        kp = _make_kp("测试程序", "经过审批批准程序后才能执行", KP_PROCEDURAL)
        q = rule_generate_essay(kp, [kp])
        assert q is not None
        assert q["question_type"] == "essay"
        assert len(q["answer"]) > 0
