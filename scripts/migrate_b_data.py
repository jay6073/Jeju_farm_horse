"""
B(SQLite)의 실제 운영 데이터를 A(Supabase)의 entrustment/auction_record/
race_record/career_summary 테이블로 이관한다.
- entrustment: B의 horse 테이블에서 entrustment 컬럼만 추려서 이관
- auction_record, race_record, career_summary: 구조 변화 없이 그대로 이관
  (날짜/불리언은 PostgreSQL 네이티브 타입으로, id는 새로 채번)
- 대상 마번이 A의 horses에 없으면 스킵 (FK 위반 방지, 로그로 남김)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from repository.horse_repository import _get_connection as a_get_connection, init_db
from psycopg.rows import dict_row
from shared.horse_number import normalize_horse_number

B_SQLITE_PATH = Path(r"C:\Users\1960100\Documents\horse-management\data\horse_management.db")

_ENTRUSTMENT_FIELDS = [
    "horse_id", "application_year", "applicant_name", "farm_name",
    "farm_in_date", "farm_out_date", "entrustment_period",
    "entrustment_fee", "status",
]


def _get_a_existing_horse_ids(a_conn) -> set[str]:
    with a_conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT 마번 FROM horses")
        return {r["마번"] for r in cur.fetchall()}


def migrate_entrustment(b_conn, a_conn, valid_ids: set[str], dry_run: bool) -> tuple[int, int]:
    rows = b_conn.execute("SELECT * FROM horse").fetchall()
    inserted, skipped = 0, 0
    for r in rows:
        row = dict(r)
        horse_id = normalize_horse_number(row["horse_id"])
        if horse_id not in valid_ids:
            skipped += 1
            print(f"  [entrustment 스킵] 마번 {horse_id}: A의 horses에 없음")
            continue
        values = {k: row.get(k) for k in _ENTRUSTMENT_FIELDS}
        values["horse_id"] = horse_id
        if not dry_run:
            with a_conn.cursor() as cur:
                cols = ", ".join(_ENTRUSTMENT_FIELDS)
                placeholders = ", ".join(["%s"] * len(_ENTRUSTMENT_FIELDS))
                cur.execute(
                    f"""
                    INSERT INTO entrustment ({cols}) VALUES ({placeholders})
                    ON CONFLICT (horse_id) DO NOTHING
                    """,
                    [values[k] for k in _ENTRUSTMENT_FIELDS],
                )
        inserted += 1
    return inserted, skipped


def migrate_auction_records(b_conn, a_conn, valid_ids: set[str], dry_run: bool) -> tuple[int, int]:
    rows = b_conn.execute("SELECT * FROM auction_record").fetchall()
    inserted, skipped = 0, 0
    for r in rows:
        row = dict(r)
        horse_id = normalize_horse_number(row["horse_id"])
        if horse_id not in valid_ids:
            skipped += 1
            continue
        if not dry_run:
            with a_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auction_record
                        (horse_id, auction_date, auction_name, hammer_price, buyer_name, is_final)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        horse_id,
                        row.get("auction_date"),
                        row.get("auction_name"),
                        row.get("hammer_price"),
                        row.get("buyer_name"),
                        bool(row.get("is_final")),
                    ),
                )
        inserted += 1
    return inserted, skipped


def migrate_race_records(b_conn, a_conn, valid_ids: set[str], dry_run: bool) -> tuple[int, int]:
    rows = b_conn.execute("SELECT * FROM race_record").fetchall()
    inserted, skipped = 0, 0
    for r in rows:
        row = dict(r)
        horse_id = normalize_horse_number(row["horse_id"])
        if horse_id not in valid_ids:
            skipped += 1
            continue
        if not dry_run:
            with a_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO race_record
                        (horse_id, race_date, race_name, distance, grade, horse_number,
                         rank, jockey, record_time, weight, horse_weight, track_condition)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        horse_id,
                        row.get("race_date"),
                        row.get("race_name"),
                        row.get("distance"),
                        row.get("grade"),
                        row.get("horse_number"),
                        row.get("rank"),
                        row.get("jockey"),
                        row.get("record_time"),
                        row.get("weight"),
                        row.get("horse_weight"),
                        row.get("track_condition"),
                    ),
                )
        inserted += 1
    return inserted, skipped


def migrate_career_summaries(b_conn, a_conn, valid_ids: set[str], dry_run: bool) -> tuple[int, int]:
    rows = b_conn.execute("SELECT * FROM career_summary").fetchall()
    inserted, skipped = 0, 0
    for r in rows:
        row = dict(r)
        horse_id = normalize_horse_number(row["horse_id"])
        if horse_id not in valid_ids:
            skipped += 1
            continue
        if not dry_run:
            with a_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO career_summary
                        (horse_id, total_starts, total_wins, win_rate, total_prize_money,
                         rating, data_source, last_scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (horse_id) DO NOTHING
                    """,
                    (
                        horse_id,
                        row.get("total_starts"),
                        row.get("total_wins"),
                        row.get("win_rate"),
                        row.get("total_prize_money"),
                        row.get("rating"),
                        row.get("data_source"),
                        row.get("last_scraped_at"),
                    ),
                )
        inserted += 1
    return inserted, skipped


def main(dry_run: bool = True):
    b_conn = sqlite3.connect(str(B_SQLITE_PATH))
    b_conn.row_factory = sqlite3.Row

    init_db()
    with a_get_connection() as a_conn:
        valid_ids = _get_a_existing_horse_ids(a_conn)

        print("=== entrustment ===")
        ins, skip = migrate_entrustment(b_conn, a_conn, valid_ids, dry_run)
        print(f"이관 {ins}건, 스킵 {skip}건")

        print("=== auction_record ===")
        ins, skip = migrate_auction_records(b_conn, a_conn, valid_ids, dry_run)
        print(f"이관 {ins}건, 스킵 {skip}건")

        print("=== race_record ===")
        ins, skip = migrate_race_records(b_conn, a_conn, valid_ids, dry_run)
        print(f"이관 {ins}건, 스킵 {skip}건")

        print("=== career_summary ===")
        ins, skip = migrate_career_summaries(b_conn, a_conn, valid_ids, dry_run)
        print(f"이관 {ins}건, 스킵 {skip}건")

        if not dry_run:
            a_conn.commit()
            print("\n전체 커밋 완료.")
        else:
            print("\n[DRY RUN] 실제로 삽입하지 않았습니다.")

    b_conn.close()


if __name__ == "__main__":
    main(dry_run=False)