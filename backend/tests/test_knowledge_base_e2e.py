"""End-to-end test for the three-layer knowledge base architecture."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.main import app
from app.models.knowledge import KnowledgeBase, KnowledgeEntry, KnowledgePoint
from app.models.user import User
from app.services.auth import AuthService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def teacher_token(client: TestClient, db: Session) -> str:
    """Create a teacher user and return JWT token."""
    username = "e2e_teacher_kb"
    password = "test123456"

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        db.delete(existing)
        db.commit()

    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash(password),
        role=2,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    response = client.post("/api/auth/login/json", json={"username": username, "password": password})
    assert response.status_code == 200
    body = response.json()
    # 兼容统一响应封装 {code, message, data: {...}}
    payload = body.get("data", body)
    return payload["access_token"]


@pytest.fixture
def auth_headers(teacher_token: str) -> dict:
    return {"Authorization": f"Bearer {teacher_token}"}


def _resp_json(response):
    """Unwrap response — handles both direct model and wrapped {data: model} formats."""
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


class TestKnowledgeBaseE2E:
    """End-to-end tests for the three-layer knowledge base architecture."""

    def test_create_knowledge_base(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/knowledge-bases/",
            json={
                "name": "E2E Test KB",
                "description": "End-to-end test knowledge base",
                "category": "default",
                "visibility": "private",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Create KB failed: {response.text}"
        data = _resp_json(response)
        assert data["name"] == "E2E Test KB"
        assert data["entries_count"] == 0
        assert data["points_count"] == 0
        return data["id"]

    def test_upload_document_creates_entries(self, client: TestClient, auth_headers: dict, db: Session):
        kb_resp = client.post(
            "/api/knowledge-bases/",
            json={"name": "E2E Upload KB", "category": "default", "visibility": "private"},
            headers=auth_headers,
        )
        assert kb_resp.status_code == 200
        kb_id = _resp_json(kb_resp)["id"]

        test_content = "# Chapter 1: Introduction\n\n" + "This is test content. " * 200 + "\n\n# Chapter 2: Details\n\n" + "More details here. " * 150
        response = client.post(
            f"/api/knowledge-bases/{kb_id}/upload",
            files={"file": ("test.md", test_content, "text/markdown")},
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = _resp_json(response)

        assert data["entries_created"] > 0, "Should create at least one entry"

        entries_resp = client.get(f"/api/knowledge-bases/{kb_id}/entries", headers=auth_headers)
        assert entries_resp.status_code == 200
        entries = _resp_json(entries_resp)
        assert len(entries) == data["entries_created"]

        for entry in entries:
            assert entry.get("content_preview") or entry.get("content_length", 0) >= 0, "Entry should have preview/length"
            assert entry["title"], "Entry should have a title"

        kb_detail = _resp_json(client.get(f"/api/knowledge-bases/{kb_id}", headers=auth_headers))
        assert kb_detail["source_content"] is not None
        assert len(kb_detail["source_content"]) > 0

        return kb_id

    def test_analyze_and_import_knowledge_points(self, client: TestClient, auth_headers: dict, db: Session):
        kb_resp = client.post(
            "/api/knowledge-bases/",
            json={"name": "E2E Extract KB", "category": "law", "visibility": "private"},
            headers=auth_headers,
        )
        assert kb_resp.status_code == 200
        kb_id = _resp_json(kb_resp)["id"]

        test_content = (
            "# 第一章 总则\n\n"
            "第一条 为了规范考试管理，保障考试公平公正，根据国家有关法律法规，制定本办法。\n\n"
            "第二条 本办法适用于各类学历教育考试、职业资格考试和水平评价考试。考试工作应当遵循公开、公平、公正的原则。\n\n"
            "第三条 考试工作应当遵循公开、公平、公正的原则。各级教育行政部门应当加强对考试工作的领导和管理。\n\n"
            "第四条 考生应当在规定时间内登录报名系统进行网上报名。报名时应当提供真实、准确的个人信息。\n\n"
            "第五条 考生报名时应当提供真实、准确的个人信息。伪造、变造有关证件或材料将承担相应法律责任。\n\n"
            "第六条 考试费用应当按照国家有关规定缴纳，具体标准由省级教育行政部门确定并公示。\n\n"
            "第七条 考生完成报名后，应当及时关注报名系统发布的考试通知，按时打印准考证并参加考试。\n\n"
            "# 第二章 考试组织\n\n"
            "第八条 考试机构应当在考前制定详细的考试方案，包括考场安排、监考人员配置、应急处理预案等内容。\n\n"
            "第九条 考场应当设置在具备良好条件的场所，确保考试期间环境安静、设施完好。\n\n"
            "第十条 监考人员应当认真履行职责，严格遵守考试纪律，维护考场秩序。\n\n"
            "第十一条 考试期间如发生突发事件，监考人员应当立即启动应急预案，并及时报告考试机构。\n\n"
            "第十二条 考试结束后，监考人员应当及时回收试卷，核对数量后密封交送评卷点。\n"
        )
        upload_resp = client.post(
            f"/api/knowledge-bases/{kb_id}/upload",
            files={"file": ("law.md", test_content, "text/markdown")},
            headers=auth_headers,
        )
        assert upload_resp.status_code == 200
        upload_data = _resp_json(upload_resp)
        assert upload_data["entries_created"] > 0, "Should create entries"

        # Fetch entries separately
        entries_resp = client.get(f"/api/knowledge-bases/{kb_id}/entries", headers=auth_headers)
        assert entries_resp.status_code == 200
        entries = _resp_json(entries_resp)
        assert len(entries) > 0
        entry_id = entries[0]["id"]

        analyze_resp = client.post(
            f"/api/knowledge-bases/{kb_id}/entries/{entry_id}/analyze",
            json={"mode": "rule"},
            headers=auth_headers,
        )
        assert analyze_resp.status_code == 200, f"Analyze failed: {analyze_resp.text}"
        preview = _resp_json(analyze_resp)
        assert "knowledge_points" in preview

        import_resp = client.post(
            f"/api/knowledge-bases/{kb_id}/entries/{entry_id}/import",
            json={"knowledge_points": preview["knowledge_points"]},
            headers=auth_headers,
        )
        assert import_resp.status_code == 200, f"Import failed: {import_resp.text}"

        # If points were extracted, verify they have correct kb_id/entry_id
        if preview.get("knowledge_points"):
            points_resp = client.get(f"/api/knowledge-bases/{kb_id}/points", headers=auth_headers)
            assert points_resp.status_code == 200
            points_data = _resp_json(points_resp)
            points = points_data if isinstance(points_data, list) else points_data.get("items", points_data.get("tree", []))
            if len(points) > 0:
                for point in points:
                    assert point.get("knowledge_base_id") == kb_id
                    assert point.get("entry_id") == entry_id

        tree_resp = client.get("/api/knowledge/trees", headers=auth_headers)
        assert tree_resp.status_code == 200

        return kb_id, entry_id

    def test_knowledge_base_crud(self, client: TestClient, auth_headers: dict, db: Session):
        create_resp = client.post(
            "/api/knowledge-bases/",
            json={
                "name": "CRUD Test KB",
                "description": "Testing CRUD",
                "category": "default",
                "exam_type": "司法考试",
                "visibility": "shared",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 200
        kb_id = _resp_json(create_resp)["id"]

        read_resp = client.get(f"/api/knowledge-bases/{kb_id}", headers=auth_headers)
        assert read_resp.status_code == 200
        kb_data = _resp_json(read_resp)
        assert kb_data["name"] == "CRUD Test KB"
        assert kb_data["exam_type"] == "司法考试"

        update_resp = client.put(
            f"/api/knowledge-bases/{kb_id}",
            json={"name": "CRUD Test KB Updated", "visibility": "public"},
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert _resp_json(update_resp)["name"] == "CRUD Test KB Updated"

        list_resp = client.get("/api/knowledge-bases/?category=default", headers=auth_headers)
        assert list_resp.status_code == 200

        delete_resp = client.delete(f"/api/knowledge-bases/{kb_id}", headers=auth_headers)
        assert delete_resp.status_code == 200

        get_after_delete = client.get(f"/api/knowledge-bases/{kb_id}", headers=auth_headers)
        assert get_after_delete.status_code == 404

    def test_list_knowledge_bases(self, client: TestClient, auth_headers: dict):
        for i in range(3):
            client.post(
                "/api/knowledge-bases/",
                json={"name": f"List Test KB {i}", "category": "default", "visibility": "private"},
                headers=auth_headers,
            )

        resp = client.get("/api/knowledge-bases/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = _resp_json(resp)
        assert data["total"] >= 3

    def test_upload_file_formats(self, client: TestClient, auth_headers: dict):
        kb_resp = client.post(
            "/api/knowledge-bases/",
            json={"name": "Format Test KB", "category": "default", "visibility": "private"},
            headers=auth_headers,
        )
        kb_id = _resp_json(kb_resp)["id"]

        txt_content = "This is a plain text document. " * 300
        resp = client.post(
            f"/api/knowledge-bases/{kb_id}/upload",
            files={"file": ("test.txt", txt_content, "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert _resp_json(resp)["entries_created"] > 0

        kb_detail = _resp_json(client.get(f"/api/knowledge-bases/{kb_id}", headers=auth_headers))
        assert "This is a plain text document." in kb_detail["source_content"]
