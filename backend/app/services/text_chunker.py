"""Text Chunker - 文档分块服务

将解析后的全文按结构切分为 1000-3000 字的块，每块对应一个 KnowledgeEntry。
策略：复用 rule_knowledge_extractor 的结构检测逻辑（章/节/条/markdown/数字标题），
但目标不是构建知识点树，而是按主要分隔符切分原文，保证每块语义完整。

分块原则：
1. 按主要结构（章/H1/大标题）切分为大块
2. 大块超过 max_chunk_size 则按次级结构（节/H2/小标题）再切
3. 小块不足 min_chunk_size 且有前一块则合并
4. 每块带 source_location（章节定位，如 "第3章" / "## 数据结构基础"）
"""

from dataclasses import dataclass
import re
from typing import List

# 中文数字映射（与 rule_knowledge_extractor 一致）
_CN_NUM_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "零": 0,
    "〇": 0,
    "百": 100,
    "千": 1000,
}


def _cn_to_int(cn: str) -> int:
    """中文数字转整数，如 '二十三' -> 23"""
    if cn.isdigit():
        return int(cn)
    result = 0
    current = 0
    for ch in cn:
        if ch in _CN_NUM_MAP:
            val = _CN_NUM_MAP[ch]
            if val >= 10:
                if current == 0:
                    current = 1
                result += current * val
                current = 0
            else:
                current = val
        elif ch.isdigit():
            current = current * 10 + int(ch)
    result += current
    return result


# 结构检测正则（与 rule_knowledge_extractor 保持一致）
PATTERNS = {
    "chapter": re.compile(r"第([一二三四五六七八九十百零〇\d]+)章\s+(.+?)(?:\n|$)"),
    "section": re.compile(r"第([一二三四五六七八九十百零〇\d]+)节\s+(.+?)(?:\n|$)"),
    "article": re.compile(r"第([一二三四五六七八九十百零〇\d]+)条\s+"),
    "h1": re.compile(r"^#\s+(.+)$", re.MULTILINE),
    "h2": re.compile(r"^##\s+(.+)$", re.MULTILINE),
    "num_h1": re.compile(r"^(\d{1,2})\.\s+([^\d].+)$", re.MULTILINE),
    "num_h2": re.compile(r"^(\d{1,2}\.\d{1,2})\s+([^\d].+)$", re.MULTILINE),
}


@dataclass
class TextChunk:
    """单个文本块"""

    title: str
    content: str
    order: int
    source_location: str  # 章节定位，如 "第3章" / "## 数据结构基础"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "order": self.order,
            "source_location": self.source_location,
        }


def _detect_doc_type(text: str) -> str:
    """检测文档结构类型：law / markdown / numbered / plain"""
    has_chapter = bool(PATTERNS["chapter"].search(text))
    has_article = bool(PATTERNS["article"].search(text))
    has_md_h1 = bool(PATTERNS["h1"].search(text))
    has_num_h1 = bool(PATTERNS["num_h1"].search(text))

    if has_chapter or has_article:
        return "law"
    if has_md_h1:
        return "markdown"
    if has_num_h1:
        return "numbered"
    return "plain"


def _split_by_pattern(text: str, pattern: re.Pattern, group_index: int = 1) -> List[tuple]:
    """按正则匹配切分文本，返回 [(title, content, source_location), ...]"""
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    chunks = []
    for i, m in enumerate(matches):
        title = m.group(group_index).strip() if m.groups() else m.group(0).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        # source_location 取匹配行原文
        line = text[start : m.end()].split("\n", 1)[0].strip()
        chunks.append((title, content, line))

    return chunks


def _split_law(text: str, max_size: int) -> List[tuple]:
    """法律文本：按章切分，章过大则按节/条再切"""
    chapters = _split_by_pattern(text, PATTERNS["chapter"], group_index=2)
    if chapters:
        return _refine_chunks(chapters, max_size, PATTERNS["section"], group_index=2)

    # 没有章只有条，按条切分（每条较短，需合并）
    articles = _split_by_pattern(text, PATTERNS["article"], group_index=1)
    if articles:
        return articles

    return []


def _split_markdown(text: str, max_size: int) -> List[tuple]:
    """Markdown：按 H1 切分，H1 过大则按 H2 再切"""
    chunks = _split_by_pattern(text, PATTERNS["h1"], group_index=1)
    if chunks:
        return _refine_chunks(chunks, max_size, PATTERNS["h2"], group_index=1)
    return []


