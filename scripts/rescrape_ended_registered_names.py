"""위탁종료 말 전체를 7일 주기와 무관하게 재수집해 registered_name을 채운다."""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from config.constants import STATUS_ENDED
from db import repository
from repository.horse_repository import init_db
from services import racing_service


def main() -> None:
    init_db()
    ended = repository.list_horses(status=STATUS_ENDED)
    horse_ids = [h["horse_id"] for h in ended if h.get("horse_id")]
    print(f"위탁종료 {len(horse_ids)}두 재수집 시작")
    result = racing_service.refresh_racehorses_by_ids(horse_ids)
    print(
        f"대상 {result.total_targets} / 성공 {result.success_count} / "
        f"이력없음 {result.no_race_history_count} / 실패 {result.failed_count}"
    )
    for detail in result.failed_details:
        print("실패:", detail)

    filled = 0
    empty = 0
    for hid in horse_ids:
        summary = repository.get_career_summary(hid)
        name = (summary or {}).get("registered_name")
        if name:
            filled += 1
        else:
            empty += 1
    print(f"registered_name 채워짐 {filled} / 비어 있음 {empty}")


if __name__ == "__main__":
    main()
