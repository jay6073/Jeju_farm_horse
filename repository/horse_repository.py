"""
horses 테이블에 대한 SQLite 접근 계층.

이 레이어의 책임: 순수 데이터 CRUD만 담당한다.
비즈니스 로직(예: 엑셀 컬럼 검증, 스크래핑, 중복 정책 판단)은 services 레이어에서 처리하고,
이 레이어는 넘어온 값을 그대로 저장/조회하는 데만 집중한다.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from models.horse import Horse, STATUS_NORMAL, HORSE_SPECIES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "horses.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS horses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    마번           TEXT,
    마명           TEXT NOT NULL,
    마종           TEXT NOT NULL,
    품종코드       TEXT,
    상태           TEXT NOT NULL DEFAULT '정상',
    상태발생일자   TEXT
);

CREATE INDEX IF NOT EXISTS idx_horses_마종_상태 ON horses(마종, 상태);
CREATE INDEX IF NOT EXISTS idx_horses_마명 ON horses(마명);
CREATE INDEX IF NOT EXISTS idx_horses_마번 ON horses(마번);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    """DB 파일과 테이블이 없으면 생성한다. 앱 시작 시 1회 호출."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


@contextmanager
def _get_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_horse(row: sqlite3.Row) -> Horse:
    return Horse(
        id=row["id"],
        마번=row["마번"],
        마명=row["마명"],
        마종=row["마종"],
        품종코드=row["품종코드"],
        상태=row["상태"],
        상태발생일자=row["상태발생일자"],
    )


class HorseRepository:
    """horses 테이블 CRUD. db_path를 주입받아 테스트 시 임시 DB로 교체 가능."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        init_db(self.db_path)

    # ---------- 생성 ----------

    def insert(self, horse: Horse) -> int:
        """말 한 마리를 등록하고 새로 생성된 id를 반환한다."""
        with _get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO horses (마번, 마명, 마종, 품종코드, 상태, 상태발생일자)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (horse.마번, horse.마명, horse.마종, horse.품종코드, horse.상태, horse.상태발생일자),
            )
            return cur.lastrowid

    def insert_many(self, horses: list[Horse]) -> int:
        """엑셀 일괄 등록용. 삽입된 행 수를 반환한다."""
        with _get_connection(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO horses (마번, 마명, 마종, 품종코드, 상태, 상태발생일자)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(h.마번, h.마명, h.마종, h.품종코드, h.상태, h.상태발생일자) for h in horses],
            )
            return len(horses)

    # ---------- 조회 ----------

    def get_by_id(self, horse_id: int) -> Optional[Horse]:
        with _get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM horses WHERE id = ?", (horse_id,)
            ).fetchone()
            return _row_to_horse(row) if row else None

    def get_active_names_by_species(self, species: str) -> list[Horse]:
        """
        main_page의 마명 select용. 오늘 기준(상태='정상')이고 해당 마종인 말만,
        마명 가나다순으로 반환한다.
        """
        if species not in HORSE_SPECIES:
            raise ValueError(f"유효하지 않은 마종입니다: {species!r}")
        with _get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM horses
                WHERE 마종 = ? AND 상태 = ?
                ORDER BY 마명 COLLATE NOCASE
                """,
                (species, STATUS_NORMAL),
            ).fetchall()
            return [_row_to_horse(r) for r in rows]

    def get_all_by_species(self, species: str) -> list[Horse]:
        """manage_page 상태변경 화면용. 상태 무관하게 해당 마종 전체를 반환한다."""
        if species not in HORSE_SPECIES:
            raise ValueError(f"유효하지 않은 마종입니다: {species!r}")
        with _get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM horses WHERE 마종 = ? ORDER BY 마명 COLLATE NOCASE",
                (species,),
            ).fetchall()
            return [_row_to_horse(r) for r in rows]

    def get_all(self) -> list[Horse]:
        """dashboard_page 전체 목록용. 상태 무관 전체 조회."""
        with _get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM horses ORDER BY 마종, 마명 COLLATE NOCASE"
            ).fetchall()
            return [_row_to_horse(r) for r in rows]

    def count_active_by_species(self) -> dict[str, int]:
        """dashboard_page 카드용. 마종별 오늘 기준(정상) 두수. 0두인 마종도 포함해 반환한다."""
        counts = {species: 0 for species in HORSE_SPECIES}
        with _get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT 마종, COUNT(*) AS cnt FROM horses
                WHERE 상태 = ?
                GROUP BY 마종
                """,
                (STATUS_NORMAL,),
            ).fetchall()
            for r in rows:
                counts[r["마종"]] = r["cnt"]
        return counts

    def exists_by_마명_or_마번(self, 마명: str, 마번: Optional[str]) -> bool:
        """엑셀 일괄 등록/개별 추가 시 중복 체크용."""
        with _get_connection(self.db_path) as conn:
            if 마번:
                row = conn.execute(
                    "SELECT 1 FROM horses WHERE 마명 = ? OR 마번 = ? LIMIT 1",
                    (마명, 마번),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM horses WHERE 마명 = ? LIMIT 1", (마명,)
                ).fetchone()
            return row is not None

    # ---------- 갱신 ----------

    def update_status_bulk(
        self, horse_ids: list[int], 상태: str, 상태발생일자: str
    ) -> int:
        """
        여러 마리의 보유상태를 한 번에 변경한다 (물리 삭제 아님).
        manage_page의 다중선택 상태변경 기능에서 사용.
        """
        if not horse_ids:
            return 0
        if 상태 == STATUS_NORMAL:
            raise ValueError("상태 변경은 정상이 아닌 상태로만 가능합니다.")
        with _get_connection(self.db_path) as conn:
            placeholders = ",".join("?" * len(horse_ids))
            cur = conn.execute(
                f"""
                UPDATE horses
                SET 상태 = ?, 상태발생일자 = ?
                WHERE id IN ({placeholders})
                """,
                (상태, 상태발생일자, *horse_ids),
            )
            return cur.rowcount

    def update_breed_code(self, horse_id: int, 품종코드: str) -> int:
        """
        품종코드를 저장/갱신한다. 엑셀 업로드 시 비어 있던 품종코드가
        scraping_service의 자동탐지로 확인됐을 때 이 메서드로 반영한다.
        """
        with _get_connection(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE horses SET 품종코드 = ? WHERE id = ?",
                (품종코드, horse_id),
            )
            return cur.rowcount
