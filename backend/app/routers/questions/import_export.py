"""Questions Import/Export Router - File parsing, preview, import, and export"""

from datetime import datetime
import io
import logging
import os
import re
from typing import List
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models.question import Question, QuestionOption
from app.models.user import User
from app.schemas.question import (
    ImportResult,
    PreviewResult,
)
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Helper Functions ============


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


def _parse_excel_questions(file_content: bytes) -> List[dict]:
    """从 Excel 文件解析题目"""
    import openpyxl

    questions = []
    wb = openpyxl.load_workbook(io.BytesIO(file_content))
    ws = wb.active

    headers = [cell.value for cell in ws[1]]
    required_cols = ["题型", "题目内容", "正确答案", "难度", "分值", "所属科目ID", "所属章节ID"]
    for col in required_cols:
        if col not in headers:
            raise ValueError(f"Excel 文件缺少必要列: {col}")

    col_map = {header: idx for idx, header in enumerate(headers)}

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue

        try:
            question_type_map = {
                "单选题": "single_choice",
                "多选题": "multiple_choice",
                "判断题": "true_false",
                "简答题": "essay",
            }
            question_type = question_type_map.get(row[col_map["题型"]], "single_choice")

            answer = str(row[col_map["正确答案"]]) if row[col_map["正确答案"]] else ""
            options = []

            if question_type in ("single_choice", "multiple_choice"):
                options_col = col_map.get("选项")
                if options_col and row[options_col]:
                    options_text = str(row[options_col])
                    option_pattern = re.compile(r"^([A-D])[\.\、]\s*(.+)$", re.MULTILINE)
                    for match in option_pattern.finditer(options_text):
                        is_correct = match.group(1) in answer.upper()
                        options.append(
                            {
                                "option_label": match.group(1),
                                "option_content": match.group(2).strip(),
                                "is_correct": is_correct,
                            }
                        )

            tags = None
            tags_col = col_map.get("标签")
            if tags_col and row[tags_col]:
                tags = {"import_tags": str(row[tags_col]).split(",")}

            question = {
                "question_type": question_type,
                "content": str(row[col_map["题目内容"]]).strip() if row[col_map["题目内容"]] else "",
                "answer": answer,
                "difficulty": int(row[col_map["难度"]]) if row[col_map["难度"]] else 1,
                "score": float(row[col_map["分值"]]) if row[col_map["分值"]] else 5.0,
                "subject_id": int(row[col_map["所属科目ID"]]) if row[col_map["所属科目ID"]] else 1,
                "chapter_id": int(row[col_map["所属章节ID"]]) if row[col_map["所属章节ID"]] else 1,
                "options": options if options else None,
                "tags": tags,
                "explanation": str(row[col_map.get("解析", "")]) if row[col_map.get("解析")] else None,
            }
            questions.append(question)
        except Exception as e:
            logger.warning(f"解析第 {row_idx} 行失败: {e}")
            continue

    return questions


