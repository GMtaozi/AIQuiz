"""Knowledge-question association routes: question-counts, knowledge questions."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import Question
from app.models.user import User
from app.schemas.knowledge import KnowledgeQuestionCountRequest
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.post("/question-counts")
def get_knowledge_point_question_counts(
    request: KnowledgeQuestionCountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定知识点及其所有子节点的题目数量统计

    用于智能组卷时根据题目数量分配权重
    """
    kp_ids = request.knowledge_ids

    if not kp_ids:
        return {}

    # 递归收集所有子节点ID
    def collect_all_child_ids(parent_id: int) -> set:
        child_ids = {parent_id}
        direct_children = db.query(KnowledgePoint.id).filter(KnowledgePoint.parent_id == parent_id).all()
        for child in direct_children:
            child_ids.add(child.id)
            child_ids.update(collect_all_child_ids(child.id))
        return child_ids

    # 先收集所有顶级知识点的子节点信息
    kp_info = {}
    for kp_id in kp_ids:
        child_ids = collect_all_child_ids(kp_id)
        kp_info[kp_id] = {"descendant_ids": child_ids}

    # 一次性查询所有相关题目
    all_questions = db.query(Question).filter(Question.meta.isnot(None)).all()

    # 统计每个顶级知识点的题目数量
    for kp_id, info in kp_info.items():
        descendant_ids = info["descendant_ids"]
        count = 0
        for q in all_questions:
            if q.meta and q.meta.get("knowledge_point_ids"):
                kp_list = q.meta.get("knowledge_point_ids", [])
                if isinstance(kp_list, list) and any(kid in descendant_ids for kid in kp_list):
                    count += 1
        info["question_count"] = count

    # 构建返回结果
    result = {
        str(kp_id): {"total_descendants": len(info["descendant_ids"]), "question_count": info["question_count"]}
        for kp_id, info in kp_info.items()
    }

    return result


@router.get("/{knowledge_id}/questions")
def get_knowledge_point_questions(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定知识点及其子知识点关联的题目列表"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == knowledge_id).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 评估 P1-10 修复：答案/解析仅管理员与题库编辑可见（审核员/其他角色不可见）
    include_answer = current_user.role in (1, 2)

    # 评估 P2-16：一次查询加载全部 (id, parent_id) 对，内存构建父子映射，
    # 替代原实现的逐节点递归 SQL（N+1 查询）。
    all_points = db.query(KnowledgePoint.id, KnowledgePoint.parent_id).all()
    children_map: dict = {}
    for pid, parent in all_points:
        children_map.setdefault(parent, []).append(pid)

    descendant_ids: set = set()

    def collect(parent_id: int) -> None:
        if parent_id in descendant_ids:
            return
        descendant_ids.add(parent_id)
        for child in children_map.get(parent_id, []):
            collect(child)

    collect(knowledge_id)

    # 查询关联题目（meta JSON 内 knowledge_point_ids 无法用 SQL 直接过滤，
    # 评估 P2-16：限制扫描数量上限防止整表加载）
    questions = (
        db.query(Question)
        .filter(Question.meta.isnot(None), Question.status == 1, Question.audit_status == "approved")
        .order_by(Question.id.desc())
        .limit(500)
        .all()
    )

    result = []
    for q in questions:
        if q.meta and q.meta.get("knowledge_point_ids"):
            kp_list = q.meta.get("knowledge_point_ids", [])
            if isinstance(kp_list, list) and any(kid in descendant_ids for kid in kp_list):
                item = {
                    "id": q.id,
                    "content": q.content,
                    "question_type": q.question_type,
                    "difficulty": q.difficulty,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
                if include_answer:
                    item["answer"] = q.answer
                    item["explanation"] = q.explanation
                result.append(item)

    return {"questions": result, "total": len(result)}
