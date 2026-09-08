"""Knowledge Bases Router - 知识库 CRUD 与文档上传"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.knowledge import KnowledgeBase, KnowledgeEntry, KnowledgePoint
from app.models.question import ExamCategory, ExamType
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeEntryBriefResponse,
    KnowledgeEntryResponse,
    UploadDocumentResponse,
)
from app.services.ai_knowledge_extractor import extract_knowledge_from_document
from app.services.document_parser import parse_document
from app.services.rule_knowledge_extractor import extract_knowledge_by_rules
from app.services.text_chunker import chunk_document
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# 支持的文档格式
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "md", "markdown", "txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _resolve_category_exam_type(
    db: Session,
    category: str | None,
    category_id: int | None,
    exam_type: str | None,
    exam_type_id: int | None,
) -> tuple[str | None, str | None]:
    """将 category_id/exam_type_id 解析为 code，优先用 ID 查询"""
    resolved_category = category
    if category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
        if cat_obj:
            resolved_category = cat_obj.code
    resolved_exam_type = exam_type
    if exam_type_id:
        et_obj = db.query(ExamType).filter(ExamType.id == exam_type_id).first()
        if et_obj:
            resolved_exam_type = et_obj.code
    return resolved_category, resolved_exam_type


def _require_kb_owner(kb: KnowledgeBase, current_user: User) -> None:
    """校验知识库归属（评估 P1-10 修复）：管理员或创建者才能操作。"""
    if current_user.role != 1 and kb.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该知识库")


def _kb_to_response(kb: KnowledgeBase, db: Session) -> KnowledgeBaseResponse:
    """将 KnowledgeBase ORM 对象转换为响应模型，附带统计数"""
    entries_count = db.query(KnowledgeEntry).filter(KnowledgeEntry.knowledge_base_id == kb.id).count()
    points_count = db.query(KnowledgePoint).filter(KnowledgePoint.knowledge_base_id == kb.id).count()
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        subject_id=kb.subject_id,
        category=kb.category,
        exam_type=kb.exam_type,
        visibility=kb.visibility,
        source_file=kb.source_file,
        source_content=kb.source_content,
        status=kb.status,
        created_by=kb.created_by,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        entries_count=entries_count,
        points_count=points_count,
    )


@router.post("/", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """创建知识库"""
    resolved_category, resolved_exam_type = _resolve_category_exam_type(db, data.category, None, data.exam_type, None)
    kb = KnowledgeBase(
        name=data.name,
        description=data.description,
        subject_id=data.subject_id,
        category=resolved_category or "default",
        exam_type=resolved_exam_type,
        visibility=data.visibility,
        created_by=current_user.id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    logger.info("知识库创建: id=%s name=%s by user=%s", kb.id, kb.name, current_user.id)
    return _kb_to_response(kb, db)


@router.get("/", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    subject_id: int | None = Query(None),
    category: str | None = Query(None),
    exam_type: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """知识库列表（分页，可按科目/分类/关键字过滤）"""
    query = db.query(KnowledgeBase).filter(KnowledgeBase.status == 1)

    # 权限过滤：非管理员只能看 public/shared 和自己创建的
    if current_user.role != 1:  # 1=admin
        query = query.filter(
            (KnowledgeBase.visibility == "public")
            | (KnowledgeBase.visibility == "shared")
            | (KnowledgeBase.created_by == current_user.id)
        )

    if subject_id:
        query = query.filter(KnowledgeBase.subject_id == subject_id)
    if category:
        query = query.filter(KnowledgeBase.category == category)
    if exam_type:
        query = query.filter(KnowledgeBase.exam_type == exam_type)
    if keyword:
        query = query.filter(KnowledgeBase.name.ilike(f"%{keyword}%"))

    total = query.count()
    items = query.order_by(KnowledgeBase.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return KnowledgeBaseListResponse(
        items=[_kb_to_response(kb, db) for kb in items],
        total=total,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库详情"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 评估 P1-10 修复：与列表接口口径一致——非管理员只能访问公开/共享/自己创建的知识库
    if current_user.role != 1 and kb.visibility not in ("public", "shared") and kb.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该知识库")

    return _kb_to_response(kb, db)


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """更新知识库"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    _require_kb_owner(kb, current_user)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kb, field, value)

    db.commit()
    db.refresh(kb)
    logger.info("知识库更新: id=%s by user=%s", kb.id, current_user.id)
    return _kb_to_response(kb, db)


