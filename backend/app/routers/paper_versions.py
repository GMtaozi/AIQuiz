"""Paper Version Router - 试卷版本管理"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper_version import PaperVersion
from app.models.user import User
from app.schemas.paper_version import PaperVersionCreate, PaperVersionListResponse, PaperVersionResponse
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter(tags=["paper-versions"])


@router.get("/{paper_id}/versions", response_model=PaperVersionListResponse)
def get_paper_versions(
    paper_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取试卷版本历史"""
    query = db.query(PaperVersion).filter(PaperVersion.paper_id == paper_id)
    query = query.order_by(PaperVersion.version_number.desc())

    total = query.count()
    versions = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [
        PaperVersionResponse(
            id=v.id,
            paper_id=v.paper_id,
            version_number=v.version_number,
            title=v.title,
            description=v.description,
            change_log=v.change_log,
            created_by=v.created_by,
            created_at=v.created_at,
            config=v.config,
            questions_snapshot=v.questions_snapshot,
        )
        for v in versions
    ]

    return PaperVersionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{paper_id}/versions", status_code=201)
def create_paper_version(
    paper_id: int,
    data: PaperVersionCreate,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """创建试卷版本快照"""
    from app.models.question import ExamPaper, ExamPaperQuestion

    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 获取当前版本号
    last_version = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper_id)
        .order_by(PaperVersion.version_number.desc())
        .first()
    )
    next_version = (last_version.version_number + 1) if last_version else 1

    # 构建题目快照
    questions = (
        db.query(ExamPaperQuestion)
        .filter(ExamPaperQuestion.exam_paper_id == paper_id)
        .order_by(ExamPaperQuestion.order)
        .all()
    )
    questions_snapshot = [
        {
            "question_id": q.question_id,
            "order": q.order,
            "score": q.score,
        }
        for q in questions
    ]

    version = PaperVersion(
        paper_id=paper_id,
        version_number=next_version,
        title=data.title,
        description=data.description,
        change_log=data.change_log,
        config=paper.config,
        questions_snapshot=questions_snapshot,
        created_by=current_user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    return PaperVersionResponse(
        id=version.id,
        paper_id=version.paper_id,
        version_number=version.version_number,
        title=version.title,
        description=version.description,
        change_log=version.change_log,
        created_by=version.created_by,
        created_at=version.created_at,
        config=version.config,
        questions_snapshot=version.questions_snapshot,
    )


@router.get("/{paper_id}/versions/{version_id}")
def get_paper_version(
    paper_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个版本详情"""
    version = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper_id, PaperVersion.id == version_id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    return PaperVersionResponse(
        id=version.id,
        paper_id=version.paper_id,
        version_number=version.version_number,
        title=version.title,
        description=version.description,
        change_log=version.change_log,
        created_by=version.created_by,
        created_at=version.created_at,
        config=version.config,
        questions_snapshot=version.questions_snapshot,
    )


@router.post("/{paper_id}/versions/{version_id}/restore")
def restore_paper_version(
    paper_id: int,
    version_id: int,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """回滚到指定版本"""
    from app.models.question import ExamPaper, ExamPaperQuestion

    version = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper_id, PaperVersion.id == version_id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 恢复配置
    if version.config:
        paper.config = version.config

    # 恢复题目列表
    if version.questions_snapshot:
        db.query(ExamPaperQuestion).filter(ExamPaperQuestion.exam_paper_id == paper_id).delete()
        for idx, q in enumerate(version.questions_snapshot):
            epq = ExamPaperQuestion(
                exam_paper_id=paper_id,
                question_id=q["question_id"],
                order=idx,
                score=q.get("score", 0),
            )
            db.add(epq)

    db.commit()
    db.refresh(paper)

    return {"message": f"已回滚到版本 {version.version_number}", "version": version.version_number}


@router.get("/{paper_id}/versions/{version_id}/compare")
def compare_paper_version(
    paper_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对比指定版本与当前版本的差异"""
    from app.models.question import ExamPaperQuestion

    target_version = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper_id, PaperVersion.id == version_id)
        .first()
    )
    if not target_version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 当前题目
    current_questions = (
        db.query(ExamPaperQuestion)
        .filter(ExamPaperQuestion.exam_paper_id == paper_id)
        .order_by(ExamPaperQuestion.order)
        .all()
    )
    current_map = {q.question_id: q for q in current_questions}
    current_ids = set(current_map.keys())

    # 目标版本题目
    target_snapshot = target_version.questions_snapshot or []
    target_ids = {q["question_id"] for q in target_snapshot}

    added = list(target_ids - current_ids)
    removed = list(current_ids - target_ids)
    modified = []

    for q in target_snapshot:
        qid = q["question_id"]
        if qid in current_map:
            current_q = current_map[qid]
            if current_q.order != q["order"] or current_q.score != q.get("score", 0):
                modified.append(
                    {
                        "question_id": qid,
                        "old_order": current_q.order,
                        "new_order": q["order"],
                        "old_score": current_q.score,
                        "new_score": q.get("score", 0),
                    }
                )

    summary = (
        f"新增 {len(added)} 题，"
        f"删除 {len(removed)} 题，"
        f"修改 {len(modified)} 题（顺序/分值）"
    )

    return {
        "target_version": target_version.version_number,
        "added_questions": added,
        "removed_questions": removed,
        "modified_questions": modified,
        "summary": summary,
    }
