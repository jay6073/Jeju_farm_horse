"""예산 비교 작업(budget_works) 저장소 — Supabase(PostgreSQL) 접근.

연결 풀은 horse_repository.pool을 그대로 재사용한다(접속 수 상한을 한 곳에서 관리).
"""
from __future__ import annotations

import threading
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from repository.horse_repository import pool

_COLUMNS = "id, title, payload, created_at, updated_at"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_works (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT NOT NULL,
    payload    JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Supabase 공개 API(anon 키)로 이 표가 노출되지 않게 막는다.
ALTER TABLE budget_works ENABLE ROW LEVEL SECURITY;
"""

_init_lock = threading.Lock()
_ready = False


def _ensure_ready() -> None:
    """풀이 닫혀 있으면 열고, 표가 없으면 만든다 (프로세스당 1회)."""
    global _ready
    if _ready:
        return
    with _init_lock:
        if _ready:
            return
        if pool.closed:
            pool.open()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA)
        _ready = True


def list_works() -> list[dict]:
    """payload를 제외한 목록 (최근 수정순)."""
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, title, updated_at FROM budget_works "
            "ORDER BY updated_at DESC LIMIT 200"
        )
        return cur.fetchall()


def get_work(work_id: UUID) -> dict | None:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM budget_works WHERE id = %s", (work_id,))
        return cur.fetchone()


def create_work(title: str, payload: dict) -> dict:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"INSERT INTO budget_works (title, payload) VALUES (%s, %s) "
            f"RETURNING {_COLUMNS}",
            (title, Jsonb(payload)),
        )
        return cur.fetchone()


def update_work(work_id: UUID, title: str, payload: dict) -> dict | None:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"UPDATE budget_works SET title = %s, payload = %s, updated_at = now() "
            f"WHERE id = %s RETURNING {_COLUMNS}",
            (title, Jsonb(payload), work_id),
        )
        return cur.fetchone()


def delete_work(work_id: UUID) -> bool:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM budget_works WHERE id = %s", (work_id,))
        return cur.rowcount > 0
