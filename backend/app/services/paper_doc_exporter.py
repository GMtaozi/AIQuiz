"""试卷 Word/PDF 文档导出模块（评估 P2-1：从 papers.py 巨型路由文件抽取）。

自包含模块：不依赖 papers 路由内部状态，仅依赖模型/SQLAlchemy 与文档库。
同时应用 P2-16 修复：字体路径配置化（settings.pdf_font_path 优先）+ 跨平台候选；
并修复 _generate_pdf_paper 中 questions_by_type 在使用前未定义导致的 NameError。
"""

import io
import logging
import os
import sys

from app.config import settings

logger = logging.getLogger(__name__)

# ---------- Word (python-docx) ----------
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx 未安装，Word导出功能将不可用")


# ---------- PDF (reportlab) ----------
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from reportlab.platypus.flowables import HRFlowable

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("reportlab 未安装，PDF导出功能将不可用")


def _find_chinese_font() -> str | None:
    """跨平台搜索中文字体并注册，返回字体名；找不到返回 None。

    评估 P2-16：优先使用 settings.pdf_font_path（配置化），
    其次按平台搜索常见系统字体路径。
    """
    if not PDF_AVAILABLE:
        return None

    font_paths = []
    configured = getattr(settings, "pdf_font_path", "") or ""
    if configured:
        font_paths.append(("SimSun", configured))

    if sys.platform == "win32":
        font_paths.extend(
            [
                ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
                ("Microsoft YaHei", "C:/Windows/Fonts/msyh.ttc"),
                ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
                ("KaiTi", "C:/Windows/Fonts/kaiti.ttf"),
            ]
        )
    elif sys.platform == "darwin":
        font_paths.extend(
            [
                ("SimSun", "/System/Library/Fonts/PingFang.ttc"),
                ("SimSun", "/System/Library/Fonts/STHeiti Light.ttc"),
            ]
        )
    else:
        font_paths.extend(
            [
                ("SimSun", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
                ("SimSun", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
                ("SimSun", "/usr/share/fonts/truetype/ubuntu/Ubuntu-LI.ttf"),
                ("SimSun", "/usr/share/fonts/google-droid/DroidSansFallbackFull.ttf"),
                ("SimSun", "/usr/share/fonts/truetype/arphic/uming.ttc"),
                ("SimSun", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ]
        )

    for font_name, font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                logger.info(f"成功注册PDF中文字体: {font_name} from {font_path}")
                return font_name
            except Exception as e:
                logger.warning(f"注册字体 {font_name} 失败: {e}")
    logger.warning("未找到任何中文字体，PDF中文可能显示异常")
    return None


REGISTERED_FONTS: list[str] = []
_font = _find_chinese_font()
if _font:
    REGISTERED_FONTS.append(_font)


def _make_chinese_run(para, text, font_name="SimSun", bold=False, italic=False, font_size=Pt(11)):
    """创建一个支持中文的run"""
    run = para.add_run(text)
    run.font.name = font_name
    run.font.size = font_size
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    if bold:
        run.bold = True
    if italic:
        run.italic = True
    return run


def _generate_word_paper(paper, subject_name, sorted_questions, q_type_names):
    """生成Word试卷文档（职业考试风格：紧凑、选项内嵌、分题型分块）"""
    doc = Document()

    # 设置默认字体
    style = doc.styles["Normal"]
    style.font.name = "SimSun"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")

    # ========== 试卷标题区 ==========
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(paper.title or "未命名试卷")
    run.font.size = Pt(22)
    run.bold = True
    run.font.name = "SimSun"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")

    # ========== 试卷信息区 ==========
    info_para = doc.add_paragraph()
    info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _make_chinese_run(info_para, f"科目：{subject_name}　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"总分：{paper.total_score}分　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"考试时间：{paper.total_time}分钟　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"及格分数：{paper.passing_score}分", font_size=Pt(12))

    # ========== 注意事项区 ==========
    doc.add_paragraph()  # 空行
    notice_para = doc.add_paragraph()
    notice_run = notice_para.add_run("【注意事项】")
    notice_run.bold = True
    notice_run.font.name = "SimSun"
    notice_run.font.size = Pt(11)
    notice_run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")

    notice_content = doc.add_paragraph()
    notice_content.paragraph_format.left_indent = Pt(20)
    _make_chinese_run(notice_content, "1. 本试卷包含客观题和主观题，请将答案直接写在试卷相应位置上。", font_size=Pt(10))
    notice_content2 = doc.add_paragraph()
    notice_content2.paragraph_format.left_indent = Pt(20)
    _make_chinese_run(notice_content2, "2. 主观题请在红线框内作答，保持字迹清晰。", font_size=Pt(10))

    doc.add_paragraph()  # 空行

    # ========== 分割线 ==========
    line_para = doc.add_paragraph()
    line_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line_run = line_para.add_run("─" * 60)
    line_run.font.color.rgb = None
    line_run.font.size = Pt(9)

    doc.add_paragraph()  # 空行

    # ========== 题目区分题型分块输出 ==========
    questions_by_type = {}
    for epq in sorted_questions:
        qtype = epq.question.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(epq)

    # 题型顺序
    type_order = ["single_choice", "multiple_choice", "true_false", "essay", "blank", "short_answer"]

    section_num = 1

    for qtype in type_order:
        if qtype not in questions_by_type:
            continue
        questions = questions_by_type[qtype]
        if not questions:
            continue

        type_name = q_type_names.get(qtype, qtype)
        per_score = questions[0].score if questions else 0
        total_score_for_type = sum(epq.score for epq in questions)
        count_for_type = len(questions)

        # ========== 题型标题区 ==========
        section_title = doc.add_paragraph()
        section_run = section_title.add_run(
            f"{_get_chinese_num(section_num)}、{type_name}（共 {count_for_type} 题，每题 {per_score} 分，共 {total_score_for_type} 分）"
        )
        section_run.bold = True
        section_run.font.name = "SimSun"
        section_run.font.size = Pt(12)
        section_run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
        section_title.paragraph_format.space_after = Pt(6)

        # ========== 该题型的所有题目 ==========
        q_index = 1  # 全局题号

        for epq in questions:
            q = epq.question

            # 题目内容（带题号）
            q_para = doc.add_paragraph()
            q_para.paragraph_format.space_after = Pt(3)
            _make_chinese_run(q_para, f"{q_index}. {q.content}", font_size=Pt(11))

            # 选项内嵌显示（选择题）- 紧凑排列
            if q.question_type in ("single_choice", "multiple_choice", "true_false"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                if options:
                    # 一行显示所有选项，更紧凑
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Pt(20)
                    opt_para.paragraph_format.space_after = Pt(6)
                    for opt in options:
                        _make_chinese_run(opt_para, f"[{opt.option_label}] {opt.option_content}   ", font_size=Pt(10))

            # 主观题添加作答区域提示
            if q.question_type in ("essay", "short_answer"):
                answer_space = doc.add_paragraph()
                answer_space.paragraph_format.left_indent = Pt(20)
                answer_space.paragraph_format.space_after = Pt(12)
                # 红色提示线
                answer_run = answer_space.add_run("答：")
                answer_run.font.name = "SimSun"
                answer_run.font.size = Pt(11)
                answer_run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")

            q_index += 1

        doc.add_paragraph()  # 题型之间空一行
        section_num += 1

    # ========== 版权水印 ==========
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_para.add_run("智题 AIQuiz © 2024-2026 | 本试卷题目为AI原创模拟题")
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = None
    footer_run.font.name = "SimSun"
    footer_run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")

    return doc


def _get_chinese_num(num):
    """将数字转换为中文数字"""
    cn_nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    if num <= 10:
        return cn_nums[num]
    return str(num)


def _generate_pdf_paper(paper, subject_name, sorted_questions, q_type_names):
    """生成PDF试卷文档（职业考试风格：紧凑、选项内嵌、分题型分块）"""
    from reportlab.lib.enums import TA_CENTER as _TA_CENTER
    from reportlab.platypus import PageBreak

    # 使用第一个可用的中文字体
    chinese_font = REGISTERED_FONTS[0] if REGISTERED_FONTS else "Helvetica"
    logger.info(f"生成PDF使用字体: {chinese_font}")

    # 评估 P2-16 修复：questions_by_type 必须先于 has_objective/has_subjective 计算
    # （原实现先引用后定义导致 NameError，PDF 导出必 500）
    questions_by_type = {}
    for epq in sorted_questions:
        qtype = epq.question.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(epq)

    # 创建PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
    )

    # 创建样式
    styles = getSampleStyleSheet()

    # 标题样式
    title_style = ParagraphStyle(
        "ChineseTitle", parent=styles["Heading1"], fontName=chinese_font, fontSize=22, alignment=TA_CENTER, spaceAfter=12
    )

    # 信息样式
    info_style = ParagraphStyle(
        "ChineseInfo", parent=styles["Normal"], fontName=chinese_font, fontSize=12, alignment=TA_CENTER, spaceAfter=6
    )

    # 注意事项标题样式
    notice_title_style = ParagraphStyle(
        "ChineseNoticeTitle", parent=styles["Normal"], fontName=chinese_font, fontSize=11, spaceBefore=12, spaceAfter=4
    )

    # 注意事项内容样式
    notice_style = ParagraphStyle(
        "ChineseNotice", parent=styles["Normal"], fontName=chinese_font, fontSize=10, leftIndent=20, spaceAfter=3
    )

    # 题型标题样式
    section_style = ParagraphStyle(
        "ChineseSection", parent=styles["Normal"], fontName=chinese_font, fontSize=12, leading=16, spaceBefore=15, spaceAfter=6
    )

    # 题目样式
    question_style = ParagraphStyle(
        "ChineseQuestion", parent=styles["Normal"], fontName=chinese_font, fontSize=11, leading=15, spaceAfter=3
    )

    # 选项样式（紧凑一行）
    option_style = ParagraphStyle(
        "ChineseOption", parent=styles["Normal"], fontName=chinese_font, fontSize=10, leading=14, leftIndent=20, spaceAfter=6
    )

    # 主观题答题提示样式
    answer_hint_style = ParagraphStyle(
        "ChineseAnswerHint", parent=styles["Normal"], fontName=chinese_font, fontSize=10, leftIndent=20, spaceAfter=12
    )

    # 构建内容
    story = []

    # ========== 试卷标题区 ==========
    story.append(Paragraph(paper.title or "未命名试卷", title_style))

    # ========== 试卷信息区 ==========
    info_text = f"科目：{subject_name}　　总分：{paper.total_score}分　　考试时间：{paper.total_time}分钟　　及格分数：{paper.passing_score}分"
    story.append(Paragraph(info_text, info_style))

    # ========== 注意事项区（根据实际题型动态生成）==========
    has_objective = any(qtype in questions_by_type for qtype in ["single_choice", "multiple_choice", "true_false"])
    has_subjective = any(qtype in questions_by_type for qtype in ["essay", "short_answer"])

    story.append(Spacer(1, 10))
    story.append(Paragraph("【注意事项】", notice_title_style))

    if has_objective and has_subjective:
        story.append(Paragraph("1. 本试卷包含客观题和主观题，请将答案直接写在试卷相应位置上。", notice_style))
        story.append(Paragraph("2. 主观题请在相应区域内作答，保持字迹清晰。", notice_style))
    elif has_objective:
        story.append(Paragraph("1. 本试卷均为客观题，请将答案直接写在试卷相应位置上。", notice_style))
    else:
        story.append(Paragraph("1. 本试卷均为主观题，请在相应区域内作答，保持字迹清晰。", notice_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=15))

    # 按题型分组（已在上面预计算 questions_by_type）
    type_order = ["single_choice", "multiple_choice", "true_false", "essay", "blank", "short_answer"]

    section_num = 1

    for qtype in type_order:
        if qtype not in questions_by_type:
            continue
        questions = questions_by_type[qtype]
        if not questions:
            continue

        type_name = q_type_names.get(qtype, qtype)
        total_score_for_type = sum(epq.score for epq in questions)
        per_score = questions[0].score if questions else 0
        count_for_type = len(questions)

        # ========== 题型标题区 ==========
        section_title = f"{_get_chinese_num(section_num)}、{type_name}（共 {count_for_type} 题，每题 {per_score} 分，共 {total_score_for_type} 分）"
        story.append(Paragraph(section_title, section_style))

        q_index = 1

        # ========== 该题型的所有题目 ==========
        for epq in questions:
            q = epq.question

            # 题目内容
            question_text = f"{q_index}. {q.content}"
            story.append(Paragraph(question_text, question_style))

            # 选项内嵌显示（选择题）- 紧凑排列
            if q.question_type in ("single_choice", "multiple_choice", "true_false"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                if options:
                    # 一行显示所有选项
                    opt_text = "   ".join([f"[{opt.option_label}] {opt.option_content}" for opt in options])
                    story.append(Paragraph(opt_text, option_style))

            # 主观题添加作答提示
            if q.question_type in ("essay", "short_answer"):
                story.append(Paragraph("答：________________________", answer_hint_style))

            q_index += 1

        section_num += 1

    # ========== 版权水印 ==========
    footer_style = ParagraphStyle(
        "ChineseFooter", parent=styles["Normal"], fontName=chinese_font, fontSize=9, alignment=TA_CENTER, spaceBefore=20
    )
    story.append(Paragraph("智题 AIQuiz © 2024-2026 | 本试卷题目为AI原创模拟题", footer_style))

    # 生成PDF
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer
