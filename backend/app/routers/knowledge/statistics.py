"""Statistics routes for knowledge points.

Provides endpoints for retrieving knowledge statistics.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.user import User
from app.routers.knowledge.tree_utils import _get_tree_depth
from app.schemas.knowledge import KnowledgeStatistics
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.get("/statistics/summary", response_model=KnowledgeStatistics)
def get_knowledge_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取知识点统计"""
    total = db.query(func.count(KnowledgePoint.id)).filter(KnowledgePoint.status == 1).scalar()

    # 按分类统计
    category_results = (
        db.query(KnowledgePoint.category, func.count(KnowledgePoint.id))
        .filter(KnowledgePoint.status == 1)
        .group_by(KnowledgePoint.category)
        .all()
    )
    by_category = {r[0]: r[1] for r in category_results}

    # 按考试类型统计
    exam_results = (
        db.query(KnowledgePoint.exam_type, func.count(KnowledgePoint.id))
        .filter(KnowledgePoint.status == 1, KnowledgePoint.exam_type.isnot(None))
        .group_by(KnowledgePoint.exam_type)
        .all()
    )
    by_exam_type = {r[0]: r[1] for r in exam_results if r[0]}

    # 计算最大深度
    all_nodes = db.query(KnowledgePoint).filter(KnowledgePoint.status == 1).all()
    nodes_dict = [{"id": n.id, "parent_id": n.parent_id} for n in all_nodes]
    max_depth = 1
    for node in nodes_dict:
        if node["parent_id"] is None:
            depth = _get_tree_depth(nodes_dict, node["id"], 1)
            max_depth = max(max_depth, depth)

    return KnowledgeStatistics(
        total=total or 0, by_category=by_category, by_exam_type=by_exam_type, max_depth=max_depth
    )
