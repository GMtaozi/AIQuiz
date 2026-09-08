"""Unit tests for enhanced AI Knowledge Extractor with RIA++ framework and triple validation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_knowledge_extractor import AIKnowledgeExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Create a fresh AIKnowledgeExtractor instance."""
    return AIKnowledgeExtractor()


@pytest.fixture
def sample_knowledge_tree():
    """Sample knowledge tree for testing validation methods."""
    return [
        {
            "name": "司法鉴定基本规范",
            "description": "司法鉴定应当遵循科学、客观、公正的原则，鉴定人必须具备相应资格",
            "excerpt": "第一条 司法鉴定应当遵循科学、客观、公正的原则。第二条 鉴定人应当具备相应资格。",
            "children": [
                {
                    "name": "什么是司法鉴定",
                    "description": "司法鉴定是指在诉讼活动中鉴定人运用科学技术或专门知识对专门性问题进行鉴别和判断的活动",
                    "excerpt": "本办法所称司法鉴定，是指在诉讼活动中鉴定人运用科学技术或者专门知识对诉讼涉及的专门性问题进行鉴别和判断并提供鉴定意见的活动。",
                    "children": [
                        {
                            "name": "要点1：鉴定人资格",
                            "description": "鉴定人应当具备相应的专业知识和资格条件",
                            "excerpt": "鉴定人应当具备下列条件：（一）具有与所申请从事的司法鉴定业务相关的高级专业技术职称；（二）具有与所申请从事的司法鉴定业务相关的专业执业资格或者高等院校相关专业本科以上学历，从事相关工作五年以上；",
                            "children": [],
                        },
                        {
                            "name": "要点2：鉴定程序",
                            "description": "鉴定应当按照规定的程序进行，包括委托、受理、实施、出具鉴定意见等环节",
                            "excerpt": "司法鉴定一般包括委托、受理、实施鉴定、出具鉴定意见书等环节。",
                            "children": [],
                        },
                    ],
                },
                {
                    "name": "适用范围：鉴定机构",
                    "description": "司法鉴定机构应当具备必要的仪器、设备和符合条件的鉴定人",
                    "excerpt": "司法鉴定机构应当具备必要的仪器、设备和符合条件的鉴定人，经省级司法行政机关批准，取得《司法鉴定许可证》。",
                    "children": [],
                },
            ],
        },
        {
            "name": "医师执业资格管理",
            "description": "医师执业必须取得执业证书，注册后方可执业",
            "excerpt": "医师执业必须取得医师执业证书，经注册后医疗卫生机构中从事医疗卫生服务工作。",
            "children": [],
        },
    ]


@pytest.fixture
def existing_knowledge():
    """Sample existing knowledge base for deduplication testing."""
    return [
        {
            "name": "司法鉴定基本规范",
            "description": "司法鉴定应当遵循科学、客观、公正的原则",
            "excerpt": "第一条 司法鉴定应当遵循科学、客观、公正的原则。",
        },
        {
            "name": "鉴定人资格条件",
            "description": "鉴定人应当具备相应的专业知识和资格条件",
            "excerpt": "鉴定人应当具备下列条件：（一）具有与所申请从事的司法鉴定业务相关的高级专业技术职称；",
        },
    ]


# ---------------------------------------------------------------------------
# RIA++ Prompt Builder Tests
# ---------------------------------------------------------------------------


class TestBuildRiaPrompt:
    """Tests for _build_ria_prompt method."""

    def test_build_ria_prompt_contains_framework(self, extractor):
        """RIA++ prompt should contain all five phases."""
        prompt = extractor._build_ria_prompt(
            document_content="测试文档内容",
            document_name="测试文档",
            category="test",
            max_points=50,
        )
        assert "R (Rule)" in prompt
        assert "I (Instruction)" in prompt
        assert "A (Application)" in prompt
        assert "E (Example)" in prompt
        assert "B (Boundary)" in prompt

    def test_build_ria_prompt_contains_document_info(self, extractor):
        """RIA++ prompt should include document name and category."""
        prompt = extractor._build_ria_prompt(
            document_content="测试内容",
            document_name="司法鉴定规范.pdf",
            category="legal",
            max_points=30,
        )
        assert "司法鉴定规范.pdf" in prompt
        assert "legal" in prompt
        assert "30" in prompt

    def test_build_ria_prompt_contains_json_format(self, extractor):
        """RIA++ prompt should include JSON format specification."""
        prompt = extractor._build_ria_prompt(
            document_content="测试内容",
            document_name="测试",
            category="test",
            max_points=50,
        )
        assert '"knowledge_points"' in prompt
        assert '"name"' in prompt
        assert '"description"' in prompt
        assert '"excerpt"' in prompt
        assert '"children"' in prompt

    def test_build_ria_prompt_contains_document_content(self, extractor):
        """RIA++ prompt should include the document content."""
        content = "这是一份关于司法鉴定的测试文档内容"
        prompt = extractor._build_ria_prompt(
            document_content=content,
            document_name="测试",
            category="test",
            max_points=50,
        )
        assert content in prompt

    def test_build_ria_prompt_respects_max_points(self, extractor):
        """RIA++ prompt should include max_points limit."""
        prompt = extractor._build_ria_prompt(
            document_content="测试",
            document_name="测试",
            category="test",
            max_points=25,
        )
        assert "25" in prompt


