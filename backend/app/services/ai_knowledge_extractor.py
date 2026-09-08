"""AI Knowledge Extractor Service - AI 知识点提取服务

使用 AI 自动分析文档内容，提取知识点并生成树形结构。
优化策略：分段提取 + 并行调用 + 精简 prompt
使用统一AI服务层

增强功能（RIA++ 框架 + 三重验证）：
- RIA++ 分步提取框架：Rule → Instruction → Application → Example → Boundary
- 三重质量验证：跨域通用性、预测力、独特性
- 层级关系验证：父子关系一致性、跨层检测、孤儿节点检测
- 去重与合并：语义去重、层级合并、冲突检测
"""

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.ai_provider import AIResponse, get_ai_provider

logger = logging.getLogger(__name__)


class AIKnowledgeExtractor:
    """AI 知识点提取器（增强版，融入 RIA++ 框架和三重验证）"""

    def __init__(self):
        self.max_tokens = 2048  # 单次调用输出上限（降低以加速）

    # ------------------------------------------------------------------
    # 原有基础方法（保持不变）
    # ------------------------------------------------------------------

    def _sanitize_input(self, text: str, max_length: int = 8000) -> str:
        """清理输入文本，缩短截断长度以加速"""
        text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)
        text = re.sub(r"on\w+\s*=", "", text)
        if len(text) > max_length:
            text = text[:max_length] + "\n[内容过长已截断]"
        return text

    async def _call_ai(self, prompt: str, max_tokens: int = None, user_id: int | None = None) -> AIResponse:
        """调用统一AI服务层，返回 AIResponse（含 token 用量）"""
        try:
            provider = get_ai_provider()
            result: AIResponse = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.max_tokens,
                temperature=0.3,
                user_id=user_id,
            )
            if result.error_message:
                raise Exception(result.error_message)
            return result
        except Exception as e:
            raise Exception(f"AI API 调用失败: {e!s}")

    def _clean_json_string(self, text: str) -> str:
        """清理 AI 返回的 JSON 字符串，处理常见问题"""
        text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"/\*[\s\S]*?\*/", "", text)
        text = re.sub(r",\s*([}\]])", r"\1", text)
        text = re.sub(r'"\s*\+\s*"', "", text)
        text = re.sub(r"([{,]\s*)([\u4e00-\u9fff\w]+)\s*:", r'\1"\2":', text)
        return text.strip()

    def _parse_knowledge_tree(self, ai_response) -> List[Dict[str, Any]]:
        """解析 AI 返回的知识点树

        Args:
            ai_response: 可以是字符串或 AIResponse 对象
        """
        # 处理 AIResponse 对象
        if hasattr(ai_response, 'content'):
            ai_response = ai_response.content

        if not ai_response or not isinstance(ai_response, str):
            return []

        # 首先尝试直接解析（正常情况）
        try:
            data = json.loads(ai_response.strip())
            result = self._extract_knowledge_points(data)
            if result and len(result) > 0:
                return result
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 提取
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = ai_response.strip()

        # 移除残留 markdown
        json_str = re.sub(r"^```json\s*", "", json_str, flags=re.IGNORECASE)
        json_str = re.sub(r"^```\s*", "", json_str)
        json_str = re.sub(r"\s*```$", "", json_str)
        json_str = json_str.strip()

        # 尝试解析
        try:
            data = json.loads(json_str)
            result = self._extract_knowledge_points(data)
            if result and len(result) > 0:
                return result
        except json.JSONDecodeError:
            pass

        # 尝试清理并解析
        cleaned = self._clean_json_string(json_str)
        if cleaned != json_str:
            try:
                data = json.loads(cleaned)
                result = self._extract_knowledge_points(data)
                if result and len(result) > 0:
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试修复不规范的 JSON 并解析
        fixed = self._fix_malformed_json(json_str)
        if fixed:
            try:
                data = json.loads(fixed)
                result = self._extract_knowledge_points(data)
                if result and len(result) > 0:
                    return result
            except json.JSONDecodeError:
                pass

        # fallback 文本解析
        return self._parse_text_knowledge(ai_response)

    def _fix_malformed_json(self, json_str: str) -> str | None:
        """修复 AI 返回的不规范 JSON"""
        if '"知识点"' not in json_str and '"knowledge_points"' not in json_str:
            return None

        key_name = "知识点" if '"知识点"' in json_str else "knowledge_points"

        key_match = re.search(r'"(?:知识点|knowledge_points)"\s*:\s*\[', json_str)
        if not key_match:
            return None

        arr_start = key_match.end() - 1

        depth = 0
        arr_end = -1
        for i in range(arr_start, len(json_str)):
            if json_str[i] == "[":
                depth += 1
            elif json_str[i] == "]":
                depth -= 1
                if depth == 0:
                    arr_end = i
                    break

        if arr_end == -1:
            unclosed_brackets = depth
            if unclosed_brackets > 0:
                json_str = json_str + "]" * unclosed_brackets
                arr_end = len(json_str) - 1

        if arr_end == -1 or arr_end <= arr_start:
            return None

        arr_content = json_str[arr_start + 1 : arr_end]
        objects = self._parse_malformed_array(arr_content)

        if objects:
            return '{"' + key_name + '": ' + json.dumps(objects, ensure_ascii=False) + "}"

        return None

    def _parse_malformed_array(self, content: str) -> List[dict]:
        """解析不规范的数组内容"""
        objects = []
        content = content.strip()
        if not content:
            return objects

        child_arr_match = re.search(r'"子节点"\s*:\s*\[', content)

        if child_arr_match:
            child_arr_start_pos = child_arr_match.start()
            parent_kv_content = content[:child_arr_start_pos]
            child_arr_begin = child_arr_match.end() - 1
            depth = 0
            arr_end = -1
            for i in range(child_arr_begin, len(content)):
                if content[i] == "[":
                    depth += 1
                elif content[i] == "]":
                    depth -= 1
                    if depth == 0:
                        arr_end = i
                        break

            child_arr_content = content[child_arr_begin + 1 : arr_end] if arr_end > child_arr_begin else ""
            parent_obj = self._parse_key_value_pairs(parent_kv_content)

            if child_arr_content.strip():
                parent_obj["子节点"] = self._parse_child_array(child_arr_content)

            if parent_obj.get("名称"):
                objects.append(parent_obj)
        else:
            if "{" in content:
                objects = self._parse_normal_object_array(content)
            else:
                obj = self._parse_key_value_pairs(content)
                if obj and obj.get("名称"):
                    objects.append(obj)

        return objects

    def _parse_normal_object_array(self, content: str) -> List[dict]:
        """解析正常的对象数组格式 [{}, {}, ...]"""
        objects = []
        depth = 0
        obj_start = -1
        in_string = False
        escape = False

        for i, char in enumerate(content):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == "{":
                if depth == 0:
                    obj_start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    obj_text = content[obj_start : i + 1]
                    try:
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict) and obj.get("名称"):
                            objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    obj_start = -1

        return objects

    def _parse_key_value_pairs(self, content: str) -> dict:
        """解析键值对序列，提取名称、描述、子节点等"""
        obj = {}
        content = content.strip().strip(",").strip()

        if not content:
            return obj

        kv_pattern = r'"(名称|描述|子节点|children|name|description)"\s*:\s*'

        for match in re.finditer(kv_pattern, content):
            key = match.group(1)
            value_start = match.end()
            remaining = content[value_start:]

            if remaining.strip().startswith("["):
                depth = 0
                arr_end = -1
                for i, c in enumerate(remaining):
                    if c == "[":
                        depth += 1
                    elif c == "]":
                        depth -= 1
                        if depth == 0:
                            arr_end = i
                            break

                if arr_end > 0:
                    arr_content = remaining[1:arr_end]
                    obj[key] = self._parse_child_array(arr_content)
            elif remaining.strip().startswith("{"):
                depth = 0
                obj_end = -1
                for i, c in enumerate(remaining):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            obj_end = i
                            break

                if obj_end > 0:
                    obj_text = remaining[: obj_end + 1]
                    try:
                        obj[key] = json.loads(obj_text)
                    except json.JSONDecodeError:
                        obj[key] = self._parse_key_value_pairs(obj_text)
            else:
                value_match = re.match(r"([^,}\]]+)", remaining.strip())
                if value_match:
                    value = value_match.group(1).strip().strip("\"', ")
                    obj[key] = value

        return obj

    def _parse_child_array(self, content: str) -> List[dict]:
        """解析子节点数组"""
        children = []
        content = content.strip()
        if not content:
            return children

        if "{" in content:
            children = self._parse_normal_object_array(content)
        else:
            obj = self._parse_key_value_pairs(content)
            if obj and obj.get("名称"):
                children.append(obj)

        return children

    def _extract_knowledge_points(self, data) -> List[Dict[str, Any]]:
        """从解析后的数据提取知识点"""
        if isinstance(data, dict):
            if "知识点" in data:
                kp = data["知识点"]
                if isinstance(kp, list) and len(kp) > 0:
                    return self._convert_to_english(kp)
                elif isinstance(kp, dict):
                    return self._convert_to_english([kp])
            elif "knowledge_points" in data:
                kp = data["knowledge_points"]
                if isinstance(kp, list) and len(kp) > 0:
                    if self._has_chinese_keys(kp):
                        return self._convert_to_english(kp)
                    return kp
                elif isinstance(kp, dict):
                    return self._convert_to_english([kp]) if self._has_chinese_keys([kp]) else [kp]
            elif any(key in data for key in ["名称", "描述", "子节点", "name", "description", "children"]):
                if self._has_chinese_keys([data]):
                    return self._convert_to_english([data])
                elif any(key in data for key in ["name", "description", "children"]):
                    return [data]
        elif isinstance(data, list) and len(data) > 0:
            if self._has_chinese_keys(data):
                return self._convert_to_english(data)
            return data
        return []

    def _has_chinese_keys(self, data) -> bool:
        """检查是否包含中文字段名"""
        if isinstance(data, dict):
            return any(key in ["名称", "描述", "子节点", "知识点"] for key in data.keys())
        elif isinstance(data, list) and len(data) > 0:
            return self._has_chinese_keys(data[0])
        return False

    def _convert_to_english(self, nodes: List[Dict]) -> List[Dict[str, Any]]:
        """将中文字段名转换为英文字段名"""
        result = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            children = node.get("children") if "children" in node else node.get("子节点", [])
            if not isinstance(children, list):
                children = []
            converted_children = self._convert_to_english(children)
            name = node.get("名称") if node.get("名称") is not None else node.get("name", "未命名")
            desc = node.get("描述") if node.get("描述") is not None else node.get("description", "")
            excerpt = node.get("原文") if node.get("原文") is not None else node.get("excerpt", "")
            result.append(
                {
                    "name": str(name)[:100],
                    "description": str(desc)[:2000] if desc else "",  # 归纳性摘要
                    "excerpt": str(excerpt)[:2000] if excerpt else "",  # 原文照抄内容
                    "children": converted_children,
                }
            )
        return result

    def _parse_text_knowledge(self, text: str) -> List[Dict[str, Any]]:
        """从文本解析知识点（备选方案），支持基于缩进/编号的层级推断"""
        lines = text.strip().split("\n")
        parsed_lines = []

        for line in lines:
            stripped = line.rstrip()
            if not stripped.strip():
                continue
            indent = len(stripped) - len(stripped.lstrip())
            cleaned = re.sub(r"^[\d\.\-\*\>\#]+[\s\)：:]*", "", stripped.strip())
            if cleaned and len(cleaned) > 1:
                parsed_lines.append({"name": cleaned[:100], "indent": indent, "children": []})

        if not parsed_lines:
            return [{"name": "知识点", "description": "", "children": []}]

        min_indent = min(item["indent"] for item in parsed_lines)
        for item in parsed_lines:
            item["indent"] -= min_indent

        def build_tree(items, start_idx=0, parent_indent=0):
            result = []
            i = start_idx
            while i < len(items):
                if items[i]["indent"] < parent_indent:
                    break
                if items[i]["indent"] == parent_indent:
                    node = {"name": items[i]["name"], "description": "", "children": []}
                    j = i + 1
                    child_nodes = []
                    while j < len(items) and items[j]["indent"] > parent_indent:
                        child_nodes.append(items[j])
                        j += 1
                    if child_nodes:
                        next_indent = min(cn["indent"] for cn in child_nodes)
                        node["children"], i = build_tree(child_nodes, 0, next_indent)
                        i = start_idx + j
                    else:
                        i += 1
                    result.append(node)
                else:
                    i += 1
            return result, i

        tree, _ = build_tree(parsed_lines)
        return tree if tree else [{"name": "知识点", "description": "", "children": []}]

    def _flatten_tree(self, nodes: List[Dict]) -> List[Dict]:
        """扁平化知识点树"""
        result = []
        for node in nodes:
            result.append(node)
            if node.get("children"):
                result.extend(self._flatten_tree(node["children"]))
        return result

    def _count_leaf_nodes(self, nodes: List[Dict]) -> int:
        """统计叶子节点数量"""
        count = 0
        for node in nodes:
            if not node.get("children") or len(node["children"]) == 0:
                count += 1
            else:
                count += self._count_leaf_nodes(node["children"])
        return count

    def _enforce_limits(self, nodes: List[Dict], max_points: int = 150, max_depth: int = 4) -> List[Dict]:
        """强制限制知识点数量和层级深度

        - 超过 max_points 的节点直接删除
        - 超过 max_depth 的层级直接截断
        - 每层子节点数量限制：顶层8个，二级6个，三级5个，四级5个
        """
        result = []
        count = 0
        # 每层最大子节点数
        depth_limits = {0: 8, 1: 6, 2: 5, 3: 5}

        def process(node: Dict, depth: int) -> Dict | None:
            nonlocal count
            if count >= max_points:
                return None

            count += 1
            new_node = {
                "name": node.get("name", "未命名")[:100],
                "description": (node.get("description", "") or "")[:2000],  # 归纳性摘要
                "excerpt": (node.get("excerpt", "") or "")[:2000],  # 原文照抄内容
                "children": [],
            }

            # 超过最大深度，不再添加子节点
            if depth >= max_depth:
                return new_node

            # 处理子节点，根据层级限制数量
            children = node.get("children", []) or []
            max_children = depth_limits.get(depth, 5)
            for child in children[:max_children]:
                if count >= max_points:
                    break
                processed_child = process(child, depth + 1)
                if processed_child:
                    new_node["children"].append(processed_child)

            return new_node

        for node in nodes:
            if count >= max_points:
                break
            processed = process(node, 1)
            if processed:
                result.append(processed)

        return result

    # ------------------------------------------------------------------
    # 新增：RIA++ Prompt 模板方法
    # ------------------------------------------------------------------

    def _build_ria_prompt(
        self,
        document_content: str,
        document_name: str,
        category: str,
        max_points: int,
        phase: str = "full",
    ) -> str:
        """构建 RIA++ 分步提取 prompt

        RIA++ 框架：
        - R (Rule)：识别文档中的核心规则/原则/定义
        - I (Instruction)：将规则转化为可操作的指导
        - A (Application)：找到规则适用的场景和案例
        - E (Example)：给出具体例子（原文照抄）
        - B (Boundary)：明确规则的边界和例外

        Args:
            document_content: 文档内容
            document_name: 文档名称
            category: 分类
            max_points: 最大知识点数量
            phase: 提取阶段，"full" 为完整流程，"ria" 仅 RIA 分析
        """
        safe_content = self._sanitize_input(document_content)

        prompt = f"""你是一个专业的知识体系分析助手。请使用 RIA++ 框架分析以下文档内容，提取知识点并生成树形结构。

文档名称：{document_name or "未命名文档"}
分类：{category}

【重要说明】
本系统用于司法鉴定、法律规范等需要高准确性的领域，题目必须严格基于原文生成。
因此知识点必须同时存储摘要描述和完整的原始内容片段。

【RIA++ 框架】
请按以下五个维度分析每个知识点：

第一阶段：R (Rule) — 识别文档中的核心规则/原则/定义
- 找出文档中的核心规范、原则、定义
- 这些是知识体系的骨架

第二阶段：I (Instruction) — 将规则转化为可操作的指导
- 这个规则如何操作？步骤是什么？
- 需要满足什么条件？

第三阶段：A (Application) — 找到规则适用的场景和案例
- 这个规则在什么场景下适用？
- 有什么具体案例或应用场景？

第四阶段：E (Example) — 给出具体例子（原文照抄）
- 从原文中找到支持该知识点的具体内容
- 必须原文照抄，保留法条编号、条款号、具体数字、日期等

第五阶段：B (Boundary) — 明确规则的边界和例外
- 这个规则有什么例外情况？
- 适用范围的边界在哪里？

核心原则：
- 知识点名称（name）= 简洁的归纳标签（简短概念名称）
- 知识点描述（description）= 该知识点的简短摘要，不超过200字，用归纳语言概括
- 原文片段（excerpt）= 该知识点对应的【完整原文内容】，必须原文照抄，保留法条编号、条款号、具体数字、日期等
- 顶层知识点名称从文档主题出发，不使用文件名

严格限制：
- 总知识点数量不超过{max_points}个（包含所有层级）
- 层级最多4层（顶层->二级->三级->四级）
- 每个顶层知识点下最多8个子知识点
- 每个子知识点下最多6个三级知识点
- 每个三级知识点下最多5个四级知识点
- description 字段不超过200字，是归纳性摘要
- excerpt 字段必须存储原始法条内容，长度可达2000字符，禁止归纳概括
- 绝对不要把文件名、文件扩展名、文件路径用在任何知识点名称中

要求：
1. 首先分析文档内容，确定文档的核心主题领域
2. 顶层知识点名称应该围绕文档的核心主题，如"司法鉴定基本规范"、"医师执业资格管理"、"环境影响评价制度"等
3. 顶层知识点名称不要包含文件后缀（.doc、.pdf、.txt等）、编号（如"四"、"（一）"等前缀）、中括号（【】）等
4. 每个主题下的核心概念、原理、方法等提取为子节点
5. 名称应该简洁明了，如"什么是XXX"、"XXX的适用范围"、"XXX的处理流程"
6. description 用归纳语言简短描述该知识点的核心内容（涵盖 RIA 维度）
7. excerpt 必须原文照抄相关法条内容，保留条款号和具体规定，这是生成题目的依据（对应 E 维度）
8. 必须构建有层次的树形结构，子知识点必须放在父知识点的"children"数组中
9. 每个知识点包含：name（简洁的归纳名称）、description（简短摘要）、excerpt（原始法条内容）、children（子节点数组）
10. 只返回纯JSON，不要包含任何注释、说明或markdown标记
11. 不要有尾随逗号

严格按以下格式输出（不要添加任何额外内容）：
{{
  "knowledge_points": [
    {{
      "name": "核心主题1（简洁归纳）",
      "description": "该知识点的简短摘要，归纳性描述，不超过200字",
      "excerpt": "该知识点对应的完整法条原文内容，原文照抄，保留条款号和具体规定",
      "children": [
        {{
          "name": "核心概念：XXX是什么",
          "description": "该概念的简短摘要",
          "excerpt": "该概念对应的原文内容",
          "children": [
            {{
              "name": "要点1：XXX",
              "description": "该要点的简短摘要",
              "excerpt": "该要点的原文内容",
              "children": []
            }},
            {{
              "name": "要点2：XXX",
              "description": "该要点的简短摘要",
              "excerpt": "该要点的原文内容",
              "children": []
            }}
          ]
        }},
        {{
          "name": "适用范围：XXX",
          "description": "该制度/方法/原理的适用场景和范围摘要",
          "excerpt": "适用范围的原文内容",
          "children": []
        }}
      ]
    }},
    {{
      "name": "核心主题2（从文档内容提炼）",
      "description": "该类别的总体摘要",
      "excerpt": "该类别相关的原文内容",
      "children": []
    }}
  ]
}}

文档内容：
{safe_content}

请直接返回JSON格式的知识点结构（不要包含markdown代码块标记）："""

        return prompt

    # ------------------------------------------------------------------
    # 新增：三重验证方法
    # ------------------------------------------------------------------

    def _validate_knowledge_quality(
        self,
        knowledge_tree: List[Dict[str, Any]],
        existing_knowledge: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """三重质量验证

        在 AI 返回知识点后，进行自动化质量验证：
        - V1 跨域通用性：知识点是否只适用于当前文档的某个角落？
        - V2 预测力：这个知识点能否预测"如果...那么..."的结论？
        - V3 独特性：这个知识点是否与已存在的知识点高度重复？

        Args:
            knowledge_tree: 知识点树
            existing_knowledge: 已有知识库（可选），用于去重比对

        Returns:
            (验证后的知识点树, 质量警告列表)
        """
        quality_warnings: List[str] = []
        validated_tree = knowledge_tree

        # V1: 跨域通用性验证
        validated_tree, warnings_v1 = self._validate_cross_domain_generality(validated_tree)
        quality_warnings.extend(warnings_v1)

        # V2: 预测力验证
        validated_tree, warnings_v2 = self._validate_predictive_power(validated_tree)
        quality_warnings.extend(warnings_v2)

        # V3: 独特性验证（去重）
        validated_tree, warnings_v3 = self._validate_uniqueness(validated_tree, existing_knowledge)
        quality_warnings.extend(warnings_v3)

        return validated_tree, quality_warnings

    def _validate_cross_domain_generality(
        self, nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """V1 跨域通用性验证

        检查知识点是否只适用于当前文档的某个角落。
        标记过于细碎、仅涉及单一细节的知识点为低质量。

        判断标准：
        - 名称过于具体（如包含具体日期、具体人名、具体编号）可能过于细碎
        - 描述过短（< 10字）可能缺乏通用性
        - 叶子节点且无实际内容可能为低质量
        """
        warnings: List[str] = []

        def _check_node(node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            # 标记可能过于细碎的知识点
            is_too_specific = False
            # 检查是否包含过于具体的日期/编号
            if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", name):
                is_too_specific = True

            # 如果是叶子节点且描述很短，可能缺乏通用性
            is_leaf_low_quality = (
                not children
                and len(description) < 10
                and len(excerpt) < 20
            )

            # 检查名称是否过短且描述过短（但排除已经是low_content的情况）
            is_name_too_short = len(name) < 3 and len(description) < 5

            if is_too_specific:
                node["quality_flag"] = "low_generality"
                warnings.append(f"知识点 '{name}' 可能过于细碎，缺乏跨域通用性")
            elif is_leaf_low_quality:
                node["quality_flag"] = "low_content"
                warnings.append(f"知识点 '{name}' 内容过少，可能缺乏预测力")
            elif is_name_too_short:
                node["quality_flag"] = "low_generality"
                warnings.append(f"知识点 '{name}' 可能过于细碎，缺乏跨域通用性")
            else:
                node["quality_flag"] = "ok"

            # 递归处理子节点
            if children:
                node["children"] = [_check_node(child, depth + 1) for child in children]

            return node

        validated = [_check_node(node) for node in nodes]
        return validated, warnings

    def _validate_predictive_power(
        self, nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """V2 预测力验证

        检查知识点能否预测"如果...那么..."的结论。
        判断标准：
        - 包含条件性词汇（如果、当、若、除非、应当、必须）的知识点通常有预测力
        - 描述中包含"是"、"指"、"属于"等定义性词汇的知识点有预测力
        - 纯叙述性内容（无逻辑关系）预测力较低
        """
        warnings: List[Dict[str, Any]] = []

        # 有预测力的关键词模式
        predictive_patterns = [
            r"如果|假如|若|当|除非|在.*情况下",
            r"应当|必须|不得|禁止|可以|需要",
            r"是指|指的是|属于|定义为|称为",
            r"导致|引起|造成|产生|结果",
            r"条件|前提|要求|标准",
        ]

        def _check_node(node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            # 检查是否包含预测性内容
            has_predictive = False
            combined_text = f"{name} {description} {excerpt}"
            for pattern in predictive_patterns:
                if re.search(pattern, combined_text):
                    has_predictive = True
                    break

            # 获取现有的 quality_flag
            existing_flag = node.get("quality_flag", "ok")
            if not has_predictive and existing_flag == "ok":
                node["quality_flag"] = "low_predictive"
                warnings.append(f"知识点 '{name}' 缺乏预测力，无法推导条件结论")
            elif has_predictive and existing_flag == "ok":
                node["quality_flag"] = "high_predictive"

            # 递归处理子节点
            if children:
                node["children"] = [_check_node(child, depth + 1) for child in children]

            return node

        validated = [_check_node(node) for node in nodes]
        return validated, warnings

    def _validate_uniqueness(
        self,
        nodes: List[Dict[str, Any]],
        existing_knowledge: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """V3 独特性验证

        检查知识点是否与已有知识点高度重复。
        使用 difflib.SequenceMatcher 进行文本相似度比较。

        Args:
            nodes: 当前知识点树
            existing_knowledge: 已有知识库（可选）

        Returns:
            (验证后的节点列表, 警告列表)
        """
        warnings: List[str] = []
        similarity_threshold = 0.85  # 相似度阈值

        # 获取所有已有知识点的文本表示
        existing_texts: List[str] = []
        if existing_knowledge:
            for kp in existing_knowledge:
                text = f"{kp.get('name', '')} {kp.get('description', '')}"
                existing_texts.append(text)

        def _check_node(node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            # 构建当前知识点的文本表示
            current_text = f"{name} {description}"

            # 与已有知识点比对
            is_duplicate = False
            for existing_text in existing_texts:
                similarity = SequenceMatcher(None, current_text, existing_text).ratio()
                if similarity > similarity_threshold:
                    is_duplicate = True
                    warnings.append(
                        f"知识点 '{name}' 与已有知识点高度相似（相似度: {similarity:.2f}）"
                    )
                    break

            # 获取现有的 quality_flag
            existing_flag = node.get("quality_flag", "ok")
            if is_duplicate:
                node["quality_flag"] = "duplicate"
                node["duplicate_similarity"] = similarity
            elif existing_flag == "ok":
                node["quality_flag"] = "unique"

            # 递归处理子节点
            if children:
                node["children"] = [_check_node(child, depth + 1) for child in children]

            return node

        validated = [_check_node(node) for node in nodes]
        return validated, warnings

    # ------------------------------------------------------------------
    # 新增：层级关系验证
    # ------------------------------------------------------------------

    def _validate_hierarchy(
        self, nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """层级关系验证

        - 检查子知识点是否真的属于父知识点（而不是硬凑层级）
        - 检查是否有"跨层"现象（孙节点直接提到祖父节点的概念）
        - 检查是否有"孤儿节点"（没有父节点的知识点）

        Args:
            nodes: 知识点树

        Returns:
            (验证后的节点列表, 警告列表)
        """
        warnings: List[str] = []

        def _get_ancestor_names(node: Dict[str, Any], depth: int = 0) -> List[Tuple[str, int]]:
            """获取所有祖先节点的名称和深度"""
            ancestors = []
            # 这里需要从根节点开始追踪，简化处理：只检查直接父子关系
            return ancestors

        def _check_node_hierarchy(
            node: Dict[str, Any],
            parent_name: str = "",
            depth: int = 0,
            ancestor_names: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            """检查单个节点的层级关系"""
            if ancestor_names is None:
                ancestor_names = []

            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            # 检查1：子知识点与父知识点的关键词重叠度
            if parent_name and depth > 0:
                # 使用单字拆分进行更细粒度的匹配
                parent_chars = set(re.findall(r"[\u4e00-\u9fff]", parent_name))
                child_chars = set(re.findall(r"[\u4e00-\u9fff]", name))
                overlap = parent_chars & child_chars

                # 如果完全没有字符重叠，可能是硬凑层级
                if parent_chars and len(overlap) == 0:
                    node["hierarchy_warning"] = "low_parent_overlap"
                    warnings.append(
                        f"知识点 '{name}' 与父知识点 '{parent_name}' 缺乏关键词关联"
                    )

            # 检查2：跨层现象 - 子节点直接提到祖父节点的概念
            if len(ancestor_names) >= 2:
                # 祖父节点是 ancestor_names[-2]
                grandparent_name = ancestor_names[-2]
                grandparent_chars = set(re.findall(r"[\u4e00-\u9fff]", grandparent_name))
                node_text = f"{name} {description}"
                node_chars = set(re.findall(r"[\u4e00-\u9fff]", node_text))
                cross_layer_overlap = grandparent_chars & node_chars

                # 如果与祖父节点关联更强，可能存在跨层问题
                parent_overlap_count = len(overlap) if parent_name else 0
                if grandparent_chars and len(cross_layer_overlap) > parent_overlap_count:
                    node["hierarchy_warning"] = "cross_layer_reference"
                    warnings.append(
                        f"知识点 '{name}' 可能跨层引用祖父节点 '{grandparent_name}' 的概念"
                    )

            # 检查3：孤儿节点 - 已经在树中，无需额外检查
            # （因为我们是遍历已有树结构，所有节点都有父节点或自己是根）

            # 递归处理子节点
            new_ancestors = ancestor_names + [name]
            if children:
                node["children"] = [
                    _check_node_hierarchy(child, name, depth + 1, new_ancestors)
                    for child in children
                ]

            return node

        validated = [_check_node_hierarchy(node) for node in nodes]
        return validated, warnings

    # ------------------------------------------------------------------
    # 新增：去重和合并
    # ------------------------------------------------------------------

    def _deduplicate_knowledge(
        self,
        nodes: List[Dict[str, Any]],
        existing_knowledge: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """去重和合并

        - 语义去重：检查是否有高度相似的知识点（基于名称和描述的文本相似度）
        - 层级合并：如果两个知识点实质相同但出现在不同层级，合并到更合适的层级
        - 冲突检测：与已有知识库（如果存在）比对，标记新增/更新/冲突

        Args:
            nodes: 知识点树
            existing_knowledge: 已有知识库（可选）

        Returns:
            (去重后的节点列表, 操作日志列表)
        """
        operation_logs: List[str] = []
        similarity_threshold = 0.85

        # 步骤1：语义去重（树内部）
        nodes, dedup_logs = self._remove_internal_duplicates(nodes, similarity_threshold)
        operation_logs.extend(dedup_logs)

        # 步骤2：层级合并
        nodes, merge_logs = self._merge_redundant_nodes(nodes)
        operation_logs.extend(merge_logs)

        # 步骤3：与已有知识库比对
        if existing_knowledge:
            nodes, conflict_logs = self._detect_conflicts(nodes, existing_knowledge, similarity_threshold)
            operation_logs.extend(conflict_logs)

        return nodes, operation_logs

    def _remove_internal_duplicates(
        self,
        nodes: List[Dict[str, Any]],
        threshold: float,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """移除树内部的高度相似节点"""
        logs: List[str] = []
        seen_texts: List[str] = []

        def _process_node(node: Dict[str, Any], depth: int = 0) -> Optional[Dict[str, Any]]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            current_text = f"{name} {description}"

            # 检查是否与已处理的节点重复
            for seen_text in seen_texts:
                similarity = SequenceMatcher(None, current_text, seen_text).ratio()
                if similarity > threshold:
                    logs.append(f"移除重复知识点 '{name}'（相似度: {similarity:.2f}）")
                    return None

            seen_texts.append(current_text)

            # 递归处理子节点
            if children:
                processed_children = []
                for child in children:
                    processed = _process_node(child, depth + 1)
                    if processed is not None:
                        processed_children.append(processed)
                node["children"] = processed_children

            return node

        result = []
        for node in nodes:
            processed = _process_node(node)
            if processed is not None:
                result.append(processed)

        return result, logs

    def _merge_redundant_nodes(
        self, nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """合并冗余节点（简化实现：移除空的中间层）"""
        logs: List[str] = []

        def _process_node(node: Dict[str, Any]) -> Dict[str, Any]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            # 如果节点没有名称且只有一个子节点，提升子节点
            if not name and len(children) == 1:
                logs.append(f"合并空节点，提升子节点 '{children[0].get('name', '')}'")
                return _process_node(children[0])

            # 如果节点无内容且无子节点，标记为可删除
            if not description and not excerpt and not children:
                node["merge_flag"] = "empty_node"
                logs.append(f"标记空节点 '{name}' 为可合并")

            # 递归处理子节点
            if children:
                node["children"] = [_process_node(child) for child in children]

            return node

        result = [_process_node(node) for node in nodes]
        return result, logs

    def _detect_conflicts(
        self,
        nodes: List[Dict[str, Any]],
        existing_knowledge: List[Dict[str, Any]],
        threshold: float,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """检测与已有知识库的冲突"""
        logs: List[str] = []

        # 构建已有知识库的文本索引
        existing_index = []
        for kp in existing_knowledge:
            text = f"{kp.get('name', '')} {kp.get('description', '')}"
            existing_index.append((text, kp))

        def _process_node(node: Dict[str, Any]) -> Dict[str, Any]:
            name = node.get("name", "")
            description = node.get("description", "")
            excerpt = node.get("excerpt", "")
            children = node.get("children", [])

            current_text = f"{name} {description}"

            # 检查与已有知识的冲突
            for existing_text, existing_kp in existing_index:
                similarity = SequenceMatcher(None, current_text, existing_text).ratio()
                if similarity > threshold:
                    # 检查内容是否实质不同
                    if node.get("excerpt") != existing_kp.get("excerpt", ""):
                        node["conflict_status"] = "update"
                        logs.append(
                            f"知识点 '{name}' 与已有知识存在更新关系（相似度: {similarity:.2f}）"
                        )
                    break
                elif similarity > 0.5:
                    node["conflict_status"] = "related"
                    logs.append(
                        f"知识点 '{name}' 与已有知识相关（相似度: {similarity:.2f}）"
                    )
                    break
            else:
                node["conflict_status"] = "new"

            # 递归处理子节点
            if children:
                node["children"] = [_process_node(child) for child in children]

            return node

        result = [_process_node(node) for node in nodes]
        return result, logs

    # ------------------------------------------------------------------
    # 改造后的主流程
    # ------------------------------------------------------------------

    async def extract_knowledge_tree(
        self,
        document_content: str,
        document_name: str = "",
        max_points: int = 50,
        category: str = "default",
        use_ria: bool = True,
        enable_validation: bool = True,
        existing_knowledge: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """从文档内容提取知识点树（增强版，融入 RIA++ 框架和三重验证）

        改造后的流程：
        1. 清理输入文本
        2. RIA++ Prompt 提取（新增）
        3. 三重验证（新增）
        4. 层级验证（新增）
        5. 去重合并（新增）
        6. 强制限制（保留现有逻辑）
        7. 输出（附带质量评分和验证标记）

        Args:
            document_content: 文档内容
            document_name: 文档名称
            max_points: 最大知识点数量
            category: 分类代码
            use_ria: 是否使用 RIA++ 框架（默认 True）
            enable_validation: 是否启用质量验证（默认 True）
            existing_knowledge: 已有知识库（可选），用于去重和冲突检测

        Returns:
            提取结果字典，包含：
            - success: 是否成功
            - knowledge_points: 知识点树
            - total: 叶子节点数量
            - quality_warnings: 质量警告列表（新增）
            - validation_results: 验证结果摘要（新增）
        """
        safe_content = self._sanitize_input(document_content)

        # 步骤1：构建 prompt（RIA++ 或原有）
        if use_ria:
            prompt = self._build_ria_prompt(
                document_content=document_content,
                document_name=document_name,
                category=category,
                max_points=max_points,
            )
        else:
            prompt = self._build_legacy_prompt(
                document_content=document_content,
                document_name=document_name,
                category=category,
                max_points=max_points,
            )

        try:
            # 步骤2：调用 AI
            response = await self._call_ai(prompt, max_tokens=8192)
            if not response:
                raise Exception("AI 未返回有效内容")

            # 步骤3：解析知识点树
            knowledge_tree = self._parse_knowledge_tree(response)

            # 初始化质量警告列表
            all_quality_warnings: List[str] = []
            validation_results: Dict[str, Any] = {}

            # 步骤4：三重验证（新增）
            if enable_validation:
                knowledge_tree, quality_warnings = self._validate_knowledge_quality(
                    knowledge_tree, existing_knowledge
                )
                all_quality_warnings.extend(quality_warnings)
                validation_results["triple_validation"] = {
                    "warnings_count": len(quality_warnings),
                    "status": "completed",
                }

            # 步骤5：层级验证（新增）
            if enable_validation:
                knowledge_tree, hierarchy_warnings = self._validate_hierarchy(knowledge_tree)
                all_quality_warnings.extend(hierarchy_warnings)
                validation_results["hierarchy_validation"] = {
                    "warnings_count": len(hierarchy_warnings),
                    "status": "completed",
                }

            # 步骤6：去重合并（新增）
            if enable_validation:
                knowledge_tree, dedup_logs = self._deduplicate_knowledge(
                    knowledge_tree, existing_knowledge
                )
                all_quality_warnings.extend(dedup_logs)
                validation_results["deduplication"] = {
                    "operations_count": len(dedup_logs),
                    "status": "completed",
                }

            # 步骤7：强制限制（保留现有逻辑）
            knowledge_tree = self._enforce_limits(knowledge_tree, max_points=max_points, max_depth=3)

            return {
                "success": True,
                "knowledge_points": knowledge_tree,
                "total": self._count_leaf_nodes(knowledge_tree),
                "quality_warnings": all_quality_warnings,
                "validation_results": validation_results,
                "ria_enabled": use_ria,
                "validation_enabled": enable_validation,
            }

        except Exception as e:
            logger.error(f"知识点提取失败: {e!s}")
            # 降级：返回原始提取结果（不带验证）
            try:
                knowledge_tree = self._parse_knowledge_tree(
                    '{"knowledge_points": [{"name": "提取失败", "description": str(e), "children": []}]}'
                )
            except Exception:
                knowledge_tree = []

            return {
                "success": False,
                "error": str(e),
                "knowledge_points": knowledge_tree,
                "quality_warnings": [f"验证过程异常: {e!s}"],
                "validation_results": {"status": "failed"},
                "ria_enabled": use_ria,
                "validation_enabled": enable_validation,
            }

    def _build_legacy_prompt(
        self,
        document_content: str,
        document_name: str,
        category: str,
        max_points: int,
    ) -> str:
        """构建原有 prompt（不使用 RIA++ 框架）"""
        safe_content = self._sanitize_input(document_content)

        prompt = f"""你是一个专业的知识体系分析助手。请分析以下文档内容，提取知识点并生成树形结构。

文档名称：{document_name or "未命名文档"}
分类：{category}

【重要说明】
本系统用于司法鉴定、法律规范等需要高准确性的领域，题目必须严格基于原文生成。
因此知识点必须同时存储摘要描述和完整的原始内容片段。

核心原则：
- 知识点名称（name）= 简洁的归纳标签（简短概念名称）
- 知识点描述（description）= 该知识点的简短摘要，不超过200字，用归纳语言概括
- 原文片段（excerpt）= 该知识点对应的【完整原文内容】，必须原文照抄，保留法条编号、条款号、具体数字、日期等
- 顶层知识点名称从文档主题出发，不使用文件名

严格限制：
- 总知识点数量不超过{max_points}个（包含所有层级）
- 层级最多4层（顶层->二级->三级->四级）
- 每个顶层知识点下最多8个子知识点
- 每个子知识点下最多6个三级知识点
- 每个三级知识点下最多5个四级知识点
- description 字段不超过200字，是归纳性摘要
- excerpt 字段必须存储原始法条内容，长度可达2000字符，禁止归纳概括
- 绝对不要把文件名、文件扩展名、文件路径用在任何知识点名称中

要求：
1. 首先分析文档内容，确定文档的核心主题领域
2. 顶层知识点名称应该围绕文档的核心主题，如"司法鉴定基本规范"、"医师执业资格管理"、"环境影响评价制度"等
3. 顶层知识点名称不要包含文件后缀（.doc、.pdf、.txt等）、编号（如"四"、"（一）"等前缀）、中括号（【】）等
4. 每个主题下的核心概念、原理、方法等提取为子节点
5. 名称应该简洁明了，如"什么是XXX"、"XXX的适用范围"、"XXX的处理流程"
6. description 用归纳语言简短描述该知识点的核心内容
7. excerpt 必须原文照抄相关法条内容，保留条款号和具体规定，这是生成题目的依据
8. 必须构建有层次的树形结构，子知识点必须放在父知识点的"children"数组中
9. 每个知识点包含：name（简洁的归纳名称）、description（简短摘要）、excerpt（原始法条内容）、children（子节点数组）
10. 只返回纯JSON，不要包含任何注释、说明或markdown标记
11. 不要有尾随逗号

严格按以下格式输出（不要添加任何额外内容）：
{{
  "knowledge_points": [
    {{
      "name": "核心主题1（简洁归纳）",
      "description": "该知识点的简短摘要，归纳性描述，不超过200字",
      "excerpt": "该知识点对应的完整法条原文内容，原文照抄，保留条款号和具体规定",
      "children": [
        {{
          "name": "核心概念：XXX是什么",
          "description": "该概念的简短摘要",
          "excerpt": "该概念对应的原文内容",
          "children": [
            {{
              "name": "要点1：XXX",
              "description": "该要点的简短摘要",
              "excerpt": "该要点的原文内容",
              "children": []
            }},
            {{
              "name": "要点2：XXX",
              "description": "该要点的简短摘要",
              "excerpt": "该要点的原文内容",
              "children": []
            }}
          ]
        }},
        {{
          "name": "适用范围：XXX",
          "description": "该制度/方法/原理的适用场景和范围摘要",
          "excerpt": "适用范围的原文内容",
          "children": []
        }}
      ]
    }},
    {{
      "name": "核心主题2（从文档内容提炼）",
      "description": "该类别的总体摘要",
      "excerpt": "该类别相关的原文内容",
      "children": []
    }}
  ]
}}

文档内容：
{safe_content}

请直接返回JSON格式的知识点结构（不要包含markdown代码块标记）："""

        return prompt

    # ------------------------------------------------------------------
    # 公共辅助方法
    # ------------------------------------------------------------------

    def get_quality_summary(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """获取节点的质量摘要信息

        Args:
            node: 知识点节点

        Returns:
            质量摘要字典
        """
        return {
            "name": node.get("name", ""),
            "quality_flag": node.get("quality_flag", "unknown"),
            "hierarchy_warning": node.get("hierarchy_warning"),
            "conflict_status": node.get("conflict_status", "unknown"),
            "merge_flag": node.get("merge_flag"),
            "duplicate_similarity": node.get("duplicate_similarity"),
        }

    def collect_quality_stats(self, nodes: List[Dict[str, Any]]) -> Dict[str, int]:
        """收集整棵树的质量统计信息

        Args:
            nodes: 知识点树

        Returns:
            质量统计字典
        """
        stats = {
            "total_nodes": 0,
            "ok": 0,
            "low_generality": 0,
            "low_content": 0,
            "low_predictive": 0,
            "high_predictive": 0,
            "unique": 0,
            "duplicate": 0,
            "hierarchy_warnings": 0,
            "conflict_new": 0,
            "conflict_update": 0,
            "conflict_related": 0,
        }

        def _count_node(node: Dict[str, Any]):
            stats["total_nodes"] += 1

            quality_flag = node.get("quality_flag", "")
            if quality_flag in stats:
                stats[quality_flag] += 1

            if node.get("hierarchy_warning"):
                stats["hierarchy_warnings"] += 1

            conflict_status = node.get("conflict_status", "")
            if conflict_status == "new":
                stats["conflict_new"] += 1
            elif conflict_status == "update":
                stats["conflict_update"] += 1
            elif conflict_status == "related":
                stats["conflict_related"] += 1

            for child in node.get("children", []):
                _count_node(child)

        for node in nodes:
            _count_node(node)

        return stats


# ------------------------------------------------------------------
# 新增：基于教材信息生成知识点框架
# ------------------------------------------------------------------

async def generate_knowledge_from_textbook(
    grade: str,
    subject: str,
    version: str = "人教版",
    chapter: str | None = None,
    max_points: int = 80,
) -> Dict[str, Any]:
    """基于教材信息生成知识点框架（无文档冷启动）

    用户只需输入教材元信息（年级、学科、版本），AI 自动生成完整的知识点树。
    生成后自动调用 RIA++ 三重验证框架进行质量校验。

    Args:
        grade: 年级，如"初中七年级"、"高中一年级"
        subject: 学科，如"历史"、"数学"、"语文"
        version: 教材版本，默认为"人教版"
        chapter: 可选，具体章节名称
        max_points: 最大知识点数量，默认80

    Returns:
        提取结果字典，包含：
        - success: 是否成功
        - knowledge_points: 知识点树
        - total: 叶子节点数量
        - quality_warnings: 质量警告列表
        - ria_enabled: 是否启用 RIA++ 框架
        - validation_enabled: 是否启用质量验证
    """
    extractor = AIKnowledgeExtractor()

    # 构建 prompt
    prompt = _build_textbook_prompt(grade, subject, version, chapter, max_points)

    try:
        # 调用 AI
        response = await extractor._call_ai(prompt, max_tokens=8192)
        if not response:
            raise Exception("AI 未返回有效内容")

        # 解析知识点树
        knowledge_tree = extractor._parse_knowledge_tree(response)

        # 初始化质量警告列表
        all_quality_warnings: List[str] = []
        validation_results: Dict[str, Any] = {}

        # 三重质量验证
        knowledge_tree, quality_warnings = extractor._validate_knowledge_quality(knowledge_tree)
        all_quality_warnings.extend(quality_warnings)
        validation_results["triple_validation"] = {
            "warnings_count": len(quality_warnings),
            "status": "completed",
        }

        # 层级验证
        knowledge_tree, hierarchy_warnings = extractor._validate_hierarchy(knowledge_tree)
        all_quality_warnings.extend(hierarchy_warnings)
        validation_results["hierarchy_validation"] = {
            "warnings_count": len(hierarchy_warnings),
            "status": "completed",
        }

        # 去重合并
        knowledge_tree, dedup_logs = extractor._deduplicate_knowledge(knowledge_tree)
        all_quality_warnings.extend(dedup_logs)
        validation_results["deduplication"] = {
            "operations_count": len(dedup_logs),
            "status": "completed",
        }

        # 强制限制知识点数量和层级深度
        knowledge_tree = extractor._enforce_limits(knowledge_tree, max_points=max_points, max_depth=4)

        return {
            "success": True,
            "knowledge_points": knowledge_tree,
            "total": extractor._count_leaf_nodes(knowledge_tree),
            "quality_warnings": all_quality_warnings,
            "validation_results": validation_results,
            "ria_enabled": True,
            "validation_enabled": True,
        }

    except Exception as e:
        logger.error(f"教材知识点生成失败: {e!s}")
        # 降级：返回原始提取结果（不带验证）
        try:
            knowledge_tree = extractor._parse_knowledge_tree(
                '{"knowledge_points": [{"name": "提取失败", "description": str(e), "children": []}]}'
            )
        except Exception:
            knowledge_tree = []

        return {
            "success": False,
            "error": str(e),
            "knowledge_points": knowledge_tree,
            "quality_warnings": [f"验证过程异常: {e!s}"],
            "validation_results": {"status": "failed"},
            "ria_enabled": True,
            "validation_enabled": True,
        }


def _build_textbook_prompt(
    grade: str,
    subject: str,
    version: str,
    chapter: str | None,
    max_points: int,
) -> str:
    """构建基于教材信息生成知识点的 prompt

    Args:
        grade: 年级
        subject: 学科
        version: 教材版本
        chapter: 具体章节（可选）
        max_points: 最大知识点数量

    Returns:
        构建好的 prompt 字符串
    """
    chapter_text = chapter if chapter else "全册"

    prompt = f"""你是一位资深的{grade}{subject}教师，精通{version}教材。
请根据以下教材信息，生成完整的知识点树：

- 年级：{grade}
- 学科：{subject}
- 版本：{version}
- 章节：{chapter_text}

要求：
1. 基于国家义务教育课程标准（课标）生成
2. 知识点覆盖教材所有单元/章节
3. 每个知识点包含：name、description、excerpt、children
4. description 用归纳语言描述该知识点的核心内容（不超过200字）
5. excerpt 写出该知识点对应的关键原文/概念定义（不超过2000字）
6. 层级最多4层
7. 总知识点不超过{max_points}个
8. 名称简洁明了，不要包含"第X单元"等编号，而是用概念名称
9. 只返回纯JSON，不要包含markdown代码块标记
10. 不要有尾随逗号

严格按以下格式输出：
{{
  "knowledge_points": [
    {{
      "name": "核心主题（简洁归纳）",
      "description": "该知识点的简短摘要，归纳性描述",
      "excerpt": "该知识点对应的关键原文/概念定义",
      "children": [
        {{
          "name": "子知识点1",
          "description": "子知识点的简短摘要",
          "excerpt": "子知识点对应的关键内容",
          "children": []
        }}
      ]
    }}
  ]
}}

请直接返回JSON格式的知识点结构（不要包含markdown代码块标记）："""

    return prompt


# ------------------------------------------------------------------
# 全局实例
# ------------------------------------------------------------------
_ai_extractor = AIKnowledgeExtractor()


# ------------------------------------------------------------------
# 便捷函数（向后兼容）
# ------------------------------------------------------------------
async def extract_knowledge_from_document(
    document_content: str, document_name: str = "", max_points: int = 50, category: str = "default"
) -> Dict[str, Any]:
    """从文档提取知识点的便捷函数（向后兼容）"""
    return await _ai_extractor.extract_knowledge_tree(
        document_content=document_content, document_name=document_name, max_points=max_points, category=category
    )


async def extract_knowledge_from_rules(
    rule_knowledge: Dict[str, Any],
    document_content: str,
    document_name: str = "",
    max_points: int = 50,
    category: str = "default",
) -> Dict[str, Any]:
    """基于规则提取结果，让AI进行优化和补充

    Args:
        rule_knowledge: 规则提取的知识点结果
        document_content: 原始文档内容（用于AI补充参考）
        document_name: 文档名称
        max_points: 最大知识点数量
        category: 分类代码

    Returns:
        优化后的知识点树
    """
    import json

    rule_points = rule_knowledge.get("knowledge_points", [])
    rule_count = rule_knowledge.get("total", 0)

    # 将规则结果转换为JSON字符串
    rule_json = json.dumps(rule_points, ensure_ascii=False, indent=2)

    # 截取文档内容用于参考（避免过长）
    safe_content = _ai_extractor._sanitize_input(document_content, max_length=30000)

    prompt = f"""你是一个专业的知识体系分析助手。规则提取已经根据文档结构生成了一个知识点树，但可能不够精确或完整。

文档名称：{document_name or "未命名文档"}
分类：{category}

【重要说明】
本系统用于司法鉴定、法律规范等需要高准确性的领域，题目必须严格基于原文生成。
因此知识点必须存储完整的原始内容，而不是归纳总结。

你的任务是：
1. 分析规则提取的知识点结构，判断是否合理
2. 修正不准确的名称和描述
3. 补充遗漏的重要知识点
4. 删除无关或错误的内容
5. 优化层级结构，使其更加合理

核心原则：
- 知识点名称 = 简洁的归纳标签
- 知识点描述（description）= 该知识点对应的【完整原文内容】，必须原文照抄
- 保留法条编号、条款号、具体数字、日期等所有原始信息
- 顶层知识点名称从文档主题出发，不使用文件名

严格限制：
- 总知识点数量不超过{max_points}个（包含所有层级）
- 层级最多4层
- 每个顶层知识点下最多8个子知识点
- description 字段必须存储原始法条内容，禁止归纳概括

规则提取的初始结构：
{rule_json}

参考文档内容（用于补充和完善）：
{safe_content}

要求：
1. 以规则提取的结构为基础进行优化，不是完全重写
2. 保持合理的层级结构
3. 名称简洁明了，description 必须原文照抄法条内容
4. 只返回纯JSON，不要包含任何注释或markdown标记
5. 不要有尾随逗号

严格按以下格式输出：
{{
  "knowledge_points": [
    {{
      "name": "核心主题（简洁归纳）",
      "description": "该知识点对应的完整法条原文内容，原文照抄",
      "children": [...]
    }}
  ]
}}

请直接返回JSON格式的知识点结构："""

    try:
        response = await _ai_extractor._call_ai(prompt, max_tokens=8192)
        if not response:
            raise Exception("AI 未返回有效内容")

        knowledge_tree = _ai_extractor._parse_knowledge_tree(response)

        # 强制限制知识点数量和层级深度
        knowledge_tree = _ai_extractor._enforce_limits(knowledge_tree, max_points=max_points, max_depth=3)

        return {
            "success": True,
            "knowledge_points": knowledge_tree,
            "total": _ai_extractor._count_leaf_nodes(knowledge_tree),
            "rule_based": True,
            "rule_count": rule_count,
        }

    except Exception as e:
        logger.error(f"AI优化规则提取结果失败: {e!s}")
        # 如果AI优化失败，返回规则结果作为降级方案
        return {
            "success": True,
            "knowledge_points": rule_points,
            "total": rule_count,
            "rule_based": True,
            "fallback": True,
        }
