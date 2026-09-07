"""Questions Import Router - Parse, preview, and import questions from Excel/Word"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import Question, QuestionOption
from app.models.user import User
from app.routers.questions.parsers import _parse_excel_questions, _parse_word_questions
from app.routers.questions.utils import _detect_file_format
from app.schemas.question import ImportResult, PreviewResult
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)

router = APIRouter()


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
            # 评估 P0：每道题用 SAVEPOINT（begin_nested）独立包裹。
            # 单题失败时仅回滚该题对应的 SAVEPOINT，已成功题目保留（部分成功语义），
            # 失败原因记录进 errors；外层事务在循环结束后统一 commit。
            try:
                with db.begin_nested():
                    existing = (
                        db.query(Question)
                        .filter(
                            Question.content == qdata["content"],
                            Question.question_type == qdata.get("question_type", "single_choice"),
                        )
                        .first()
                    )
                    if existing:
                        # 重复题目：不算失败，直接跳过（SAVEPOINT 正常释放）
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

                        db.flush()

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
