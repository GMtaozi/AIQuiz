"""Subjects Router - CRUD for subjects"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.question import SubjectCreate, SubjectUpdate, SubjectResponse
from app.models.question import Subject
from app.models.user import User
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter()


@router.get("/", response_model=List[SubjectResponse])
def list_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all subjects (requires authentication)"""
    subjects = db.query(Subject).filter(Subject.status == 1).order_by(Subject.id).all()
    return subjects


@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    subject_data: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin)
):
    """Create a new subject (teacher/admin only)"""
    existing = db.query(Subject).filter(Subject.code == subject_data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Subject code already exists")

    subject = Subject(
        name=subject_data.name,
        code=subject_data.code,
        description=subject_data.description,
        status=subject_data.status if subject_data.status is not None else 1,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a subject by ID (requires authentication)"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.put("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin)
):
    """Update a subject (teacher/admin only)"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    update_data = subject_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subject, field, value)

    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin)
):
    """Delete a subject - soft delete by setting status to inactive (teacher/admin only)"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject.status = 0
    db.commit()
    return None