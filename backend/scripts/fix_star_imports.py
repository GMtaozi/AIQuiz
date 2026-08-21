#!/usr/bin/env python3
"""Replace star imports with explicit imports in router files."""

from pathlib import Path

routers_dir = Path("app/routers")

# Map router file -> (schema module, list of classes used)
ROUTER_SCHEMA_USAGE = {
    "audit.py": (
        "app.schemas.audit",
        ["AuditQuestionResponse", "AuditListResponse", "RejectRequest", "BatchAuditRequest"],
    ),
    "auth.py": ("app.schemas.auth", ["ForgotPasswordRequest", "TokenRefreshResponse"]),
    "dashboard.py": (
        "app.schemas.dashboard",
        [
            "OverviewStats",
            "TrendDataPoint",
            "QuestionTypeDistribution",
            "DifficultyDistribution",
            "ActivityItem",
            "DashboardOverview",
        ],
    ),
    "exam_records.py": (
        "app.schemas.exam_record",
        [
            "QuestionResponse",
            "UserAnswerDetailResponse",
            "ExamRecordListResponse",
            "ExamRecordDetailResponse",
            "ExamRecordStatsResponse",
        ],
    ),
    "exams.py": (
        "app.schemas.exam",
        [
            "UserAnswerCreate",
            "UserAnswerResponse",
            "ExamRecordResponse",
            "ExamCreate",
            "ExamUpdate",
            "ExamResponse",
            "ExamGradeRequest",
            "ExamGradeResponse",
        ],
    ),
    "knowledge.py": (
        "app.schemas.knowledge",
        [
            "KnowledgePointCreate",
            "KnowledgePointUpdate",
            "KnowledgePointResponse",
            "KnowledgeStatistics",
            "AIImportRequest",
            "BatchImportRequest",
            "KnowledgeQuestionCountRequest",
        ],
    ),
    "notifications.py": ("app.schemas.notification", ["NotificationResponse", "NotificationStats"]),
    "paper_template.py": (
        "app.schemas.paper_template",
        ["PaperTemplateCreate", "PaperTemplateUpdate", "PaperTemplateResponse"],
    ),
    "papers.py": (
        "app.schemas.paper",
        [
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
    ),
}

for router_file, (schema_module, classes) in ROUTER_SCHEMA_USAGE.items():
    filepath = routers_dir / router_file
    if not filepath.exists():
        print(f"⚠ {filepath} not found")
        continue

    content = filepath.read_text(encoding="utf-8")

    # Replace star import with explicit import
    star_import = f"from {schema_module} import *"
    explicit_import = f"from {schema_module} import {', '.join(classes)}"

    if star_import in content:
        content = content.replace(star_import, explicit_import)
        filepath.write_text(content, encoding="utf-8")
        print(f"  ✓ {router_file}: {explicit_import}")
    else:
        print(f"  ⊘ {router_file}: star import not found")

print("\n✓ Done!")
