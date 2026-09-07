"""Questions Import/Export Utility Functions

Shared helper functions for file format detection, content validation,
answer formatting, and Excel formula injection prevention.
"""

import io
import logging
import os
import re
from typing import List
import zipfile

from app.config import settings
from app.models.question import QuestionOption

logger = logging.getLogger(__name__)


def _get_type_name(qtype: str) -> str:
    """题型名称映射"""
    type_map = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "essay": "简答题",
    }
    return type_map.get(qtype, qtype)


def _get_difficulty_name(diff: int) -> str:
    if diff <= 2:
        return "简单"
    elif diff == 3:
        return "中等"
    return "困难"


def _format_answer(answer: str, options: List[QuestionOption], question_type: str = None) -> str:
    """格式化答案"""
    if not answer:
        return "-"

    if question_type == "true_false" or answer in ("true", "false", "True", "False"):
        return "正确" if answer.lower() == "true" else "错误"

    if "," in answer:
        return answer

    return answer


def _detect_file_format(file_content: bytes) -> tuple[str | None, str | None]:
    """根据文件魔数和内容检测文件格式，并验证是否为题目导入文件

    Returns:
        (format, error_message) - format 为 "excel" 或 "word"，error_message 为 None 表示验证通过
    """
    if not file_content or len(file_content) < 4:
        return None, "文件内容为空或过小"

    file_type = None

    # Excel .xlsx 和 Word .docx 都是 ZIP 格式，以 PK 开头
    if file_content[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                names = [n.lower() for n in zf.namelist()]
                if any("word/" in n or "word\\" in n for n in names):
                    file_type = "word"
                elif any(n.startswith("xl/") or n.startswith("xl\\") for n in names):
                    file_type = "excel"
                else:
                    return None, "无法识别的文件类型（不是有效的 Excel 或 Word 文件）"
        except zipfile.BadZipFile:
            return None, "文件损坏或不是有效的压缩文件"

    # Excel .xls (BIFF格式) 和 Word .doc (OLE2格式)
    elif file_content[:4] == b"\xd0\xcf\x11\xe0":
        content_preview = file_content[:200].decode("latin-1", errors="ignore")
        if "Microsoft Word" in content_preview or "Word.Document" in content_preview:
            file_type = "word"
        elif "Microsoft Excel" in content_preview or "Excel.Sheet" in content_preview:
            file_type = "excel"
        else:
            return None, "无法确定文件类型，请确保文件为 .xlsx/.xls 或 .docx/.doc 格式"

    else:
        return None, "文件格式不受支持（需要 Excel 或 Word 格式）"

    return file_type, None


def _validate_excel_content(file_content: bytes) -> str | None:
    """验证 Excel 文件内容是否为题目导入格式

    要求：第一行表头必须包含"题型"、"题目"或"内容"等关键字
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
    ws = wb.active

    headers = []
    for cell in ws[1]:
        if cell.value:
            headers.append(str(cell.value).strip().lower())

    wb.close()

    valid_keywords = [
        "题型",
        "题目",
        "内容",
        "question",
        "答案",
        "answer",
        "选项",
        "option",
        "难度",
        "difficulty",
        "分值",
        "分数",
        "score",
    ]

    has_type_or_content = any(any(k in h for k in ["题型", "题目", "内容", "question"]) for h in headers)

    has_answer = any(any(k in h for k in ["答案", "answer"]) for h in headers)

    if not has_type_or_content:
        return "Excel 文件内容不符合题目导入格式。请确保表头包含'题型'、'题目'或'内容'等关键字"

    if not has_answer:
        return "Excel 文件内容不符合题目导入格式。请确保表头包含'答案'或'answer'关键字"

    return None


def _validate_word_content(file_content: bytes) -> str | None:
    """验证 Word 文件内容是否为题目导入格式

    要求：必须包含【题型】标记和"答案："等关键字
    """
    from docx import Document

    doc = Document(io.BytesIO(file_content))
    full_text = "\n".join([para.text for para in doc.paragraphs])

    has_type_marker = "【" in full_text and "】" in full_text
    has_answer_marker = "答案" in full_text or "answer" in full_text.lower()
    has_option_markers = any(marker in full_text for marker in ["[A]", "[B]", "[C]", "[D]", "A.", "B.", "C.", "D."])

    if has_type_marker and (has_answer_marker or has_option_markers):
        return None

    if not has_type_marker:
        return "Word 文件内容不符合题目导入格式。请确保文件包含【题型】标记（如【单选题】）"

    if not (has_answer_marker or has_option_markers):
        return "Word 文件内容不符合题目导入格式。请确保文件包含'答案：'关键字或选项标记（如 A. B. C. D.）"

    return None


def _safe_cell_value(value) -> str:
    """评估 P1-13：防 Excel 公式注入——以 = + - @ 开头的内容强制按文本写入。

    openpyxl 会把以 '=' 开头的字符串当作公式，导出的 xlsx 被打开即执行。
    """
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
