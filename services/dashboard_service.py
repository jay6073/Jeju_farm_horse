"""
대시보드 집계 서비스 (아키텍처 프롬프트 4-3절).
오늘 기준(상태='정상') 마종별 두수와 전체 목록을 제공한다.
별도 조회시점 계산은 하지 않는다 — 상태발생일자만으로 사람이 직접 시점을 가늠할 수
있다는 판단에 따라 범위에서 제외한 것(아키텍처 프롬프트 0장 참고).

[정합성 수정] 위수탁마는 예외: '상태' 값과 무관하게 entrustment 테이블에 존재하는
전체 두수(위탁중+위탁종료)를 그대로 보여준다. 위수탁마는 '상태=정상'만 골라 세면
위탁종료된 말이 누락되어 entrustment 두수와 어긋나기 때문 (위탁종료도 여전히
위수탁마 이력의 일부).
"""
from __future__ import annotations

from models.horse import Horse
from repository.horse_repository import HorseRepository
from services import entrustment_service


def get_species_counts(repository: HorseRepository) -> dict[str, int]:
    """마종별 두수. 위수탁마만 entrustment 전체 두수로 덮어쓰고, 나머지는 상태='정상' 기준."""
    counts = repository.count_active_by_species()
    counts["위수탁마"] = len(entrustment_service.list_horses())
    return counts


def get_all_horses(repository: HorseRepository) -> list[Horse]:
    """전체 목록 테이블용. 상태 무관 전체 조회 (마종, 마명 순 정렬)."""
    return repository.get_all()