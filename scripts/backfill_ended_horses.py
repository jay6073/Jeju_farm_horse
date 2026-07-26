"""
B(SQLite)의 위탁종료 말 중 A의 horses에 없는 142두를 A로 백필한다.
- 마종은 전부 '위수탁마'로 고정 (B가 다루는 말은 전부 이 마종)
- 품종코드는 기본값 '00100'(더러브렛)
- 퇴사일은 B의 entrustment(farm_out_date)에서 가져와 채움
- 실행 전 dry-run으로 먼저 몇 건이 실제로 들어갈지 확인 가능
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
DEFAULT_BREED_CODE = "00100"  # 더러브렛


def main(dry_run: bool = True):
    conn = sqlite3.connect(str(B_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    b_rows = conn.execute(
        "SELECT horse_id, name, farm_in_date, farm_out_date FROM horse"
    ).fetchall()
    conn.close()

    init_db()
    with a_get_connection() as a_conn:
        with a_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT 마번 FROM horses")
            existing_in_a = {r["마번"] for r in cur.fetchall()}

    to_insert = []
    for r in b_rows:
        normalized_id = normalize_horse_number(r["horse_id"])
        if normalized_id in existing_in_a:
            continue  # 이미 A에 있는 43두는 스킵
        to_insert.append(
            {
                "마번": normalized_id,
                "마종": "위수탁마",
                "마명": r["name"],
                "품종코드": DEFAULT_BREED_CODE,
                "최초등록일": r["farm_in_date"],
                "퇴사일": r["farm_out_date"],
            }
        )

    print(f"백필 대상: {len(to_insert)}건")
    for row in to_insert[:5]:
        print(f"  {row}")
    if len(to_insert) > 5:
        print(f"  ... 외 {len(to_insert) - 5}건")

    if dry_run:
        print("\n[DRY RUN] 실제로 삽입하지 않았습니다. 결과가 맞으면 dry_run=False로 다시 실행하세요.")
        return

    with a_get_connection() as a_conn:
        with a_conn.cursor() as cur:
            for row in to_insert:
                cur.execute(
                    """
                    INSERT INTO horses (마번, 마종, 마명, 품종코드, 최초등록일, 퇴사일)
                    VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (마번) DO NOTHING
                    """,
                    (
                        row["마번"],
                        row["마종"],
                        row["마명"],
                        row["품종코드"],
                        row["최초등록일"],
                        row["퇴사일"],
                    ),
                )
        a_conn.commit()
    print(f"\n{len(to_insert)}건 삽입 완료.")


if __name__ == "__main__":
    main(dry_run=False)