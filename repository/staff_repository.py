"""인력현황(staff) 저장소 — Supabase(PostgreSQL) 접근.

연결 풀은 horse_repository.pool을 그대로 재사용한다(접속 수 상한을 한 곳에서 관리).
"""
from __future__ import annotations

import threading
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from config.constants import DUTY_PARTS   # 추가
from repository.horse_repository import pool

_COLUMNS = "id, name, birth_date, position, contact, duty_part, note, created_at, updated_at"

_duty_parts_sql = ", ".join(f"'{p}'" for p in DUTY_PARTS)  # 고정 상수 목록이라 안전

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS staff (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    birth_date DATE NOT NULL,
    position   TEXT NOT NULL DEFAULT '',
    contact    TEXT NOT NULL DEFAULT '',
    duty_part  TEXT NOT NULL CHECK (duty_part IN ({_duty_parts_sql})),
    note       TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Supabase 공개 API(anon 키)로 이 표가 노출되지 않게 막는다.
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
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


def list_staff() -> list[dict]:
    """전체 인력 목록 (이름순). 파트별 묶음은 화면에서 처리한다."""
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM staff ORDER BY name")
        return cur.fetchall()


def get_staff(staff_id: UUID) -> dict | None:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM staff WHERE id = %s", (staff_id,))
        return cur.fetchone()


def create_staff(
    name: str, birth_date, position: str, contact: str, duty_part: str, note: str
) -> dict:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"INSERT INTO staff (name, birth_date, position, contact, duty_part, note) "
            f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_COLUMNS}",
            (name, birth_date, position, contact, duty_part, note),
        )
        return cur.fetchone()


def update_staff(
    staff_id: UUID,
    name: str,
    birth_date,
    position: str,
    contact: str,
    duty_part: str,
    note: str,
) -> dict | None:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"UPDATE staff SET name = %s, birth_date = %s, position = %s, "
            f"contact = %s, duty_part = %s, note = %s, updated_at = now() "
            f"WHERE id = %s RETURNING {_COLUMNS}",
            (name, birth_date, position, contact, duty_part, note, staff_id),
        )
        return cur.fetchone()


def delete_staff(staff_id: UUID) -> bool:
    _ensure_ready()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
        return cur.rowcount > 0