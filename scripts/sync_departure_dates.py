"""
A에 이미 존재하는 말(기존 겹치는 43두 포함)에 대해, B의 farm_out_date를 기준으로
horses.퇴사일을 동기화한다. backfill_ended_horses.py는 신규 삽입만 했으므로,
기존에 A에 있던 말의 퇴사일 갱신은 별도로 처리해야 한다.
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


def main(dry_run: bool = True):
    conn = sqlite3.connect(str(B_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    b_rows = conn.execute(
        "SELECT horse_id, farm_out_date FROM horse WHERE farm_out_date IS NOT NULL"
    ).fetchall()
    conn.close()

    init_db()
    with a_get_connection() as a_conn:
        with a_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT 마번, 퇴사일 FROM horses")
            a_current = {r["마번"]: r["퇴사일"] for r in cur.fetchall()}

    to_update = []
    for r in b_rows:
        normalized_id = normalize_horse_number(r["horse_id"])
        if normalized_id not in a_current:
            continue  # A에 아예 없는 마번은 여기서 처리 대상 아님
        current_value = a_current[normalized_id]
        b_value = r["farm_out_date"]
        # A에 퇴사일이 비어있거나, B와 다르면 갱신 대상
        if current_value is None or str(current_value) != str(b_value):
            to_update.append((normalized_id, current_value, b_value))

    print(f"동기화 대상: {len(to_update)}건")
    for horse_id, old, new in to_update[:10]:
        print(f"  {horse_id}: {old} -> {new}")
    if len(to_update) > 10:
        print(f"  ... 외 {len(to_update) - 10}건")

    if dry_run:
        print("\n[DRY RUN] 실제로 갱신하지 않았습니다.")
        return

    with a_get_connection() as a_conn:
        with a_conn.cursor() as cur:
            for horse_id, _, new_value in to_update:
                cur.execute(
                    "UPDATE horses SET 퇴사일 = %s WHERE 마번 = %s",
                    (new_value, horse_id),
                )
        a_conn.commit()
    print(f"\n{len(to_update)}건 갱신 완료.")


if __name__ == "__main__":
    main(dry_run=True)