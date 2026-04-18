"""Rule-based Knowledge Extractor - 基于规则的知识点提取服务

不依赖 AI，通过正则匹配文档结构（章、节、条、标题层级）自动提取知识点树。
适用于法律条文、教材等结构化文档，毫秒级返回结果。
"""

import re
from typing import List, Dict, Any, Optional


# 中文数字映射
CN_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '零': 0, '〇': 0, '百': 100, '千': 1000,
}


def cn_to_int(cn: str) -> int:
    """中文数字转整数，如 '二十三' → 23"""
    if cn.isdigit():
        return int(cn)
    result = 0
    current = 0
    for ch in cn:
        if ch in CN_NUM_MAP:
            val = CN_NUM_MAP[ch]
            if val >= 10:
                if current == 0:
                    current = 1
                result += current * val
                current = 0
            else:
                current = val
        else:
            # 阿拉伯数字
            if ch.isdigit():
                current = current * 10 + int(ch)
    result += current
    return result


class RuleKnowledgeExtractor:
    """基于规则的知识点提取器"""

    # 常见章节模式
    PATTERNS = {
        # 第一章、第二章...
        'chapter': re.compile(r'第([一二三四五六七八九十百零〇\d]+)章\s+(.+?)(?:\n|$)'),
        # 第一节、第二节...
        'section': re.compile(r'第([一二三四五六七八九十百零〇\d]+)节\s+(.+?)(?:\n|$)'),
        # 第一条、第二条...
        'article': re.compile(r'第([一二三四五六七八九十百零〇\d]+)条\s+'),
        # Markdown 标题
        'h1': re.compile(r'^#\s+(.+)$', re.MULTILINE),
        'h2': re.compile(r'^##\s+(.+)$', re.MULTILINE),
        'h3': re.compile(r'^###\s+(.+)$', re.MULTILINE),
        # 数字编号 1. / 1.1 / 1.1.1
        'num_h1': re.compile(r'^(\d{1,2})\.\s+([^\d].+)$', re.MULTILINE),
        'num_h2': re.compile(r'^(\d{1,2}\.\d{1,2})\s+([^\d].+)$', re.MULTILINE),
        'num_h3': re.compile(r'^(\d{1,2}\.\d{1,2}\.\d{1,2})\s+([^\d].+)$', re.MULTILINE),
        # （一）（二）（三）条款项
        'clause': re.compile(r'[（(]([一二三四五六七八九十]+)[）)]\s*'),
    }

    def extract(self, text: str, max_children: int = 5, max_depth: int = 3) -> List[Dict[str, Any]]:
        """从文本提取知识点树

        自动检测文档结构类型，选择最佳解析策略：
        1. 法律条文：章→条 结构
        2. Markdown：标题层级
        3. 数字编号：1. → 1.1 → 1.1.1
        4. 纯文本兜底：按段落拆分
        """
        # 检测文档类型
        has_chapter = bool(self.PATTERNS['chapter'].search(text))
        has_article = bool(self.PATTERNS['article'].search(text))
        has_section = bool(self.PATTERNS['section'].search(text))
        has_md_h1 = bool(self.PATTERNS['h1'].search(text))
        has_num_h1 = bool(self.PATTERNS['num_h1'].search(text))

        if has_chapter or has_article:
            return self._extract_law(text, max_children, max_depth)
        elif has_md_h1:
            return self._extract_markdown(text, max_children, max_depth)
        elif has_num_h1:
            return self._extract_numbered(text, max_children, max_depth)
        else:
            return self._extract_plain(text, max_children, max_depth)

    def _extract_law(self, text: str, max_children: int, max_depth: int) -> List[Dict[str, Any]]:
        """提取法律条文类文档：章→条 结构"""
        chapters = list(self.PATTERNS['chapter'].finditer(text))
        articles = list(self.PATTERNS['article'].finditer(text))

        if not chapters and not articles:
            return self._extract_plain(text, max_children, max_depth)

        # 计算章节位置
        chapter_positions = [(m.start(), m.end(), m.group(1), m.group(2).strip()) for m in chapters]
        article_positions = [(m.start(), m.end(), m.group(1)) for m in articles]

        # 如果没有章但有条，条作为顶层
        if not chapter_positions:
            return self._group_articles(text, article_positions, max_children)

        # 给章设置结束位置
        chapter_ranges = []
        for i, (start, end, num, name) in enumerate(chapter_positions):
            next_start = chapter_positions[i + 1][0] if i + 1 < len(chapter_positions) else len(text)
            chapter_ranges.append((start, next_start, num, name))

        tree = []
        for ch_start, ch_end, ch_num, ch_name in chapter_ranges:
            # 收集该章内的条
            ch_articles = [(a_start, a_end, a_num) for a_start, a_end, a_num in article_positions
                           if ch_start <= a_start < ch_end]

            ch_node = {
                "name": ch_name,
                "description": f"第{ch_num}章，共{len(ch_articles)}条",
                "children": []
            }

            if ch_articles:
                groups = self._split_into_groups(ch_articles, max_children)
                for group in groups:
                    if len(groups) == 1:
                        # 只有1组，条直接作为子节点
                        for a_start, a_end, a_num in group:
                            summary = self._get_first_sentence(text, a_end)
                            ch_node["children"].append({
                                "name": f"第{a_num}条",
                                "description": summary,
                                "children": []
                            })
                    else:
                        # 多组，每组作为一个二级节点
                        first_num = group[0][2]
                        last_num = group[-1][2]
                        group_desc = self._get_first_sentence(text, group[0][1])

                        group_node = {
                            "name": f"第{first_num}-{last_num}条",
                            "description": group_desc,
                            "children": []
                        }

                        for a_start, a_end, a_num in group:
                            summary = self._get_first_sentence(text, a_end)
                            group_node["children"].append({
                                "name": f"第{a_num}条",
                                "description": summary,
                                "children": []
                            })

                        ch_node["children"].append(group_node)

            tree.append(ch_node)

        return tree

    def _group_articles(self, text: str, article_positions: list, max_children: int) -> List[Dict[str, Any]]:
        """没有章时，将条分组为顶层节点"""
        groups = self._split_into_groups(article_positions, max_children)
        tree = []

        for group in groups:
            first_num = group[0][2]
            last_num = group[-1][2]
            group_desc = self._get_first_sentence(text, group[0][1])

            group_node = {
                "name": f"第{first_num}-{last_num}条",
                "description": group_desc,
                "children": []
            }

            for a_start, a_end, a_num in group:
                summary = self._get_first_sentence(text, a_end)
                group_node["children"].append({
                    "name": f"第{a_num}条",
                    "description": summary,
                    "children": []
                })

            tree.append(group_node)

        return tree

    def _extract_markdown(self, text: str, max_children: int, max_depth: int) -> List[Dict[str, Any]]:
        """提取 Markdown 标题结构"""
        h1_list = list(self.PATTERNS['h1'].finditer(text))
        if not h1_list:
            return self._extract_plain(text, max_children, max_depth)

        tree = []
        for i, h1 in enumerate(h1_list):
            h1_end = h1.end()
            next_h1 = h1_list[i + 1].start() if i + 1 < len(h1_list) else len(text)
            section_text = text[h1_end:next_h1]

            node = {
                "name": h1.group(1).strip(),
                "description": "",
                "children": []
            }

            # 找 h2
            h2_list = list(self.PATTERNS['h2'].finditer(section_text))
            if h2_list:
                for j, h2 in enumerate(h2_list):
                    h2_end = h2.end()
                    next_h2 = h2_list[j + 1].start() if j + 1 < len(h2_list) else len(section_text)
                    h2_text = section_text[h2_end:next_h2]

                    h2_node = {
                        "name": h2.group(1).strip(),
                        "description": self._get_summary(h2_text),
                        "children": []
                    }

                    # 找 h3
                    if max_depth >= 3:
                        h3_list = list(self.PATTERNS['h3'].finditer(h2_text))
                        for h3 in h3_list[:max_children]:
                            h3_node = {
                                "name": h3.group(1).strip(),
                                "description": "",
                                "children": []
                            }
                            h2_node["children"].append(h3_node)

                    node["children"].append(h2_node)
            else:
                # 没有 h2，取段落摘要
                node["description"] = self._get_summary(section_text)

            tree.append(node)

        return tree

    def _extract_numbered(self, text: str, max_children: int, max_depth: int) -> List[Dict[str, Any]]:
        """提取数字编号结构 1. → 1.1 → 1.1.1"""
        h3_list = list(self.PATTERNS['num_h3'].finditer(text))
        h2_list = list(self.PATTERNS['num_h2'].finditer(text))
        h1_list = list(self.PATTERNS['num_h1'].finditer(text))

        if not h1_list:
            return self._extract_plain(text, max_children, max_depth)

        tree = []
        for i, h1 in enumerate(h1_list):
            h1_end = h1.end()
            next_h1 = h1_list[i + 1].start() if i + 1 < len(h1_list) else len(text)

            node = {
                "name": h1.group(2).strip(),
                "description": "",
                "children": []
            }

            # 找该范围内的 h2
            h2_in_range = [m for m in h2_list if h1_end <= m.start() < next_h1]
            if h2_in_range:
                for j, h2 in enumerate(h2_in_range[:max_children]):
                    h2_end = h2.end()
                    next_h2 = h2_in_range[j + 1].start() if j + 1 < len(h2_in_range) else next_h1

                    h2_node = {
                        "name": h2.group(2).strip(),
                        "description": "",
                        "children": []
                    }

                    # 找 h3
                    if max_depth >= 3:
                        h3_in_range = [m for m in h3_list if h2_end <= m.start() < next_h2]
                        for h3 in h3_in_range[:max_children]:
                            h3_node = {
                                "name": h3.group(2).strip(),
                                "description": "",
                                "children": []
                            }
                            h2_node["children"].append(h3_node)

                    node["children"].append(h2_node)
            else:
                node["description"] = self._get_summary(text[h1_end:next_h1])

            tree.append(node)

        return tree

    def _extract_plain(self, text: str, max_children: int, max_depth: int) -> List[Dict[str, Any]]:
        """纯文本兜底：按段落拆分"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 10]
        if not paragraphs:
            return [{"name": "文档内容", "description": text[:200], "children": []}]

        tree = []
        for i in range(0, min(len(paragraphs), 50), max_children):
            group = paragraphs[i:i + max_children]
            group_node = {
                "name": f"段落{i + 1}-{min(i + max_children, len(paragraphs))}",
                "description": group[0][:100] if group else "",
                "children": []
            }
            for j, para in enumerate(group):
                # 取第一句作为名称
                first_sentence = para.split('。')[0].strip() if '。' in para else para[:50].strip()
                group_node["children"].append({
                    "name": first_sentence[:30],
                    "description": para[:150],
                    "children": []
                })
            tree.append(group_node)

        return tree

    def _split_into_groups(self, positions: list, max_per_group: int) -> list:
        """将位置列表按 max_per_group 分组"""
        groups = []
        for i in range(0, len(positions), max_per_group):
            groups.append(positions[i:i + max_per_group])
        return groups

    def _get_first_sentence(self, text: str, start_pos: int, max_len: int = 100) -> str:
        """获取从 start_pos 开始的第一句话"""
        chunk = text[start_pos:start_pos + 500].strip()
        # 找第一个句号/问号/感叹号
        for end_char in ['。', '？', '！', '?', '!']:
            idx = chunk.find(end_char)
            if idx > 0:
                result = chunk[:idx + 1].strip()
                return result[:max_len] if len(result) > max_len else result
        # 没有句号，取前 max_len 字符
        return chunk[:max_len].strip()

    def _get_summary(self, text: str, max_len: int = 100) -> str:
        """获取文本摘要"""
        text = text.strip()
        if not text:
            return ""
        # 取前几个非空行
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            summary = lines[0][:max_len]
            return summary
        return text[:max_len]


# 便捷函数
_rule_extractor = RuleKnowledgeExtractor()


def extract_knowledge_by_rules(
    text: str,
    max_children: int = 5,
    max_depth: int = 3
) -> Dict[str, Any]:
    """基于规则提取知识点

    Args:
        text: 文档文本内容
        max_children: 每个节点最多子节点数
        max_depth: 最大层级深度

    Returns:
        提取结果字典，包含 knowledge_points 和 total
    """
    knowledge_points = _rule_extractor.extract(text, max_children, max_depth)

    # 计算叶子节点数（末级节点）
    def count_leaf_nodes(nodes):
        c = 0
        for n in nodes:
            if not n.get("children") or len(n.get("children", [])) == 0:
                c += 1
            else:
                c += count_leaf_nodes(n.get("children", []))
        return c

    total = count_leaf_nodes(knowledge_points)

    return {
        "success": True,
        "knowledge_points": knowledge_points,
        "total": total,
        "method": "rule-based",
        "message": f"规则解析完成，提取 {total} 个知识点"
    }
