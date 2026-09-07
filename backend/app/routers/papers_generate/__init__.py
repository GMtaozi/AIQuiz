"""智能组卷路由包（从 papers_generate.py 拆分）。

包含：智能组卷预览、难度分布、AI 大纲、自动组卷、A/B 卷、组卷进度。
"""

import logging

from fastapi import APIRouter

from app.routers.papers_generate import generate, preview

# 尝试导入 python-docx（保持与 papers.py 的兼容性）
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.getLogger(__name__).warning("python-docx 未安装，Word导出功能将不可用")

# 评估 P2-1：Word/PDF 导出逻辑已抽取到 app.services.paper_doc_exporter（含字体注册/P2-16 配置化）
from app.services.paper_doc_exporter import (
    PDF_AVAILABLE,
    REGISTERED_FONTS,
    _generate_pdf_paper,
    _generate_word_paper,
    _get_chinese_num,
    _make_chinese_run,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 评估 P2-1/路由顺序修复：先生成组卷子路由（/auto-generate/*、/generate/{task_id}/progress
# 等静态/前缀路径）必须先于 /{paper_id} 注册，否则会被参数路由遮蔽（此前
# GET /generate/{task_id}/progress 被 GET /{paper_id} 遮蔽导致 422）。
router.include_router(preview.router)
router.include_router(generate.router)

__all__ = [
    "DOCX_AVAILABLE",
    "PDF_AVAILABLE",
    "REGISTERED_FONTS",
    "_generate_pdf_paper",
    "_generate_word_paper",
    "_get_chinese_num",
    "_make_chinese_run",
    "router",
]