# ---------------------------------------------------------------------------
# Triple Validation Tests
# ---------------------------------------------------------------------------


class TestValidateKnowledgeQuality:
    """Tests for _validate_knowledge_quality method."""

    def test_validate_returns_tuple(self, extractor, sample_knowledge_tree):
        """Validation should return (tree, warnings) tuple."""
        result = extractor._validate_knowledge_quality(sample_knowledge_tree)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_validate_adds_quality_flags(self, extractor, sample_knowledge_tree):
        """Validation should add quality_flag to each node."""
        validated_tree, _ = extractor._validate_knowledge_quality(sample_knowledge_tree)
        for node in validated_tree:
            assert "quality_flag" in node
            for child in node.get("children", []):
                assert "quality_flag" in child

    def test_validate_with_existing_knowledge(self, extractor, sample_knowledge_tree, existing_knowledge):
        """Validation should detect duplicates when existing knowledge is provided."""
        _, warnings = extractor._validate_knowledge_quality(
            sample_knowledge_tree, existing_knowledge
        )
        # Should have warnings about duplicates
        duplicate_warnings = [w for w in warnings if "高度相似" in w or "duplicate" in w.lower()]
        assert len(duplicate_warnings) > 0

    def test_validate_without_existing_knowledge(self, extractor, sample_knowledge_tree):
        """Validation should work without existing knowledge."""
        validated_tree, warnings = extractor._validate_knowledge_quality(
            sample_knowledge_tree, None
        )
        assert len(validated_tree) > 0


class TestValidateCrossDomainGenerality:
    """Tests for _validate_cross_domain_generality method."""

    def test_detects_too_specific_node(self, extractor):
        """Should flag nodes with overly specific dates."""
        nodes = [
            {
                "name": "2023年5月15日规定",
                "description": "",
                "excerpt": "",
                "children": [],
            }
        ]
        validated, warnings = extractor._validate_cross_domain_generality(nodes)
        assert validated[0].get("quality_flag") == "low_generality"
        assert any("过于细碎" in w for w in warnings)

    def test_detects_low_content_leaf(self, extractor):
        """Should flag leaf nodes with very short content."""
        nodes = [
            {
                "name": "短",
                "description": "",
                "excerpt": "",
                "children": [],
            }
        ]
        validated, warnings = extractor._validate_cross_domain_generality(nodes)
        assert validated[0].get("quality_flag") == "low_content"

    def test_approves_good_node(self, extractor):
        """Should approve nodes with sufficient content."""
        nodes = [
            {
                "name": "司法鉴定基本原则",
                "description": "司法鉴定应当遵循科学、客观、公正的原则，这是鉴定活动的核心要求",
                "excerpt": "第一条 司法鉴定应当遵循科学、客观、公正的原则。",
                "children": [],
            }
        ]
        validated, warnings = extractor._validate_cross_domain_generality(nodes)
        assert validated[0].get("quality_flag") == "ok"


