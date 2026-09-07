"""P0 回归：批量导入的 SAVEPOINT 部分成功语义（import_export.import_questions）。

背景：工程师在每题循环体加了 `with db.begin_nested():`，声称单题失败只回滚该题、
其余题目正常落库。其验证用的临时脚本已删除，无法复现，故由 QA 重新编写正式用例。

覆盖场景：
  A. 全部成功        → success_count == 文件行数，全部落库
  B. 中间某题失败    → 该题回滚，其余落库，errors 有正确原因
  C. 连续多题失败    → 不影响后续题目
  D. 全部失败        → success_count == 0，无脏数据落库
  E. 回归：MAX_IMPORT_SIZE / _safe_cell_value / ImportResult 结构未被破坏

失败注入方式：SQLAlchemy `before_flush` 事件，对 content 含哨兵值的题目抛出
IntegrityError（与生产环境 flush 阶段真实抛出的异常类型一致），从而精确控制
"第几题失败"，并验证 SAVEPOINT 回滚后外层事务仍可继续 commit。
"""

import io
import uuid

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.user import User
from app.services.auth import AuthService

IMPORT_URL = "/api/questions/import"
BOOM = "__BOOM__"  # 触发注入失败的哨兵

HEADERS = ["题型", "题目内容", "正确答案", "难度", "分值", "所属科目ID", "所属章节ID", "选项", "解析"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_xlsx(rows) -> bytes:
    """rows: list of [question_type, content, answer, ...]，构造符合解析器的 xlsx。"""
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _payload(resp) -> dict:
    """解包统一响应信封（app.utils.response.wrap_response）后的业务数据。"""
    body = resp.json()
    return body.get("data", body) if isinstance(body, dict) else body


def _choice_row(content: str, answer: str = "A", boom: bool = False):
    """一行单选题（含 A-D 四个选项，换行分隔以匹配解析器的 MULTILINE 正则）。"""
    text = content if not boom else f"{content} {BOOM}"
    options = "A. 选项甲\nB. 选项乙\nC. 选项丙\nD. 选项丁"
    return ["单选题", text, answer, 1, 5.0, 1, 1, options, "解析"]


def _ensure_teacher(db: Session, username: str = "imp_teacher") -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("Test123456!"),
        role=2,  # teacher
        menu_permissions=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _teacher_token(client: TestClient, db: Session, username: str = "imp_teacher") -> str:
    _ensure_teacher(db, username)
    resp = client.post("/api/auth/login/json", json={"username": username, "password": "Test123456!"})
    assert resp.status_code == 200, resp.text
    body = _payload(resp)
    return body.get("data", body)["access_token"]


def _do_import(client: TestClient, token: str, payload: bytes, filename: str = "q.xlsx"):
    return client.post(
        IMPORT_URL,
        files={"file": (filename, payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {token}"},
    )


def _imported_contents(db: Session, marker: str):
    return [c for (c,) in db.query(Question.content).filter(Question.content.like(f"%{marker}%")).all()]


@pytest.fixture()
def fail_on_boom():
    """让 content 含哨兵的题目在 flush 阶段抛出 IntegrityError。

    模拟生产环境中单题写入违反约束（唯一键/非空/外键）的真实失败，
    异常类型与 SQLAlchemy 实际抛出的类型一致。
    """
    fails = []

    def _hook(session, flush_context, instances):
        for obj in session.new:
            if isinstance(obj, Question) and BOOM in (obj.content or ""):
                fails.append(obj.content)
                raise IntegrityError("模拟单题写入失败", None, Exception("boom"))

    event.listen(Session, "before_flush", _hook)
    yield fails
    event.remove(Session, "before_flush", _hook)


@pytest.fixture()
def import_env(client: TestClient, db: Session):
    token = _teacher_token(client, db)
    # uuid4 保证 marker 全局唯一：测试共用同一 test.db，数据跨用例持久保留
    marker = f"svpt-{uuid.uuid4().hex}"
    yield client, db, token, marker


def _refresh(db: Session) -> None:
    """结束当前读事务，确保后续查询能看到请求侧新提交的数据。"""
    db.rollback()


# --------------------------------------------------------------------------- #
# A~D: 部分成功语义
# --------------------------------------------------------------------------- #
class TestImportSavepointSemantics:
    def test_all_success(self, import_env):
        """A. 全部成功：success_count == 行数，全部落库，fail_count == 0。"""
        client, db, token, marker = import_env
        rows = [_choice_row(f"{marker}-Q{i}") for i in range(1, 5)]
        resp = _do_import(client, token, _make_xlsx(rows))

        assert resp.status_code == 200, resp.text
        body = _payload(resp)
        assert body["success_count"] == 4
        assert body["fail_count"] == 0
        assert body["errors"] == []

        _refresh(db)
        stored = _imported_contents(db, marker)
        assert len(stored) == 4
        assert {f"{marker}-Q{i}" for i in range(1, 5)} <= set(stored)

    def test_middle_failure_keeps_others(self, import_env, fail_on_boom):
        """B. 中间某题失败：仅该题回滚，其余题目正常落库，errors 记录原因与题号。"""
        client, db, token, marker = import_env
        rows = [
            _choice_row(f"{marker}-Q1"),
            _choice_row(f"{marker}-Q2", boom=True),  # 第 2 题失败
            _choice_row(f"{marker}-Q3"),
            _choice_row(f"{marker}-Q4"),
        ]
        resp = _do_import(client, token, _make_xlsx(rows))

        assert resp.status_code == 200, resp.text
        body = _payload(resp)
        assert body["success_count"] == 3
        assert body["fail_count"] == 1
        assert len(body["errors"]) == 1
        assert "第 2 题导入失败" in body["errors"][0]

        _refresh(db)
        stored = set(_imported_contents(db, marker))
        assert f"{marker}-Q1" in stored
        assert f"{marker}-Q3" in stored
        assert f"{marker}-Q4" in stored
        assert not any("Q2" in c for c in stored), f"失败题目不应落库，实际: {stored}"

    def test_consecutive_failures_do_not_block_later_rows(self, import_env, fail_on_boom):
        """C. 连续多题失败：失败不污染后续题目，后续题正常落库。"""
        client, db, token, marker = import_env
        rows = [
            _choice_row(f"{marker}-Q1", boom=True),
            _choice_row(f"{marker}-Q2", boom=True),
            _choice_row(f"{marker}-Q3"),
        ]
        resp = _do_import(client, token, _make_xlsx(rows))

        assert resp.status_code == 200, resp.text
        body = _payload(resp)
        assert body["success_count"] == 1
        assert body["fail_count"] == 2
        assert sorted(e.split("题导入")[0] for e in body["errors"]) == ["第 1 ", "第 2 "]

        _refresh(db)
        stored = set(_imported_contents(db, marker))
        assert f"{marker}-Q3" in stored, "连续失败后第 3 题仍应落库"
        assert not any(c.endswith("Q1") or c.endswith("Q2") for c in stored)

    def test_all_fail_leaves_no_dirty_data(self, import_env, fail_on_boom):
        """D. 全部失败：success_count == 0，数据库无脏数据。"""
        client, db, token, marker = import_env
        rows = [_choice_row(f"{marker}-Q{i}", boom=True) for i in range(1, 4)]
        resp = _do_import(client, token, _make_xlsx(rows))

        assert resp.status_code == 200, resp.text
        body = _payload(resp)
        assert body["success_count"] == 0
        assert body["fail_count"] == 3

        _refresh(db)
        assert _imported_contents(db, marker) == [], "全部失败时不应有任何题目落库"

    def test_failure_does_not_orphan_options(self, import_env, fail_on_boom):
        """失败题目的选项必须随 SAVEPOINT 一并回滚，不能留下孤儿选项。"""
        client, db, token, marker = import_env
        rows = [_choice_row(f"{marker}-Q1", boom=True), _choice_row(f"{marker}-Q2")]
        resp = _do_import(client, token, _make_xlsx(rows))
        assert resp.status_code == 200, resp.text

        _refresh(db)
        from app.models.question import QuestionOption

        orphan = (
            db.query(QuestionOption)
            .outerjoin(Question, QuestionOption.question_id == Question.id)
            .filter(Question.id.is_(None))
            .count()
        )
        assert orphan == 0, "SAVEPOINT 回滚后不应残留指向不存在题目的选项"


# --------------------------------------------------------------------------- #
# E: 同文件改动的回归风险
# --------------------------------------------------------------------------- #
class TestImportRegressionGuards:
    def test_oversized_file_rejected_with_413(self, import_env):
        """回归：MAX_IMPORT_SIZE（10MB）限制未被破坏。"""
        client, _db, token, _marker = import_env
        payload = b"x" * (10 * 1024 * 1024 + 1)
        resp = _do_import(client, token, payload)
        assert resp.status_code == 413
        assert "10MB" in resp.json()["detail"]

    def test_safe_cell_value_neutralizes_formula_injection(self):
        """回归：导出防公式注入未被破坏（= + - @ 开头强制转文本）。"""
        from app.routers.questions.import_export import _safe_cell_value

        assert _safe_cell_value("=1+1") == "'=1+1"
        assert _safe_cell_value("+1+1") == "'+1+1"
        assert _safe_cell_value("-1+1") == "'-1+1"
        assert _safe_cell_value("@SUM(A1)") == "'@SUM(A1)"
        assert _safe_cell_value("普通文本") == "普通文本"
        assert _safe_cell_value(123) == 123

    def test_import_result_schema_unchanged(self):
        """回归：ImportResult 返回结构未变（success_count/fail_count/errors）。"""
        from app.schemas.question import ImportResult

        r = ImportResult(success_count=1, fail_count=2, errors=["e"])
        assert r.model_dump() == {"success_count": 1, "fail_count": 2, "errors": ["e"]}
        assert ImportResult(success_count=0, fail_count=0).errors == []

    def test_empty_file_returns_zero_counts(self, import_env):
        """无题目可解析时返回 0/0 且给出提示，不抛 500。"""
        client, _db, token, _marker = import_env
        resp = _do_import(client, token, _make_xlsx([]))
        assert resp.status_code == 200, resp.text
        body = _payload(resp)
        assert body["success_count"] == 0
        assert body["fail_count"] == 0
