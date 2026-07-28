"""
B(SQLite) -> A(Supabase) 마이그레이션 사전 점검.
B의 모든 마번이 A의 horses 테이블에 존재하는지 확인하고,
없는 마번 목록을 출력한다. 실제 마이그레이션 전에 반드시 실행.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from repository.horse_repository import _get_connection as a_get_connection, init_db
from psycopg.rows import dict_row
from shared.horse_number import normalize_horse_number

# B의 SQLite 파일 경로로 수정
B_SQLITE_PATH = Path(r"C:\Users\1960100\Documents\horse-management\data\horse_management.db")


def main():
    if not B_SQLITE_PATH.exists():
        print(f"B의 SQLite 파일을 찾을 수 없습니다: {B_SQLITE_PATH}")
        return

    conn = sqlite3.connect(str(B_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    b_rows = conn.execute("SELECT horse_id, name FROM horse").fetchall()
    conn.close()

    b_horse_ids = [r["horse_id"] for r in b_rows]
    print(f"B에 등록된 말 수: {len(b_horse_ids)}")

    # 정규화 안 된 마번이 있는지 확인
    non_normalized = [
        (r["horse_id"], normalize_horse_number(r["horse_id"]))
        for r in b_rows
        if r["horse_id"] != normalize_horse_number(r["horse_id"])
    ]
    if non_normalized:
        print(f"\n⚠️ 정규화 안 된 마번 {len(non_normalized)}건:")
        for original, normalized in non_normalized:
            print(f"  {original} -> {normalized}")

    init_db()
    # A의 horses에 존재하는지 확인 (정규화된 값 기준)
    with a_get_connection() as a_conn:
        with a_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT 마번 FROM horses")
            a_horse_ids = {r["마번"] for r in cur.fetchall()}

    missing_in_a = []
    for r in b_rows:
        normalized_id = normalize_horse_number(r["horse_id"])
        if normalized_id not in a_horse_ids:
            missing_in_a.append((r["horse_id"], normalized_id, r["name"]))

    if missing_in_a:
        print(f"\n⚠️ A의 horses에 없는 마번 {len(missing_in_a)}건 (위탁 계약 이관 불가):")
        for original, normalized, name in missing_in_a:
            print(f"  {original} (정규화: {normalized}) - {name}")
    else:
        print("\n✅ B의 모든 마번이 A의 horses에 존재합니다. 마이그레이션 가능.")


if __name__ == "__main__":
    main()