class TestValidatePredictivePower:
    """Tests for _validate_predictive_power method."""

    def test_detects_predictive_content(self, extractor):
        """Should detect nodes with conditional/predictive language."""
        nodes = [
            {
                "name": "鉴定人资格条件",
                "description": "如果鉴定人不具备相应资格，那么其出具的鉴定意见无效",
                "excerpt": "鉴定人应当具备相应资格，否则鉴定意见无效。",
                "children": [],
            }
        ]
        validated, _ = extractor._validate_predictive_power(nodes)
        assert validated[0].get("quality_flag") == "high_predictive"

    def test_detects_low_predictive_content(self, extractor):
        """Should flag nodes without predictive language."""
        nodes = [
            {
                "name": "某规定",
                "description": "这是一个普通描述",
                "excerpt": "普通内容",
                "children": [],
            }
        ]
        validated, warnings = extractor._validate_predictive_power(nodes)
        assert validated[0].get("quality_flag") == "low_predictive"
        assert any("缺乏预测力" in w for w in warnings)


class TestValidateUniqueness:
    """Tests for _validate_uniqueness method."""

    def test_detects_duplicate_with_existing(self, extractor, existing_knowledge):
        """Should detect duplicates against existing knowledge."""
        nodes = [
            {
                "name": "司法鉴定基本规范",
                "description": "司法鉴定应当遵循科学、客观、公正的原则",
                "excerpt": "第一条",
                "children": [],
            }
        ]
        validated, warnings = extractor._validate_uniqueness(nodes, existing_knowledge)
        assert validated[0].get("quality_flag") == "duplicate"
        assert any("高度相似" in w for w in warnings)

    def test_approves_unique_node(self, extractor, existing_knowledge):
        """Should approve nodes that are not duplicates."""
        nodes = [
            {
                "name": "完全新的知识点",
                "description": "这是一个全新的内容，与已有知识无关",
                "excerpt": "新内容",
                "children": [],
            }
        ]
        validated, _ = extractor._validate_uniqueness(nodes, existing_knowledge)
        assert validated[0].get("quality_flag") == "unique"

    def test_works_without_existing_knowledge(self, extractor):
        """Should work when no existing knowledge is provided."""
        nodes = [
            {
                "name": "测试知识点",
                "description": "测试描述",
                "excerpt": "测试内容",
                "children": [],
            }
        ]
        validated, _ = extractor._validate_uniqueness(nodes, None)
        assert validated[0].get("quality_flag") == "unique"


# ---------------------------------------------------------------------------
# Hierarchy Validation Tests
# ---------------------------------------------------------------------------


