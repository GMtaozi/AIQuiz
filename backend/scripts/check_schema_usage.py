#!/usr/bin/env python3
"""Check which schema classes each router actually uses."""

from pathlib import Path

routers_dir = Path("app/routers")

schema_classes = {
    "audit": ["AuditQuestionResponse", "AuditListResponse", "RejectRequest", "BatchAuditRequest"],
    "auth": ["ForgotPasswordRequest", "TokenRefreshResponse"],
    "dashboard": [
        "OverviewStats",
        "TrendDataPoint",
        "QuestionTypeDistribution",
        "DifficultyDistribution",
        "ActivityItem",
        "DashboardOverview",
    ],
    "exam_record": [
        "QuestionResponse",
        "UserAnswerDetailResponse",
        "ExamRecordListResponse",
        "ExamRecordDetailResponse",
        "ExamRecordStatsResponse",
    ],
    "exam": [
        "UserAnswerCreate",
        "UserAnswerResponse",
        "ExamRecordResponse",
        "ExamCreate",
        "ExamUpdate",
        "ExamResponse",
        "ExamGradeRequest",
        "ExamGradeResponse",
    ],
    "knowledge": [
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
    "notification": ["NotificationResponse", "NotificationStats"],
    "paper_template": ["PaperTemplateCreate", "PaperTemplateUpdate", "PaperTemplateResponse"],
    "paper": [
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

for router_file in [
    "audit.py",
    "auth.py",
    "dashboard.py",
    "exam_records.py",
    "exams.py",
    "knowledge.py",
    "notifications.py",
    "paper_template.py",
    "papers.py",
]:
    filepath = routers_dir / router_file
    content = filepath.read_text(encoding="utf-8")

    # Find which schema module this router uses
    schema_match = None
    for schema_name in schema_classes:
        if f"from app.schemas.{schema_name} import *" in content:
            schema_match = schema_name
            break

    if not schema_match:
        print(f"{router_file}: no schema import found")
        continue

    # Find which classes from this schema are actually used
    classes = schema_classes[schema_match]
    used = []
    for cls in classes:
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("from ") or stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if cls in line:
                used.append(cls)
                break

    print(f"{router_file}: uses {used}")
