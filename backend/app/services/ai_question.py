"""AI Question Generation Service - 使用统一AI服务层"""
import asyncio
import json
import logging
import re
from typing import List, Optional
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)


def _sanitize_for_prompt(value: str) -> str:
    """Sanitize user input to prevent prompt injection attacks.

    Removes potentially dangerous characters that could manipulate
    the AI's behavior or leak context.
    """
    if not value:
        return ""
    # Remove common injection patterns
    dangerous_patterns = [
        r'```[\s\S]*?```',  # Code blocks
        r'\$\{.*?\}',      # Template variables
        r'{{.*?}}',        # Mustache templates
        r'<script.*?/script>',  # HTML script tags
        r'javascript:',    # JS protocol
        r'on\w+\s*=',     # Event handlers
    ]
    result = str(value)
    for pattern in dangerous_patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    # Escape double quotes and backslashes
    result = result.replace('\\', '\\\\').replace('"', '\\"')
    # Truncate to reasonable length
    return result[:500] if len(result) > 500 else result


async def _call_ai_with_retry(
    prompt: str,
    model: str = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    max_retries: int = 2
) -> Optional[str]:
    """使用统一AI服务层调用AI API，支持重试"""
    backoff = 2.0
    max_backoff = 8.0

    for attempt in range(max_retries):
        try:
            provider = get_ai_provider()
            t0 = asyncio.get_event_loop().time()
            result = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=max_tokens,
                temperature=temperature
            )
            elapsed = asyncio.get_event_loop().time() - t0

            if result is not None:
                logger.info(f"AI API: attempt {attempt+1} 成功, 耗时 {elapsed:.1f}s, "
                           f"prompt_len={len(prompt)}, response_len={len(result)}")
                return result
            else:
                logger.warning(f"AI API: attempt {attempt+1} 返回为空, 耗时 {elapsed:.1f}s")

        except Exception as e:
            logger.warning(f"AI API: attempt {attempt+1} 失败: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    logger.warning("AI API: 所有重试均失败")
    return None


def build_question_generation_prompt(
    subject_name: str,
    chapter_names: List[str],
    question_type: str,
    difficulty: int,
    count: int,
    knowledge_content: str = "",
) -> str:
    """Build a prompt for generating questions with sanitized inputs."""
    difficulty_label = {1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难"}.get(difficulty, "中等")

    type_map = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "essay": "问答题",
    }
    type_label = type_map.get(question_type, question_type)

    # Sanitize user inputs to prevent prompt injection
    safe_subject_name = _sanitize_for_prompt(subject_name)
    safe_chapter_names = [_sanitize_for_prompt(c) for c in (chapter_names or [])]
    chapters_str = "、".join(safe_chapter_names) if safe_chapter_names else "全章节"
    safe_count = min(max(1, count), 50)  # Clamp count between 1 and 50

    # 构建知识点内容区域
    knowledge_section = ""
    if knowledge_content:
        # 截断过长的知识点内容，保留前6000字符（分组后通常不超4000）
        safe_content = knowledge_content[:6000] if len(knowledge_content) > 6000 else knowledge_content
        knowledge_section = f'''
知识点参考内容：
---
{safe_content}
---

请严格按照上述知识点参考内容来出题，题目必须围绕这些知识点展开，确保题目内容与知识点直接相关。不要凭空编造不在知识点范围内的题目。
'''

    prompt = f'''你是一个专业的试题生成助手。请根据以下要求生成{safe_count}道题目。

科目："{safe_subject_name}"
章节："{chapters_str}"
题型：{type_label}
难度：{difficulty_label}（1-5级）
{knowledge_section}
要求：
1. 每道题目必须包含：题目内容、正确答案、详细解析
2. 选择题必须提供4个选项（A/B/C/D），并标明正确答案
3. 判断题只需提供题目内容和正确答案（正确/错误）
4. 问答题只需提供题目内容和详细答案要点
5. 难度{difficulty}表示{difficulty_label}，请确保题目难度适中
6. 题目应覆盖不同知识点，避免重复考查同一知识点
7. 解析应引用具体知识点内容，帮助考生理解
8. 返回JSON数组格式，每道题目包含以下字段：
   - question_type: 题型
   - content: 题目内容
   - answer: 正确答案（选择题为选项标签如"A"，判断题为"true"/"false"，问答为答案要点）
   - explanation: 详细解析
   - difficulty: 难度等级（{difficulty}）
   - options: 数组，仅选择题有此字段，每个选项包含option_label(A/B/C/D)和option_content

请直接返回JSON数组，不要包含任何其他文字。'''
    return prompt


def _try_parse_questions_json(text: str) -> Optional[List[dict]]:
    """Try to parse questions JSON from AI response, with fallback for truncated output."""
    text = text.strip()

    # Handle markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array from text (model may add extra text)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Try to fix truncated JSON: find last complete object and close the array
    # Pattern: find the last "}" before the truncation point
    last_brace = text.rfind('}')
    if last_brace > 0:
        truncated = text[:last_brace + 1] + ']'
        try:
            data = json.loads(truncated)
            if isinstance(data, list) and len(data) > 0:
                logger.warning(f"Recovered truncated JSON: got {len(data)} questions")
                return data
        except json.JSONDecodeError:
            pass

    return None


async def _verify_questions(
    questions: List[dict],
    knowledge_content: str,
    question_type: str,
) -> List[dict]:
    """Verify generated questions against knowledge source.

    Checks each question for:
    - Answer can be derived from knowledge content
    - Options are relevant and non-contradictory
    - Question is complete (not truncated)
    - No self-contradictions

    Returns only questions that pass verification.
    """
    if not questions or not knowledge_content:
        return questions

    type_name_map = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "essay": "问答题",
    }
    type_label = type_name_map.get(question_type, question_type)

    # 构建校验 prompt
    questions_json = json.dumps(questions, ensure_ascii=False, indent=2)

    verify_prompt = f"""你是一个专业的试题质量审核员。请审核以下{type_label}题目，验证它们是否可以从给定的知识点内容中正确推导。

题型：{type_label}

知识点内容：
---
{knowledge_content[:3000]}
---

待审核的题目（JSON格式）：
{questions_json}

审核标准：
1. 选择题：正确答案必须能从知识点内容直接推导，干扰选项不能与知识点矛盾
2. 判断题：题目必须完整（不是残缺的句子），答案必须明确
3. 问答题：答案要点必须能从知识点内容中找到
4. 所有题目：不能有答非所问、选项与题干无关、内容残缺（含"..."）等问题

请对每道题目进行审核，返回JSON数组格式：
[{{
  "original_index": 0,  // 原始题目索引
  "valid": true/false,  // 是否有效
  "reason": "通过/无效原因"  // 简要说明
}}]

只返回JSON数组，不要包含其他文字。"""

    try:
        provider = get_ai_provider()
        result_text = await provider.chat(
            messages=[{"role": "user", "content": verify_prompt}],
            max_tokens=4096,
            temperature=0.3,
        )

        if not result_text:
            logger.warning("题目校验：AI未返回结果，跳过校验")
            return questions

        # 解析校验结果
        verified_data = None
        try:
            # 尝试直接解析
            verified_data = json.loads(result_text.strip())
        except json.JSONDecodeError:
            # 尝试从文本中提取JSON
            match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if match:
                try:
                    verified_data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if not verified_data or not isinstance(verified_data, list):
            logger.warning("题目校验：解析校验结果失败，跳过校验")
            return questions

        # 过滤无效题目
        valid_questions = []
        invalid_count = 0
        for item in verified_data:
            idx = item.get("original_index", -1)
            if item.get("valid", True) and 0 <= idx < len(questions):
                valid_questions.append(questions[idx])
            else:
                invalid_count += 1
                reason = item.get("reason", "未知原因")
                logger.info(f"题目校验：第{idx}题无效 - {reason}")

        if invalid_count > 0:
            logger.info(f"题目校验完成：{len(valid_questions)}/{len(questions)} 题通过，{invalid_count} 题被剔除")

        return valid_questions

    except Exception as e:
        logger.error(f"题目校验异常：{str(e)}，跳过校验")
        return questions


