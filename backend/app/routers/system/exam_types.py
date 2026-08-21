"""System Router - Exam Category and Exam Type management endpoints"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import ExamCategory, ExamType, Subject
from app.models.user import User
from app.routers.system.schemas import (
    ExamCategoryCreate,
    ExamCategoryResponse,
    ExamCategoryUpdate,
    ExamTypeCreate,
    ExamTypeResponse,
    ExamTypeUpdate,
)
from app.utils.security import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Exam Categories ============


@router.get("/exam-categories")
def get_exam_categories(
    status: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取考试种类列表"""
    query = db.query(ExamCategory)
    if status is not None:
        query = query.filter(ExamCategory.status == status)
    categories = query.order_by(ExamCategory.id).all()
    items = [ExamCategoryResponse.model_validate(e) for e in categories]
    return {"items": items, "total": len(items)}


@router.post("/exam-categories", status_code=201)
def create_exam_category(
    data: ExamCategoryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建考试种类"""
    existing = db.query(ExamCategory).filter(ExamCategory.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="考试种类代码已存在")

    category = ExamCategory(
        name=data.name,
        code=data.code,
        description=data.description,
        status=data.status,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return ExamCategoryResponse.model_validate(category)


@router.put("/exam-categories/{category_id}")
def update_exam_category(
    category_id: int,
    data: ExamCategoryUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新考试种类"""
    category = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="考试种类不存在")

    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.status is not None:
        category.status = data.status

    db.commit()
    db.refresh(category)
    return ExamCategoryResponse.model_validate(category)


@router.delete("/exam-categories/{category_id}")
def delete_exam_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除考试种类"""
    category = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="考试种类不存在")

    db.delete(category)
    db.commit()
    return {"message": "删除成功"}


# ============ Exam Types ============


@router.get("/exam-types")
def get_exam_types(
    category_id: int | None = None,
    status: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取考试科目列表"""
    query = db.query(ExamType)
    if category_id is not None:
        query = query.filter(ExamType.category_id == category_id)
    if status is not None:
        query = query.filter(ExamType.status == status)
    exam_types = query.order_by(ExamType.id).all()
    items = [ExamTypeResponse.from_orm_with_types(e) for e in exam_types]
    return {"items": items, "total": len(items)}


@router.post("/exam-types", status_code=201)
def create_exam_type(
    data: ExamTypeCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建考试科目（同时创建对应的科目）"""
    existing = db.query(ExamType).filter(ExamType.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="考试科目代码已存在")

    # 先创建对应的科目
    subject = Subject(
        name=data.name,
        code=data.code,
        description=data.description or None,
        status=1,
    )
    db.add(subject)
    db.flush()

    exam_type = ExamType(
        category_id=data.category_id,
        subject_id=subject.id,
        name=data.name,
        code=data.code,
        level=data.level,
        description=data.description,
        duration=data.duration,
        total_score=data.total_score,
        passing_score=data.passing_score,
        question_types=json.dumps(data.question_types) if data.question_types else "[]",
        status=data.status,
    )
    db.add(exam_type)
    db.commit()
    db.refresh(exam_type)
    return ExamTypeResponse.from_orm_with_types(exam_type)


@router.put("/exam-types/{type_id}")
def update_exam_type(
    type_id: int,
    data: ExamTypeUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新考试科目"""
    exam_type = db.query(ExamType).filter(ExamType.id == type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="考试科目不存在")

    if data.category_id is not None:
        exam_type.category_id = data.category_id
    if data.name is not None:
        exam_type.name = data.name
    if data.level is not None:
        exam_type.level = data.level
    if data.description is not None:
        exam_type.description = data.description
    if data.duration is not None:
        exam_type.duration = data.duration
    if data.total_score is not None:
        exam_type.total_score = data.total_score
    if data.passing_score is not None:
        exam_type.passing_score = data.passing_score
    if data.question_types is not None:
        exam_type.question_types = json.dumps(data.question_types)
    if data.status is not None:
        exam_type.status = data.status

    db.commit()
    db.refresh(exam_type)
    return ExamTypeResponse.from_orm_with_types(exam_type)


@router.delete("/exam-types/{type_id}")
def delete_exam_type(
    type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除考试科目"""
    exam_type = db.query(ExamType).filter(ExamType.id == type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="考试科目不存在")

    db.delete(exam_type)
    db.commit()
    return {"message": "删除成功"}