def _split_numbered(text: str, max_size: int) -> List[tuple]:
    """数字编号：按 1. 切分，过大则按 1.1 再切"""
    chunks = _split_by_pattern(text, PATTERNS["num_h1"], group_index=2)
    if chunks:
        return _refine_chunks(chunks, max_size, PATTERNS["num_h2"], group_index=2)
    return []


def _split_plain(text: str, max_size: int) -> List[tuple]:
    """纯文本：按段落合并，每块不超过 max_size"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current_content = ""
    current_title = ""
    count = 0

    for para in paragraphs:
        if not current_content:
            current_title = para[:50].split("\n")[0]
            current_content = para
        elif len(current_content) + len(para) + 2 <= max_size:
            current_content += "\n\n" + para
        else:
            count += 1
            chunks.append((current_title, current_content, f"段落{count}"))
            current_title = para[:50].split("\n")[0]
            current_content = para

    if current_content:
        count += 1
        chunks.append((current_title, current_content, f"段落{count}"))

    return chunks


def _refine_chunks(chunks: List[tuple], max_size: int, sub_pattern: re.Pattern, group_index: int) -> List[tuple]:
    """对超过 max_size 的块按次级结构再切分"""
    refined = []
    for title, content, location in chunks:
        if len(content) <= max_size:
            refined.append((title, content, location))
        else:
            sub_chunks = _split_by_pattern(content, sub_pattern, group_index=group_index)
            if sub_chunks:
                for sub_title, sub_content, sub_loc in sub_chunks:
                    refined.append((sub_title, sub_content, sub_loc))
            else:
                # 次级结构也无法切分，按 max_size 硬切
                for i in range(0, len(content), max_size):
                    part = content[i : i + max_size]
                    refined.append((title, part, f"{location} (续)"))
    return refined


def _merge_small_chunks(chunks: List[tuple], min_size: int) -> List[tuple]:
    """合并过小的块到前一块

    仅当一块的内容明显过短（< min_size）且前一块加上后仍 < min_size*4 时才合并，
    避免把多个独立章节错误合并。
    """
    if len(chunks) <= 1:
        return chunks

    merged = []
    for chunk in chunks:
        _title, content, _location = chunk
        if merged and len(content) < min_size and len(merged[-1][1]) + len(content) < min_size * 4:
            # 块过小，合并到前一块
            prev_title, prev_content, prev_loc = merged[-1]
            merged[-1] = (
                prev_title,
                prev_content + "\n\n" + content,
                prev_loc,
            )
        else:
            merged.append(chunk)
    return merged


def chunk_document(text: str, max_chunk_size: int = 3000, min_chunk_size: int = 500) -> List[dict]:
    """将全文按结构分块

    Args:
        text: 解析后的全文
        max_chunk_size: 单块最大字符数，默认 3000
        min_chunk_size: 单块最小字符数，不足则合并到前一块，默认 500

    Returns:
        分块列表 [{title, content, order, source_location}, ...]
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # 检测文档类型并按对应策略切分
    doc_type = _detect_doc_type(text)
    is_structured = doc_type != "plain"
    if doc_type == "law":
        raw_chunks = _split_law(text, max_chunk_size)
    elif doc_type == "markdown":
        raw_chunks = _split_markdown(text, max_chunk_size)
    elif doc_type == "numbered":
        raw_chunks = _split_numbered(text, max_chunk_size)
    else:
        raw_chunks = _split_plain(text, max_chunk_size)

    # 如果结构化切分失败，回退到纯文本切分
    if not raw_chunks:
        raw_chunks = _split_plain(text, max_chunk_size)
        is_structured = False

    # 仅对纯文本块做合并；结构化分块（章/节/H1）保持边界，不过度合并
    if not is_structured:
        raw_chunks = _merge_small_chunks(raw_chunks, min_chunk_size)

    # 转换为 TextChunk 并分配 order
    result = []
    for i, (title, content, location) in enumerate(raw_chunks):
        result.append(
            TextChunk(
                title=title[:200],  # 标题截断到 200 字
                content=content,
                order=i,
                source_location=location[:100] if location else None,
            ).to_dict()
        )

    return result
