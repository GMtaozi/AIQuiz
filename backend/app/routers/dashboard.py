"""Dashboard Router - 仪表盘统计模块"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import ExamPaper, ExamRecord, GenerationTask, Question
from app.models.user import User
from app.schemas.dashboard import (
    ActivityItem,
    DashboardOverview,
    DifficultyDistribution,
    OverviewStats,
    QuestionTypeDistribution,
    TrendDataPoint,
)
from app.utils.security import get_current_user

router = APIRouter(tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_dashboard_overview(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘概览数据 - 优化查询"""
    from sqlalchemy import case

    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    # 使用单次查询获取所有基础统计
    # Question 基础统计
    question_stats = db.query(
        func.count(Question.id).label("total"),
        func.sum(case((Question.created_at >= today_start, 1), else_=0)).label("today"),
        func.sum(case((Question.audit_status == "pending", 1), else_=0)).label("pending"),
        func.sum(case((Question.is_ai_generated == True, 1), else_=0)).label("ai_generated"),
    ).first()

    total_questions = question_stats.total or 0
    today_questions = question_stats.today or 0
    pending_audit = question_stats.pending or 0
    ai_generated = question_stats.ai_generated or 0

    # 题型分布 - 单次 GROUP BY 查询
    type_dist_results = db.query(Question.question_type, func.count(Question.id)).group_by(Question.question_type).all()
    type_dist_dict = {r[0]: r[1] for r in type_dist_results}

    question_type_dist = QuestionTypeDistribution(
        single_choice=type_dist_dict.get("single_choice", 0),
        multiple_choice=type_dist_dict.get("multiple_choice", 0),
        true_false=type_dist_dict.get("true_false", 0),
        essay=type_dist_dict.get("essay", 0),
    )

    # 难度分布 - 单次查询
    difficulty_result = db.query(
        func.sum(case((Question.difficulty <= 2, 1), else_=0)).label("easy"),
        func.sum(case((Question.difficulty == 3, 1), else_=0)).label("medium"),
        func.sum(case((Question.difficulty >= 4, 1), else_=0)).label("hard"),
    ).first()

    difficulty_dist = DifficultyDistribution(
        easy=difficulty_result.easy or 0, medium=difficulty_result.medium or 0, hard=difficulty_result.hard or 0
    )

    # 其他基础统计
    total_papers = db.query(func.count(ExamPaper.id)).scalar() or 0
    total_exams = db.query(func.count(ExamRecord.id)).filter(ExamRecord.status == "graded").scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0

    # 今日考试
    today_exams = db.query(func.count(ExamRecord.id)).filter(ExamRecord.submitted_at >= today_start).scalar() or 0

    stats = OverviewStats(
        total_questions=total_questions,
        total_papers=total_papers,
        total_exams=total_exams,
        total_users=total_users,
        today_questions=today_questions,
        today_exams=today_exams,
        pending_audit=pending_audit,
        ai_generated=ai_generated,
    )

    # 题目趋势 - 优化为单次查询获取多天数据
    date_list = [today - timedelta(days=days - i - 1) for i in range(days)]
    date_strs = [d.strftime("%Y-%m-%d") for d in date_list]

    # 获取日期范围内的所有题目创建日期
    range_start = datetime.combine(date_list[0], datetime.min.time())
    range_end = datetime.combine(date_list[-1], datetime.max.time())

    trend_query = (
        db.query(func.date(Question.created_at).label("create_date"), func.count(Question.id).label("count"))
        .filter(Question.created_at >= range_start, Question.created_at <= range_end)
        .group_by(func.date(Question.created_at))
        .all()
    )

    trend_dict = {str(r[0]): r[1] for r in trend_query}
    question_trend = [TrendDataPoint(date=ds, count=trend_dict.get(ds, 0)) for ds in date_strs]

    # 最近活动（从数据库获取真实数据）

    # 获取最近创建的题目
    recent_questions = (
        db.query(Question.id, Question.content, Question.is_ai_generated, Question.created_at, User.username)
        .join(User, Question.created_by == User.id, isouter=True)
        .order_by(Question.created_at.desc())
        .limit(5)
        .all()
    )

    # 获取最近创建的试卷
    recent_papers = (
        db.query(ExamPaper.id, ExamPaper.title, ExamPaper.created_at, User.username)
        .join(User, ExamPaper.created_by == User.id, isouter=True)
        .order_by(ExamPaper.created_at.desc())
        .limit(3)
        .all()
    )

    # 获取最近完成的AI任务
    recent_ai_tasks = (
        db.query(
            GenerationTask.id, GenerationTask.status, GenerationTask.result, GenerationTask.created_at, User.username
        )
        .join(User, GenerationTask.user_id == User.id, isouter=True)
        .order_by(GenerationTask.created_at.desc())
        .limit(3)
        .all()
    )

    # 构建活动列表
    recent_activities = []
    activity_id = 1

    for q in recent_questions:
        if q.content:
            content_preview = q.content[:30] + "..." if len(q.content) > 30 else q.content
        else:
            content_preview = "题目"
        recent_activities.append(
            ActivityItem(
                id=activity_id,
                type="question_created",
                description=f"新增题目：{content_preview}",
                user=q.username or "系统",
                created_at=q.created_at,
            )
        )
        activity_id += 1

    for p in recent_papers:
        recent_activities.append(
            ActivityItem(
                id=activity_id,
                type="paper_created",
                description=f"创建试卷：{p.title}",
                user=p.username or "系统",
                created_at=p.created_at,
            )
        )
        activity_id += 1

    for t in recent_ai_tasks:
        status_text = "完成" if t.status == "completed" else "失败"
        recent_activities.append(
            ActivityItem(
                id=activity_id,
                type="ai_task",
                description=f"AI出题任务{status_text}",
                user=t.username or "系统",
                created_at=t.created_at,
            )
        )
        activity_id += 1

    # 按时间排序
    recent_activities.sort(key=lambda x: x.created_at, reverse=True)
    recent_activities = recent_activities[:10]  # 最多10条

    return DashboardOverview(
        stats=stats,
        question_trend=question_trend,
        question_type_dist=question_type_dist,
        difficulty_dist=difficulty_dist,
        recent_activities=recent_activities,
    )


