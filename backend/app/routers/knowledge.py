"""Knowledge Router - 知识点管理模块"""

import base64
from datetime import datetime
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.constants import UserRole
from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import ExamCategory, ExamType, Question
from app.models.user import User
from app.schemas.knowledge import (
    AIImportRequest,
    BatchImportRequest,
    KnowledgePointCreate,
    KnowledgePointResponse,
    KnowledgePointUpdate,
    KnowledgeQuestionCountRequest,
    KnowledgeStatistics,
)
from app.services.ai_knowledge_extractor import extract_knowledge_from_document
from app.services.document_parser import parse_document, truncate_for_analysis
from app.services.rule_knowledge_extractor import extract_knowledge_by_rules
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


def _count_tree_nodes(nodes: List[dict]) -> int:
    """递归统计树中节点总数"""
    count = 0
    for node in nodes:
        count += 1
        children = node.get("children") or node.get("子节点", [])
        if children and isinstance(children, list):
            count += _count_tree_nodes(children)
    return count


def _build_tree(nodes: List[KnowledgePoint], parent_id: int | None = None) -> List[dict]:
    """递归构建树形结构"""
    tree = []
    for node in nodes:
        if node.parent_id == parent_id:
            # 递归获取子节点
            children_nodes = [n for n in nodes if n.parent_id == node.id]
            children = _build_tree(nodes, node.id)

            # 只有根节点（parent_id is None）才在名称后面显示最末级知识点统计
            display_name = node.name
            is_root = parent_id is None
            leaf_count = 0
            if is_root and children:
                # 统计该根节点下的所有叶子节点数量
                leaf_count = _count_leaf_nodes(children)
                display_name = f"{node.name}（共{leaf_count}个知识点）"

            tree.append(
                {
                    "id": node.id,
                    "name": display_name,
                    "original_name": node.name,  # 保留原始名称
                    "parent_id": node.parent_id,
                    "category": node.category,
                    "exam_type": node.exam_type,
                    "description": node.description,
                    "order": node.order,
                    "status": node.status,
                    "created_by": node.created_by,
                    "created_at": node.created_at,
                    "updated_at": node.updated_at,
                    "leaf_count": leaf_count if is_root else 0,  # 仅根节点记录叶子节点数
                    "children": children,
                }
            )
    return tree


def _count_leaf_nodes(nodes: List[dict]) -> int:
    """统计节点列表中的叶子节点数量（没有 children 或 children 为空的节点）"""
    count = 0
    for node in nodes:
        if not node.get("children") or len(node["children"]) == 0:
            count += 1
        else:
            count += _count_leaf_nodes(node["children"])
    return count


def _get_tree_depth(nodes: List[dict], node_id: int | None, current_depth: int = 1) -> int:
    """计算树的深度"""
    children = [n for n in nodes if n.get("parent_id") == node_id]
    if not children:
        return current_depth
    return max(_get_tree_depth(nodes, child["id"], current_depth + 1) for child in children)


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


def _build_kp_tree(root_points: list, child_points: list) -> list:
    """从根知识点和子知识点列表构建树（复用 _build_tree 逻辑但用对象而非全量查询）"""
    all_points = root_points + child_points
    return _build_tree(all_points, None)


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


