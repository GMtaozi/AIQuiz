"""Knowledge CRUD routes: detail, create, update, delete."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import ExamCategory, ExamType
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgePointCreate,
    KnowledgePointResponse,
    KnowledgePointUpdate,
)
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.get("/{knowledge_id}")
def get_knowledge_point(
    knowledge_id: int,
    current_user: User = Depends(require_teacher_or_admin),
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
