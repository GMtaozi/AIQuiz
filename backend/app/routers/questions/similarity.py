"""Question Similarity Detection Router"""

from collections import Counter
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import Question
from app.models.user import User
from app.schemas.question import QuestionDetailResponse, QuestionSimilarityResponse, SimilarQuestionResponse
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# 评估 P2-16：两两比较为 O(n²)，限制单次检查的题目数上限，防止大题库内存/CPU 爆炸
MAX_QUESTIONS_TO_CHECK = 2000


def _compute_text_similarity(text_a: str, text_b: str) -> float:
    """计算两个文本的相似度（0-1）

    评估 P2-16：原实现 `sum(1 for c in text_a if c in text_b)` 为 O(len²) 字符查找，
    改用 Counter 交集（O(len_a + len_b)）。
    """
    if not text_a or not text_b:
        return 0.0

    text_a = text_a.strip().lower()
    text_b = text_b.strip().lower()

    # 计算共有字符比例（Counter 交集）
    counter_a = Counter(text_a)
    counter_b = Counter(text_b)
    common_chars = sum((counter_a & counter_b).values())
    max_len = max(len(text_a), len(text_b))
    if max_len == 0:
        return 0.0
    char_similarity = common_chars / max_len

    # 计算共有词比例
    words_a = set(text_a.split())
    words_b = set(text_b.split())
    if words_a and words_b:
        word_overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    else:
        word_overlap = 0.0

    # 综合相似度（字符40% + 词60%）
    return round((char_similarity * 0.4 + word_overlap * 0.6), 3)


@router.get("/similarity-check", response_model=QuestionSimilarityResponse)
def check_question_similarity(
    subject_id: int | None = Query(None, description="限定科目"),
    chapter_id: int | None = Query(None, description="限定章节"),
    question_type: str | None = Query(None, description="限定题型"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="相似度阈值"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查题库中是否存在相似/重复题目

    基于以下维度判断相似度：
    1. 知识点/章节重叠度
    2. 题型一致性
    3. 内容文本相似度
    """
    # 构建查询
    query = db.query(Question).filter(Question.status == 1, Question.audit_status == "approved")
    if subject_id is not None:
        query = query.filter(Question.subject_id == subject_id)
    if chapter_id is not None:
        query = query.filter(Question.chapter_id == chapter_id)
    if question_type is not None:
        query = query.filter(Question.question_type == question_type)

    questions = query.limit(MAX_QUESTIONS_TO_CHECK).all()

    if len(questions) < 2:
        return QuestionSimilarityResponse(
            total_checked=len(questions),
            similar_pairs_count=0,
            similar_pairs=[],
            message="题目数量不足，无需检测"
        )

    # 两两比较（O(n²) 受 MAX_QUESTIONS_TO_CHECK 约束）
    similar_pairs = []
    total_checked = len(questions)
    truncated = len(questions) >= MAX_QUESTIONS_TO_CHECK

    for i in range(total_checked):
        for j in range(i + 1, total_checked):
            q_a = questions[i]
            q_b = questions[j]

            # 题型必须相同
            if q_a.question_type != q_b.question_type:
                continue

            # 计算章节重叠度
            chapter_overlap = 1.0 if q_a.chapter_id == q_b.chapter_id else 0.0

            # 计算内容相似度
            content_similarity = _compute_text_similarity(q_a.content, q_b.content)

            # 综合相似度（章节50% + 内容50%）
            overall_similarity = round(chapter_overlap * 0.5 + content_similarity * 0.5, 3)

            if overall_similarity >= threshold:
                similar_pairs.append(SimilarQuestionResponse(
                    question_a_id=q_a.id,
                    question_a_content=q_a.content[:200],
                    question_b_id=q_b.id,
                    question_b_content=q_b.content[:200],
                    question_type=q_a.question_type,
                    similarity_score=overall_similarity,
                    similarity_reason=f"章节{'相同' if chapter_overlap > 0 else '不同'}；内容相似度{content_similarity:.1%}"
                ))

    # 按相似度降序排序
    similar_pairs.sort(key=lambda x: x.similarity_score, reverse=True)

    message = None
    if not similar_pairs:
        message = f"未发现相似度超过 {threshold} 的题目对，题库质量良好"
    elif truncated:
        message = f"题库题目过多，本次仅检查前 {MAX_QUESTIONS_TO_CHECK} 题"

    return QuestionSimilarityResponse(
        total_checked=total_checked,
        similar_pairs_count=len(similar_pairs),
        similar_pairs=similar_pairs,
        message=message
    )
