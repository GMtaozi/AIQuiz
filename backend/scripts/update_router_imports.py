#!/usr/bin/env python3
"""
Update router files to import schemas from app/schemas/ instead of inline definitions.
"""

from __future__ import annotations

from pathlib import Path
import re

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"

# Map of router file -> schema file to import from
ROUTER_SCHEMA_IMPORTS = {
    "routers/audit.py": "app.schemas.audit",
    "routers/auth.py": "app.schemas.auth",
    "routers/dashboard.py": "app.schemas.dashboard",
    "routers/exam_records.py": "app.schemas.exam_record",
    "routers/exams.py": "app.schemas.exam",
    "routers/knowledge.py": "app.schemas.knowledge",
    "routers/notifications.py": "app.schemas.notification",
    "routers/paper_template.py": "app.schemas.paper_template",
    "routers/papers.py": "app.schemas.paper",
}

# Classes to import from each schema file (for reference, we'll import *)
SCHEMA_CLASSES = {
    "app.schemas.audit": [
        "AuditQuestionResponse",
        "AuditListResponse",
        "RejectRequest",
        "BatchAuditRequest",
    ],
    "app.schemas.auth": [
        "ForgotPasswordRequest",
        "TokenRefreshResponse",
    ],
    "app.schemas.dashboard": [
        "OverviewStats",
        "TrendDataPoint",
        "QuestionTypeDistribution",
        "DifficultyDistribution",
        "ActivityItem",
        "DashboardOverview",
    ],
    "app.schemas.exam_record": [
        "QuestionResponse",
        "UserAnswerDetailResponse",
        "ExamRecordListResponse",
        "ExamRecordDetailResponse",
        "ExamRecordStatsResponse",
    ],
    "app.schemas.exam": [
        "UserAnswerCreate",
        "UserAnswerResponse",
        "ExamRecordResponse",
        "ExamCreate",
        "ExamUpdate",
        "ExamResponse",
        "ExamGradeRequest",
        "ExamGradeResponse",
    ],
    "app.schemas.knowledge": [
        "KnowledgePointCreate",
        "KnowledgePointUpdate",
        "KnowledgePointResponse",
        "KnowledgeStatistics",
        "AIImportRequest",
        "BatchAnalyzeRequest",
        "DocumentKnowledgeImport",
        "BatchImportRequest",
        "KnowledgeQuestionCountRequest",
    ],
    "app.schemas.notification": [
        "NotificationResponse",
        "NotificationStats",
    ],
    "app.schemas.paper_template": [
        "PaperTemplateCreate",
        "PaperTemplateUpdate",
        "PaperTemplateResponse",
    ],
    "app.schemas.paper": [
        "QuestionOptionSimpleResponse",
        "QuestionInPaperResponse",
        "ExamPaperQuestionResponse",
        "PaperCreateFixed",
        "FixedQuestionItem",
        "PaperCreateRandom",
        "RandomSelectionRules",
        "PaperUpdate",
        "PaperResponse",
        "PaperDetailResponse",
        "PaperListResponse",
        "PaperCreateUnion",
        "AutoGenerateRequest",
        "AutoGeneratePreviewRequest",
        "DifficultyDistributionRequest",
        "DifficultyDistributionResponse",
        "ExportPaperRequest",
    ],
}


def remove_schema_blocks(content: str, class_names: list[str]) -> str:
    """Remove inline BaseModel class definitions and their section header."""
    lines = content.split("\n")
    result = []
    skip_until_next_top_level = False
    class_name_set = set(class_names)

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this line starts a class we want to remove
        match = re.match(r"^class\s+(\w+)\s*\(\s*BaseModel\s*\)\s*:", stripped)
        if match and match.group(1) in class_name_set:
            skip_until_next_top_level = True
            # Check if previous line was a section comment
            if result and result[-1].strip().startswith("# ============ Schema"):
                result.pop()
            continue

        # Check if we're still in a class block (indented content)
        if skip_until_next_top_level:
            if stripped == "":
                # Skip blank lines within class blocks (but preserve one)
                if result and result[-1].strip() != "":
                    continue
                else:
                    skip_until_next_top_level = False
                    result.append(line)
                    continue
            # If line is at top level (no indent or just a comment/string), stop skipping
            indent = len(line) - len(line.lstrip())
            if indent == 0 and stripped and not stripped.startswith("#"):
                skip_until_next_top_level = False
                result.append(line)
            # Otherwise skip this line (it's inside the class)
            continue

        result.append(line)

    return "\n".join(result)


def add_schema_imports(content: str, schema_module: str) -> str:
    """Add import statement for schemas module."""
    lines = content.split("\n")
    import_line = f"from {schema_module} import *"

    # Find the right place to insert - after existing imports, before logger/router
    insert_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from app.") or stripped.startswith("import ") or stripped == "":
            insert_idx = i + 1
        elif stripped.startswith("logger") or stripped.startswith("router ="):
            break
        elif (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith('"""')
            and not stripped.startswith("'''")
        ):
            if insert_idx > 0:
                break

    # Check if import already exists
    if import_line in content:
        return content

    lines.insert(insert_idx, import_line)
    return "\n".join(lines)


def process_router(rel_path: str, schema_module: str, class_names: list[str]) -> None:
    """Process a single router file."""
    filepath = APP_DIR / rel_path
    if not filepath.exists():
        print(f"⚠ Skipping {filepath} (not found)")
        return

    content = filepath.read_text(encoding="utf-8")

    # Remove schema blocks
    updated = remove_schema_blocks(content, class_names)

    # Add schema imports
    updated = add_schema_imports(updated, schema_module)

    filepath.write_text(updated, encoding="utf-8")
    print(f"  ✓ Updated {rel_path}")


def main() -> None:
    for rel_path, schema_module in ROUTER_SCHEMA_IMPORTS.items():
        class_names = SCHEMA_CLASSES.get(schema_module, [])
        if class_names:
            process_router(rel_path, schema_module, class_names)

    print("\n✓ Router imports updated!")


if __name__ == "__main__":
    main()
