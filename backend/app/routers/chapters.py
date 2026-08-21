"""Chapters Router - CRUD for chapters with tree structure support"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import Chapter
from app.models.user import User
from app.schemas.question import ChapterCreate, ChapterResponse, ChapterTreeResponse, ChapterUpdate
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter()


@router.get("/subjects/{subject_id}/chapters", response_model=List[ChapterResponse])
def list_chapters(
    subject_id: int,
    tree: bool = Query(False, description="Return as tree structure"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all chapters for a subject (requires authentication)"""
    chapters = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id, Chapter.status == 1)
        .order_by(Chapter.order, Chapter.id)
        .all()
    )

    if tree:
        # Build tree structure
        chapter_dict = {c.id: c for c in chapters}
        root_chapters = []
        children_map = {}

        for c in chapters:
            if c.parent_id is None:
                root_chapters.append(c)
            else:
                if c.parent_id not in children_map:
                    children_map[c.parent_id] = []
                children_map[c.parent_id].append(c)

        def to_tree(chapter: Chapter) -> ChapterTreeResponse:
            kids = children_map.get(chapter.id, [])
            return ChapterTreeResponse(
                id=chapter.id,
                subject_id=chapter.subject_id,
                name=chapter.name,
                code=chapter.code,
                parent_id=chapter.parent_id,
                order=chapter.order,
                description=chapter.description,
                status=chapter.status,
                created_at=chapter.created_at,
                updated_at=chapter.updated_at,
                children=[to_tree(child) for child in kids],
            )

        return [to_tree(r) for r in root_chapters]

    return chapters


@router.post("/subjects/{subject_id}/chapters", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
def create_chapter(
    subject_id: int,
    chapter_data: ChapterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Create a new chapter for a subject (teacher/admin only)"""
    chapter = Chapter(
        subject_id=subject_id,
        name=chapter_data.name,
        code=chapter_data.code,
        parent_id=chapter_data.parent_id,
        order=chapter_data.order or 0,
        description=chapter_data.description,
        status=chapter_data.status if chapter_data.status is not None else 1,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.get("/{chapter_id}", response_model=ChapterResponse)
def get_chapter(chapter_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a chapter by ID (requires authentication)"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.put("/{chapter_id}", response_model=ChapterResponse)
def update_chapter(
    chapter_id: int,
    chapter_data: ChapterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update a chapter (teacher/admin only)"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    update_data = chapter_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)

    db.commit()
    db.refresh(chapter)
    return chapter


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_teacher_or_admin)
):
    """Delete a chapter - soft delete (teacher/admin only)"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    chapter.status = 0
    db.commit()
    return None
