#!/usr/bin/env python3
"""
Extract inline Pydantic schemas from router files into app/schemas/.
Uses AST parsing for reliable extraction.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import re

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"
SCHEMAS_DIR = APP_DIR / "schemas"

FILES_TO_PROCESS = [
    "routers/audit.py",
    "routers/auth.py",
    "routers/dashboard.py",
    "routers/exam_records.py",
    "routers/exams.py",
    "routers/knowledge.py",
    "routers/notifications.py",
    "routers/paper_template.py",
    "routers/papers.py",
    "routers/ai_templates/tasks.py",
]

# Map class names to target schema files
CLASS_TO_FILE = {
    # audit
    "AuditQuestionResponse": "audit.py",
    "AuditListResponse": "audit.py",
    "RejectRequest": "audit.py",
    "BatchAuditRequest": "audit.py",
    # auth
    "ForgotPasswordRequest": "auth.py",
    "TokenRefreshResponse": "auth.py",
    # dashboard
    "OverviewStats": "dashboard.py",
    "TrendDataPoint": "dashboard.py",
    "QuestionTypeDistribution": "dashboard.py",
    "DifficultyDistribution": "dashboard.py",
    "ActivityItem": "dashboard.py",
    "DashboardOverview": "dashboard.py",
    # exam_records
    "QuestionResponse": "exam_record.py",
    "UserAnswerDetailResponse": "exam_record.py",
    "ExamRecordListResponse": "exam_record.py",
    "ExamRecordDetailResponse": "exam_record.py",
    "ExamRecordStatsResponse": "exam_record.py",
    # exams
    "UserAnswerCreate": "exam.py",
    "UserAnswerResponse": "exam.py",
    "ExamRecordResponse": "exam.py",
    "ExamCreate": "exam.py",
    "ExamUpdate": "exam.py",
    "ExamResponse": "exam.py",
    "ExamGradeRequest": "exam.py",
    "ExamGradeResponse": "exam.py",
    # knowledge
    "KnowledgePointCreate": "knowledge.py",
    "KnowledgePointUpdate": "knowledge.py",
    "KnowledgePointResponse": "knowledge.py",
    "KnowledgeStatistics": "knowledge.py",
    "AIImportRequest": "knowledge.py",
    "BatchAnalyzeRequest": "knowledge.py",
    "DocumentKnowledgeImport": "knowledge.py",
    "BatchImportRequest": "knowledge.py",
    "KnowledgeQuestionCountRequest": "knowledge.py",
    # notifications
    "NotificationResponse": "notification.py",
    "NotificationStats": "notification.py",
    # paper_template
    "PaperTemplateCreate": "paper_template.py",
    "PaperTemplateUpdate": "paper_template.py",
    "PaperTemplateResponse": "paper_template.py",
    # papers
    "QuestionOptionSimpleResponse": "paper.py",
    "QuestionInPaperResponse": "paper.py",
    "ExamPaperQuestionResponse": "paper.py",
    "PaperCreateFixed": "paper.py",
    "FixedQuestionItem": "paper.py",
    "PaperCreateRandom": "paper.py",
    "RandomSelectionRules": "paper.py",
    "PaperUpdate": "paper.py",
    "PaperResponse": "paper.py",
    "PaperDetailResponse": "paper.py",
    "PaperListResponse": "paper.py",
    "PaperCreateUnion": "paper.py",
    "AutoGenerateRequest": "paper.py",
    "AutoGeneratePreviewRequest": "paper.py",
    "DifficultyDistributionRequest": "paper.py",
    "DifficultyDistributionResponse": "paper.py",
    "ExportPaperRequest": "paper.py",
    # ai_templates/tasks
    "GenerationTaskResponse": "ai_task.py",
    "TaskProgressResponse": "ai_task.py",
    "TaskListResponse": "ai_task.py",
}


def get_base_classes(node: ast.ClassDef) -> set[str]:
    """Get all base class names for a class definition."""
    bases = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.add(base.id)
        elif isinstance(base, ast.Attribute):
            if isinstance(base.value, ast.Name):
                bases.add(f"{base.value.id}.{base.attr}")
    return bases


def extract_class_source(content: str, node: ast.ClassDef) -> str:
    """Extract the source code for a class definition including decorators."""
    lines = content.split("\n")

    # Find start line (including decorators)
    start_line = node.lineno - 1  # 0-indexed
    for decorator in node.decorator_list:
        dec_line = decorator.lineno - 1
        if dec_line < start_line:
            start_line = dec_line

    # Find end line
    end_line = getattr(node, "end_lineno", None)
    if end_line is None:
        # Fallback: estimate based on body size
        end_line = node.lineno + sum(getattr(n, "end_lineno", n.lineno) - n.lineno + 1 for n in node.body) + 5

    return "\n".join(lines[start_line:end_line])


def find_basemodel_classes(content: str) -> dict[str, str]:
    """Find all top-level classes inheriting from BaseModel."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}

    classes = {}
    for node in tree.body:  # Only top-level nodes
        if isinstance(node, ast.ClassDef):
            bases = get_base_classes(node)
            if "BaseModel" in bases:
                class_block = extract_class_source(content, node)
                classes[node.name] = class_block

    return classes


def create_schema_file(filepath: Path, blocks: list[str]) -> None:
    """Create a schema file with the given class blocks."""
    all_text = "\n".join(blocks)

    # Standard imports
    header = [
        '"""Schemas - Pydantic models for API requests and responses"""',
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from typing import Any, List, Optional",
        "",
        "from pydantic import BaseModel, ConfigDict, Field, field_validator",
    ]

    # Add EmailStr if any class has email field
    if any("email" in b.lower() for b in blocks):
        header[header.index("from pydantic import BaseModel, ConfigDict, Field, field_validator")] = (
            "from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator"
        )

    # Add re if needed
    if any("re.search" in b or "re.match" in b for b in blocks):
        header.append("import re")

    content = "\n".join(header) + "\n\n\n" + "\n\n".join(sorted(blocks)) + "\n"
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✓ Created {filepath} ({len(blocks)} schemas)")


def main() -> None:
    SCHEMAS_DIR.mkdir(exist_ok=True)

    all_schema_blocks: dict[str, list[str]] = defaultdict(list)

    for rel_path in FILES_TO_PROCESS:
        filepath = APP_DIR / rel_path
        if not filepath.exists():
            print(f"⚠ Skipping {filepath} (not found)")
            continue

        content = filepath.read_text(encoding="utf-8")
        classes = find_basemodel_classes(content)

        if not classes:
            continue

        print(f"Processing {rel_path}: found {len(classes)} schemas")
        for class_name, block in classes.items():
            target = CLASS_TO_FILE.get(class_name)
            if target:
                all_schema_blocks[target].append(block)
            else:
                print(f"  ⚠ No mapping for {class_name}")

    # Create schema files
    for schema_file, blocks in sorted(all_schema_blocks.items()):
        filepath = SCHEMAS_DIR / schema_file
        if filepath.exists() and schema_file != "system.py":
            print(f"⚠ {filepath} already exists, skipping")
            continue
        create_schema_file(filepath, blocks)

    print("\n✓ Schema extraction complete!")
    print(f"  Created {len(all_schema_blocks)} schema files in {SCHEMAS_DIR}")


if __name__ == "__main__":
    main()