@router.delete("/{kb_id}")
def delete_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """删除知识库（软删除：status=0，级联软删 entries，知识点解绑）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    _require_kb_owner(kb, current_user)

    try:
        # 软删知识库
        kb.status = 0
        # 软删关联条目（条目无 status 字段，物理删除）
        db.query(KnowledgeEntry).filter(KnowledgeEntry.knowledge_base_id == kb_id).delete(synchronize_session=False)
        # 解绑知识点（不删知识点，仅清除关联）
        db.query(KnowledgePoint).filter(KnowledgePoint.knowledge_base_id == kb_id).update(
            {KnowledgePoint.knowledge_base_id: None, KnowledgePoint.entry_id: None},
            synchronize_session=False,
        )
        db.commit()
        logger.info("知识库删除: id=%s by user=%s", kb_id, current_user.id)
    except Exception:
        db.rollback()
        logger.exception("知识库删除失败: id=%s", kb_id)
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试")

    return {"success": True, "message": "知识库已删除"}


@router.post("/{kb_id}/upload", response_model=UploadDocumentResponse)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """上传文档到知识库

    流程：parse_document -> chunk_document -> 存 KnowledgeEntry + 更新 source_content
    """
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    _require_kb_owner(kb, current_user)

    # 读取文件内容
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}")

    try:
        # 解析文档为纯文本
        text_content = parse_document(content, ext, filename)
        if len(text_content.strip()) < 50:
            raise HTTPException(status_code=400, detail="文档内容过少或无法提取文本")

        # 分块
        chunks = chunk_document(text_content, max_chunk_size=3000, min_chunk_size=500)
        if not chunks:
            raise HTTPException(status_code=400, detail="文档分块失败，未生成任何条目")

        # 删除旧条目（重新上传时）
        db.query(KnowledgeEntry).filter(KnowledgeEntry.knowledge_base_id == kb_id).delete(synchronize_session=False)

        # 创建条目
        for chunk in chunks:
            entry = KnowledgeEntry(
                knowledge_base_id=kb_id,
                title=chunk["title"],
                content=chunk["content"],
                order=chunk["order"],
                source_location=chunk["source_location"],
            )
            db.add(entry)

        # 更新知识库的全文和文件名
        kb.source_content = text_content
        kb.source_file = filename

        db.commit()
        logger.info(
            "文档上传成功: kb_id=%s file=%s entries=%d chars=%d",
            kb_id,
            filename,
            len(chunks),
            len(text_content),
        )
        return UploadDocumentResponse(
            success=True,
            message=f"文档上传成功，生成 {len(chunks)} 个知识条目",
            source_file=filename,
            entries_created=len(chunks),
            total_chars=len(text_content),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("文档上传失败: kb_id=%s", kb_id)
        raise HTTPException(status_code=500, detail="文档上传失败，请稍后重试") from e


@router.get("/{kb_id}/entries", response_model=list[KnowledgeEntryBriefResponse])
def list_entries(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出知识库的所有条目（简要信息，不含全文）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 评估 P1-10 修复：与列表接口口径一致——非管理员只能访问公开/共享/自己创建的知识库
    if current_user.role != 1 and kb.visibility not in ("public", "shared") and kb.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该知识库")

    entries = (
        db.query(KnowledgeEntry).filter(KnowledgeEntry.knowledge_base_id == kb_id).order_by(KnowledgeEntry.order).all()
    )
    return [
        KnowledgeEntryBriefResponse(
            id=e.id,
            knowledge_base_id=e.knowledge_base_id,
            title=e.title,
            order=e.order,
            source_location=e.source_location,
            content_preview=e.content[:200] if e.content else "",
            content_length=len(e.content) if e.content else 0,
        )
        for e in entries
    ]


@router.get("/{kb_id}/entries/{entry_id}", response_model=KnowledgeEntryResponse)
def get_entry(
    kb_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个条目详情（含全文）"""
    entry = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.id == entry_id, KnowledgeEntry.knowledge_base_id == kb_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")

    # 评估 P1-10 修复：与列表接口口径一致——非管理员只能访问公开/共享/自己创建的知识库
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if kb and current_user.role != 1 and kb.visibility not in ("public", "shared") and kb.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该知识库")

    return entry


