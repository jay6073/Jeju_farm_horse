"""
대시보드 집계 서비스 (아키텍처 프롬프트 4-3절).
오늘 기준(상태='정상') 마종별 두수와 전체 목록을 제공한다.
별도 조회시점 계산은 하지 않는다 — 상태발생일자만으로 사람이 직접 시점을 가늠할 수
있다는 판단에 따라 범위에서 제외한 것(아키텍처 프롬프트 0장 참고).

[정합성 수정 v2] 위수탁마는 예외: 대시보드에서는 '실제 사육 중인 두수'를 보여주는
것이 목적이므로, entrustment 상태='위탁중'인 두수만 센다 (위탁종료는 제외).
- entrustment 테이블 전체 두수(위탁중+위탁종료)가 필요하면 entrustment_service의
  통계 함수(get_statistics_by_year 등)를 별도로 참고할 것.

"""
from __future__ import annotations

from config.constants import STATUS_ENTRUSTED 
from models.horse import Horse
from repository.horse_repository import HorseRepository
from services import entrustment_service


def get_species_counts(repository: HorseRepository) -> dict[str, int]:
    """마종별 두수. 위수탁마만 entrustment '위탁중' 두수로 덮어쓰고, 나머지는 상태='정상' 기준."""
    counts = repository.count_active_by_species()
    counts["위수탁마"] = len(
        entrustment_service.list_horses(status=STATUS_ENTRUSTED)   # ← status 인자 추가
    )
    return counts


def get_all_horses(repository: HorseRepository) -> list[Horse]:
    """전체 목록 테이블용. 상태 무관 전체 조회 (마종, 마명 순 정렬)."""
    return repository.get_all()
