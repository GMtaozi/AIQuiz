"""智能组卷工具函数。

包含：按使用次数优先级选题、按难度配置选题。
"""

import random
from typing import List

from app.models.question import Question


def select_questions_by_usage_priority(question_pool: list, count: int) -> list:
    """根据使用次数优先级选择题目

    优先选择使用次数少的题目，同时保持随机性：
    1. 按使用次数分组
    2. 优先从低使用次数组选择
    3. 同组内随机选择
    """
    if count <= 0 or not question_pool:
        return []
    if len(question_pool) <= count:
        return question_pool

    # 按使用次数分组
    by_usage = {}
    for q in question_pool:
        used = getattr(q, "used_count", 0) or 0
        if used not in by_usage:
            by_usage[used] = []
        by_usage[used].append(q)

    selected = []
    remaining = count

    # 从低使用次数到高使用次数依次选择
    for used_count in sorted(by_usage.keys()):
        if remaining <= 0:
            break
        pool = by_usage[used_count]
        # 从该组中选择，最多选完该组或剩余需求
        take = min(remaining, len(pool))
        if take == len(pool):
            selected.extend(pool)
        else:
            selected.extend(random.sample(pool, take))
        remaining -= take

    # 如果还不够（应该不会发生），从剩余池中随机补充
    if remaining > 0:
        selected_ids = {q.id for q in selected}
        remaining_pool = [q for q in question_pool if q.id not in selected_ids]
        if remaining_pool:
            selected.extend(random.sample(remaining_pool, min(remaining, len(remaining_pool))))

    return selected


def _select_questions_by_difficulty(
    available_questions: List[Question], count: int, difficulty_config: dict, questions_by_difficulty: dict
) -> List[Question]:
    """根据难度配置比例从可用题目中选择题目

    Args:
        available_questions: 该题型可用的题目列表
        count: 需要选择的题目数量
        difficulty_config: 难度配置 {"easy": 0.3, "medium": 0.5, "hard": 0.2}
        questions_by_difficulty: 按难度分组的题目 {"easy": [...], "medium": [...], "hard": [...]}

    Returns:
        选中的题目列表
    """
    if not difficulty_config:
        return random.sample(available_questions, count)

    # 计算各难度需要选择的数量
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
    ratio_sum = sum(difficulty_config.values())

    for diff, ratio in difficulty_config.items():
        difficulty_counts[diff] = int(count * ratio / ratio_sum)

    # 确保总数正确，分配余数
    actual_total = sum(difficulty_counts.values())
    remainder = count - actual_total
    if remainder > 0:
        # 将余数分配给中等难度
        difficulty_counts["medium"] += remainder

    selected = []
    available_by_diff = {
        "easy": [q for q in available_questions if q.difficulty <= 2],
        "medium": [q for q in available_questions if q.difficulty == 3],
        "hard": [q for q in available_questions if q.difficulty >= 4],
    }

    for diff, need_count in difficulty_counts.items():
        if need_count <= 0:
            continue
        candidates = available_by_diff.get(diff, [])
        # 过滤掉已选中的
        candidates = [q for q in candidates if q not in selected]
        if len(candidates) < need_count:
            # 如果该难度不足，从其他难度补充
            shortfall = need_count - len(candidates)
            selected.extend(candidates)
            # 从其他难度补充
            for other_diff, other_candidates in available_by_diff.items():
                if other_diff == diff:
                    continue
                other_available = [q for q in other_candidates if q not in selected]
                supplement = min(shortfall, len(other_available))
                selected.extend(random.sample(other_available, supplement))
                shortfall -= supplement
                if shortfall <= 0:
                    break
        else:
            selected.extend(random.sample(candidates, need_count))

    # 如果还有不足（极端情况下），用随机补充
    if len(selected) < count:
        remaining = [q for q in available_questions if q not in selected]
        selected.extend(random.sample(remaining, count - len(selected)))

    return selected[:count]