@router.get("/{kb_id}/points")
def list_knowledge_points(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出知识库下所有知识点（树形结构）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 评估 P1-10 修复：与列表接口口径一致——非管理员只能访问公开/共享/自己创建的知识库
    if current_user.role != 1 and kb.visibility not in ("public", "shared") and kb.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该知识库")

    points = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.knowledge_base_id == kb_id, KnowledgePoint.status == 1)
        .order_by(KnowledgePoint.order)
        .all()
    )

    # 构建树
    point_map = {p.id: {"id": p.id, "name": p.name, "description": p.description, "children": []} for p in points}
    tree = []
    for p in points:
        node = point_map[p.id]
        if p.parent_id and p.parent_id in point_map:
            point_map[p.parent_id]["children"].append(node)
        else:
            tree.append(node)

    return {"success": True, "knowledge_points": tree, "total": len(points)}


# ---------------------------------------------------------------------------
# 从知识库条目提取知识点
# ---------------------------------------------------------------------------


class AnalyzeEntryRequest(BaseModel):
    """从条目提取知识点的请求"""

    mode: str = "ai"  # "ai" / "rule" / "auto"（auto = 先规则后 AI 补充）
    max_points: int = 50


class ImportPointsRequest(BaseModel):
    """确认导入提取的知识点"""

    knowledge_points: List[dict]
    parent_id: int | None = None


def _get_kb_or_404(db: Session, kb_id: int) -> KnowledgeBase:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.status == 1).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


def _get_entry_or_404(db: Session, kb_id: int, entry_id: int) -> KnowledgeEntry:
    entry = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.id == entry_id, KnowledgeEntry.knowledge_base_id == kb_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return entry


@router.post("/{kb_id}/entries/{entry_id}/analyze")
async def analyze_entry(
    kb_id: int,
    entry_id: int,
    request: AnalyzeEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """从单个知识条目提取知识点（AI/规则），返回预览树，不写入数据库

    提取时喂 entry.content（单条目 1000-3000 字），而非全文，解决大文件上下文溢出。
    """
    kb = _get_kb_or_404(db, kb_id)
    entry = _get_entry_or_404(db, kb_id, entry_id)
    _require_kb_owner(kb, current_user)

    content = entry.content
    if len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="条目内容过少，无法提取知识点")

    mode = request.mode
    if mode == "auto":
        # 先规则提取
        rule_result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
        # 再用 AI 补充优化
        try:
            ai_result = await extract_knowledge_from_document(
                document_content=content,
                document_name=entry.title,
                max_points=request.max_points,
                category=kb.category,
            )
            if ai_result.get("success") and ai_result.get("knowledge_points"):
                points = ai_result["knowledge_points"]
                total = ai_result["total"]
                method = "ai"
            else:
                points = rule_result["knowledge_points"]
                total = rule_result["total"]
                method = "rule-based"
        except Exception:
            logger.exception("AI 提取失败，回退到规则提取")
            points = rule_result["knowledge_points"]
            total = rule_result["total"]
            method = "rule-based (ai failed)"
    elif mode == "rule":
        result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
        points = result["knowledge_points"]
        total = result["total"]
        method = "rule-based"
    else:  # ai
        result = await extract_knowledge_from_document(
            document_content=content,
            document_name=entry.title,
            max_points=request.max_points,
            category=kb.category,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=f"AI 提取失败: {result.get('error', '未知错误')}")
        points = result["knowledge_points"]
        total = result["total"]
        method = "ai"

    return {
        "success": True,
        "knowledge_points": points,
        "total": total,
        "method": method,
        "entry_id": entry_id,
        "entry_title": entry.title,
        "source_location": entry.source_location,
    }