def _parse_word_questions(file_content: bytes) -> List[dict]:
    """从 Word 文件解析题目

    支持的格式：
    - 格式1（标记格式）：【单选题】【多选题】【判断题】【简答题】
    - 格式2（编号格式）：1. 题目内容 或 1、题目内容
    - 格式3（【编号】格式）：【1】【2】或 一、二、三（中文数字）
    - 格式4（判断题）：题目内容（√）或（×）
    - 格式5（选项内联）：A. 选项1 B. 选项2 C. 选项3 D. 选项4（同一行）
    - 格式6（分列选项）：A. 选项1 单独一行
    - 答案格式：答案：A、答案：AB、答案：√、答案：×
    - 支持表格形式组织的题目

    关键规则：
    1. 选项行（A. B. C. D.）永远不会被创建为新题目
    2. 章节标题（判断题50道、多选题 100 题、一、二、三、基础理论等）跳过
    3. 文档标题（长度>30且以特定词开头）跳过
    4. 题目内容以（）结尾的才认为是选择题/判断题
    5. 长度<15且不以（）结尾的内容，不是题目
    """
    questions = []
    doc = Document(io.BytesIO(file_content))

    # ============ 辅助函数 ============

    def _create_question(question_type: str, content: str) -> dict:
        """创建题目对象"""
        return {
            "question_type": question_type,
            "content": content.strip() if content else "",
            "options": [],
            "answer": "",
            "difficulty": 1,
            "score": 5.0,
            "subject_id": None,
            "chapter_id": None,
        }

    def _is_option_line(text: str) -> bool:
        """判断是否是选项行（A. xxx 或 A、xxx 或 A．xxx）"""
        return bool(re.match(r"^[A-D][\.\、．]\s*\S", text))

    def _is_chapter_title(text: str) -> bool:
        """判断是否是章节标题"""
        if re.match(r"^.{0,6}题\s*\d+\s*[道题]$", text):
            return True
        if re.match(r"^[一二三四五六七八九十]{1,3}[、.．]", text):
            return True
        return False

    def _is_document_title(text: str) -> bool:
        """判断是否是文档标题或说明"""
        if "本套试题" in text or "说明：" in text:
            return True
        if len(text) > 20 and any(
            text.startswith(prefix) for prefix in ["电子数据", "考试", "测试", "练习", "题库", "声像资料", "司法鉴定"]
        ):
            if re.search(r"[（(]\s*[√×]\s*[）)]$", text):
                return False
            if re.search(r"[（(]\s*[A-D]?\s*[）)]$", text):
                return False
            return True
        return False

    def _is_answer_line(text: str) -> tuple[bool, str]:
        """判断是否是答案行，返回 (是否答案行, 答案内容)"""
        m = re.match(r"^答案[：:]\s*([A-D]{2,})\s*$", text)
        if m:
            return True, m.group(1)
        m = re.match(r"^答案[：:]\s*([A-D])\s*$", text)
        if m:
            return True, m.group(1)
        m = re.match(r"^答案[：:]\s*([√×])\s*$", text)
        if m:
            return True, m.group(1)
        return False, ""

    def _parse_inline_options(line: str) -> List[dict]:
        """解析同一行中的多个选项：A. 选项1 B. 选项2 C. 选项3 D. 选项4"""
        options = []
        parts = re.split(r"(?=[A-D][\.\、．])", line)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            m = re.match(r"([A-D])[\.\、．]\s*(.+)", part)
            if m:
                options.append({"option_label": m.group(1), "option_content": m.group(2).strip(), "is_correct": False})
        return options

    def _parse_judge_answer(text: str) -> tuple[bool, str]:
        m = re.search(r"[（(]\s*([√×])\s*[）)]$", text)
        if m:
            return True, m.group(1)
        return False, ""

    def _strip_judge_answer(text: str) -> str:
        return re.sub(r"\s*[（(]\s*[√×]\s*[）)]\s*$", "", text).strip()

    def _parse_single_choice_answer(text: str) -> tuple[bool, str]:
        m = re.search(r"[（(]\s*([A-D])\s*[）)]$", text)
        if m:
            return True, m.group(1)
        return False, ""

    def _strip_single_choice_answer(text: str) -> str:
        return re.sub(r"\s*[（(]\s*[A-D]\s*[）)]\s*$", "", text).strip()

    def _parse_multiple_choice_answer(text: str) -> tuple[bool, str]:
        m = re.search(r"[（(]\s*([A-D]{2,})\s*[）)]$", text)
        if m:
            return True, m.group(1)
        return False, ""

    def _strip_multiple_choice_answer(text: str) -> str:
        return re.sub(r"\s*[（(]\s*[A-D]{2,}\s*[）)]\s*$", "", text).strip()

    def _detect_question_type_from_text(text: str) -> str:
        if "（多选）" in text or "(多选)" in text:
            return "multiple_choice"
        if "（判断）" in text or "(判断)" in text:
            return "true_false"
        has_judge, _ = _parse_judge_answer(text)
        if has_judge:
            return "true_false"
        has_multi, _ = _parse_multiple_choice_answer(text)
        if has_multi:
            return "multiple_choice"
        return "single_choice"

    def _finalize_question(q: dict, opts_buffer: List[dict]) -> None:
        if not q or not q["content"]:
            return
        if q["question_type"] in ("single_choice", "multiple_choice") and q["answer"] and opts_buffer:
            for opt in opts_buffer:
                opt["is_correct"] = opt["option_label"] in q["answer"].upper()
            q["options"].extend(opts_buffer)
        questions.append(q)

    def _parse_table_questions(doc: Document) -> List[dict]:
        """从表格中解析题目"""
        table_questions = []
        for table in doc.tables:
            if len(table.columns) < 2:
                continue

            header_map = {}
            header_row = None
            for row_idx, row in enumerate(table.rows):
                cells = [cell.text.strip() for cell in row.cells]
                header_keywords = ["题型", "题目", "内容", "选项", "答案", "难度"]
                if any(kw in " ".join(cells) for kw in header_keywords):
                    header_row = row_idx
                    for col_idx, cell_text in enumerate(cells):
                        for kw in header_keywords:
                            if kw in cell_text:
                                header_map[col_idx] = kw
                                break
                    break

            if not header_map:
                continue

            start_row = header_row + 1 if header_row is not None else 0
            for row_idx in range(start_row, len(table.rows)):
                row = table.rows[row_idx]
                cells = [cell.text.strip() for cell in row.cells]
                if not any(cells):
                    continue

                try:
                    question_type = "single_choice"
                    content = ""
                    options = []
                    answer = ""

                    for col_idx, header in header_map.items():
                        if col_idx >= len(cells):
                            continue
                        cell_value = cells[col_idx]
                        if not cell_value:
                            continue

                        if header == "题型":
                            type_map = {
                                "单选": "single_choice",
                                "多选": "multiple_choice",
                                "判断": "true_false",
                                "简答": "essay",
                            }
                            for k, v in type_map.items():
                                if k in cell_value:
                                    question_type = v
                                    break
                        elif header in ["题目", "内容"]:
                            content = cell_value
                        elif header == "选项":
                            opts = _parse_inline_options(cell_value)
                            if opts:
                                options.extend(opts)
                        elif header == "答案":
                            ans_m = re.search(r"[A-D]", cell_value)
                            if ans_m:
                                answer = ans_m.group()
                            elif "√" in cell_value or "正确" in cell_value:
                                answer = "√"
                            elif "×" in cell_value or "错误" in cell_value:
                                answer = "×"

                    if content:
                        q = _create_question(question_type, content)
                        q["answer"] = answer
                        if options and answer:
                            for opt in options:
                                opt["is_correct"] = opt["option_label"] in answer.upper()
                            q["options"] = options
                        table_questions.append(q)
                except Exception:
                    continue

        return table_questions

    # ============ 解析逻辑 ============

    para_list = list(doc.paragraphs)
    total_paras = len(para_list)

    # 先从表格解析题目
    table_questions = _parse_table_questions(doc)
    if table_questions:
        logger.info(f"从表格中解析出 {len(table_questions)} 道题目")
        questions.extend(table_questions)

    current_question = None
    options_buffer: List[dict] = []

    idx = 0
    while idx < total_paras:
        text = para_list[idx].text.strip()
        idx += 1

        if not text:
            continue

        # ===== 跳过非题目内容 =====
        if _is_option_line(text):
            if current_question and current_question["question_type"] in ("single_choice", "multiple_choice"):
                inline_opts = _parse_inline_options(text)
                options_buffer.extend(inline_opts)
            continue

        if _is_chapter_title(text):
            continue

        if _is_document_title(text):
            continue

        # 跳过题目解析/分析内容（如"1、解析A"）
        if re.match(r"^\d+[．、.。]\s*解析", text):
            continue

        # ===== 检查是否是答案行 =====
        is_answer, answer_value = _is_answer_line(text)
        if is_answer:
            if current_question:
                if current_question["question_type"] == "single_choice" and len(answer_value) > 1:
                    current_question["question_type"] = "multiple_choice"
                current_question["answer"] = answer_value
                if options_buffer:
                    for opt in options_buffer:
                        opt["is_correct"] = opt["option_label"] in answer_value.upper()
                    current_question["options"].extend(options_buffer)
                    options_buffer = []
                _finalize_question(current_question, [])
                current_question = None
            continue

        if text.startswith("解析：") or text.startswith("解析:"):
            if current_question:
                current_question["explanation"] = text.replace("解析：", "").replace("解析:", "").strip()
            continue

        if text.startswith("难度：") or text.startswith("难度:"):
            if current_question:
                try:
                    current_question["difficulty"] = int(re.search(r"\d+", text).group())
                except:
                    pass
            continue

        # ===== 格式1：题型标记格式 =====
        if "【单选题】" in text:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = text.replace("【单选题】", "")
            current_question = _create_question("single_choice", content)
            options_buffer = []
            continue

        if "【多选题】" in text:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = text.replace("【多选题】", "")
            current_question = _create_question("multiple_choice", content)
            options_buffer = []
            continue

        if "【判断题】" in text:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = text.replace("【判断题】", "")
            current_question = _create_question("true_false", content)
            options_buffer = []
            continue

        if "【简答题】" in text:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = text.replace("【简答题】", "")
            current_question = _create_question("essay", content)
            options_buffer = []
            continue

        # ===== 格式3：【编号】格式 =====
        m = re.match(r"^【(\d+)】\s*(.+)$", text)
        if m:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = m.group(2)
            question_type = _detect_question_type_from_text(content)
            current_question = _create_question(question_type, content)
            options_buffer = []
            continue

        # ===== 格式3变体：中文数字序号 =====
        m = re.match(r"^([一二三四五六七八九十]+)[、.．]\s*(.+)$", text)
        if m:
            potential_content = m.group(2)
            if potential_content.endswith("（）") or len(potential_content) >= 15:
                if current_question:
                    _finalize_question(current_question, options_buffer)
                question_type = _detect_question_type_from_text(potential_content)
                current_question = _create_question(question_type, potential_content)
                options_buffer = []
            continue

        # ===== 格式2：编号题目格式 =====
        m = re.match(r"^(\d+)[．、.。]?\s*(.+)$", text)
        if m:
            if current_question:
                _finalize_question(current_question, options_buffer)
            content = m.group(2)
            question_type = _detect_question_type_from_text(content)

            has_judge, judge_answer = _parse_judge_answer(content)
            if has_judge:
                content = _strip_judge_answer(content)
                current_question = _create_question("true_false", content)
                current_question["answer"] = judge_answer
                questions.append(current_question)
                current_question = None
                options_buffer = []
                continue

            has_single, single_answer = _parse_single_choice_answer(content)
            if has_single:
                content = _strip_single_choice_answer(content)
                current_question = _create_question("single_choice", content)
                current_question["answer"] = single_answer
                options_buffer = []
                continue

            has_multi, multi_answer = _parse_multiple_choice_answer(content)
            if has_multi:
                content = _strip_multiple_choice_answer(content)
                current_question = _create_question("multiple_choice", content)
                current_question["answer"] = multi_answer
                options_buffer = []
                continue

            if idx < total_paras:
                next_text = para_list[idx].text.strip()
                is_ans, ans_val = _is_answer_line(next_text)
                if is_ans and len(ans_val) > 1:
                    question_type = "multiple_choice"

            current_question = _create_question(question_type, content)
            options_buffer = []
            continue

        # ===== 无标记题目格式：题目内容以（）结尾 =====
        if not current_question:
            if re.search(r"[（(].*[）)]$", text):
                question_type = _detect_question_type_from_text(text)

                has_judge, judge_answer = _parse_judge_answer(text)
                if has_judge:
                    content = _strip_judge_answer(text)
                    current_question = _create_question("true_false", content)
                    current_question["answer"] = judge_answer
                    questions.append(current_question)
                    current_question = None
                else:
                    has_multi, multi_answer = _parse_multiple_choice_answer(text)
                    if has_multi:
                        content = _strip_multiple_choice_answer(text)
                        current_question = _create_question(question_type, content)
                        current_question["answer"] = multi_answer
                    else:
                        current_question = _create_question(question_type, text)
                    options_buffer = []
                continue

            if len(text) >= 15:
                question_type = _detect_question_type_from_text(text)
                current_question = _create_question(question_type, text)
                options_buffer = []
                continue

            continue

        # ===== 有当前题目时：处理内容延续 =====
        if len(text) >= 15 or re.search(r"[（(].*[）)]$", text):
            if current_question.get("answer") and options_buffer:
                for opt in options_buffer:
                    opt["is_correct"] = opt["option_label"] in current_question["answer"].upper()
                current_question["options"].extend(options_buffer)
                options_buffer = []
            if current_question["content"] and current_question.get("answer"):
                _finalize_question(current_question, [])
                current_question = None
            else:
                current_question["content"] += " " + text
                continue

            idx -= 1
            continue

        if not text.startswith("A.") and not text.startswith("A、"):
            current_question["content"] += " " + text

    # 处理最后一道题目
    if current_question and current_question["content"]:
        if current_question.get("answer") and options_buffer:
            for opt in options_buffer:
                opt["is_correct"] = opt["option_label"] in current_question["answer"].upper()
            current_question["options"].extend(options_buffer)
        _finalize_question(current_question, [])

    logger.info(f"Word解析完成，共解析出 {len(questions)} 道题目")
    return questions