class TestValidateHierarchy:
    """Tests for _validate_hierarchy method."""

    def test_detects_low_parent_overlap(self, extractor):
        """Should detect child nodes with no keyword overlap with parent."""
        nodes = [
            {
                "name": "司法鉴定规范",
                "description": "关于司法鉴定的规范",
                "excerpt": "第一条",
                "children": [
                    {
                        "name": "烹饪技巧指南",
                        "description": "如何烹饪美食",
                        "excerpt": "烹饪内容",
                        "children": [],
                    }
                ],
            }
        ]
        validated, warnings = extractor._validate_hierarchy(nodes)
        child = validated[0]["children"][0]
        assert child.get("hierarchy_warning") == "low_parent_overlap"
        assert any("缺乏关键词关联" in w for w in warnings)

    def test_approves_good_hierarchy(self, extractor, sample_knowledge_tree):
        """Should approve nodes with proper parent-child relationships."""
        validated, warnings = extractor._validate_hierarchy(sample_knowledge_tree)
        # The sample tree has good hierarchy, so no low_parent_overlap warnings
        overlap_warnings = [w for w in warnings if "缺乏关键词关联" in w]
        assert len(overlap_warnings) == 0

    def test_handles_deep_nesting(self, extractor):
        """Should handle deeply nested structures."""
        nodes = [
            {
                "name": "根节点",
                "description": "根描述",
                "excerpt": "根内容",
                "children": [
                    {
                        "name": "二级节点",
                        "description": "二级描述",
                        "excerpt": "二级内容",
                        "children": [
                            {
                                "name": "三级节点",
                                "description": "三级描述",
                                "excerpt": "三级内容",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        validated, _ = extractor._validate_hierarchy(nodes)
        assert len(validated) == 1


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------


class TestDeduplicateKnowledge:
    """Tests for _deduplicate_knowledge method."""

    def test_removes_internal_duplicates(self, extractor):
        """Should remove highly similar nodes within the tree."""
        nodes = [
            {
                "name": "司法鉴定规范",
                "description": "司法鉴定应当遵循科学、客观、公正的原则",
                "excerpt": "第一条",
                "children": [],
            },
            {
                "name": "司法鉴定规范",
                "description": "司法鉴定应当遵循科学、客观、公正的原则",
                "excerpt": "第一条",
                "children": [],
            },
        ]
        result, logs = extractor._deduplicate_knowledge(nodes)
        assert len(result) < len(nodes)
        assert any("移除重复" in log for log in logs)

    def test_merges_empty_nodes(self, extractor):
        """Should flag empty nodes for merging."""
        nodes = [
            {
                "name": "父节点",
                "description": "父描述",
                "excerpt": "父内容",
                "children": [
                    {
                        "name": "",
                        "description": "",
                        "excerpt": "",
                        "children": [],
                    }
                ],
            }
        ]
        result, logs = extractor._deduplicate_knowledge(nodes)
        child = result[0]["children"][0]
        assert child.get("merge_flag") == "empty_node"

    def test_detects_conflicts_with_existing(self, extractor, existing_knowledge):
        """Should detect conflicts with existing knowledge."""
        nodes = [
            {
                "name": "司法鉴定基本规范",
                "description": "司法鉴定应当遵循科学、客观、公正的原则（修订版）",
                "excerpt": "修订后的内容",
                "children": [],
            }
        ]
        result, logs = extractor._deduplicate_knowledge(nodes, existing_knowledge)
        assert result[0].get("conflict_status") == "update"

    def test_marks_new_knowledge(self, extractor, existing_knowledge):
        """Should mark truly new knowledge as 'new'."""
        nodes = [
            {
                "name": "全新的知识点",
                "description": "这是一个完全新的内容",
                "excerpt": "新内容",
                "children": [],
            }
        ]
        result, _ = extractor._deduplicate_knowledge(nodes, existing_knowledge)
        assert result[0].get("conflict_status") == "new"


class TestRemoveInternalDuplicates:
    """Tests for _remove_internal_duplicates method."""

    def test_removes_exact_duplicates(self, extractor):
        """Should remove exact duplicate nodes."""
        nodes = [
            {"name": "A", "description": "desc A", "excerpt": "", "children": []},
            {"name": "A", "description": "desc A", "excerpt": "", "children": []},
        ]
        result, logs = extractor._remove_internal_duplicates(nodes, 0.85)
        assert len(result) == 1

    def test_keeps_different_nodes(self, extractor):
        """Should keep nodes that are different."""
        nodes = [
            {"name": "A", "description": "desc A", "excerpt": "", "children": []},
            {"name": "B", "description": "desc B", "excerpt": "", "children": []},
        ]
        result, _ = extractor._remove_internal_duplicates(nodes, 0.85)
        assert len(result) == 2


class TestMergeRedundantNodes:
    """Tests for _merge_redundant_nodes method."""

    def test_promotes_single_child(self, extractor):
        """Should promote child when parent has no name and single child."""
        nodes = [
            {
                "name": "",
                "description": "",
                "excerpt": "",
                "children": [
                    {"name": "Child", "description": "desc", "excerpt": "", "children": []}
                ],
            }
        ]
        result, logs = extractor._merge_redundant_nodes(nodes)
        assert result[0]["name"] == "Child"
        assert any("合并空节点" in log for log in logs)

    def test_flags_empty_leaf(self, extractor):
        """Should flag empty leaf nodes."""
        nodes = [
            {
                "name": "Empty",
                "description": "",
                "excerpt": "",
                "children": [],
            }
        ]
        result, _ = extractor._merge_redundant_nodes(nodes)
        assert result[0].get("merge_flag") == "empty_node"


class TestDetectConflicts:
    """Tests for _detect_conflicts method."""

    def test_detects_update(self, extractor, existing_knowledge):
        """Should detect when a node updates existing knowledge."""
        nodes = [
            {
                "name": "司法鉴定基本规范",
                "description": "司法鉴定应当遵循科学、客观、公正的原则",
                "excerpt": "修订后的内容",
                "children": [],
            }
        ]
        result, logs = extractor._detect_conflicts(nodes, existing_knowledge, 0.85)
        assert result[0].get("conflict_status") == "update"

    def test_detects_related(self, extractor, existing_knowledge):
        """Should detect when a node is related but not identical."""
        nodes = [
            {
                "name": "司法鉴定相关问题",
                "description": "司法鉴定应当遵循相关原则",
                "excerpt": "相关内容",
                "children": [],
            }
        ]
        result, logs = extractor._detect_conflicts(nodes, existing_knowledge, 0.85)
        assert result[0].get("conflict_status") in ("related", "new")

    def test_marks_new(self, extractor, existing_knowledge):
        """Should mark completely new nodes."""
        nodes = [
            {
                "name": "完全不相关的主题",
                "description": "这是一个全新的领域",
                "excerpt": "新内容",
                "children": [],
            }
        ]
        result, _ = extractor._detect_conflicts(nodes, existing_knowledge, 0.85)
        assert result[0].get("conflict_status") == "new"


# ---------------------------------------------------------------------------
# Legacy Prompt Builder Tests
# ---------------------------------------------------------------------------


class TestBuildLegacyPrompt:
    """Tests for _build_legacy_prompt method."""

    def test_legacy_prompt_contains_format(self, extractor):
        """Legacy prompt should contain JSON format specification."""
        prompt = extractor._build_legacy_prompt(
            document_content="测试内容",
            document_name="测试文档",
            category="test",
            max_points=50,
        )
        assert '"knowledge_points"' in prompt
        assert "测试文档" in prompt

    def test_legacy_prompt_no_ria_framework(self, extractor):
        """Legacy prompt should NOT contain RIA++ framework."""
        prompt = extractor._build_legacy_prompt(
            document_content="测试内容",
            document_name="测试",
            category="test",
            max_points=50,
        )
        assert "R (Rule)" not in prompt
        assert "RIA++" not in prompt


# ---------------------------------------------------------------------------
# Quality Summary and Stats Tests
# ---------------------------------------------------------------------------


class TestQualitySummary:
    """Tests for get_quality_summary and collect_quality_stats methods."""

    def test_get_quality_summary(self, extractor):
        """Should return quality summary for a node."""
        node = {
            "name": "测试",
            "quality_flag": "ok",
            "hierarchy_warning": None,
            "conflict_status": "new",
        }
        summary = extractor.get_quality_summary(node)
        assert summary["name"] == "测试"
        assert summary["quality_flag"] == "ok"
        assert summary["conflict_status"] == "new"

    def test_collect_quality_stats(self, extractor):
        """Should collect statistics across the tree."""
        nodes = [
            {
                "name": "A",
                "quality_flag": "ok",
                "conflict_status": "new",
                "children": [
                    {
                        "name": "B",
                        "quality_flag": "low_predictive",
                        "conflict_status": "update",
                        "hierarchy_warning": "low_parent_overlap",
                        "children": [],
                    }
                ],
            }
        ]
        stats = extractor.collect_quality_stats(nodes)
        assert stats["total_nodes"] == 2
        assert stats["ok"] == 1
        assert stats["low_predictive"] == 1
        assert stats["conflict_new"] == 1
        assert stats["conflict_update"] == 1
        assert stats["hierarchy_warnings"] == 1


# ---------------------------------------------------------------------------
# Integration Tests for extract_knowledge_tree
# ---------------------------------------------------------------------------


class TestExtractKnowledgeTreeIntegration:
    """Integration tests for the enhanced extract_knowledge_tree method."""

    @pytest.mark.asyncio
    async def test_extract_with_ria_enabled(self, extractor):
        """Should use RIA++ prompt when use_ria=True."""
        mock_response = MagicMock()
        mock_response.content = '{"knowledge_points": [{"name": "测试", "description": "测试描述", "excerpt": "测试内容", "children": []}]}'
        mock_response.error_message = None

        with patch.object(extractor, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await extractor.extract_knowledge_tree(
                document_content="测试文档内容",
                document_name="测试",
                max_points=10,
                use_ria=True,
                enable_validation=True,
            )
            assert result["success"] is True
            assert result["ria_enabled"] is True
            assert result["validation_enabled"] is True
            assert "quality_warnings" in result
            assert "validation_results" in result

    @pytest.mark.asyncio
    async def test_extract_with_ria_disabled(self, extractor):
        """Should use legacy prompt when use_ria=False."""
        mock_response = MagicMock()
        mock_response.content = '{"knowledge_points": [{"name": "测试", "description": "测试描述", "excerpt": "测试内容", "children": []}]}'
        mock_response.error_message = None

        with patch.object(extractor, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await extractor.extract_knowledge_tree(
                document_content="测试文档内容",
                document_name="测试",
                max_points=10,
                use_ria=False,
                enable_validation=False,
            )
            assert result["success"] is True
            assert result["ria_enabled"] is False
            assert result["validation_enabled"] is False

    @pytest.mark.asyncio
    async def test_extract_handles_ai_failure(self, extractor):
        """Should handle AI call failure gracefully."""
        with patch.object(extractor, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("API Error")
            result = await extractor.extract_knowledge_tree(
                document_content="测试内容",
                document_name="测试",
                max_points=10,
            )
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_with_existing_knowledge(self, extractor):
        """Should pass existing knowledge to validation."""
        mock_response = MagicMock()
        mock_response.content = '{"knowledge_points": [{"name": "司法鉴定", "description": "司法鉴定描述", "excerpt": "第一条", "children": []}]}'
        mock_response.error_message = None

        existing = [
            {
                "name": "司法鉴定",
                "description": "司法鉴定描述",
                "excerpt": "第一条",
            }
        ]

        with patch.object(extractor, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await extractor.extract_knowledge_tree(
                document_content="测试内容",
                document_name="测试",
                max_points=10,
                existing_knowledge=existing,
            )
            assert result["success"] is True
            # Should have deduplication warnings about duplicates
            assert "validation_results" in result


# ---------------------------------------------------------------------------
# Backward Compatibility Tests
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing API."""

    @pytest.mark.asyncio
    async def test_default_parameters(self, extractor):
        """Default parameters should work as before."""
        mock_response = MagicMock()
        mock_response.content = '{"knowledge_points": [{"name": "测试", "description": "测试", "excerpt": "测试", "children": []}]}'
        mock_response.error_message = None

        with patch.object(extractor, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await extractor.extract_knowledge_tree(
                document_content="测试内容",
                document_name="测试",
            )
            assert result["success"] is True
            assert "knowledge_points" in result
            assert "total" in result

    def test_flatten_tree_unchanged(self, extractor, sample_knowledge_tree):
        """_flatten_tree should work as before."""
        flat = extractor._flatten_tree(sample_knowledge_tree)
        assert len(flat) > len(sample_knowledge_tree)

    def test_count_leaf_nodes_unchanged(self, extractor, sample_knowledge_tree):
        """_count_leaf_nodes should work as before."""
        count = extractor._count_leaf_nodes(sample_knowledge_tree)
        assert count > 0

    def test_enforce_limits_unchanged(self, extractor, sample_knowledge_tree):
        """_enforce_limits should work as before."""
        limited = extractor._enforce_limits(sample_knowledge_tree, max_points=50, max_depth=3)
        assert len(limited) <= 50


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_knowledge_tree(self, extractor):
        """Should handle empty knowledge tree."""
        validated, warnings = extractor._validate_knowledge_quality([])
        assert validated == []
        assert warnings == []

    def test_single_node_tree(self, extractor):
        """Should handle single node tree."""
        nodes = [{"name": "单一节点", "description": "描述", "excerpt": "内容", "children": []}]
        validated, _ = extractor._validate_knowledge_quality(nodes)
        assert len(validated) == 1

    def test_deeply_nested_tree(self, extractor):
        """Should handle deeply nested structures."""
        # Build a 5-level deep tree
        leaf = {"name": "叶子", "description": "叶子描述", "excerpt": "叶子内容", "children": []}
        for i in range(4):
            leaf = {"name": f"节点{i}", "description": f"描述{i}", "excerpt": f"内容{i}", "children": [leaf]}

        validated, _ = extractor._validate_hierarchy([leaf])
        assert len(validated) == 1

    def test_node_with_special_characters(self, extractor):
        """Should handle nodes with special characters."""
        nodes = [
            {
                "name": "【特殊】字符<节点>&",
                "description": "包含特殊字符的描述",
                "excerpt": "特殊<内容>&",
                "children": [],
            }
        ]
        validated, _ = extractor._validate_knowledge_quality(nodes)
        assert len(validated) == 1

    def test_very_long_content(self, extractor):
        """Should handle very long content."""
        long_text = "A" * 5000
        nodes = [
            {
                "name": "长内容节点",
                "description": long_text,
                "excerpt": long_text,
                "children": [],
            }
        ]
        validated, _ = extractor._validate_knowledge_quality(nodes)
        assert len(validated) == 1

    def test_unicode_content(self, extractor):
        """Should handle unicode content properly."""
        nodes = [
            {
                "name": "🔬 科学鉴定",
                "description": "包含emoji和中文的描述",
                "excerpt": "📋 原文内容",
                "children": [],
            }
        ]
        validated, _ = extractor._validate_knowledge_quality(nodes)
        assert len(validated) == 1
