"""Batch Document Processor - 批量文档处理服务

支持同时处理多个文档的知识点提取，每个文档独立生成知识点树。
"""

import asyncio
import logging
import re
from typing import Any, Dict, List

from fastapi import UploadFile

from app.services.ai_knowledge_extractor import extract_knowledge_from_document, extract_knowledge_from_rules
from app.services.document_parser import parse_document, truncate_for_analysis
from app.services.rule_knowledge_extractor import extract_knowledge_by_rules

logger = logging.getLogger(__name__)


class BatchDocumentProcessor:
    """批量文档处理器"""

    def __init__(self):
        self.supported_extensions = {"pdf", "docx", "doc", "md", "markdown", "txt", "text"}

    async def process_single(
        self,
        file: UploadFile,
        subject_id: int,
        category: str,
        parent_kp_id: int | None = None,
        extraction_mode: str = "auto",
        max_points: int = 150,
    ) -> Dict[str, Any]:
        """处理单个文档

        Args:
            file: 上传的文件
            subject_id: 科目ID
            category: 分类代码
            parent_kp_id: 父知识点ID，用于挂载
            extraction_mode: 提取模式 - "auto", "rule_only", "ai"
            max_points: 最大知识点数量（AI模式）

        Returns:
            处理结果字典
        """
        filename = file.filename or "unknown"
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        # 清理文件名，去掉扩展名、编号前缀、括号内容等干扰信息
        clean_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        clean_name = re.sub(r"^【[^】]*】", "", clean_name)  # 去掉【编号】前缀
        clean_name = re.sub(r"^\[[^\]]*\]", "", clean_name)  # 去掉[编号]前缀
        clean_name = re.sub(r"^[一二三四五六七八九十百千零○零\d\s]+[.、)）]", "", clean_name)  # 去掉中文/数字序号前缀
        clean_name = re.sub(r"^\d+[.、)\s]", "", clean_name)  # 去掉纯数字序号前缀
        clean_name = re.sub(
            r"^[第][一二三四五六七八九十百千\d]+[章节条款段篇点题]", "", clean_name
        )  # 去掉"第X章"等前缀
        clean_name = clean_name.strip()

        if ext not in self.supported_extensions:
            return {
                "filename": filename,
                "status": "failed",
                "error": f"不支持的文件格式: .{ext}",
                "knowledge_tree": None,
            }

        try:
            # 读取文件内容
            content = await file.read()

            if len(content) > 10 * 1024 * 1024:  # 10MB
                return {
                    "filename": filename,
                    "status": "failed",
                    "error": "文件大小超过10MB限制",
                    "knowledge_tree": None,
                }

            # 解析文档
            text_content = parse_document(content, ext, filename)
            text_content = truncate_for_analysis(text_content, max_chars=150000)

            if len(text_content.strip()) < 50:
                return {
                    "filename": filename,
                    "status": "failed",
                    "error": "文档内容过少或无法提取文本",
                    "knowledge_tree": None,
                }

            # 根据模式提取知识点
            if extraction_mode == "rule_only":
                result = extract_knowledge_by_rules(text=text_content, max_children=5, max_depth=3)
                method = "rule-based"
            elif extraction_mode == "ai":
                result = await extract_knowledge_from_document(
                    document_content=text_content, document_name=clean_name, max_points=max_points, category=category
                )
                method = "ai"
            elif extraction_mode == "rule_then_ai":
                # 先用规则快速提取结构，再用AI基于规则结果进行优化
                rule_result = extract_knowledge_by_rules(text=text_content, max_children=5, max_depth=3)
                rule_count = rule_result.get("total", 0)

                # 如果规则提取结果足够多，让AI基于规则结构优化
                if rule_count >= 3:
                    result = await extract_knowledge_from_rules(
                        rule_knowledge=rule_result,
                        document_content=text_content,
                        document_name=clean_name,
                        max_points=max_points,
                        category=category,
                    )
                    method = "ai-optimized"
                else:
                    # 规则结果太少，直接用AI完整分析
                    result = await extract_knowledge_from_document(
                        document_content=text_content,
                        document_name=clean_name,
                        max_points=max_points,
                        category=category,
                    )
                    method = "ai"
            else:  # auto - 自动选择
                # 先尝试规则解析，如果结果太少再用AI
                rule_result = extract_knowledge_by_rules(text=text_content, max_children=5, max_depth=3)
                rule_count = rule_result.get("total", 0)

                if rule_count >= 3:
                    result = rule_result
                    method = "rule-based"
                else:
                    # 内容太少，使用AI补充
                    result = await extract_knowledge_from_document(
                        document_content=text_content, document_name=filename, max_points=max_points, category=category
                    )
                    method = "ai"

            # 检查AI返回结果
            if extraction_mode in ("ai", "auto") and not result.get("success"):
                return {
                    "filename": filename,
                    "status": "failed",
                    "error": result.get("error", "AI分析失败"),
                    "knowledge_tree": None,
                }

            return {
                "filename": filename,
                "status": "completed",
                "method": method,
                "knowledge_tree": result.get("knowledge_points", []),
                "total_points": result.get("total", 0),
                "text_preview": text_content[:300] + "..." if len(text_content) > 300 else text_content,
                "parent_kp_id": parent_kp_id,
                "error": None,
            }

        except ImportError as e:
            logger.error(f"批量处理失败，缺少依赖: {e}")
            return {"filename": filename, "status": "failed", "error": f"缺少解析依赖: {e!s}", "knowledge_tree": None}
        except Exception as e:
            logger.error(f"批量处理文档失败 {filename}: {e}")
            return {"filename": filename, "status": "failed", "error": f"处理失败: {e!s}", "knowledge_tree": None}

    async def process_batch(
        self,
        files: List[UploadFile],
        subject_id: int,
        category: str,
        parent_kp_id: int | None = None,
        extraction_mode: str = "auto",
        max_points: int = 150,
    ) -> Dict[str, Any]:
        """批量处理多个文档

        Args:
            files: 文件列表
            subject_id: 科目ID
            category: 分类代码
            parent_kp_id: 父知识点ID
            extraction_mode: 提取模式
            max_points: 最大知识点数

        Returns:
            批量处理结果
        """
        if not files:
            return {"total": 0, "completed": 0, "failed": 0, "results": []}

        # 并行处理所有文档
        tasks = [
            self.process_single(
                file=file,
                subject_id=subject_id,
                category=category,
                parent_kp_id=parent_kp_id,
                extraction_mode=extraction_mode,
                max_points=max_points,
            )
            for file in files
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计
        completed = 0
        failed = 0
        processed_results = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "filename": files[i].filename if hasattr(files[i], "filename") else f"file_{i}",
                        "status": "failed",
                        "error": str(result),
                        "knowledge_tree": None,
                    }
                )
                failed += 1
            else:
                processed_results.append(result)
                if result.get("status") == "completed":
                    completed += 1
                else:
                    failed += 1

        return {"total": len(files), "completed": completed, "failed": failed, "results": processed_results}
