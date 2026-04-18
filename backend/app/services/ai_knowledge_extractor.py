"""AI Knowledge Extractor Service - AI 知识点提取服务

使用 AI 自动分析文档内容，提取知识点并生成树形结构。
优化策略：分段提取 + 并行调用 + 精简 prompt
使用统一AI服务层
"""

import json
import re
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)


class AIKnowledgeExtractor:
    """AI 知识点提取器"""

    def __init__(self):
        self.max_tokens = 2048  # 单次调用输出上限（降低以加速）

    def _sanitize_input(self, text: str, max_length: int = 8000) -> str:
        """清理输入文本，缩短截断长度以加速"""
        text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'on\w+\s*=', '', text)
        if len(text) > max_length:
            text = text[:max_length] + "\n[内容过长已截断]"
        return text

    async def _call_ai(self, prompt: str, max_tokens: int = None) -> Optional[str]:
        """调用统一AI服务层"""
        try:
            provider = get_ai_provider()
            result = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.max_tokens,
                temperature=0.3  # 结构化提取不需要高创造性
            )
            return result
        except Exception as e:
            raise Exception(f"AI API 调用失败: {str(e)}")

    def _clean_json_string(self, text: str) -> str:
        """清理 AI 返回的 JSON 字符串，处理常见问题"""
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        text = re.sub(r',\s*([}\]])', r'\1', text)
        text = re.sub(r'"\s*\+\s*"', '', text)
        text = re.sub(r'([{,]\s*)([\u4e00-\u9fff\w]+)\s*:', r'\1"\2":', text)
        return text.strip()

    def _parse_knowledge_tree(self, ai_response: str) -> List[Dict[str, Any]]:
        """解析 AI 返回的知识点树"""
        # 首先尝试直接解析（正常情况）
        try:
            data = json.loads(ai_response.strip())
            result = self._extract_knowledge_points(data)
            if result and len(result) > 0:
                return result
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 提取
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = ai_response.strip()

        # 移除残留 markdown
        json_str = re.sub(r'^```json\s*', '', json_str, flags=re.IGNORECASE)
        json_str = re.sub(r'^```\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
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

    def _fix_malformed_json(self, json_str: str) -> Optional[str]:
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
            if json_str[i] == '[':
                depth += 1
            elif json_str[i] == ']':
                depth -= 1
                if depth == 0:
                    arr_end = i
                    break

        if arr_end == -1:
            unclosed_brackets = depth
            if unclosed_brackets > 0:
                json_str = json_str + ']' * unclosed_brackets
                arr_end = len(json_str) - 1

        if arr_end == -1 or arr_end <= arr_start:
            return None

        arr_content = json_str[arr_start + 1:arr_end]
        objects = self._parse_malformed_array(arr_content)

        if objects:
            return '{"' + key_name + '": ' + json.dumps(objects, ensure_ascii=False) + '}'

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
                if content[i] == '[':
                    depth += 1
                elif content[i] == ']':
                    depth -= 1
                    if depth == 0:
                        arr_end = i
                        break

            child_arr_content = content[child_arr_begin + 1:arr_end] if arr_end > child_arr_begin else ""
            parent_obj = self._parse_key_value_pairs(parent_kv_content)

            if child_arr_content.strip():
                parent_obj['子节点'] = self._parse_child_array(child_arr_content)

            if parent_obj.get('名称'):
                objects.append(parent_obj)
        else:
            if '{' in content:
                objects = self._parse_normal_object_array(content)
            else:
                obj = self._parse_key_value_pairs(content)
                if obj and obj.get('名称'):
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
            if char == '\\':
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == '{':
                if depth == 0:
                    obj_start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    obj_text = content[obj_start:i+1]
                    try:
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict) and obj.get('名称'):
                            objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    obj_start = -1

        return objects

    def _parse_key_value_pairs(self, content: str) -> dict:
        """解析键值对序列，提取名称、描述、子节点等"""
        obj = {}
        content = content.strip().strip(',').strip()

        if not content:
            return obj

        kv_pattern = r'"(名称|描述|子节点|children|name|description)"\s*:\s*'

        for match in re.finditer(kv_pattern, content):
            key = match.group(1)
            value_start = match.end()
            remaining = content[value_start:]

            if remaining.strip().startswith('['):
                depth = 0
                arr_end = -1
                for i, c in enumerate(remaining):
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            arr_end = i
                            break

                if arr_end > 0:
                    arr_content = remaining[1:arr_end]
                    obj[key] = self._parse_child_array(arr_content)
            elif remaining.strip().startswith('{'):
                depth = 0
                obj_end = -1
                for i, c in enumerate(remaining):
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            obj_end = i
                            break

                if obj_end > 0:
                    obj_text = remaining[:obj_end+1]
                    try:
                        obj[key] = json.loads(obj_text)
                    except json.JSONDecodeError:
                        obj[key] = self._parse_key_value_pairs(obj_text)
            else:
                value_match = re.match(r'([^,}\]]+)', remaining.strip())
                if value_match:
                    value = value_match.group(1).strip().strip('"\', ')
                    obj[key] = value

        return obj

    def _parse_child_array(self, content: str) -> List[dict]:
        """解析子节点数组"""
        children = []
        content = content.strip()
        if not content:
            return children

        if '{' in content:
            children = self._parse_normal_object_array(content)
        else:
            obj = self._parse_key_value_pairs(content)
            if obj and obj.get('名称'):
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
            return any(key in ['名称', '描述', '子节点', '知识点'] for key in data.keys())
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
            result.append({
                "name": str(name)[:100],
                "description": str(desc)[:500] if desc else "",
                "children": converted_children
            })
        return result

    def _parse_text_knowledge(self, text: str) -> List[Dict[str, Any]]:
        """从文本解析知识点（备选方案），支持基于缩进/编号的层级推断"""
        lines = text.strip().split('\n')
        parsed_lines = []

        for line in lines:
            stripped = line.rstrip()
            if not stripped.strip():
                continue
            indent = len(stripped) - len(stripped.lstrip())
            cleaned = re.sub(r'^[\d\.\-\*\>\#]+[\s\)：:]*', '', stripped.strip())
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

    async def extract_knowledge_tree(
        self,
        document_content: str,
        document_name: str = "",
        max_points: int = 50,
        category: str = "default"
    ) -> Dict[str, Any]:
        """从文档内容提取知识点树

        优化策略：
        - 降低 temperature 提高结构化输出稳定性
        - 精简但完整的 prompt，保留格式示例确保输出质量
        - 合理的 max_tokens 和文档截断
        """
        safe_content = self._sanitize_input(document_content)

        prompt = f"""你是一个专业的知识体系分析助手。请分析以下文档内容，提取知识点并生成树形结构。

文档名称：{document_name or "未命名文档"}
分类：{category}

核心原则：
- 知识点应该是归纳、提炼后的概念，而不是原文照抄
- 避免提取具体条款号、具体数字、具体日期等原始数据
- 用自己的话总结核心概念、原理、方法、制度要点
- 顶层知识点名称完全从文档内容的主题出发，不使用文件名

严格限制：
- 总知识点数量不超过{max_points}个（包含所有层级）
- 层级最多4层（顶层→二级→三级→四级）
- 每个顶层知识点下最多8个子知识点
- 每个子知识点下最多6个三级知识点
- 每个三级知识点下最多5个四级知识点
- 知识点的名称和描述必须是经过归纳总结后的内容
- 绝对不要把文件名、文件扩展名、文件路径用在任何知识点名称中

要求：
1. 首先分析文档内容，确定文档的核心主题领域
2. 顶层知识点名称应该围绕文档的核心主题，如"司法鉴定基本规范"、"医师执业资格管理"、"环境影响评价制度"等
3. 顶层知识点名称不要包含文件后缀（.doc、.pdf、.txt等）、编号（如"四"、"（一）"等前缀）、中括号（【】）等
4. 每个主题下的核心概念、原理、方法等提取为子节点
5. 名称应该简洁明了，如"什么是XXX"、"XXX的适用范围"、"XXX的处理流程"
6. 描述应该用归纳性的语言概括核心要点，不要复制原文
7. 必须构建有层次的树形结构，子知识点必须放在父知识点的"children"数组中
8. 每个知识点包含：name（简洁的归纳名称）、description（核心要点归纳）、children（子节点数组）
9. 只返回纯JSON，不要包含任何注释、说明或markdown标记
10. 不要有尾随逗号

严格按以下格式输出（不要添加任何额外内容）：
{{
  "knowledge_points": [
    {{
      "name": "核心主题1（从文档内容提炼）",
      "description": "该类别下知识点的总体概述，包含哪些方面的核心要点",
      "children": [
        {{
          "name": "核心概念：XXX是什么",
          "description": "用归纳的语言描述该概念的本质特征和主要方面",
          "children": [
            {{
              "name": "要点1：XXX",
              "description": "该要点的核心内容",
              "children": []
            }},
            {{
              "name": "要点2：XXX",
              "description": "该要点的核心内容",
              "children": []
            }}
          ]
        }},
        {{
          "name": "适用范围：XXX",
          "description": "该制度/方法/原理的适用场景和范围",
          "children": []
        }}
      ]
    }},
    {{
      "name": "核心主题2（从文档内容提炼）",
      "description": "该类别下知识点的总体概述",
      "children": []
    }}
  ]
}}

文档内容：
{safe_content}

请直接返回JSON格式的知识点结构（不要包含markdown代码块标记）："""

        try:
            response = await self._call_ai(prompt, max_tokens=8192)
            if not response:
                raise Exception("AI 未返回有效内容")

            knowledge_tree = self._parse_knowledge_tree(response)

            # 强制限制知识点数量和层级深度
            knowledge_tree = self._enforce_limits(knowledge_tree, max_points=max_points, max_depth=3)

            return {
                "success": True,
                "knowledge_points": knowledge_tree,
                "total": self._count_leaf_nodes(knowledge_tree)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "knowledge_points": []
            }

    def _flatten_tree(self, nodes: List[Dict]) -> List[Dict]:
        """扁平化知识点树"""
        result = []
        for node in nodes:
            result.append(node)
            if "children" in node and node["children"]:
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

        def process(node: Dict, depth: int) -> Optional[Dict]:
            nonlocal count
            if count >= max_points:
                return None

            count += 1
            new_node = {
                "name": node.get("name", "未命名")[:100],
                "description": (node.get("description", "") or "")[:500],
                "children": []
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


# 全局实例
_ai_extractor = AIKnowledgeExtractor()


async def extract_knowledge_from_document(
    document_content: str,
    document_name: str = "",
    max_points: int = 50,
    category: str = "default"
) -> Dict[str, Any]:
    """从文档提取知识点的便捷函数"""
    return await _ai_extractor.extract_knowledge_tree(
        document_content=document_content,
        document_name=document_name,
        max_points=max_points,
        category=category
    )


async def extract_knowledge_from_rules(
    rule_knowledge: Dict[str, Any],
    document_content: str,
    document_name: str = "",
    max_points: int = 50,
    category: str = "default"
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

你的任务是：
1. 分析规则提取的知识点结构，判断是否合理
2. 修正不准确的名称和描述
3. 补充遗漏的重要知识点
4. 删除无关或错误的内容
5. 优化层级结构，使其更加合理

核心原则：
- 知识点应该是归纳、提炼后的概念，不是原文照抄
- 避免提取具体条款号、具体数字、具体日期等原始数据
- 用自己的话总结核心概念、原理、方法、制度要点
- 顶层知识点名称完全从文档内容的主题出发，不使用文件名

严格限制：
- 总知识点数量不超过{max_points}个（包含所有层级）
- 层级最多4层
- 每个顶层知识点下最多8个子知识点
- 知识点的名称和描述必须是经过归纳总结后的内容

规则提取的初始结构：
{rule_json}

参考文档内容（用于补充和完善）：
{safe_content}

要求：
1. 以规则提取的结构为基础进行优化，不是完全重写
2. 保持合理的层级结构
3. 名称简洁明了，描述归纳核心要点
4. 只返回纯JSON，不要包含任何注释或markdown标记
5. 不要有尾随逗号

严格按以下格式输出：
{{
  "knowledge_points": [
    {{
      "name": "核心主题（简洁归纳）",
      "description": "该主题下知识点的总体概述",
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
        knowledge_tree = _ai_extractor._enforce_limits(
            knowledge_tree, max_points=max_points, max_depth=3
        )

        return {
            "success": True,
            "knowledge_points": knowledge_tree,
            "total": _ai_extractor._count_leaf_nodes(knowledge_tree),
            "rule_based": True,
            "rule_count": rule_count
        }

    except Exception as e:
        logger.error(f"AI优化规则提取结果失败: {str(e)}")
        # 如果AI优化失败，返回规则结果作为降级方案
        return {
            "success": True,
            "knowledge_points": rule_points,
            "total": rule_count,
            "rule_based": True,
            "fallback": True
        }
