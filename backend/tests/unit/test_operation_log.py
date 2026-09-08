"""Unit tests for the Operation Log System."""

import asyncio
import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from app.main import app
from app.models import OperationLog, User
from app.models.user import ROLE_DEFAULT_PERMISSIONS
from app.services.auth import AuthService
from app.services.operation_log_service import (
    OperationAction,
    ResourceType,
    export_logs_csv,
    get_log_by_id,
    log_operation,
    query_logs,
)


def create_access_token(data: dict) -> str:
    """Helper function to create access token using AuthService."""
    return AuthService.create_access_token(data)


def consume_async_gen(async_gen):
    """Helper to consume an async generator into a list."""
    return asyncio.run(_async_gen_to_list(async_gen))


async def _async_gen_to_list(async_gen):
    result = []
    async for chunk in async_gen:
        result.append(chunk)
    return result


# ============ Fixtures ============


@pytest.fixture
def db():
    """Provide a database session (from conftest)."""
    from app.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db: Session) -> User:
    """Create or get an admin user."""
    user = db.query(User).filter(User.username == "testadmin").first()
    if not user:
        user = User(
            username="testadmin",
            email="admin@test.com",
            hashed_password=bcrypt.hash("TestPassword123"),
            role=1,
            status=1,
            menu_permissions=ROLE_DEFAULT_PERMISSIONS[1],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate admin JWT token."""
    return create_access_token({"sub": str(admin_user.id), "role": admin_user.role})


@pytest.fixture
def sample_logs(db: Session, admin_user: User) -> list:
    """Create sample operation logs."""
    logs = [
        OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=admin_user.id,
            description=f"用户登录: {admin_user.username}",
            ip_address="127.0.0.1",
            status="success",
            created_at=datetime.utcnow() - timedelta(hours=2),
        ),
        OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.CREATE,
            resource_type=ResourceType.PAPER,
            resource_id=1,
            description="创建试卷: 测试试卷",
            ip_address="127.0.0.1",
            status="success",
            created_at=datetime.utcnow() - timedelta(hours=1),
        ),
        OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=999,
            description="登录失败: unknown_user",
            ip_address="10.0.0.1",
            status="failure",
            created_at=datetime.utcnow() - timedelta(minutes=30),
        ),
    ]
    for log in logs:
        db.add(log)
    db.commit()
    return logs


# ============ Model Tests ============


class TestOperationLogModel:
    """Test OperationLog model attributes."""

    def test_create_operation_log(self, db: Session, admin_user: User):
        """Test creating an operation log entry."""
        log = OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=admin_user.id,
            description="Test login",
            ip_address="127.0.0.1",
            status="success",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.id is not None
        assert log.user_id == admin_user.id
        assert log.username == admin_user.username
        assert log.action == OperationAction.LOGIN
        assert log.resource_type == ResourceType.USER
        assert log.status == "success"
        assert log.created_at is not None

    def test_default_values(self, db: Session, admin_user: User):
        """Test default values are set correctly."""
        log = OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.CREATE,
            resource_type=ResourceType.QUESTION,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.status == "success"
        assert log.resource_id is None
        assert log.description is None
        assert log.ip_address is None
        assert log.user_agent is None
        assert log.details is None

    def test_details_json_field(self, db: Session, admin_user: User):
        """Test JSON details field."""
        details = {"paper_type": "fixed", "question_count": 10}
        log = OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.CREATE,
            resource_type=ResourceType.PAPER,
            resource_id=1,
            details=details,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.details == details
        assert log.details["paper_type"] == "fixed"
        assert log.details["question_count"] == 10


# ============ Service Tests ============


class TestLogOperation:
    """Test log_operation service function."""

    def test_log_basic_operation(self, db: Session, admin_user: User):
        """Test logging a basic operation."""
        log = log_operation(
            db=db,
            user=admin_user,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=admin_user.id,
            description="Test login",
        )

        assert log.id is not None
        assert log.user_id == admin_user.id
        assert log.action == OperationAction.LOGIN
        assert log.status == "success"

    def test_log_with_ip_and_ua(self, db: Session, admin_user: User):
        """Test logging with IP and User-Agent."""
        log = log_operation(
            db=db,
            user=admin_user,
            action=OperationAction.CREATE,
            resource_type=ResourceType.PAPER,
            resource_id=1,
            description="Created paper",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "Mozilla/5.0"

    def test_log_failure_status(self, db: Session, admin_user: User):
        """Test logging a failed operation."""
        log = log_operation(
            db=db,
            user=admin_user,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            status="failure",
            details={"reason": "invalid_password"},
        )

        assert log.status == "failure"
        assert log.details["reason"] == "invalid_password"


class TestQueryLogs:
    """Test query_logs service function."""

    def test_query_all_logs(self, db: Session, sample_logs):
        """Test querying all logs."""
        logs, total = query_logs(db=db)
        assert total >= len(sample_logs)
        assert len(logs) >= len(sample_logs)

    def test_query_by_user_id(self, db: Session, sample_logs, admin_user: User):
        """Test filtering by user_id."""
        logs, total = query_logs(db=db, user_id=admin_user.id)
        assert all(log.user_id == admin_user.id for log in logs)

    def test_query_by_action(self, db: Session, sample_logs):
        """Test filtering by action."""
        logs, total = query_logs(db=db, action=OperationAction.LOGIN)
        assert all(log.action == OperationAction.LOGIN for log in logs)

    def test_query_by_status(self, db: Session, sample_logs):
        """Test filtering by status."""
        logs, total = query_logs(db=db, status="failure")
        assert all(log.status == "failure" for log in logs)

    def test_query_by_date_range(self, db: Session, sample_logs):
        """Test filtering by date range."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        logs, total = query_logs(db=db, start_date=yesterday, end_date=today)
        assert total > 0

    def test_query_pagination(self, db: Session, sample_logs):
        """Test pagination."""
        logs_page1, total = query_logs(db=db, page=1, page_size=2)
        assert len(logs_page1) <= 2


class TestExportLogsCsv:
    """Test export_logs_csv service function."""

    def test_export_returns_streaming_response(self, db: Session, sample_logs):
        """Test export returns StreamingResponse."""
        response = export_logs_csv(db=db)
        assert response.status_code == 200
        assert "text/csv" in response.media_type

    def test_export_csv_content(self, db: Session, sample_logs):
        """Test CSV content has correct headers and rows."""
        response = export_logs_csv(db=db)

        # Consume async generator
        chunks = consume_async_gen(response.body_iterator)
        content = b"".join(chunks)

        # Check BOM
        assert content[:3] == b"\xef\xbb\xbf"

        # Parse CSV
        csv_text = content[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Check header
        assert rows[0] == [
            "ID",
            "用户ID",
            "用户名",
            "操作",
            "资源类型",
            "资源ID",
            "描述",
            "IP地址",
            "状态",
            "详情",
            "时间",
        ]

        # Check data rows
        assert len(rows) >= len(sample_logs) + 1  # +1 for header

    def test_export_with_filters(self, db: Session, sample_logs):
        """Test export with filters."""
        response = export_logs_csv(
            db=db,
            action=OperationAction.LOGIN,
        )
        chunks = consume_async_gen(response.body_iterator)
        content = b"".join(chunks)
        csv_text = content[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Filter out header and empty rows
        data_rows = [row for row in rows[1:] if row]

        # All data rows should have LOGIN action (column index 3)
        for row in data_rows:
            assert row[3] == OperationAction.LOGIN


class TestGetLogById:
    """Test get_log_by_id service function."""

    def test_get_existing_log(self, db: Session, sample_logs):
        """Test getting an existing log."""
        log_id = sample_logs[0].id
        log = get_log_by_id(db=db, log_id=log_id)
        assert log is not None
        assert log.id == log_id

    def test_get_nonexistent_log(self, db: Session):
        """Test getting a non-existent log."""
        log = get_log_by_id(db=db, log_id=99999)
        assert log is None


def _login(client: TestClient, username: str = "testadmin", password: str = "TestPassword123") -> str:
    """Login and return access token."""
    resp = client.post("/api/auth/login/json", json={"username": username, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    # Response may be wrapped in "data" envelope
    if "data" in body:
        return body["data"]["access_token"]
    return body["access_token"]


# ============ API Endpoint Tests ============


class TestOperationLogAPI:
    """Test operation log API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_operation_logs_admin(
        self, client: TestClient, db: Session, admin_user: User, sample_logs
    ):
        """Test admin can list operation logs."""
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/system/operation-logs", headers=headers)
        assert response.status_code == 200
        # Response may be wrapped in standard envelope
        resp_data = response.json()
        data = resp_data.get("data", resp_data)
        assert "items" in data
        assert "total" in data
        assert data["total"] >= len(sample_logs)

    def test_list_operation_logs_with_filters(
        self, client: TestClient, db: Session, admin_user: User, sample_logs
    ):
        """Test listing logs with filters."""
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/api/system/operation-logs",
            params={"action": OperationAction.LOGIN},
            headers=headers,
        )
        assert response.status_code == 200
        resp_data = response.json()
        data = resp_data.get("data", resp_data)
        assert all(item["action"] == OperationAction.LOGIN for item in data["items"])

    def test_list_operation_logs_pagination(
        self, client: TestClient, db: Session, admin_user: User, sample_logs
    ):
        """Test pagination."""
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/api/system/operation-logs",
            params={"page": 1, "page_size": 2},
            headers=headers,
        )
        assert response.status_code == 200
        resp_data = response.json()
        data = resp_data.get("data", resp_data)
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_export_operation_logs(
        self, client: TestClient, db: Session, admin_user: User, sample_logs
    ):
        """Test exporting logs as CSV."""
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/api/system/operation-logs/export",
            headers=headers,
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_list_action_types(self, client: TestClient, db: Session, admin_user: User):
        """Test getting action types enum."""
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/api/system/operation-logs/actions",
            headers=headers,
        )
        assert response.status_code == 200
        resp_data = response.json()
        data = resp_data.get("data", resp_data)
        assert "actions" in data
        assert "resource_types" in data
        assert "statuses" in data
        assert len(data["actions"]) > 0


# ============ Integration Tests ============


class TestInstrumentationIntegration:
    """Test operation log is created when instrumented endpoints are called."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_login_creates_operation_log(
        self, client: TestClient, admin_user: User
    ):
        """Test that login creates an operation log."""
        from app.database import SessionLocal
        
        # Login
        response = client.post(
            "/api/auth/login/json",
            json={"username": "testadmin", "password": "TestPassword123"},
        )
        assert response.status_code == 200

        # Check log was created using a new session
        session = SessionLocal()
        try:
            log = (
                session.query(OperationLog)
                .filter(OperationLog.action == OperationAction.LOGIN)
                .first()
            )
            assert log is not None
            assert log.user_id == admin_user.id
            assert log.username == "testadmin"
        finally:
            session.close()

    def test_logout_creates_operation_log(
        self, client: TestClient, admin_user: User
    ):
        """Test that logout creates an operation log."""
        # Login first to get token
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Logout
        response = client.post("/api/auth/logout", headers=headers)
        assert response.status_code == 200

        # Check log was created using a new session
        from app.database import SessionLocal
        session = SessionLocal()
        try:
            log = (
                session.query(OperationLog)
                .filter(OperationLog.action == OperationAction.LOGOUT)
                .order_by(OperationLog.id.desc())
                .first()
            )
            assert log is not None
            assert log.user_id == admin_user.id
        finally:
            session.close()


# ============ Security Tests ============


class TestSecurity:
    """Security-related tests for operation log system."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_sql_injection_in_keyword(self, client: TestClient, admin_user: User):
        """Test SQL injection attempts are handled."""
        token = create_access_token({"sub": str(admin_user.id), "role": admin_user.role})
        headers = {"Authorization": f"Bearer {token}"}

        # Try SQL injection in keyword
        response = client.get(
            "/api/system/operation-logs",
            params={"keyword": "'; DROP TABLE operation_logs; --"},
            headers=headers,
        )
        assert response.status_code == 200

        # Table should still exist
        response = client.get(
            "/api/system/operation-logs",
            headers=headers,
        )
        assert response.status_code == 200

    def test_csv_formula_injection_prevention(self, db: Session, admin_user: User):
        """Test CSV export prevents formula injection."""
        # Create log with formula-like content
        log = OperationLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=OperationAction.CREATE,
            resource_type=ResourceType.PAPER,
            description="=CMD|' /C calc'!A0",
            status="success",
        )
        db.add(log)
        db.commit()

        response = export_logs_csv(db=db)
        chunks = consume_async_gen(response.body_iterator)
        content = b"".join(chunks)
        csv_text = content[3:].decode("utf-8")

        # The formula-injected content should be prefixed with '
        assert "'=CMD" in csv_text or "=CMD" not in csv_text.split("\n")[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
