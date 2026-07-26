"""
순수 CRUD 전용 계층. 비즈니스 로직(상태 자동계산, 통계 가공 등)은 절대 넣지 않는다.
[지침 변경 포인트] 여기 함수 시그니처를 바꾸면 services/*.py 호출부도 함께 확인해야 한다.
규칙: ui -> services -> repository 순서로만 호출한다. repository가 ui/services를 참조하지 않는다.
"""
from __future__ import annotations

from typing import Any, Optional

from repository.horse_repository import _get_connection as get_connection

# ── Entrustment (구 Horse) ──────────────────────────────────────────────


def insert_horse(horse_dict: dict[str, Any]) -> None:
    columns = list(horse_dict.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    col_sql = ", ".join(columns)
    values = [horse_dict[c] for c in columns]
    with get_connection() as conn:
        conn.execute(f"INSERT INTO entrustment ({col_sql}) VALUES ({placeholders})", values)


def upsert_horse(horse_dict: dict[str, Any]) -> None:
    """horse_id가 이미 있으면 덮어쓰기, 없으면 신규 삽입 (엑셀 재이관 등에 사용)."""
    columns = list(horse_dict.keys())
    col_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_sql = ", ".join([f"{c}=excluded.{c}" for c in columns if c != "horse_id"])
    values = [horse_dict[c] for c in columns]
    with get_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO entrustment ({col_sql}) VALUES ({placeholders})
            ON CONFLICT(horse_id) DO UPDATE SET {update_sql}
            """,
            values,
        )


def get_horse(horse_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM entrustment WHERE horse_id = %s", (horse_id,)
        ).fetchone()
        return dict(row) if row else None


def _normalize_company_mark(text: str) -> str:
    """
    '㈜'(전각 기호 한 글자)와 '(주)'(괄호+주+괄호 세 글자)를 동일하게 취급하기 위해
    검색 시 둘 다 제거한 형태로 비교한다.
    """
    return text.replace("㈜", "").replace("(주)", "").replace(" ", "")


def list_horses(
    status: Optional[str] = None,
    applicant_name: Optional[str] = None,
    application_year: Optional[int] = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM entrustment WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND status = %s"
        params.append(status)
    if application_year:
        query += " AND application_year = %s"
        params.append(application_year)
    query += " ORDER BY application_year DESC, horse_id"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        results = [dict(r) for r in rows]

    if applicant_name:
        target = _normalize_company_mark(applicant_name)
        results = [
            r for r in results
            if r.get("applicant_name")
            and target in _normalize_company_mark(r["applicant_name"])
        ]

    return results


def update_horse(horse_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    set_sql = ", ".join([f"{k} = %s" for k in fields.keys()])
    values = list(fields.values()) + [horse_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE entrustment SET {set_sql} WHERE horse_id = %s", values)


def delete_horse(horse_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM entrustment WHERE horse_id = %s", (horse_id,))


def horse_exists(horse_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM entrustment WHERE horse_id = %s", (horse_id,)
        ).fetchone()
        return row is not None


# ── AuctionRecord ──────────────────────────────────────────────────────


def insert_auction_record(record_dict: dict[str, Any]) -> int:
    columns = [c for c in record_dict.keys() if c != "id"]
    placeholders = ", ".join(["%s"] * len(columns))
    col_sql = ", ".join(columns)
    values = [record_dict[c] for c in columns]
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO auction_record ({col_sql}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        return cur.fetchone()[0]


def list_auction_records(horse_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM auction_record WHERE horse_id = %s ORDER BY auction_date",
            (horse_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_auction_record(record_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM auction_record WHERE id = %s", (record_id,)
        ).fetchone()
        return dict(row) if row else None


def update_auction_record(record_id: int, fields: dict[str, Any]) -> None:
    if not fields:
        return
    set_sql = ", ".join([f"{k} = %s" for k in fields.keys()])
    values = list(fields.values()) + [record_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE auction_record SET {set_sql} WHERE id = %s", values)


def unset_final_flag_for_horse(horse_id: str, except_id: Optional[int] = None) -> None:
    """해당 말의 다른 경매 건들의 is_final을 FALSE로 내린다 (최종건은 항상 1개만 존재)."""
    with get_connection() as conn:
        if except_id is None:
            conn.execute(
                "UPDATE auction_record SET is_final = FALSE WHERE horse_id = %s",
                (horse_id,),
            )
        else:
            conn.execute(
                "UPDATE auction_record SET is_final = FALSE WHERE horse_id = %s AND id != %s",
                (horse_id, except_id),
            )


def list_all_auction_records_with_horse() -> list[dict[str, Any]]:
    """경매관리 화면 전체 목록용. Horse 기본정보(마명)와 위탁정보(신청인/상태)를 조인해서 반환."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ar.*, h.마명 AS horse_name, e.applicant_name, e.status AS horse_status
            FROM auction_record ar
            JOIN horses h ON h.마번 = ar.horse_id
            LEFT JOIN entrustment e ON e.horse_id = ar.horse_id
            ORDER BY ar.auction_date DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def delete_auction_record(record_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM auction_record WHERE id = %s", (record_id,))


# ── RaceRecord ─────────────────────────────────────────────────────────


def insert_race_record(record_dict: dict[str, Any]) -> int:
    columns = [c for c in record_dict.keys() if c != "id"]
    placeholders = ", ".join(["%s"] * len(columns))
    col_sql = ", ".join(columns)
    values = [record_dict[c] for c in columns]
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO race_record ({col_sql}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        return cur.fetchone()[0]


def list_race_records(horse_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM race_record WHERE horse_id = %s ORDER BY race_date DESC",
            (horse_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_race_records_by_horse(horse_id: str) -> None:
    """재스크래핑 시 중복 방지를 위해 기존 기록을 지우고 새로 채운다 (전체 새로고침 방식)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM race_record WHERE horse_id = %s", (horse_id,))


# ── CareerSummary ────────────────────────────────────────────────────


def upsert_career_summary(summary_dict: dict[str, Any]) -> None:
    columns = list(summary_dict.keys())
    col_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_sql = ", ".join([f"{c}=excluded.{c}" for c in columns if c != "horse_id"])
    values = [summary_dict[c] for c in columns]
    with get_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO career_summary ({col_sql}) VALUES ({placeholders})
            ON CONFLICT(horse_id) DO UPDATE SET {update_sql}
            """,
            values,
        )


def get_career_summary(horse_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM career_summary WHERE horse_id = %s", (horse_id,)
        ).fetchone()
        return dict(row) if row else None


def list_all_career_summaries_with_horse() -> list[dict[str, Any]]:
    """대시보드 전체 통산요약 목록. Horse 기본정보(마명)와 위탁정보(신청인/상태)를 조인해서 반환."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cs.*, h.마명 AS horse_name, e.applicant_name, e.status AS horse_status
            FROM career_summary cs
            JOIN horses h ON h.마번 = cs.horse_id
            LEFT JOIN entrustment e ON e.horse_id = cs.horse_id
            """
        ).fetchall()
        return [dict(r) for r in rows]


# ── 통계용 원자료 조회 (집계/가공은 services 레이어에서) ───────────────


def fetch_all_horses_df_rows() -> list[dict[str, Any]]:
    """통계 계산을 위해 전체 위탁정보 원자료를 그대로 반환한다. 가공은 service에서."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM entrustment").fetchall()
        return [dict(r) for r in rows]