async def generate_questions(
    subject_id: int,
    subject_name: str,
    chapter_ids: List[int],
    chapter_names: List[str],
    question_type: str,
    difficulty: int,
    count: int,
    knowledge_content: str = "",
) -> List[dict]:
    """Generate questions using MiniMax API.

    Automatically splits large requests into batches of max 5 questions
    to avoid output truncation with smaller models.

    Args:
        subject_id: Subject ID
        subject_name: Subject name
        chapter_ids: List of chapter IDs
        chapter_names: List of chapter names
        question_type: Question type (single_choice, multiple_choice, true_false, essay)
        difficulty: Difficulty level (1-5)
        count: Number of questions to generate
        knowledge_content: Knowledge point content text for contextual question generation

    Returns:
        List of question dicts ready for database insertion
    """
    BATCH_SIZE = 5  # 每批最多5题，避免小模型输出截断
    all_processed = []
    total_expected = count

    # 知识点内容截断：每组已由上层控制不超过 4000 字符
    # 这里做最终安全截断，防止极端情况
    safe_knowledge = knowledge_content
    if len(safe_knowledge) > 5000:
        safe_knowledge = safe_knowledge[:5000] + "\n...(内容过长已截断)"

    for batch_start in range(0, count, BATCH_SIZE):
        batch_count = min(BATCH_SIZE, count - batch_start)

        prompt = build_question_generation_prompt(
            subject_name=subject_name,
            chapter_names=chapter_names,
            question_type=question_type,
            difficulty=difficulty,
            count=batch_count,
            knowledge_content=safe_knowledge,
        )

        result_text = await _call_ai_with_retry(prompt, max_tokens=8192)

        if result_text is None:
            logger.warning(f"Batch {batch_start//BATCH_SIZE + 1}: AI API returned None, expected {batch_count} questions")
            continue

        questions_data = _try_parse_questions_json(result_text)

        if questions_data is not None and len(questions_data) > 0:
            for q in questions_data:
                processed_q = {
                    "content": q.get("content", ""),
                    "answer": q.get("answer", ""),
                    "explanation": q.get("explanation", ""),
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "chapter_id": chapter_ids[0] if chapter_ids else None,
                    "subject_id": subject_id,
                    "options": q.get("options", []),
                }
                all_processed.append(processed_q)
            logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Generated {len(questions_data)}/{batch_count} questions (total: {len(all_processed)}/{total_expected})")
        else:
            logger.warning(f"Batch {batch_start//BATCH_SIZE + 1}: Failed to parse AI response, raw text length={len(result_text)}")

    # 补题机制：如果实际生成题数不足，尝试再补一轮
    missing = total_expected - len(all_processed)
    if missing > 0 and len(all_processed) > 0:
        logger.info(f"题目不足，尝试补题 {missing} 道...")
        supplement = min(missing, BATCH_SIZE)  # 最多补一批
        prompt = build_question_generation_prompt(
            subject_name=subject_name,
            chapter_names=chapter_names,
            question_type=question_type,
            difficulty=difficulty,
            count=supplement,
            knowledge_content=safe_knowledge,
        )
        result_text = await _call_ai_with_retry(prompt, max_tokens=8192)
        if result_text:
            questions_data = _try_parse_questions_json(result_text)
            if questions_data:
                for q in questions_data:
                    processed_q = {
                        "content": q.get("content", ""),
                        "answer": q.get("answer", ""),
                        "explanation": q.get("explanation", ""),
                        "question_type": question_type,
                        "difficulty": difficulty,
                        "chapter_id": chapter_ids[0] if chapter_ids else None,
                        "subject_id": subject_id,
                        "options": q.get("options", []),
                    }
                    all_processed.append(processed_q)
                logger.info(f"补题成功：新增 {len(questions_data)} 道 (total: {len(all_processed)}/{total_expected})")

    if len(all_processed) < total_expected:
        logger.warning(f"最终生成 {len(all_processed)}/{total_expected} 题，缺少 {total_expected - len(all_processed)} 题")

    # 题目校验：AI自检，剔除答非所问的题目
    if all_processed and safe_knowledge:
        logger.info(f"开始题目校验，共 {len(all_processed)} 题...")
        all_processed = await _verify_questions(all_processed, safe_knowledge, question_type)

    return all_processed