"""AI analysis routes: rule-based analyze, AI analyze, AI import, AI preview."""

import logging
import re
import traceback
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import ExamCategory, ExamType
from app.models.user import User
from app.schemas.knowledge import AIImportRequest
from app.services.ai_knowledge_extractor import extract_knowledge_from_document
from app.services.document_parser import parse_document, truncate_for_analysis
from app.services.rule_knowledge_extractor import extract_knowledge_by_rules
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.post("/rule/analyze")
async def rule_analyze_document(
    file: UploadFile = File(...),
    parent_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    max_children: int = Form(default=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """基于规则解析文档结构，自动提取知识点

    无需 AI，毫秒级返回。适用于法律条文、教材等结构化文档。
    支持格式：PDF, Word(.docx), Markdown(.md), TXT

    解析策略：
    - 法律条文：识别"第X章"、"第X条"结构
    - Markdown：识别 # 标题层级
    - 数字编号：识别 1. → 1.1 → 1.1.1
    - 纯文本：按段落拆分
    """
    # 解析 category
    resolved_category = category
    if category_id and category_id.isdigit():
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code

    # 读取文件内容
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        # 解析文档为文本
        text_content = parse_document(content, ext, filename)
        text_content = truncate_for_analysis(text_content, max_chars=200000)

        if len(text_content.strip()) < 50:
            raise HTTPException(status_code=400, detail="文档内容过少或无法提取文本")

        # 规则解析提取知识点
        result = extract_knowledge_by_rules(text=text_content, max_children=max_children, max_depth=3)

        return_parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

        logger.info(f"用户 {current_user.id} 规则解析了文档: {filename}, 提取 {result.get('total', 0)} 个知识点")

        return {
            "success": True,
            "document_name": filename,
            "text_preview": text_content[:500] + "..." if len(text_content) > 500 else text_content,
            "knowledge_points": result.get("knowledge_points", []),
            "total_points": result.get("total", 0),
            "parent_id": return_parent_id,
            "method": "rule-based",
            "message": f"规则解析完成，提取 {result.get('total', 0)} 个知识点，可确认导入",
        }

    except ImportError as e:
        logger.error(f"缺少解析依赖: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="缺少解析依赖，请联系管理员")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"规则文档解析失败: {e!s}\n{tb}")
        raise HTTPException(status_code=500, detail="文档解析失败，请稍后重试")


@router.post("/ai/analyze")
async def ai_analyze_document(
    file: UploadFile = File(...),
    parent_id: str = Form(default=""),
    category: str = Form(default="default"),
    category_id: str = Form(default=""),
    max_points: int = Form(default=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """AI 智能分析文档并提取知识点

    支持格式：PDF, Word(.docx), Markdown(.md), TXT

    返回提取的知识点树结构，供用户确认后保存。
    """
    # 如果前端传了 category_id（数字 ID），查询对应的 code
    resolved_category = category
    if category_id and category_id.isdigit():
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == int(category_id)).first()
        if cat_obj:
            resolved_category = cat_obj.code
    # 读取文件内容
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:  # 10MB 限制
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    # 获取文件扩展名
    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        # 解析文档
        text_content = parse_document(content, ext, filename)
        text_content = truncate_for_analysis(text_content, max_chars=50000)

        if len(text_content.strip()) < 50:
            raise HTTPException(status_code=400, detail="文档内容过少或无法提取文本")

        # 调用 AI 提取知识点
        result = await extract_knowledge_from_document(
            document_content=text_content, document_name=filename, max_points=max_points, category=resolved_category
        )

        if not result.get("success"):
            error_msg = result.get("error", "AI 分析失败")
            raise HTTPException(status_code=500, detail=f"AI 分析失败: {error_msg}")

        logger.info(f"用户 {current_user.id} 使用 AI 分析了文档: {filename}, 生成了 {result.get('total', 0)} 个知识点")

        return_parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

        return {
            "success": True,
            "document_name": filename,
            "text_preview": text_content[:500] + "..." if len(text_content) > 500 else text_content,
            "knowledge_points": result.get("knowledge_points", []),
            "total_points": result.get("total", 0),
            "parent_id": return_parent_id,
            "message": "AI 分析完成，请确认知识点结构后保存",
        }

    except ImportError as e:
        logger.error(f"缺少解析依赖: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="缺少解析依赖，请联系管理员")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 评估 P1-9 修复：异常详情只进日志，不返回给客户端（原实现泄露完整 traceback）
        tb = traceback.format_exc()
        logger.error(f"AI 文档分析失败: {e!s}\n{tb}")
        raise HTTPException(status_code=500, detail="文档分析失败，请稍后重试")


@router.post("/ai/import")
async def ai_import_knowledge(
    import_request: AIImportRequest = Body(..., media_type="application/json"),
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量导入 AI 生成的知识点

    接收 AI 分析后确认的知识点点结构，批量创建到数据库。
    """
    knowledge_points = import_request.knowledge_points
    category = import_request.category or "default"
    exam_type = import_request.exam_type
    parent_id = import_request.parent_id

    # 如果前端传了 category_id（数字 ID），查询对应的 code
    if import_request.category_id:
        cat_obj = db.query(ExamCategory).filter(ExamCategory.id == import_request.category_id).first()
        if cat_obj:
            category = cat_obj.code
        # 如果前端传了 exam_type_id，查询对应的 code
        if import_request.exam_type_id:
            et_obj = db.query(ExamType).filter(ExamType.id == import_request.exam_type_id).first()
            if et_obj:
                exam_type = et_obj.code

    logger.debug(
        f"AI导入请求: parent_id={parent_id}, category={category}, exam_type={exam_type}, points_count={len(knowledge_points)}, document_name={import_request.document_name}"
    )

    if not knowledge_points:
        raise HTTPException(status_code=400, detail="知识点列表不能为空")

    # 验证父节点存在
    if parent_id:
        parent = db.query(KnowledgePoint).filter(KnowledgePoint.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        # 如果父节点的 category 是 default，更新为导入的 category/exam_type
        if parent.category == "default" or not parent.category:
            if category and category != "default":
                parent.category = category
            if exam_type:
                parent.exam_type = exam_type

    created_count = 0
    id_mapping = {}  # 旧ID -> 新ID 的映射（用于处理树结构）

    # 如果没有指定父节点但有文档名，创建一个文档节点作为父节点
    # 这样可以让多个知识点根节点都挂在这个文档节点下
    effective_parent_id = parent_id
    if not effective_parent_id and import_request.document_name:
        doc_name = import_request.document_name.strip()
        if doc_name:
            # 清理文档名（去掉扩展名、前缀编号等）

            doc_name = re.sub(r"\.[^.]+$", "", doc_name)  # 去掉扩展名
            doc_name = re.sub(r"^【[^】]*】", "", doc_name)  # 去掉【编号】前缀
            doc_name = re.sub(r"^\[[^\]]*\]", "", doc_name)  # 去掉[编号]前缀
            doc_name = re.sub(r"^[一二三四五六七八九十百千零○零\d\s]+[.、)）]", "", doc_name)  # 去掉中文/数字序号前缀
            doc_name = re.sub(r"^\d+[.、)\s]", "", doc_name)  # 去掉纯数字序号前缀
            doc_name = re.sub(
                r"^[第][一二三四五六七八九十百千\d]+[章节条款段篇点题]", "", doc_name
            )  # 去掉"第X章"等前缀
            doc_name = doc_name.strip() or "未命名文档"

            doc_node = KnowledgePoint(
                name=doc_name[:100],
                parent_id=None,
                category=category,
                exam_type=exam_type,
                description=f"导入自文档: {import_request.document_name}",
                order=0,
                status=1,
                created_by=current_user.id,
            )
            db.add(doc_node)
            db.flush()
            effective_parent_id = doc_node.id
            created_count += 1
            logger.info(f"创建文档节点: id={doc_node.id}, name={doc_name}")

    def create_nodes(nodes: List[dict], parent_id: int | None = None):
        nonlocal created_count
        for node in nodes:
            # 兼容中英文 key
            name = node.get("name") or node.get("名称", "未命名")
            description = node.get("description") or node.get("描述", "")
            excerpt = node.get("excerpt") or node.get("原文", "")
            children = node.get("children") or node.get("子节点", [])

            logger.debug(f"创建知识点: name={name}, parent_id={parent_id}")

            # 创建知识点
            kp = KnowledgePoint(
                name=name[:100],
                parent_id=parent_id,
                category=category,
                exam_type=exam_type,
                description=description[:2000] if description else None,
                content_excerpt=excerpt[:2000] if excerpt else None,
                knowledge_base_id=import_request.knowledge_base_id,
                entry_id=import_request.entry_id,
                order=created_count,
                status=1,
                created_by=current_user.id,
            )
            db.add(kp)
            db.flush()  # 获取 ID

            old_id = node.get("id", 0)
            if old_id:
                id_mapping[old_id] = kp.id

            created_count += 1

            # 递归创建子节点
            if children:
                create_nodes(children if isinstance(children, list) else [], parent_id=kp.id)

    try:
        create_nodes(knowledge_points, parent_id=effective_parent_id)
        db.commit()

        logger.info(f"用户 {current_user.id} 批量导入了 {created_count} 个知识点")

        return {"success": True, "created_count": created_count, "message": f"成功导入 {created_count} 个知识点"}
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入知识点失败: {e!s}")
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试")


@router.post("/ai/preview")
async def ai_preview_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher_or_admin),
):
    """预览文档内容（用于确认上传文件是否正确）"""
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        text_content = parse_document(content, ext, filename)
        preview = truncate_for_analysis(text_content, max_chars=2000)

        return {
            "success": True,
            "filename": filename,
            "file_type": ext,
            "text_length": len(text_content),
            "preview": preview,
            "message": "文档预览成功",
        }
    except Exception as e:
        logger.error(f"文档预览失败: {e!s}")
        raise HTTPException(status_code=400, detail="文档预览失败，请检查文件格式")