@router.get("/question-trend")
def get_question_trend(
    period: str = Query("week", pattern="^(week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取题目趋势数据

    评估 P2-16：原实现按天循环 365 次串行 COUNT（year 时 365 次查询），
    改为单次 GROUP BY 聚合 + 内存补零，复杂度 O(1) 查询。
    """
    days = {"week": 7, "month": 30, "year": 365}[period]
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)

    rows = (
        db.query(func.date(Question.created_at).label("d"), func.count(Question.id))
        .filter(Question.created_at >= datetime.combine(start_date, datetime.min.time()))
        .group_by(func.date(Question.created_at))
        .all()
    )
    counts = {str(r[0]): r[1] for r in rows}

    trend = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        key = date.strftime("%Y-%m-%d")
        trend.append({"date": key, "count": counts.get(key, 0)})

    return {"trend": trend, "period": period}


@router.get("/exam-trend")
def get_exam_trend(
    period: str = Query("week", pattern="^(week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取考试趋势数据（单次 GROUP BY 聚合，评估 P2-16）"""
    days = {"week": 7, "month": 30, "year": 365}[period]
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)

    rows = (
        db.query(func.date(ExamRecord.submitted_at).label("d"), func.count(ExamRecord.id))
        .filter(ExamRecord.submitted_at >= datetime.combine(start_date, datetime.min.time()))
        .group_by(func.date(ExamRecord.submitted_at))
        .all()
    )
    counts = {str(r[0]): r[1] for r in rows}

    trend = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        key = date.strftime("%Y-%m-%d")
        trend.append({"date": key, "count": counts.get(key, 0)})

    return {"trend": trend, "period": period}


@router.get("/recent-activity")
def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最近活动（评估 P2-16：原实现返回硬编码假数据，改为真实数据源）

    数据源：最近创建的题目、最近创建的试卷、最近完成的考试记录。
    按 created_at 倒序合并取前 limit 条。
    """
    activities = []

    # 最近创建的题目
    questions = (
        db.query(Question, User)
        .outerjoin(User, Question.created_by == User.id)
        .order_by(Question.created_at.desc())
        .limit(limit)
        .all()
    )
    for q, creator in questions:
        activities.append(
            {
                "id": f"q{q.id}",
                "type": "question_created",
                "description": f"新增题目：{(q.content or '')[:30]}",
                "user": creator.username if creator else "system",
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
        )

    # 最近创建的试卷
    papers = (
        db.query(ExamPaper, User)
        .outerjoin(User, ExamPaper.created_by == User.id)
        .order_by(ExamPaper.created_at.desc())
        .limit(limit)
        .all()
    )
    for p, creator in papers:
        activities.append(
            {
                "id": f"p{p.id}",
                "type": "paper_created",
                "description": f"创建试卷：{p.title}",
                "user": creator.username if creator else "system",
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
        )

    # 最近提交的考试记录
    records = (
        db.query(ExamRecord, User)
        .outerjoin(User, ExamRecord.user_id == User.id)
        .filter(ExamRecord.submitted_at.isnot(None))
        .order_by(ExamRecord.submitted_at.desc())
        .limit(limit)
        .all()
    )
    for rec, user in records:
        activities.append(
            {
                "id": f"r{rec.id}",
                "type": "exam_submitted",
                "description": f"用户提交考试（记录 #{rec.id}）",
                "user": user.username if user else "system",
                "created_at": rec.submitted_at.isoformat() if rec.submitted_at else None,
            }
        )

    # 按时间倒序合并
    activities.sort(key=lambda a: a["created_at"] or "", reverse=True)
    return {"activities": activities[:limit]}
