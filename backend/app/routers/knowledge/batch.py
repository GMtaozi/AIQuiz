"""Batch document processing routes: batch analyze, batch import."""

import logging
import re
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import ExamCategory, ExamType
from app.models.user import User
from app.schemas.knowledge import BatchImportRequest
from app.services.batch_document_processor import BatchDocumentProcessor
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])

batch_processor = BatchDocumentProcessor()


@router.post("/batch/analyze")
async def batch_analyze_documents(
    files: List[UploadFile] = File(...),
    subject_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    exam_type: str = Form(default=""),
    exam_type_id: str = Form(default=""),
    parent_kp_id: str = Form(default=""),
    extraction_mode: str = Form(default="auto"),
    max_points_per_doc: int = Form(default=50),
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量分析多个文档，返回每个文档的知识点树

    支持格式：PDF, Word(.docx), Markdown(.md), TXT
    每个文档独立处理，生成独立的知识点树。

    extraction_mode:
    - "auto": 自动选择（规则解析结果少时用AI）
    - "rule_only": 仅规则解析（快，无AI调用）
    - "ai": 仅AI解析（准确性高，需API配额）
    """
    # 解析 category/exam_type
    resolved_category = category
    if category_id and category_id.isdigit():
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code

    resolved_exam_type = exam_type if exam_type else None
    if exam_type_id and exam_type_id.isdigit():
        et_obj = db.query(ExamType).filter(ExamType.id == int(exam_type_id)).first()
        if et_obj:
            resolved_exam_type = et_obj.code

    resolved_parent_id = int(parent_kp_id) if parent_kp_id and parent_kp_id.isdigit() else None

    # 验证父节点存在
    if resolved_parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == resolved_parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")

    # 批量处理
    result = await batch_processor.process_batch(
        files=files,
        subject_id=subject_id,
        category=resolved_category,
        parent_kp_id=resolved_parent_id,
        extraction_mode=extraction_mode,
        max_points=max_points_per_doc,
    )

    logger.info(
        f"用户 {current_user.id} 批量分析了 {len(files)} 个文档，成功 {result['completed']}，失败 {result['failed']}"
    )
    for r in result.get("results", []):
        logger.info(f"  文档分析结果: {r['filename']}, 状态={r['status']}, 节点数={r.get('total_points', 0)}")

    return {
        "success": True,
        "total": result["total"],
        "completed": result["completed"],
        "failed": result["failed"],
        "results": result["results"],
        "message": f"批量分析完成：成功 {result['completed']}，失败 {result['failed']}",
    }


@router.post("/batch/import")
async def batch_import_knowledge(
    import_request: BatchImportRequest,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量导入多个文档的知识点

    每个文档的知识点作为独立的顶级节点（文档名），其下的章节/小节作为子节点。
    文档之间没有父子关系。
    """
    category = import_request.category or "default"
    exam_type = import_request.exam_type
    parent_id = import_request.parent_kp_id

    # 解析 category_id/exam_type_id → code
    if import_request.category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == import_request.category_id).first()
        if cat_obj:
            category = cat_obj.code

    if import_request.exam_type_id:
        et_obj = db.query(ExamType).filter(ExamType.id == import_request.exam_type_id).first()
        if et_obj:
            exam_type = et_obj.code

    # 验证父节点存在
    if parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        # 更新父节点的 category/exam_type
        if parent.category == "default" or not parent.category:
            if category and category != "default":
                parent.category = category
            if exam_type:
                parent.exam_type = exam_type

    if not import_request.documents:
        raise HTTPException(status_code=400, detail="文档列表不能为空")

    created_count = 0
    failed_count = 0
    errors = []

    for doc in import_request.documents:
        created_before = created_count
        try:
            # 评估 P1-11：每个文档使用 SAVEPOINT，失败仅回滚该文档的写入，
            # 避免 flush 错误后 session 进入 pending-rollback 导致整体 500、
            # 或把失败文档的半成品数据随最终 commit 一起入库。
            with db.begin_nested():
                # 清理文件名作为父节点名称（去掉扩展名、前缀编号等）

                doc_name = doc.filename
                if "." in doc_name:
                    doc_name = doc_name.rsplit(".", 1)[0]
                doc_name = re.sub(r"^【[^】]*】", "", doc_name)
                doc_name = re.sub(r"^\[[^\]]*\]", "", doc_name)
                doc_name = re.sub(r"^[一二三四五六七八九十百千零○零\d\s]+[.、)）]", "", doc_name)
                doc_name = re.sub(r"^\d+[.、)\s]", "", doc_name)
                doc_name = re.sub(r"^[第][一二三四五六七八九十百千\d]+[章节条款段篇点题]", "", doc_name)
                doc_name = doc_name.strip()

                doc_node = KnowledgePoint(
                    name=doc_name[:100] or "未命名文档",
                    parent_id=parent_id,
                    category=category,
                    exam_type=exam_type,
                    description=f"导入自文档: {doc.filename}",
                    order=created_count,
                    status=1,
                    created_by=current_user.id,
                )
                db.add(doc_node)
                db.flush()
                created_count += 1  # 计入文档节点

                # 递归创建知识点树
                def create_tree_nodes(nodes: List[dict], doc_parent_id: int):
                    nonlocal created_count
                    for node in nodes:
                        name = node.get("name") or node.get("名称", "未命名")
                        description = node.get("description") or node.get("描述", "")
                        excerpt = node.get("excerpt") or node.get("原文", "")
                        children = node.get("children") or node.get("子节点", [])

                        kp = KnowledgePoint(
                            name=name[:100],
                            parent_id=doc_parent_id,
                            category=category,
                            exam_type=exam_type,
                            description=description[:2000] if description else None,
                            content_excerpt=excerpt[:2000] if excerpt else None,
                            order=created_count,
                            status=1,
                            created_by=current_user.id,
                        )
                        db.add(kp)
                        db.flush()
                        created_count += 1

                        if children and isinstance(children, list):
                            create_tree_nodes(children, kp.id)

                tree_node_count = _count_tree_nodes(doc.knowledge_tree)
                logger.info(f"文档 {doc.filename} 原始树节点数: {tree_node_count}")

                create_tree_nodes(doc.knowledge_tree, doc_node.id)
                # 文档节点已在之前计数过，不需要再次 +1
                logger.info(f"文档 {doc.filename} 导入完成，当前文档累计: {created_count}")

        except Exception as e:
            created_count = created_before  # SAVEPOINT 已回滚该文档，计数同步回退
            failed_count += 1
            errors.append(f"{doc.filename}: {e!s}")
            logger.error(f"批量导入文档知识点失败 {doc.filename}: {e}")

    try:
        db.commit()
        logger.info(f"用户 {current_user.id} 批量导入了 {created_count} 个知识点（失败 {failed_count}）")

        return {
            "success": True,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors if errors else None,
            "message": f"成功导入 {created_count} 个知识点" + (f"，失败 {failed_count} 个" if failed_count > 0 else ""),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入失败: {e}")
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")


def _count_tree_nodes(nodes: List[dict]) -> int:
    """递归统计树中节点总数（本地副本，避免跨模块导入）"""
    count = 0
    for node in nodes:
        count += 1
        children = node.get("children") or node.get("子节点", [])
        if children and isinstance(children, list):
            count += _count_tree_nodes(children)
    return count
