"""
Paper Generator Service

Provides automatic exam paper generation functionality with support for
question type and difficulty distribution.
"""

import random
from typing import Any

from sqlalchemy import and_, select

from app.database import Question, async_session_maker


class InsufficientQuestionsError(Exception):
    """Raised when there are not enough questions to generate a paper."""

    def __init__(self, message: str, required: int, available: int):
        super().__init__(message)
        self.required = required
        self.available = available


async def auto_generate_paper(
    subject_id: int,
    question_count: int,
    type_distribution: dict,
    difficulty_distribution: dict,
    chapter_ids: list[int] | None = None,
    total_score: int = 100,
) -> dict[str, Any]:
    """
    Auto-generate an exam paper with questions distributed by type and difficulty.

    Args:
        subject_id: ID of the subject to generate paper for.
        question_count: Total number of questions in the paper.
        type_distribution: Dict mapping question_type -> proportion (e.g., {"single_choice": 0.4}).
        difficulty_distribution: Dict mapping difficulty (1-5) -> proportion (e.g., {1: 0.2, 2: 0.3}).
        chapter_ids: Optional list of chapter IDs to filter questions from.
        total_score: Total score for the paper (default 100).

    Returns:
        Dict with paper structure:
        {
            "questions": [{"question_id", "order", "score", "question_detail"}, ...],
            "total_score": int,
            "question_count": int
        }

    Raises:
        InsufficientQuestionsError: When there are not enough questions to meet distribution requirements.
    """
    async with async_session_maker() as session:
        # Step 1: Build query to filter questions
        conditions = [Question.subject_id == subject_id]

        if chapter_ids:
            conditions.append(Question.chapter_id.in_(chapter_ids))

        # Get all questions that match the filters
        stmt = select(Question).where(and_(*conditions))
        result = await session.execute(stmt)
        all_questions = result.scalars().all()

        if not all_questions:
            raise InsufficientQuestionsError(
                f"No questions found for subject_id={subject_id}",
                required=question_count,
                available=0,
            )

        # Step 2: Group available questions by (difficulty, question_type)
        grouped: dict[tuple[int, str], list[Question]] = {}
        for q in all_questions:
            key = (q.difficulty, q.question_type)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(q)

        # Step 3: Calculate required count per (type, difficulty) combo
        required_counts: dict[tuple[int, str], int] = {}
        for q_type, type_ratio in type_distribution.items():
            type_count = max(1, int(question_count * type_ratio))
            for difficulty, diff_ratio in difficulty_distribution.items():
                diff_count = max(1, int(type_count * diff_ratio))
                key = (difficulty, q_type)
                required_counts[key] = required_counts.get(key, 0) + diff_count

        # Normalize to match question_count
        total_required = sum(required_counts.values())
        if total_required > question_count:
            scale = question_count / total_required
            for key in required_counts:
                required_counts[key] = max(1, int(required_counts[key] * scale))

        # Step 4 & 5: Select questions randomly and track duplicates
        selected_questions: list[Question] = []
        selected_ids: set[int] = set()

        for (difficulty, q_type), needed in sorted(required_counts.items(), key=lambda x: -x[0][0]):
            pool = [q for q in grouped.get((difficulty, q_type), []) if q.id not in selected_ids]

            if len(pool) < needed:
                raise InsufficientQuestionsError(
                    f"Insufficient questions for (difficulty={difficulty}, type={q_type}): "
                    f"required={needed}, available={len(pool)}",
                    required=needed,
                    available=len(pool),
                )

            sampled = random.sample(pool, needed)
            selected_questions.extend(sampled)
            selected_ids.update(q.id for q in sampled)

        # Adjust if we selected more or fewer than requested
        if len(selected_questions) > question_count:
            selected_questions = selected_questions[:question_count]
        elif len(selected_questions) < question_count:
            remaining_pool = [q for q in all_questions if q.id not in selected_ids]
            needed_extra = question_count - len(selected_questions)
            if len(remaining_pool) < needed_extra:
                raise InsufficientQuestionsError(
                    f"Cannot reach question_count={question_count}: "
                    f"only {len(selected_questions) + len(remaining_pool)} available",
                    required=question_count,
                    available=len(selected_questions) + len(remaining_pool),
                )
            extra = random.sample(remaining_pool, needed_extra)
            selected_questions.extend(extra)
            selected_ids.update(q.id for q in extra)

        # Step 6: Calculate per-question score and build result
        per_question_score = total_score / question_count

        questions_output = []
        for order, question in enumerate(selected_questions, start=1):
            # Build question detail from question and its options
            options_detail = []
            if question.options:
                for opt in sorted(question.options, key=lambda o: o.order or 0):
                    options_detail.append(
                        {
                            "option_label": opt.option_label,
                            "option_content": opt.option_content,
                            "is_correct": opt.is_correct,
                        }
                    )

            question_detail = {
                "content": question.content,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "answer": question.answer,
                "explanation": question.explanation,
                "options": options_detail,
            }

            questions_output.append(
                {
                    "question_id": question.id,
                    "order": order,
                    "score": per_question_score,
                    "question_detail": question_detail,
                }
            )

        return {
            "questions": questions_output,
            "total_score": total_score,
            "question_count": len(questions_output),
        }