# ============ Export Generation Helpers ============


def _safe_cell_value(value) -> str:
    """评估 P1-13：防 Excel 公式注入——以 = + - @ 开头的内容强制按文本写入。

    openpyxl 会把以 '=' 开头的字符串当作公式，导出的 xlsx 被打开即执行。
    """
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _generate_excel(questions: List[Question]):
    """生成 Excel 文件"""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "题目列表"

    headers = ["序号", "题型", "难度", "题目内容", "选项A", "选项B", "选项C", "选项D", "正确答案", "解析"]
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, q in enumerate(questions, 2):
        ws.cell(row=row_idx, column=2, value=_get_type_name(q.question_type))
        ws.cell(row=row_idx, column=3, value=_get_difficulty_name(q.difficulty))
        ws.cell(row=row_idx, column=4, value=_safe_cell_value(q.content))
        ws.cell(row=row_idx, column=4).alignment = Alignment(wrap_text=True)

        options = sorted(q.options, key=lambda x: x.order) if q.options else []
        option_labels = ["A", "B", "C", "D"]
        for opt_idx, opt in enumerate(options[:4]):
            ws.cell(
                row=row_idx,
                column=5 + opt_idx,
                value=_safe_cell_value(f"{opt.option_label}. {opt.option_content}"),
            )

        ws.cell(row=row_idx, column=9, value=_safe_cell_value(_format_answer(q.answer, q.options, q.question_type)))
        ws.cell(row=row_idx, column=10, value=_safe_cell_value(q.explanation or ""))
        ws.cell(row=row_idx, column=10).alignment = Alignment(wrap_text=True)

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 40
    ws.column_dimensions["E"].width = 25
    ws.column_dimensions["F"].width = 25
    ws.column_dimensions["G"].width = 25
    ws.column_dimensions["H"].width = 25
    ws.column_dimensions["I"].width = 10
    ws.column_dimensions["J"].width = 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"questions_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    return output.getvalue(), filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _generate_word(questions: List[Question]):
    """生成 Word 文件"""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    title = doc.add_heading("题目列表", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    stats_para = doc.add_paragraph()
    stats_para.add_run(f"总题数：{len(questions)}").bold = True
    stats_para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph()

    questions_by_type = {}
    for q in questions:
        qtype = q.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(q)

    type_order = ["single_choice", "multiple_choice", "true_false", "essay"]
    type_names = {
        "single_choice": "一、单项选择题",
        "multiple_choice": "二、多项选择题",
        "true_false": "三、判断题",
        "essay": "四、简答题",
    }

    q_index = 1
    for qtype in type_order:
        if qtype not in questions_by_type:
            continue

        qs = questions_by_type[qtype]
        if not qs:
            continue

        section_title = doc.add_paragraph()
        section_title.add_run(type_names.get(qtype, qtype)).bold = True
        section_title.add_run(f"（共 {len(qs)} 题）")

        for q in qs:
            q_para = doc.add_paragraph()
            q_para.add_run(f"{q_index}. ").bold = True
            q_para.add_run(f"【{_get_type_name(q.question_type)}】")
            q_para.add_run(f"（{_get_difficulty_name(q.difficulty)}）")
            q_para.add_run(f" {q.content}")

            if q.question_type in ("single_choice", "multiple_choice"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                for opt in options:
                    opt_para = doc.add_paragraph(style="List Bullet")
                    opt_para.add_run(f"{opt.option_label}. {opt.option_content}")

            if q.answer:
                ans_para = doc.add_paragraph()
                ans_para.add_run(f"答案：{_format_answer(q.answer, q.options, q.question_type)}").italic = True

            if q.explanation:
                exp_para = doc.add_paragraph()
                exp_para.add_run(f"解析：{q.explanation}").italic = True

            doc.add_paragraph()
            q_index += 1

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)

    filename = f"questions_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    return output.getvalue(), filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _register_chinese_font() -> str | None:
    """评估 P2-16：中文字体路径配置化 + 多平台候选探测。

    原实现硬编码 Windows 路径 `C:/Windows/Fonts/simsun.ttc`，
    在 Linux 部署时导出 PDF 中文会回退 Helvetica（乱码/方块）。
    优先使用 settings.pdf_font_path，其次探测常见系统字体。
    返回注册后的字体内部名，找不到返回 None。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = []
    configured = getattr(settings, "pdf_font_path", "") or ""
    if configured:
        candidates.append(configured)
    candidates.extend(
        [
            "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux 文泉驿微米黑
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto CJK
            "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", path))
                return "ChineseFont"
            except Exception:
                continue
    return None


def _generate_pdf(questions: List[Question]):
    """生成 PDF 文件"""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    chinese_font = _register_chinese_font() or "Helvetica"

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Heading1"],
        fontName=chinese_font,
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=10,
    )

    info_style = ParagraphStyle(
        "ChineseInfo",
        parent=styles["Normal"],
        fontName=chinese_font,
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=5,
    )

    section_style = ParagraphStyle(
        "ChineseSection",
        parent=styles["Normal"],
        fontName=chinese_font,
        fontSize=12,
        spaceBefore=10,
        spaceAfter=5,
    )

    question_style = ParagraphStyle(
        "ChineseQuestion",
        parent=styles["Normal"],
        fontName=chinese_font,
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )

    option_style = ParagraphStyle(
        "ChineseOption",
        parent=styles["Normal"],
        fontName=chinese_font,
        fontSize=9,
        leading=12,
        leftIndent=15,
        spaceAfter=2,
    )

    answer_style = ParagraphStyle(
        "ChineseAnswer",
        parent=styles["Normal"],
        fontName=chinese_font,
        fontSize=9,
        textColor=colors.blue,
        leftIndent=15,
        spaceAfter=2,
    )

    story = []

    story.append(Paragraph("题目列表", title_style))
    story.append(Paragraph(f"总题数：{len(questions)}", info_style))
    story.append(Spacer(1, 15))

    questions_by_type = {}
    for q in questions:
        qtype = q.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(q)

    type_order = ["single_choice", "multiple_choice", "true_false", "essay"]
    type_names = {
        "single_choice": "一、单项选择题",
        "multiple_choice": "二、多项选择题",
        "true_false": "三、判断题",
        "essay": "四、简答题",
    }

    q_index = 1
    for qtype in type_order:
        if qtype not in questions_by_type:
            continue

        qs = questions_by_type[qtype]
        if not qs:
            continue

        story.append(Paragraph(f"{type_names.get(qtype, qtype)}（共 {len(qs)} 题）", section_style))

        for q in qs:
            q_text = (
                f"{q_index}. 【{_get_type_name(q.question_type)}】（{_get_difficulty_name(q.difficulty)}） {q.content}"
            )
            story.append(Paragraph(q_text, question_style))

            if q.question_type in ("single_choice", "multiple_choice"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                for opt in options:
                    story.append(Paragraph(f"{opt.option_label}. {opt.option_content}", option_style))

            if q.answer:
                story.append(Paragraph(f"答案：{_format_answer(q.answer, q.options, q.question_type)}", answer_style))

            if q.explanation:
                explanation_style = ParagraphStyle(
                    "ChineseExplanation",
                    parent=styles["Normal"],
                    fontName=chinese_font,
                    fontSize=9,
                    textColor=colors.grey,
                    leftIndent=15,
                    spaceAfter=2,
                )
                story.append(Paragraph(f"解析：{q.explanation}", explanation_style))

            story.append(Spacer(1, 5))
            q_index += 1

    doc.build(story)
    output.seek(0)

    filename = f"questions_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return output.getvalue(), filename, "application/pdf"


# ============ Export Endpoint ============


@router.get("/export")
def export_questions(
    subject_id: int | None = None,
    question_type: str | None = None,
    difficulty: int | None = None,
    question_ids: str | None = Query(None, description="逗号分隔的题目ID列表，如: 1,2,3"),
    format: str = Query("excel", pattern="^(excel|word|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """导出题目"""
    query = db.query(Question).options(joinedload(Question.options))

    if question_ids:
        ids = [int(x.strip()) for x in question_ids.split(",") if x.strip().isdigit()]
        if ids:
            query = query.filter(Question.id.in_(ids))
    else:
        if subject_id is not None:
            query = query.filter(Question.subject_id == subject_id)
        if question_type is not None:
            query = query.filter(Question.question_type == question_type)
        if difficulty is not None:
            query = query.filter(Question.difficulty == difficulty)

    questions = query.all()

    if not questions:
        raise HTTPException(status_code=404, detail="没有找到符合条件的题目")

    if format == "excel":
        file_content, filename, media_type = _generate_excel(questions)
    elif format == "word":
        file_content, filename, media_type = _generate_word(questions)
    else:
        file_content, filename, media_type = _generate_pdf(questions)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        "Access-Control-Allow-Origin": "*",
    }

    return StreamingResponse(iter([file_content]), media_type=media_type, headers=headers)


# ============ Preview Endpoint ============


@router.post("/preview")
async def preview_import(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """预览导入文件，解析并返回题型统计（不实际导入）"""
    form_data = await request.form()
    file = form_data.get("file")
    format = form_data.get("format")

    if not file:
        raise HTTPException(status_code=400, detail="请上传文件")

    if hasattr(file, "read"):
        file_content = await file.read()
    else:
        file_content = file

    try:
        detected_format = format
        if not detected_format:
            detected_format, validation_error = _detect_file_format(file_content)
            if validation_error:
                raise HTTPException(status_code=400, detail=validation_error)
            if not detected_format:
                raise HTTPException(
                    status_code=400, detail="无法识别文件格式，请确保文件为 .xlsx/.xls 或 .docx/.doc 格式"
                )

        if detected_format == "excel":
            questions_data = _parse_excel_questions(file_content)
        elif detected_format == "word":
            questions_data = _parse_word_questions(file_content)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {detected_format}")

        if not questions_data:
            return PreviewResult(total=0, errors=["未能从文件中解析出任何题目"])

        stats = {"single_choice": 0, "multiple_choice": 0, "true_false": 0, "essay": 0}
        for q in questions_data:
            qtype = q.get("question_type", "single_choice")
            if qtype in stats:
                stats[qtype] += 1
            else:
                stats["single_choice"] += 1

        seen_contents = set()
        internal_duplicate_count = 0
        unique_questions = []
        for q in questions_data:
            key = (q["content"], q.get("question_type", "single_choice"))
            if key in seen_contents:
                internal_duplicate_count += 1
            else:
                seen_contents.add(key)
                unique_questions.append(q)

        duplicate_count = 0
        for q in unique_questions:
            existing = (
                db.query(Question)
                .filter(
                    Question.content == q["content"], Question.question_type == q.get("question_type", "single_choice")
                )
                .first()
            )
            if existing:
                duplicate_count += 1

        unique_count = len(unique_questions) - duplicate_count

        return PreviewResult(
            total=len(questions_data),
            single_choice=stats["single_choice"],
            multiple_choice=stats["multiple_choice"],
            true_false=stats["true_false"],
            essay=stats["essay"],
            duplicate_count=duplicate_count,
            internal_duplicate_count=internal_duplicate_count,
            unique_count=unique_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览解析失败: {e}")
        raise HTTPException(status_code=500, detail="预览解析失败，请检查文件格式")


# ============ Import Endpoint ============


@router.post("/import", response_model=ImportResult)
async def import_questions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """批量导入题目（Excel 或 Word 格式，导入后需审核才能使用）

    Excel 格式要求：
    - 第一行为表头，包含：题型、题目内容、正确答案、难度、分值、所属科目ID、所属章节ID
    - 题型：单选题、多选题、判断题、简答题
    - 选择题选项格式：A. 选项1; B. 选项2; C. 选项3; D. 选项4

    Word 格式要求：
    - 每道题以【题型】开头，如【单选题】
    - 答案格式：答案：X
    - 选项格式：A. 选项内容
    """
    form_data = await request.form()
    file = form_data.get("file")
    format = form_data.get("format")
    subject_id = form_data.get("subject_id")
    chapter_id = form_data.get("chapter_id")

    if not file:
        raise HTTPException(status_code=400, detail="请上传文件")

    # 评估 P1-13：文件大小上限（防 zip bomb / 超大文件内存 DoS）
    MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10MB
    file_size = getattr(file, "size", None)
    if file_size and file_size > MAX_IMPORT_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，最大支持 10MB")

    if hasattr(file, "read"):
        file_content = await file.read()
        if len(file_content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大支持 10MB")
    else:
        file_content = file
        if len(file_content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大支持 10MB")

    subject_id_int = int(subject_id) if subject_id else None
    chapter_id_int = int(chapter_id) if chapter_id else None

    try:
        detected_format = format
        if not detected_format:
            detected_format, validation_error = _detect_file_format(file_content)
            if validation_error:
                raise HTTPException(status_code=400, detail=validation_error)
            if not detected_format:
                raise HTTPException(
                    status_code=400, detail="无法识别文件格式，请确保文件为 .xlsx/.xls 或 .docx/.doc 格式"
                )

        logger.info(f"导入文件格式: {detected_format}")

        if detected_format == "excel":
            questions_data = _parse_excel_questions(file_content)
        elif detected_format == "word":
            questions_data = _parse_word_questions(file_content)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {detected_format}")

        if not questions_data:
            return ImportResult(success_count=0, fail_count=0, errors=["未能从文件中解析出任何题目"])

        seen_contents = set()
        unique_questions = []
        for q in questions_data:
            key = (q["content"], q.get("question_type", "single_choice"))
            if key not in seen_contents:
                seen_contents.add(key)
                unique_questions.append(q)
        logger.info(f"导入题目去重：原始{len(questions_data)}道，去重后{len(unique_questions)}道")

        success_count = 0
        fail_count = 0
        errors = []

        for idx, qdata in enumerate(unique_questions):
            try:
                existing = (
                    db.query(Question)
                    .filter(
                        Question.content == qdata["content"],
                        Question.question_type == qdata.get("question_type", "single_choice"),
                    )
                    .first()
                )
                if existing:
                    continue

                question = Question(
                    chapter_id=qdata.get("chapter_id") or chapter_id_int or 1,
                    subject_id=qdata.get("subject_id") or subject_id_int or 1,
                    question_type=qdata.get("question_type", "single_choice"),
                    content=qdata["content"],
                    answer=qdata.get("answer", ""),
                    explanation=qdata.get("explanation"),
                    difficulty=qdata.get("difficulty", 1),
                    score=qdata.get("score", 5.0),
                    is_public=False,
                    tags=qdata.get("tags"),
                    status=1,
                    source="import",
                    audit_status="pending",
                    created_by=current_user.id,
                )
                db.add(question)
                db.flush()

                if qdata.get("options"):
                    for opt in qdata["options"]:
                        option = QuestionOption(
                            question_id=question.id,
                            option_label=opt["option_label"],
                            option_content=opt["option_content"],
                            is_correct=opt.get("is_correct", False),
                            order=ord(opt["option_label"]) - ord("A"),
                        )
                        db.add(option)

                success_count += 1
            except Exception as e:
                fail_count += 1
                errors.append(f"第 {idx + 1} 题导入失败: {e!s}")
                logger.warning(f"导入题目失败: {e}")

        db.commit()

        return ImportResult(success_count=success_count, fail_count=fail_count, errors=errors[:50])

    except ValueError as e:
        logger.warning(f"导入题目参数错误: {e}")
        raise HTTPException(status_code=400, detail="导入参数不正确，请检查文件格式")
    except Exception as e:
        logger.error(f"导入题目失败: {e}")
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")