@router.post("/{kb_id}/entries/{entry_id}/import")
def import_points_from_entry(
    kb_id: int,
    entry_id: int,
    request: ImportPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """确认导入从条目提取的知识点，创建 KnowledgePoint（带 kb_id + entry_id + excerpt）"""
    kb = _get_kb_or_404(db, kb_id)
    entry = _get_entry_or_404(db, kb_id, entry_id)
    _require_kb_owner(kb, current_user)

    if not request.knowledge_points:
        raise HTTPException(status_code=400, detail="知识点列表不能为空")

    created_count = 0

    def create_nodes(nodes: List[dict], parent_id: int | None = None):
        nonlocal created_count
        for node in nodes:
            name = node.get("name") or node.get("名称", "未命名")
            description = node.get("description") or node.get("描述", "")
            excerpt = node.get("excerpt") or node.get("原文", "")
            children = node.get("children") or node.get("子节点", [])

            kp = KnowledgePoint(
                name=name[:100],
                parent_id=parent_id,
                category=kb.category,
                exam_type=kb.exam_type,
                subject_id=kb.subject_id,
                description=description[:2000] if description else None,
                content_excerpt=excerpt[:2000] if excerpt else None,
                knowledge_base_id=kb_id,
                entry_id=entry_id,
                order=created_count,
                status=1,
                created_by=current_user.id,
            )
            db.add(kp)
            db.flush()
            created_count += 1

            if children and isinstance(children, list):
                create_nodes(children, parent_id=kp.id)

    try:
        create_nodes(request.knowledge_points, parent_id=request.parent_id)
        db.commit()
        logger.info(
            "从条目导入知识点: kb_id=%s entry_id=%s count=%d by user=%s",
            kb_id,
            entry_id,
            created_count,
            current_user.id,
        )
        return {
            "success": True,
            "created_count": created_count,
            "message": f"成功导入 {created_count} 个知识点",
        }
    except Exception:
        db.rollback()
        logger.exception("知识点导入失败: kb_id=%s entry_id=%s", kb_id, entry_id)
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")


@router.post("/{kb_id}/analyze-all")
async def analyze_all_entries(
    kb_id: int,
    request: AnalyzeEntryRequest = Body(default=AnalyzeEntryRequest(mode="auto", max_points=50)),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """批量分析知识库中的所有条目，返回汇总预览（不写入数据库）

    对每个条目执行规则/AI 提取，返回每个条目的知识点数量和总体统计。
    """
    kb = _get_kb_or_404(db, kb_id)
    _require_kb_owner(kb, current_user)
    entries = db.query(KnowledgeEntry).filter(KnowledgeEntry.knowledge_base_id == kb_id).all()
    if not entries:
        return {
            "success": True,
            "total_entries": 0,
            "results": [],
            "total_points": 0,
            "message": "知识库暂无条目",
        }

    results = []
    total_points = 0

    for entry in entries:
        content = entry.content or ""
        if len(content.strip()) < 20:
            results.append(
                {
                    "entry_id": entry.id,
                    "entry_title": entry.title,
                    "success": False,
                    "error": "条目内容过少，无法提取",
                    "knowledge_points": [],
                    "total": 0,
                    "method": None,
                }
            )
            continue

        method = "rule-based"
        points: List[Dict[str, Any]] = []
        total = 0

        if request.mode == "rule":
            rule_result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
            points = rule_result.get("knowledge_points", [])
            total = rule_result.get("total", 0)
            method = "rule-based"
        elif request.mode == "ai":
            try:
                ai_result = await extract_knowledge_from_document(
                    document_content=content,
                    document_name=entry.title,
                    max_points=request.max_points,
                    category=kb.category,
                )
                if ai_result.get("success") and ai_result.get("knowledge_points"):
                    points = ai_result["knowledge_points"]
                    total = ai_result["total"]
                    method = "ai"
                else:
                    rule_result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
                    points = rule_result.get("knowledge_points", [])
                    total = rule_result.get("total", 0)
                    method = "rule-based (ai failed)"
            except Exception:
                logger.exception("AI 提取失败: kb_id=%s entry_id=%s", kb_id, entry.id)
                rule_result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
                points = rule_result.get("knowledge_points", [])
                total = rule_result.get("total", 0)
                method = "rule-based (ai failed)"
        else:
            # auto: 先规则，再 AI 补充
            rule_result = extract_knowledge_by_rules(content, max_children=6, max_depth=3)
            points = rule_result.get("knowledge_points", [])
            total = rule_result.get("total", 0)
            method = "rule-based"
            try:
                ai_result = await extract_knowledge_from_document(
                    document_content=content,
                    document_name=entry.title,
                    max_points=request.max_points,
                    category=kb.category,
                )
                if ai_result.get("success") and ai_result.get("knowledge_points"):
                    points = ai_result["knowledge_points"]
                    total = ai_result["total"]
                    method = "ai"
            except Exception:
                logger.exception("AI 提取失败: kb_id=%s entry_id=%s", kb_id, entry.id)

        results.append(
            {
                "entry_id": entry.id,
                "entry_title": entry.title,
                "success": True,
                "knowledge_points": points,
                "total": total,
                "method": method,
            }
        )
        total_points += total

    return {
        "success": True,
        "total_entries": len(entries),
        "results": results,
        "total_points": total_points,
        "message": f"批量分析完成，共 {len(entries)} 个条目，提取 {total_points} 个知识点",
    }
