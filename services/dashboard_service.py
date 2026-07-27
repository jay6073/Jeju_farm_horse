"""
대시보드 집계 서비스 (아키텍처 프롬프트 4-3절).
오늘 기준(상태='정상') 마종별 두수와 전체 목록을 제공한다.
별도 조회시점 계산은 하지 않는다 — 상태발생일자만으로 사람이 직접 시점을 가늠할 수
있다는 판단에 따라 범위에서 제외한 것(아키텍처 프롬프트 0장 참고).
"""
from __future__ import annotations

from models.horse import Horse
from repository.horse_repository import HorseRepository


def get_species_counts(repository: HorseRepository) -> dict[str, int]:
    """마종별 오늘 기준(정상) 두수. 합계는 호출부에서 sum()으로 계산한다."""
    return repository.count_active_by_species()


def get_all_horses(repository: HorseRepository) -> list[Horse]:
    """전체 목록 테이블용. 상태 무관 전체 조회 (마종, 마명 순 정렬)."""
    return repository.get_all()