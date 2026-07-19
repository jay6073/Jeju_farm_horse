"""
horses 테이블에 대한 PostgreSQL(Supabase) 접근 계층.
"""
from __future__ import annotations

import io
import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from models.horse import Horse, STATUS_NORMAL, HORSE_SPECIES, ALL_STATUSES

DATABASE_URL = os.environ["DATABASE_URL"]
POOL_MIN_SIZE = int(os.environ.get("DATABASE_POOL_MIN", "1"))
POOL_MAX_SIZE = int(os.environ.get("DATABASE_POOL_MAX", "4"))
POOL_TIMEOUT = int(os.environ.get("DATABASE_POOL_TIMEOUT", "10"))

_STATUS_ALLOWED = ", ".join(f"'{s}'" for s in ALL_STATUSES)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=POOL_MIN_SIZE,
    max_size=POOL_MAX_SIZE,
    timeout=POOL_TIMEOUT,
    open=False,
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS horses (
    id             BIGSERIAL PRIMARY KEY,
    마번           TEXT,
    마명           TEXT NOT NULL,
    마종           TEXT NOT NULL,
    품종코드       TEXT,
    상태           TEXT NOT NULL DEFAULT '{STATUS_NORMAL}',
    상태발생일자   DATE,

    CONSTRAINT chk_horses_status CHECK (상태 IN ({_STATUS_ALLOWED}))
);
"""


def _escape_copy_value(value: Any) -> str:
    """COPY TEXT FORMAT 스펙에 맞춘 NULL 및 특수문자 이스케이프."""
    if value is None:
        return r"\N"

    s = str(value)
    s = s.replace("\\", "\\\\")
    if s.upper() == "N":
        return r"\N"

    s = s.replace("\t", r"\t")
    s = s.replace("\n", r"\n")
    s = s.replace("\r", r"\r")
    return s


def _validate_horse(horse: Horse) -> None:
    """단건 및 대량 등록 시 데이터 정합성을 보장하기 위한 공통 검증 함수."""
    if not horse.마명:
        raise ValueError("마명은 필수입니다.")
    if not horse.마종:
        raise ValueError("마종은 필수입니다.")
    if horse.상태 not in ALL_STATUSES:
        raise ValueError(f"허용되지 않는 상태입니다: {horse.상태}")


def init_db() -> None:
    """테이블 생성, 레거시 인덱스 제거, 마번 고유 인덱스를 보장한다. (idempotent)"""
    if pool.closed:
        pool.open()

    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA)
                cur.execute("DROP INDEX IF EXISTS uq_horses_mamyeong;")
                cur.execute("DROP INDEX IF EXISTS uq_horses_identity;")
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_horses_mabeon "
                    "ON horses(마번) WHERE 마번 IS NOT NULL;"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_horses_majong_sangtae "
                    "ON horses(마종, 상태);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_horses_status_name "
                    "ON horses(상태, 마명);"
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def close_pool() -> None:
    """애플리케이션 종료 시 커넥션 pool을 안전하게 닫는다."""
    if not pool.closed:
        pool.close()


@contextmanager
def _get_connection() -> Iterator:
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _row_to_horse(row: dict) -> Horse:
    db_date = row["상태발생일자"]
    str_date = db_date.strftime("%Y-%m-%d") if db_date else None

    return Horse(
        id=row["id"],
        마번=row["마번"],
        마명=row["마명"],
        마종=row["마종"],
        품종코드=row["품종코드"],
        상태=row["상태"],
        상태발생일자=str_date,
    )


class HorseRepository:
    """horses 테이블 CRUD 계층."""

    def __init__(self):
        # SQLite 버전과 동일하게, 인스턴스 생성 시 스키마가 항상 준비되도록 보장한다.
        # init_db()는 CREATE TABLE IF NOT EXISTS 등 전부 idempotent라 여러 번 불러도 안전하다.
        init_db()

    # ---------- 생성 ----------

    def insert(self, horse: Horse) -> int:
        _validate_horse(horse)

        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO horses (마번, 마명, 마종, 품종코드, 상태, 상태발생일자)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (horse.마번, horse.마명, horse.마종, horse.품종코드, horse.상태, horse.상태발생일자),
                )
                return cur.fetchone()["id"]

    def insert_many(self, horses: list[Horse]) -> int:
        """사전 유효성 검증 + COPY 기반 고성능 일괄 삽입."""
        if not horses:
            return 0

        seen_mabeon = set()
        for idx, h in enumerate(horses):
            try:
                _validate_horse(h)
            except ValueError as e:
                raise ValueError(f"Batch index {idx}: {e}") from e

            if h.마번:
                if h.마번 in seen_mabeon:
                    raise ValueError(
                        f"Batch 내부에 중복된 마번({h.마번!r})이 포함되어 일괄 처리가 불가능합니다."
                    )
                seen_mabeon.add(h.마번)

        buffer = io.StringIO()
        for h in horses:
            v_mabeon = _escape_copy_value(h.마번)
            v_mamyeong = _escape_copy_value(h.마명)
            v_majong = _escape_copy_value(h.마종)
            v_pumjong = _escape_copy_value(h.품종코드)
            v_sangtae = _escape_copy_value(h.상태)
            v_ilja = _escape_copy_value(h.상태발생일자)

            buffer.write(f"{v_mabeon}\t{v_mamyeong}\t{v_majong}\t{v_pumjong}\t{v_sangtae}\t{v_ilja}\n")

        buffer.seek(0)

        with _get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    with cur.copy(
                        "COPY horses (마번, 마명, 마종, 품종코드, 상태, 상태발생일자) FROM STDIN"
                    ) as copy_op:
                        copy_op.write(buffer.getvalue())
                except Exception as db_err:
                    raise RuntimeError(
                        "데이터베이스 벌크 복사(COPY) 처리 중 제약조건 충돌 또는 연동 오류가 "
                        f"발생했습니다. 원인: {db_err}"
                    ) from db_err

        return len(horses)

    # ---------- 조회 ----------

    def get_by_id(self, horse_id: int) -> Optional[Horse]:
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM horses WHERE id = %s", (horse_id,))
                row = cur.fetchone()
                return _row_to_horse(row) if row else None

    def get_active_names_by_species(self, species: str) -> list[Horse]:
        if species not in HORSE_SPECIES:
            raise ValueError(f"유효하지 않은 마종입니다: {species!r}")
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM horses WHERE 마종 = %s AND 상태 = %s ORDER BY 마명",
                    (species, STATUS_NORMAL),
                )
                rows = cur.fetchall()
                return [_row_to_horse(r) for r in rows]

    def get_all_by_species(self, species: str) -> list[Horse]:
        if species not in HORSE_SPECIES:
            raise ValueError(f"유효하지 않은 마종입니다: {species!r}")
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM horses WHERE 마종 = %s ORDER BY 마명", (species,))
                rows = cur.fetchall()
                return [_row_to_horse(r) for r in rows]

    def get_all(self) -> list[Horse]:
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM horses ORDER BY 마종, 마명")
                rows = cur.fetchall()
                return [_row_to_horse(r) for r in rows]

    def count_active_by_species(self) -> dict[str, int]:
        counts = {species: 0 for species in HORSE_SPECIES}
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT 마종, COUNT(*) AS cnt FROM horses WHERE 상태 = %s GROUP BY 마종",
                    (STATUS_NORMAL,),
                )
                rows = cur.fetchall()
                for r in rows:
                    counts[r["마종"]] = r["cnt"]
        return counts

    def exists_by_마명_or_마번(self, 마명: str, 마번: Optional[str]) -> bool:
        """
        동명이마(같은 마명)를 허용하지 않는다 — 마명이 이미 있으면 무조건 중복으로 본다.
        추가로 마번이 주어졌다면, 마번이 일치하는 경우도 중복으로 잡는다
        (서로 다른 마명이지만 등록번호가 같은, 데이터 오류에 가까운 케이스 방지).
        """
        with _get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if 마번:
                    cur.execute(
                        "SELECT 1 FROM horses WHERE 마명 = %s OR 마번 = %s LIMIT 1",
                        (마명, 마번),
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM horses WHERE 마명 = %s LIMIT 1",
                        (마명,),
                    )
                return cur.fetchone() is not None

    # ---------- 갱신 ----------

    def update_status_bulk(self, horse_ids: list[int], 상태: str, 상태발생일자: str) -> int:
        if not horse_ids:
            return 0
        if 상태 == STATUS_NORMAL:
            raise ValueError("상태 변경은 정상이 아닌 상태로만 가능합니다.")
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE horses
                    SET 상태 = %s, 상태발생일자 = %s
                    WHERE id = ANY(%s)
                    """,
                    (상태, 상태발생일자, horse_ids),
                )
                return cur.rowcount

    def update_breed_code(self, horse_id: int, 품종코드: str) -> int:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE horses SET 품종코드 = %s WHERE id = %s",
                    (품종코드, horse_id),
                )
                return cur.rowcount