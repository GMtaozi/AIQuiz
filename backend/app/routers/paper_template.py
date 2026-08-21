"""Paper Template Router - 试卷模板管理模块"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper_template import PaperTemplate
from app.models.user import User
from app.schemas.paper_template import PaperTemplateCreate, PaperTemplateResponse, PaperTemplateUpdate
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter(tags=["paper-templates"])


# ============ 模板市场 ============


@router.get("/marketplace")
def marketplace_templates(
    subject_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """模板市场：浏览公开模板"""
    query = db.query(PaperTemplate).filter(
        PaperTemplate.is_deleted == False,
        PaperTemplate.is_public == True,
    )

    if subject_id is not None:
        query = query.filter(PaperTemplate.subject_id == subject_id)

    query = query.order_by(PaperTemplate.usage_count.desc(), PaperTemplate.rating.desc())

    total = query.count()
    templates = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for t in templates:
        items.append(
            PaperTemplateResponse(
                id=t.id,
                name=t.name,
                subject_id=t.subject_id,
                description=t.description,
                config=t.question_distribution or {},
                status=t.status,
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at,
                total_score=t.total_score,
                duration=t.duration,
                is_public=t.is_public,
                rating=t.rating,
                usage_count=t.usage_count,
            )
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/recommend")
def recommend_templates(
    subject_id: int | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """推荐模板（按使用量 + 评分综合排序）"""
    query = db.query(PaperTemplate).filter(
        PaperTemplate.is_deleted == False,
        PaperTemplate.is_public == True,
    )

    if subject_id is not None:
        query = query.filter(PaperTemplate.subject_id == subject_id)

    templates = query.order_by(PaperTemplate.usage_count.desc(), PaperTemplate.rating.desc()).limit(limit).all()

    items = []
    for t in templates:
        items.append(
            PaperTemplateResponse(
                id=t.id,
                name=t.name,
                subject_id=t.subject_id,
                description=t.description,
                config=t.question_distribution or {},
                status=t.status,
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at,
                total_score=t.total_score,
                duration=t.duration,
                is_public=t.is_public,
                rating=t.rating,
                usage_count=t.usage_count,
            )
        )

    return {"items": items}


@router.post("/{template_id}/use")
def use_template(
    template_id: int,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """使用模板创建新试卷（基于模板配置初始化）"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权使用该私有模板")

    # 增加使用次数
    template.usage_count = (template.usage_count or 0) + 1
    db.commit()

    return {
        "template_id": template.id,
        "name": template.name,
        "subject_id": template.subject_id,
        "config": template.question_distribution or {},
        "total_score": template.total_score,
        "duration": template.duration,
        "message": "模板已加载，请继续配置试卷",
    }


@router.post("/{template_id}/rate")
def rate_template(
    template_id: int,
    rating: float = Query(..., ge=0, le=5),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """给模板评分（0-5分）"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 简单平均评分更新（生产环境应记录用户评分历史）
    old_rating = template.rating or 0
    old_count = template.usage_count or 0
    template.rating = round((old_rating * old_count + rating) / (old_count + 1), 2)
    template.usage_count = old_count + 1

    db.commit()
    return {"rating": template.rating}


@router.post("/{template_id}/share")
def share_template(
    template_id: int,
    shared_with: list[int] | None = None,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """共享模板给指定用户"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建者才能共享模板")

    template.is_public = True
    template.shared_with = shared_with or []
    db.commit()

    return {"message": "共享设置已更新", "shared_with": template.shared_with}


# ============ 原有 CRUD ============


@router.get("/")
def list_templates(
    subject_id: int | None = None,
    status: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取试卷模板列表"""
    query = db.query(PaperTemplate).filter(PaperTemplate.is_deleted == False)

    # 评估 P1-10 修复：非管理员只能看到公开模板与自己创建的模板
    if current_user.role != 1:
        query = query.filter((PaperTemplate.is_public == True) | (PaperTemplate.created_by == current_user.id))

    if subject_id is not None:
        query = query.filter(PaperTemplate.subject_id == subject_id)
    if status is not None:
        query = query.filter(PaperTemplate.status == status)

    total = query.count()
    templates = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for t in templates:
        items.append(
            PaperTemplateResponse(
                id=t.id,
                name=t.name,
                subject_id=t.subject_id,
                description=t.description,
                config=t.question_distribution or {},
                status=t.status,
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at,
                total_score=t.total_score,
                duration=t.duration,
                is_public=t.is_public,
                rating=t.rating,
                usage_count=t.usage_count,
            )
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{template_id}")
def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取模板详情"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 评估 P1-10 修复：非管理员只能访问公开模板或自己创建的模板
    if current_user.role != 1 and not template.is_public and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该模板")

    return PaperTemplateResponse(
        id=template.id,
        name=template.name,
        subject_id=template.subject_id,
        description=template.description,
        config=template.question_distribution or {},
        status=template.status,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        total_score=template.total_score,
        duration=template.duration,
        is_public=template.is_public,
        rating=template.rating,
        usage_count=template.usage_count,
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
        created_by=current_user.id,
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
        updated_at=new_template.updated_at,
        total_score=new_template.total_score,
        duration=new_template.duration,
        is_public=new_template.is_public,
        rating=new_template.rating,
        usage_count=new_template.usage_count,
    )


@router.put("/{template_id}")
def update_template(
    template_id: int,
    data: PaperTemplateUpdate,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """更新试卷模板"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 评估 P1-10 修复：非管理员只能修改自己创建的模板
    if current_user.role != 1 and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改该模板")

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.config is not None:
        template.question_distribution = data.config
    if data.status is not None:
        template.status = data.status
    if data.is_public is not None:
        template.is_public = data.is_public
    if data.shared_with is not None:
        template.shared_with = data.shared_with

    db.commit()
    db.refresh(template)

    return PaperTemplateResponse(
        id=template.id,
        name=template.name,
        subject_id=template.subject_id,
        description=template.description,
        config=template.question_distribution or {},
        status=template.status,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        total_score=template.total_score,
        duration=template.duration,
        is_public=template.is_public,
        rating=template.rating,
        usage_count=template.usage_count,
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """删除试卷模板（软删除）"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 评估 P1-10 修复：非管理员只能删除自己创建的模板
    if current_user.role != 1 and template.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该模板")

    template.is_deleted = True
    template.status = 0
    db.commit()

    return {"message": "模板已删除"}


@router.post("/{template_id}/duplicate")
def duplicate_template(
    template_id: int,
    new_name: str | None = None,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """复制模板"""
    template = (
        db.query(PaperTemplate).filter(PaperTemplate.id == template_id, PaperTemplate.is_deleted == False).first()
    )
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
        updated_at=new_template.updated_at,
        total_score=new_template.total_score,
        duration=new_template.duration,
        is_public=new_template.is_public,
        rating=new_template.rating,
        usage_count=new_template.usage_count,
    )
