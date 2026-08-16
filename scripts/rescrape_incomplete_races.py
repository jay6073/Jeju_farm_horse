"""통산보다 전적 행이 부족한 말을 새 스크래퍼로 강제 재수집한다."""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from repository.horse_repository import init_db
from services import racing_service

INCOMPLETE_HORSE_IDS = [
    "0051069",  # 심신지려자마
    "0046839",  # 아침사랑자마
    "0053138",  # 꿈의실현자마
    "0052902",  # 랭귀지오브러브자마
    "0051084",  # 임브레이싱크리시자마
    "0047392",  # 재퍼댄싱자마
    "1412326",  # 탱고앤탱고자마
    "0047231",  # 주말파티자마
    "0044300",  # 미스스트라빈스키자마
    "0044211",  # 풀문파티자마
    "0053341",  # 선앤드문자마
]


def main() -> None:
    init_db()
    result = racing_service.refresh_racehorses_by_ids(INCOMPLETE_HORSE_IDS)
    print(
        f"대상 {result.total_targets} / 성공 {result.success_count} / "
        f"이력없음 {result.no_race_history_count} / 실패 {result.failed_count}"
    )
    for detail in result.failed_details:
        print("실패:", detail)


if __name__ == "__main__":
    main()