@router.get("/{knowledge_id}")
def get_knowledge_point(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取知识点详情"""
    node = db.query(KnowledgePoint).filter(KnowledgePoint.id == knowledge_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 获取子节点数量
    children_count = db.query(func.count(KnowledgePoint.id)).filter(KnowledgePoint.parent_id == knowledge_id).scalar()

    return {
        "id": node.id,
        "name": node.name,
        "parent_id": node.parent_id,
        "category": node.category,
        "exam_type": node.exam_type,
        "description": node.description,
        "order": node.order,
        "status": node.status,
        "created_by": node.created_by,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
        "question_count": 0,
        "children_count": children_count,
    }


@router.post("/", response_model=KnowledgePointResponse, status_code=201)
def create_knowledge_point(
    data: KnowledgePointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """创建知识点"""
    # 解析 category/exam_type：优先从 ID 查询 code
    category = data.category or "default"
    exam_type = data.exam_type

    if data.category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == data.category_id).first()
        if cat_obj:
            category = cat_obj.code
    if data.exam_type_id:
        et_obj = db.query(ExamType).filter(ExamType.id == data.exam_type_id).first()
        if et_obj:
            exam_type = et_obj.code

    # 验证父节点存在
    if data.parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父节点不存在")

    node = KnowledgePoint(
        name=data.name,
        parent_id=data.parent_id,
        category=category,
        exam_type=exam_type,
        description=data.description,
        order=data.order,
        status=1,
        created_by=current_user.id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    logger.info(f"用户 {current_user.id} 创建了知识点: id={node.id}, name={node.name}")
    return node


@router.put("/{knowledge_id}", response_model=KnowledgePointResponse)
def update_knowledge_point(
    knowledge_id: int,
    data: KnowledgePointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """更新知识点"""
    node = db.query(KnowledgePoint).filter(KnowledgePoint.id == knowledge_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 验证父节点存在
    if data.parent_id is not None and data.parent_id != node.id:
        if data.parent_id > 0:
            parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == data.parent_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="父节点不存在")
            # 防止循环引用
            if data.parent_id == knowledge_id:
                raise HTTPException(status_code=400, detail="不能将自己设为父节点")

    # 解析 category_id/exam_type_id → code
    if data.category_id is not None:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == data.category_id).first()
        if cat_obj:
            node.category = cat_obj.code
    elif data.category is not None:
        node.category = data.category

    if data.exam_type_id is not None:
        et_obj = db.query(ExamType).filter(ExamType.id == data.exam_type_id).first()
        if et_obj:
            node.exam_type = et_obj.code
    elif data.exam_type is not None:
        node.exam_type = data.exam_type

    # 更新其他字段（排除 category_id/exam_type_id，它们不是模型字段）
    update_data = data.model_dump(exclude_unset=True)
    for field in ["category_id", "exam_type_id", "category", "exam_type"]:
        update_data.pop(field, None)
    for field, value in update_data.items():
        setattr(node, field, value)

    db.commit()
    db.refresh(node)

    logger.info(f"用户 {current_user.id} 更新了知识点: id={node.id}")
    return node


@router.delete("/{knowledge_id}")
def delete_knowledge_point(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """删除知识点（使用事务保证原子性）"""
    node = db.query(KnowledgePoint).filter(KnowledgePoint.id == knowledge_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="知识点不存在")

    try:
        # 收集所有要删除的节点ID（先收集再删除，避免在迭代中修改）
        nodes_to_delete = []

        def _collect_nodes(node_id: int):
            children = db.query(KnowledgePoint.id).filter(KnowledgePoint.parent_id == node_id).all()
            nodes_to_delete.append(node_id)
            for child in children:
                _collect_nodes(child.id)

        _collect_nodes(knowledge_id)

        # 批量删除（使用IN查询一次性删除，更高效且保证原子性）
        if nodes_to_delete:
            db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(nodes_to_delete)).delete(synchronize_session=False)
        db.commit()

        logger.info(
            f"用户 {current_user.id} 删除了知识点(含子节点): id={knowledge_id}, 共删除{len(nodes_to_delete)}个节点"
        )
        return {"message": "删除成功", "id": knowledge_id, "deleted_count": len(nodes_to_delete)}
    except Exception as e:
        db.rollback()
        logger.error(f"删除知识点失败: id={knowledge_id}, error={e!s}")
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试")


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


# ============ 规则解析导入（零AI调用，毫秒级） ============


@router.post("/rule/analyze")
async def rule_analyze_document(
    file: UploadFile = File(...),
    parent_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    max_children: int = Form(default=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """基于规则解析文档结构，自动提取知识点

    无需 AI，毫秒级返回。适用于法律条文、教材等结构化文档。
    支持格式：PDF, Word(.docx), Markdown(.md), TXT

    解析策略：
    - 法律条文：识别"第X章"、"第X条"结构
    - Markdown：识别 # 标题层级
    - 数字编号：识别 1. → 1.1 → 1.1.1
    - 纯文本：按段落拆分
    """
    # 解析 category
    resolved_category = category
    if category_id and category_id.isdigit():
        from app.models.question import ExamCategory

        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code

    # 读取文件内容
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        # 解析文档为文本
        text_content = parse_document(content, ext, filename)
        text_content = truncate_for_analysis(text_content, max_chars=200000)

        if len(text_content.strip()) < 50:
            raise HTTPException(status_code=400, detail="文档内容过少或无法提取文本")

        # 规则解析提取知识点
        result = extract_knowledge_by_rules(text=text_content, max_children=max_children, max_depth=3)

        return_parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

        logger.info(f"用户 {current_user.id} 规则解析了文档: {filename}, 提取 {result.get('total', 0)} 个知识点")

        return {
            "success": True,
            "document_name": filename,
            "text_preview": text_content[:500] + "..." if len(text_content) > 500 else text_content,
            "knowledge_points": result.get("knowledge_points", []),
            "total_points": result.get("total", 0),
            "parent_id": return_parent_id,
            "method": "rule-based",
            "message": f"规则解析完成，提取 {result.get('total', 0)} 个知识点，可确认导入",
        }

    except ImportError as e:
        logger.error(f"缺少解析依赖: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="缺少解析依赖，请联系管理员")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.error(f"规则文档解析失败: {e!s}\n{tb}")
        raise HTTPException(status_code=500, detail="文档解析失败，请稍后重试")


# ============ AI 智能导入 ============


@router.post("/ai/analyze")
async def ai_analyze_document(
    file: UploadFile = File(...),
    parent_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    max_points: int = Form(default=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """AI 智能分析文档并提取知识点

    支持格式：PDF, Word(.docx), Markdown(.md), TXT

    返回提取的知识点树结构，供用户确认后保存。
    """
    # 如果前端传了 category_id（数字 ID），查询对应的 code
    resolved_category = category
    if category_id and category_id.isdigit():
        from app.models.question import ExamCategory

        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code
    # 读取文件内容
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:  # 10MB 限制
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    # 获取文件扩展名
    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        # 解析文档
        text_content = parse_document(content, ext, filename)
        text_content = truncate_for_analysis(text_content, max_chars=50000)

        if len(text_content.strip()) < 50:
            raise HTTPException(status_code=400, detail="文档内容过少或无法提取文本")

        # 调用 AI 提取知识点
        result = await extract_knowledge_from_document(
            document_content=text_content, document_name=filename, max_points=max_points, category=resolved_category
        )

        if not result.get("success"):
            error_msg = result.get("error", "AI 分析失败")
            raise HTTPException(status_code=500, detail=f"AI 分析失败: {error_msg}")

        logger.info(f"用户 {current_user.id} 使用 AI 分析了文档: {filename}, 生成了 {result.get('total', 0)} 个知识点")

        return_parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

        return {
            "success": True,
            "document_name": filename,
            "text_preview": text_content[:500] + "..." if len(text_content) > 500 else text_content,
            "knowledge_points": result.get("knowledge_points", []),
            "total_points": result.get("total", 0),
            "parent_id": return_parent_id,
            "message": "AI 分析完成，请确认知识点结构后保存",
        }

    except ImportError as e:
        logger.error(f"缺少解析依赖: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="缺少解析依赖，请联系管理员")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 评估 P1-9 修复：异常详情只进日志，不返回给客户端（原实现泄露完整 traceback）
        import traceback

        tb = traceback.format_exc()
        logger.error(f"AI 文档分析失败: {e!s}\n{tb}")
        raise HTTPException(status_code=500, detail="文档分析失败，请稍后重试")


@router.post("/ai/import")
async def ai_import_knowledge(
    import_request: AIImportRequest = Body(..., media_type="application/json"),
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量导入 AI 生成的知识点

    接收 AI 分析后确认的知识点点结构，批量创建到数据库。
    """
    knowledge_points = import_request.knowledge_points
    category = import_request.category or "default"
    exam_type = import_request.exam_type
    parent_id = import_request.parent_id

    # 如果前端传了 category_id（数字 ID），查询对应的 code
    if import_request.category_id:
        from app.models.question import ExamCategory, ExamType

        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == import_request.category_id).first()
        if cat_obj:
            category = cat_obj.code
        # 如果前端传了 exam_type_id，查询对应的 code
        if import_request.exam_type_id:
            et_obj = db.query(ExamType).filter(ExamType.id == import_request.exam_type_id).first()
            if et_obj:
                exam_type = et_obj.code

    logger.debug(
        f"AI导入请求: parent_id={parent_id}, category={category}, exam_type={exam_type}, points_count={len(knowledge_points)}, document_name={import_request.document_name}"
    )

    if not knowledge_points:
        raise HTTPException(status_code=400, detail="知识点列表不能为空")

    # 验证父节点存在
    if parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        # 如果父节点的 category 是 default，更新为导入的 category/exam_type
        if parent.category == "default" or not parent.category:
            if category and category != "default":
                parent.category = category
            if exam_type:
                parent.exam_type = exam_type

    created_count = 0
    id_mapping = {}  # 旧ID -> 新ID 的映射（用于处理树结构）

    # 如果没有指定父节点但有文档名，创建一个文档节点作为父节点
    # 这样可以让多个知识点根节点都挂在这个文档节点下
    effective_parent_id = parent_id
    if not effective_parent_id and import_request.document_name:
        doc_name = import_request.document_name.strip()
        if doc_name:
            # 清理文档名（去掉扩展名、前缀编号等）
            import re

            doc_name = re.sub(r"\.[^.]+$", "", doc_name)  # 去掉扩展名
            doc_name = re.sub(r"^【[^】]*】", "", doc_name)  # 去掉【编号】前缀
            doc_name = re.sub(r"^\[[^\]]*\]", "", doc_name)  # 去掉[编号]前缀
            doc_name = re.sub(r"^[一二三四五六七八九十百千零○零\d\s]+[.、)）]", "", doc_name)  # 去掉中文/数字序号前缀
            doc_name = re.sub(r"^\d+[.、)\s]", "", doc_name)  # 去掉纯数字序号前缀
            doc_name = re.sub(
                r"^[第][一二三四五六七八九十百千\d]+[章节条款段篇点题]", "", doc_name
            )  # 去掉"第X章"等前缀
            doc_name = doc_name.strip() or "未命名文档"

            doc_node = KnowledgePoint(
                name=doc_name[:100],
                parent_id=None,
                category=category,
                exam_type=exam_type,
                description=f"导入自文档: {import_request.document_name}",
                order=0,
                status=1,
                created_by=current_user.id,
            )
            db.add(doc_node)
            db.flush()
            effective_parent_id = doc_node.id
            created_count += 1
            logger.info(f"创建文档节点: id={doc_node.id}, name={doc_name}")

    def create_nodes(nodes: List[dict], parent_id: int | None = None):
        nonlocal created_count
        for node in nodes:
            # 兼容中英文 key
            name = node.get("name") or node.get("名称", "未命名")
            description = node.get("description") or node.get("描述", "")
            excerpt = node.get("excerpt") or node.get("原文", "")
            children = node.get("children") or node.get("子节点", [])

            logger.debug(f"创建知识点: name={name}, parent_id={parent_id}")

            # 创建知识点
            kp = KnowledgePoint(
                name=name[:100],
                parent_id=parent_id,
                category=category,
                exam_type=exam_type,
                description=description[:2000] if description else None,
                content_excerpt=excerpt[:2000] if excerpt else None,
                knowledge_base_id=import_request.knowledge_base_id,
                entry_id=import_request.entry_id,
                order=created_count,
                status=1,
                created_by=current_user.id,
            )
            db.add(kp)
            db.flush()  # 获取 ID

            old_id = node.get("id", 0)
            if old_id:
                id_mapping[old_id] = kp.id

            created_count += 1

            # 递归创建子节点
            if children:
                create_nodes(children if isinstance(children, list) else [], parent_id=kp.id)

    try:
        create_nodes(knowledge_points, parent_id=effective_parent_id)
        db.commit()

        logger.info(f"用户 {current_user.id} 批量导入了 {created_count} 个知识点")

        return {"success": True, "created_count": created_count, "message": f"成功导入 {created_count} 个知识点"}
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入知识点失败: {e!s}")
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")


