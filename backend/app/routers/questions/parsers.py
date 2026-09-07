"""Questions Import Parsers - Parse questions from Excel/Word files"""

import io
import logging
import re
from typing import List

from app.routers.questions.utils import (
    _detect_file_format,
    _validate_excel_content,
    _validate_word_content,
)

logger = logging.getLogger(__name__)


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
    from docx import Document

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
