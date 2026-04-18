"""Paper Template Router - 试卷模板管理模块"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.paper_template import PaperTemplate
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter(tags=["paper-templates"])

# ============ Schema ============

class PaperTemplateCreate(BaseModel):
    name: str
    subject_id: int
    description: Optional[str] = None
    config: dict = {}  # 模板配置
    status: int = 1


class PaperTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[int] = None


class PaperTemplateResponse(BaseModel):
    id: int
    name: str
    subject_id: int
    description: Optional[str]
    config: dict
    status: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Router ============

@router.get("/")
def list_templates(
    subject_id: Optional[int] = None,
    status: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取试卷模板列表"""
    query = db.query(PaperTemplate).filter(PaperTemplate.is_deleted == False)

    if subject_id is not None:
        query = query.filter(PaperTemplate.subject_id == subject_id)
    if status is not None:
        query = query.filter(PaperTemplate.status == status)

    total = query.count()
    templates = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for t in templates:
        items.append(PaperTemplateResponse(
            id=t.id,
            name=t.name,
            subject_id=t.subject_id,
            description=t.description,
            config=t.question_distribution or {},
            status=t.status,
            created_by=None,
            created_at=t.created_at,
            updated_at=t.updated_at
        ))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{template_id}")
def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取模板详情"""
    template = db.query(PaperTemplate).filter(
        PaperTemplate.id == template_id,
        PaperTemplate.is_deleted == False
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return PaperTemplateResponse(
        id=template.id,
        name=template.name,
        subject_id=template.subject_id,
        description=template.description,
        config=template.question_distribution or {},
        status=template.status,
        created_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


@router.post("/", status_code=201)
def create_template(
    data: PaperTemplateCreate,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """创建试卷模板"""
    new_template = PaperTemplate(
        name=data.name,
        subject_id=data.subject_id,
        description=data.description,
        question_distribution=data.config,
        status=data.status,
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    return PaperTemplateResponse(
        id=new_template.id,
        name=new_template.name,
        subject_id=new_template.subject_id,
        description=new_template.description,
        config=new_template.question_distribution or {},
        status=new_template.status,
        created_by=current_user.id,
        created_at=new_template.created_at,
        updated_at=new_template.updated_at
    )


@router.put("/{template_id}")
def update_template(
    template_id: int,
    data: PaperTemplateUpdate,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """更新试卷模板"""
    template = db.query(PaperTemplate).filter(
        PaperTemplate.id == template_id,
        PaperTemplate.is_deleted == False
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.config is not None:
        template.question_distribution = data.config
    if data.status is not None:
        template.status = data.status

    db.commit()
    db.refresh(template)

    return PaperTemplateResponse(
        id=template.id,
        name=template.name,
        subject_id=template.subject_id,
        description=template.description,
        config=template.question_distribution or {},
        status=template.status,
        created_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """删除试卷模板（软删除）"""
    template = db.query(PaperTemplate).filter(
        PaperTemplate.id == template_id,
        PaperTemplate.is_deleted == False
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    template.is_deleted = True
    template.status = 0
    db.commit()

    return {"message": "模板已删除"}


@router.post("/{template_id}/duplicate")
def duplicate_template(
    template_id: int,
    new_name: Optional[str] = None,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """复制模板"""
    template = db.query(PaperTemplate).filter(
        PaperTemplate.id == template_id,
        PaperTemplate.is_deleted == False
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    new_template = PaperTemplate(
        name=new_name or f"{template.name} (副本)",
        subject_id=template.subject_id,
        description=template.description,
        question_distribution=template.question_distribution,
        total_score=template.total_score,
        duration=template.duration,
        status=1,
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    return PaperTemplateResponse(
        id=new_template.id,
        name=new_template.name,
        subject_id=new_template.subject_id,
        description=new_template.description,
        config=new_template.question_distribution or {},
        status=new_template.status,
        created_by=current_user.id,
        created_at=new_template.created_at,
        updated_at=new_template.updated_at
    )
