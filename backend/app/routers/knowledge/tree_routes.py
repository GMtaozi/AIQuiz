"""Tree routes for knowledge points.

Provides endpoints for retrieving knowledge trees and hierarchy trees.
List and category routes moved to crud.py.
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import ExamCategory, ExamType
from app.models.user import User
from app.routers.knowledge.tree_utils import _build_tree
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.get("/trees")
def get_knowledge_trees(
    category: str | None = None,
    exam_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取知识点树形结构"""
    query = db.query(KnowledgePoint).filter(KnowledgePoint.status == 1)

    if category:
        query = query.filter(KnowledgePoint.category == category)
    if exam_type:
        query = query.filter(KnowledgePoint.exam_type == exam_type)

    nodes = query.order_by(KnowledgePoint.order, KnowledgePoint.id).all()
    trees = _build_tree(nodes, None)

    return {"trees": trees, "total": len(trees)}


@router.get("/hierarchy-trees")
def get_knowledge_hierarchy_trees(
    category_id: int | None = Query(None),
    exam_type_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取按 考试种类→考试科目→知识点 三级组织的树形结构

    返回结构:
    [
      {
        "id": "cat_1", "name": "软考", "node_type": "category",
        "children": [
          {
            "id": "et_1", "name": "网络管理员", "node_type": "exam_type",
            "children": [ ... 知识点树 ... ]
          }
        ]
      }
    ]

    核心逻辑：只按根知识点（parent_id=None）的 category/exam_type 归类，
    子节点跟随根节点，避免同一棵树被拆散。
    """
    # 1. 获取所有考试种类和科目
    categories = db.query(ExamCategory).filter(ExamCategory.status == 1).all()
    exam_types = db.query(ExamType).filter(ExamType.status == 1).all()
    cat_map = {c.code: c for c in categories}
    et_map = {e.code: e for e in exam_types}

    # 2. 获取所有知识点（不按 category 过滤，因为子节点可能和根节点不同）
    all_points = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.status == 1)
        .order_by(KnowledgePoint.order, KnowledgePoint.id)
        .all()
    )

    # 3. 用 _build_tree 构建完整的知识点树（只有根节点 parent_id=None）
    all_trees = _build_tree(all_points, None)

    # 4. 按根节点的 category/exam_type 归类到考试种类→考试科目下
    #    如果根节点 category=default，则从子节点中推断
    kp_map = {p.id: p for p in all_points}

    def _find_category_from_children(tree_node: dict) -> tuple:
        """从树节点及其子节点中找到第一个非 default 的 category/exam_type"""
        kp = kp_map.get(tree_node["id"])
        if kp and kp.category and kp.category != "default":
            return kp.category, (kp.exam_type or "default")
        if kp and kp.exam_type and kp.exam_type != "default":
            return (kp.category or "default"), kp.exam_type
        for child in tree_node.get("children", []):
            cat, et = _find_category_from_children(child)
            if cat != "default" or et != "default":
                return cat, et
        return "default", "default"

    cat_et_groups: Dict[str, Dict[str, list]] = {}  # cat_code -> et_code -> [tree_nodes]
    for tree_node in all_trees:
        kp = kp_map.get(tree_node["id"])
        cat_code = kp.category if kp and kp.category and kp.category != "default" else None
        et_code = kp.exam_type if kp and kp.exam_type and kp.exam_type != "default" else None
        # 如果根节点没有明确的 category，从子节点推断
        if not cat_code and not et_code:
            cat_code, et_code = _find_category_from_children(tree_node)
        else:
            cat_code = cat_code or "default"
            et_code = et_code or "default"
        if cat_code not in cat_et_groups:
            cat_et_groups[cat_code] = {}
        if et_code not in cat_et_groups[cat_code]:
            cat_et_groups[cat_code][et_code] = []
        cat_et_groups[cat_code][et_code].append(tree_node)

    # 5. 如果指定了 category_id/exam_type_id 过滤，只保留匹配的
    if category_id:
        cat = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
        if cat:
            cat_et_groups = {k: v for k, v in cat_et_groups.items() if k == cat.code}
    if exam_type_id:
        et = db.query(ExamType).filter(ExamType.id == exam_type_id).first()
        if et:
            for cat_code in cat_et_groups:
                cat_et_groups[cat_code] = {k: v for k, v in cat_et_groups[cat_code].items() if k == et.code}

    # 6. 构建 category → exam_type 层级映射（从数据库关系）
    et_by_cat: Dict[str, list] = {}
    for et in exam_types:
        cat_code = "default"
        if et.category_id:
            parent_cat = cat_map.get(et.category_id)
            if parent_cat:
                cat_code = parent_cat.code
        if cat_code not in et_by_cat:
            et_by_cat[cat_code] = []
        et_by_cat[cat_code].append(et)

    # 7. 组装最终层级树
    result = []
    used_cat_codes = set()

    # 如果指定了 exam_type_id，只返回该科目及其知识点
    if exam_type_id:
        et = db.query(ExamType).filter(ExamType.id == exam_type_id).first()
        if not et:
            return {"trees": result, "total": 0}
        # 获取该科目对应的考试种类
        if not et.category_id:
            return {"trees": result, "total": 0}
        cat = db.query(ExamCategory).filter(ExamCategory.id == et.category_id).first()
        if not cat:
            return {"trees": result, "total": 0}
        # 获取该科目的所有知识点（按 exam_type 过滤）
        all_kp = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.status == 1, KnowledgePoint.exam_type == et.code)
            .order_by(KnowledgePoint.order, KnowledgePoint.id)
            .all()
        )

        # 使用 _build_tree 构建知识点树，只取挂在 exam_type 下的根节点（parent_id = None）
        kp_trees = _build_tree(all_kp, None)

        # 只有当知识点不为空时才添加到结果
        if kp_trees:
            cat_node = {
                "id": f"cat_{cat.code}",
                "name": cat.name,
                "node_type": "category",
                "category_id": cat.id,
                "children": [
                    {
                        "id": f"et_{et.code}",
                        "name": et.name,
                        "node_type": "exam_type",
                        "exam_type_id": et.id,
                        "children": kp_trees,
                    }
                ],
            }
            result.append(cat_node)
        return {"trees": result, "total": len(result)}
    else:
        # 原有的正常逻辑：显示所有考试种类和科目
        for cat_code, et_groups in cat_et_groups.items():
            if cat_code == "default":
                continue
            cat_obj = cat_map.get(cat_code)
            cat_node = {
                "id": f"cat_{cat_code}",
                "name": cat_obj.name if cat_obj else cat_code,
                "node_type": "category",
                "category_id": cat_obj.id if cat_obj else None,
                "children": [],
            }
            used_cat_codes.add(cat_code)

            for et_code, kp_trees in et_groups.items():
                et_obj = et_map.get(et_code)
                et_node = {
                    "id": f"et_{et_code}",
                    "name": et_obj.name if et_obj else et_code,
                    "node_type": "exam_type",
                    "exam_type_id": et_obj.id if et_obj else None,
                    "children": kp_trees,
                }
                cat_node["children"].append(et_node)

            # 补上该种类下没有知识点但有数据的考试科目
            existing_et_codes = set(et_groups.keys())
            for et_obj in et_by_cat.get(cat_code, []):
                if et_obj.code not in existing_et_codes:
                    cat_node["children"].append(
                        {
                            "id": f"et_{et_obj.code}",
                            "name": et_obj.name,
                            "node_type": "exam_type",
                            "exam_type_id": et_obj.id,
                            "children": [],
                        }
                    )

            result.append(cat_node)

    # 未分类的知识点（category=default）
    default_groups = cat_et_groups.get("default", {})
    if default_groups:
        for et_code, kp_trees in default_groups.items():
            if et_code == "default":
                # 完全未分类，直接放在"未分类"种类下
                default_cat = next((n for n in result if n["id"] == "cat_default"), None)
                if not default_cat:
                    default_cat = {
                        "id": "cat_default",
                        "name": "未分类",
                        "node_type": "category",
                        "category_id": None,
                        "children": list(kp_trees),
                    }
                    result.append(default_cat)
                else:
                    default_cat["children"].extend(kp_trees)
            else:
                # 有考试科目但无考试种类
                et_obj = et_map.get(et_code)
                default_cat = next((n for n in result if n["id"] == "cat_default"), None)
                if not default_cat:
                    default_cat = {
                        "id": "cat_default",
                        "name": "未分类",
                        "node_type": "category",
                        "category_id": None,
                        "children": [],
                    }
                    result.append(default_cat)
                default_cat["children"].append(
                    {
                        "id": f"et_{et_code}",
                        "name": et_obj.name if et_obj else et_code,
                        "node_type": "exam_type",
                        "exam_type_id": et_obj.id if et_obj else None,
                        "children": kp_trees,
                    }
                )

    # 没有知识点的考试种类也要显示
    for cat in categories:
        if cat.code not in used_cat_codes:
            cat_node = {
                "id": f"cat_{cat.code}",
                "name": cat.name,
                "node_type": "category",
                "category_id": cat.id,
                "children": [],
            }
            for et_obj in et_by_cat.get(cat.code, []):
                cat_node["children"].append(
                    {
                        "id": f"et_{et_obj.code}",
                        "name": et_obj.name,
                        "node_type": "exam_type",
                        "exam_type_id": et_obj.id,
                        "children": [],
                    }
                )
            result.append(cat_node)

    return {"trees": result, "total": len(result)}


@router.get("/")
def get_knowledge_list(
    category: str | None = None,
    exam_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取知识点列表（扁平，分页）"""
    query = db.query(KnowledgePoint)

    if category:
        query = query.filter(KnowledgePoint.category == category)
    if exam_type:
        query = query.filter(KnowledgePoint.exam_type == exam_type)

    total = query.count()
    nodes = (
        query.order_by(KnowledgePoint.order, KnowledgePoint.id).offset((page - 1) * page_size).limit(page_size).all()
    )

    return {
        "items": [
            {
                "id": n.id,
                "name": n.name,
                "parent_id": n.parent_id,
                "category": n.category,
                "exam_type": n.exam_type,
                "description": n.description,
                "order": n.order,
                "status": n.status,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "question_count": 0,
            }
            for n in nodes
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/category/{category}")
def get_by_category(
    category: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按分类获取知识点"""
    nodes = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.category == category, KnowledgePoint.status == 1)
        .order_by(KnowledgePoint.order, KnowledgePoint.id)
        .all()
    )

    trees = _build_tree(nodes, None)
    return {"items": trees, "total": len(trees)}