@router.post("/ai/preview")
async def ai_preview_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher_or_admin),
):
    """预览文档内容（用于确认上传文件是否正确）"""
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        text_content = parse_document(content, ext, filename)
        preview = truncate_for_analysis(text_content, max_chars=2000)

        return {
            "success": True,
            "filename": filename,
            "file_type": ext,
            "text_length": len(text_content),
            "preview": preview,
            "message": "文档预览成功",
        }
    except Exception as e:
        logger.error(f"文档预览失败: {e!s}")
        raise HTTPException(status_code=400, detail="文档预览失败，请检查文件格式")


# ============ 批量文档处理 ============

from app.services.batch_document_processor import BatchDocumentProcessor

batch_processor = BatchDocumentProcessor()


@router.post("/batch/analyze")
async def batch_analyze_documents(
    files: List[UploadFile] = File(...),
    subject_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    exam_type: str = Form(default=""),
    exam_type_id: str = Form(default=""),
    parent_kp_id: str = Form(default=""),
    extraction_mode: str = Form(default="auto"),
    max_points_per_doc: int = Form(default=50),
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量分析多个文档，返回每个文档的知识点树

    支持格式：PDF, Word(.docx), Markdown(.md), TXT
    每个文档独立处理，生成独立的知识点树。

    extraction_mode:
    - "auto": 自动选择（规则解析结果少时用AI）
    - "rule_only": 仅规则解析（快，无AI调用）
    - "ai": 仅AI解析（准确性高，需API配额）
    """
    # 解析 category/exam_type
    resolved_category = category
    if category_id and category_id.isdigit():
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code

    resolved_exam_type = exam_type if exam_type else None
    if exam_type_id and exam_type_id.isdigit():
        et_obj = db.query(ExamType).filter(ExamType.id == int(exam_type_id)).first()
        if et_obj:
            resolved_exam_type = et_obj.code

    resolved_parent_id = int(parent_kp_id) if parent_kp_id and parent_kp_id.isdigit() else None

    # 验证父节点存在
    if resolved_parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == resolved_parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")

    # 批量处理
    result = await batch_processor.process_batch(
        files=files,
        subject_id=subject_id,
        category=resolved_category,
        parent_kp_id=resolved_parent_id,
        extraction_mode=extraction_mode,
        max_points=max_points_per_doc,
    )

    logger.info(
        f"用户 {current_user.id} 批量分析了 {len(files)} 个文档，成功 {result['completed']}，失败 {result['failed']}"
    )
    for r in result.get("results", []):
        logger.info(f"  文档分析结果: {r['filename']}, 状态={r['status']}, 节点数={r.get('total_points', 0)}")

    return {
        "success": True,
        "total": result["total"],
        "completed": result["completed"],
        "failed": result["failed"],
        "results": result["results"],
        "message": f"批量分析完成：成功 {result['completed']}，失败 {result['failed']}",
    }


@router.post("/batch/import")
async def batch_import_knowledge(
    import_request: BatchImportRequest,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量导入多个文档的知识点

    每个文档的知识点作为独立的顶级节点（文档名），其下的章节/小节作为子节点。
    文档之间没有父子关系。
    """
    category = import_request.category or "default"
    exam_type = import_request.exam_type
    parent_id = import_request.parent_kp_id

    # 解析 category_id/exam_type_id → code
    if import_request.category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == import_request.category_id).first()
        if cat_obj:
            category = cat_obj.code

    if import_request.exam_type_id:
        et_obj = db.query(ExamType).filter(ExamType.id == import_request.exam_type_id).first()
        if et_obj:
            exam_type = et_obj.code

    # 验证父节点存在
    if parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        # 更新父节点的 category/exam_type
        if parent.category == "default" or not parent.category:
            if category and category != "default":
                parent.category = category
            if exam_type:
                parent.exam_type = exam_type

    if not import_request.documents:
        raise HTTPException(status_code=400, detail="文档列表不能为空")

    created_count = 0
    failed_count = 0
    errors = []

    for doc in import_request.documents:
        created_before = created_count
        try:
            # 评估 P1-11：每个文档使用 SAVEPOINT，失败仅回滚该文档的写入，
            # 避免 flush 错误后 session 进入 pending-rollback 导致整体 500、
            # 或把失败文档的半成品数据随最终 commit 一起入库。
            with db.begin_nested():
                # 清理文件名作为父节点名称（去掉扩展名、前缀编号等）
                import re

                doc_name = doc.filename
                if "." in doc_name:
                    doc_name = doc_name.rsplit(".", 1)[0]
                doc_name = re.sub(r"^【[^】]*】", "", doc_name)
                doc_name = re.sub(r"^\[[^\]]*\]", "", doc_name)
                doc_name = re.sub(r"^[一二三四五六七八九十百千零○零\d\s]+[.、)）]", "", doc_name)
                doc_name = re.sub(r"^\d+[.、)\s]", "", doc_name)
                doc_name = re.sub(r"^[第][一二三四五六七八九十百千\d]+[章节条款段篇点题]", "", doc_name)
                doc_name = doc_name.strip()

                doc_node = KnowledgePoint(
                    name=doc_name[:100] or "未命名文档",
                    parent_id=parent_id,
                    category=category,
                    exam_type=exam_type,
                    description=f"导入自文档: {doc.filename}",
                    order=created_count,
                    status=1,
                    created_by=current_user.id,
                )
                db.add(doc_node)
                db.flush()
                created_count += 1  # 计入文档节点

                # 递归创建知识点树
                def create_tree_nodes(nodes: List[dict], doc_parent_id: int):
                    nonlocal created_count
                    for node in nodes:
                        name = node.get("name") or node.get("名称", "未命名")
                        description = node.get("description") or node.get("描述", "")
                        excerpt = node.get("excerpt") or node.get("原文", "")
                        children = node.get("children") or node.get("子节点", [])

                        kp = KnowledgePoint(
                            name=name[:100],
                            parent_id=doc_parent_id,
                            category=category,
                            exam_type=exam_type,
                            description=description[:2000] if description else None,
                            content_excerpt=excerpt[:2000] if excerpt else None,
                            order=created_count,
                            status=1,
                            created_by=current_user.id,
                        )
                        db.add(kp)
                        db.flush()
                        created_count += 1

                        if children and isinstance(children, list):
                            create_tree_nodes(children, kp.id)

                tree_node_count = _count_tree_nodes(doc.knowledge_tree)
                logger.info(f"文档 {doc.filename} 原始树节点数: {tree_node_count}")

                create_tree_nodes(doc.knowledge_tree, doc_node.id)
                # 文档节点已在之前计数过，不需要再次 +1
                logger.info(f"文档 {doc.filename} 导入完成，当前文档累计: {created_count}")

        except Exception as e:
            created_count = created_before  # SAVEPOINT 已回滚该文档，计数同步回退
            failed_count += 1
            errors.append(f"{doc.filename}: {e!s}")
            logger.error(f"批量导入文档知识点失败 {doc.filename}: {e}")

    try:
        db.commit()
        logger.info(f"用户 {current_user.id} 批量导入了 {created_count} 个知识点（失败 {failed_count}）")

        return {
            "success": True,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors if errors else None,
            "message": f"成功导入 {created_count} 个知识点" + (f"，失败 {failed_count} 个" if failed_count > 0 else ""),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入失败: {e}")
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")


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


@router.post("/import")
async def import_knowledge_points(
    file: UploadFile = File(...),
    parent_id: int | None = Form(None),
    category_id: int | None = Form(None),
    exam_type_id: int | None = Form(None),
    category: str | None = Form(None),
    exam_type: str | None = Form(None),
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """导入知识点文件（支持 JSON 和 Excel）

    - JSON 格式：数组或嵌套对象，支持 name/description/children/excerpt
    - Excel 格式：表头 name, description, parent_name（可选）
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未上传文件")

    file_content = await file.read()
    await file.close()

    if not file_content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 解析文件内容
    ext = file.filename.lower().split(".")[-1]
    nodes: List[Dict[str, Any]] = []

    if ext == "json":
        import json

        try:
            data = json.loads(file_content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {e}") from e

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON 格式错误：应为数组或对象数组")

        def flatten(item: Dict[str, Any], parent_name: str | None = None) -> List[Dict[str, Any]]:
            result = []
            name = item.get("name") or item.get("名称") or item.get("title") or ""
            if not name:
                return result
            result.append(
                {
                    "name": str(name)[:100],
                    "description": (item.get("description") or item.get("描述") or "")[:2000],
                    "excerpt": (item.get("excerpt") or item.get("原文") or "")[:2000],
                    "parent_name": parent_name,
                }
            )
            children = item.get("children") or item.get("子节点") or []
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        result.extend(flatten(child, name))
            return result

        for item in data:
            if isinstance(item, dict):
                nodes.extend(flatten(item))
    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
        except ImportError as e:
            raise HTTPException(status_code=500, detail="缺少 openpyxl 依赖") from e

        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Excel 解析失败: {e}") from e

        ws = wb.active
        headers = []
        for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
            headers = [str(cell).lower().strip() if cell else "" for cell in row]

        name_idx = next((i for i, h in enumerate(headers) if h == "name"), None)
        desc_idx = next((i for i, h in enumerate(headers) if h == "description"), None)
        parent_idx = next((i for i, h in enumerate(headers) if h == "parent_name"), None)

        if name_idx is None:
            raise HTTPException(status_code=400, detail="Excel 缺少 name 列")

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row:
                continue
            name = row[name_idx] if name_idx is not None and name_idx < len(row) else None
            if not name:
                continue
            nodes.append(
                {
                    "name": str(name)[:100],
                    "description": (str(row[desc_idx]) if desc_idx is not None and desc_idx < len(row) and row[desc_idx] else "")[:2000],
                    "excerpt": "",
                    "parent_name": str(row[parent_idx]) if parent_idx is not None and parent_idx < len(row) and row[parent_idx] else None,
                }
            )
        wb.close()
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 json/xlsx")

    if not nodes:
        raise HTTPException(status_code=400, detail="文件中未找到有效知识点")

    # 解析 category/exam_type
    effective_category = category or "default"
    effective_exam_type = exam_type
    if category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
        if cat_obj:
            effective_category = cat_obj.code
    if exam_type_id:
        et_obj = db.query(ExamType).filter(ExamType.id == exam_type_id).first()
        if et_obj:
            effective_exam_type = et_obj.code

    # 验证父节点
    effective_parent_id = parent_id
    if effective_parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == effective_parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        if parent.category == "default" or not parent.category:
            parent.category = effective_category
        if effective_exam_type:
            parent.exam_type = effective_exam_type

    # 构建 parent_name -> id 映射
    name_to_id = {}
    if effective_parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == effective_parent_id).first()
        if parent:
            name_to_id[parent.name] = effective_parent_id

    # 创建知识点
    created = []
    for node in nodes:
        parent_name = node.get("parent_name")
        resolved_parent_id = effective_parent_id
        if parent_name and parent_name in name_to_id:
            resolved_parent_id = name_to_id[parent_name]
        elif parent_name:
            # 创建父节点
            parent_kp = KnowledgePoint(
                name=parent_name[:100],
                parent_id=effective_parent_id,
                category=effective_category,
                exam_type=effective_exam_type,
                order=len(created),
                status=1,
                created_by=current_user.id,
            )
            db.add(parent_kp)
            db.flush()
            name_to_id[parent_name] = parent_kp.id
            resolved_parent_id = parent_kp.id
            created.append(parent_kp)

        kp = KnowledgePoint(
            name=node["name"],
            parent_id=resolved_parent_id,
            category=effective_category,
            exam_type=effective_exam_type,
            description=node.get("description") or None,
            content_excerpt=node.get("excerpt") or None,
            order=len(created),
            status=1,
            created_by=current_user.id,
        )
        db.add(kp)
        db.flush()
        created.append(kp)

    db.commit()
    for kp in created:
        db.refresh(kp)

    return {
        "success": True,
        "message": f"成功导入 {len(created)} 个知识点",
        "created_count": len(created),
        "items": [
            {
                "id": kp.id,
                "name": kp.name,
                "parent_id": kp.parent_id,
            }
            for kp in created
        ],
    }


# reload trigger
