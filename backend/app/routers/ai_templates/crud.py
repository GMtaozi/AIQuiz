"""AI Templates CRUD - Template management endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import AIPromptTemplate
from app.models.user import User
from app.schemas.question import AiTemplateCreate, AiTemplateResponse, AiTemplateUpdate
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_template_owner(template: AIPromptTemplate, current_user: User) -> None:
    """校验模板归属（评估 P1-10 修复）：管理员或创建者才能操作。"""
    if current_user.role != 1 and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模板")


@router.get("/templates", response_model=List[AiTemplateResponse])
def list_templates(
    template_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all AI prompt templates"""
    query = db.query(AIPromptTemplate)
    if template_type:
        query = query.filter(AIPromptTemplate.template_type == template_type)
    # 评估 P1-10 修复：非管理员只能看到活跃模板
    if current_user.role != 1:
        query = query.filter(AIPromptTemplate.status == "active")
    elif status:
        query = query.filter(AIPromptTemplate.status == status)
    else:
        query = query.filter(AIPromptTemplate.status == "active")
    return query.order_by(AIPromptTemplate.id).all()


@router.post("/templates", response_model=AiTemplateResponse, status_code=201)
def create_template(
    template_data: AiTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Create a new AI prompt template"""
    template = AIPromptTemplate(
        name=template_data.name,
        template_type=template_data.template_type,
        prompt_template=template_data.prompt_template,
        variables=template_data.variables,
        model=template_data.model or "abab6.5s-chat",
        config=template_data.config,
        status=template_data.status or "active",
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates/{template_id}", response_model=AiTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a template by ID"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    # 评估 P1-10 修复：非活跃模板仅创建者/管理员可查看
    if template.status != "active" and current_user.role != 1 and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该模板")
    return template


@router.put("/templates/{template_id}", response_model=AiTemplateResponse)
def update_template(
    template_id: int,
    template_data: AiTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update a template"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    _require_template_owner(template, current_user)
    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Delete a template (soft delete)"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    _require_template_owner(template, current_user)
    template.status = "inactive"
    db.commit()
    return None
