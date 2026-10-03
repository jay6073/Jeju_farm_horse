"""
보유현황 집계 — 기준일 시점의 마종×관리파트 교차표.

보유 판정 기준 (horses.상태만 사용):
- 상태가 '정상'이면 보유 중으로 판정.
- 상태가 '정상'이 아니면(폐사/매각/위탁종료/기타), 상태발생일자가 기준일보다
  "이후"일 때만 기준일 시점엔 아직 보유 중이었던 것으로 판정.
  (상태발생일자 당일 및 그 이후는 보유하지 않은 것으로 처리 — 퇴사/사망 당일부터 제외)
- 참고: horses에 최초 등록일이 없어, 기준일이 그 말의 실제 등록일보다
  과거라면 집계가 실제보다 많게 나올 수 있다 (알려진 한계, 감수하고 진행).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from config.constants import HORSE_DUTY_PARTS
from models.horse import HORSE_SPECIES, STATUS_NORMAL, Horse
from repository.horse_repository import HorseRepository


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def is_held_as_of(horse: Horse, as_of: date) -> bool:
    """horse가 as_of 시점에 보유 중이었는지 (horses.상태만으로 판정)."""
    if horse.상태 == STATUS_NORMAL:
        return True
    changed = _parse_date(horse.상태발생일자)
    if changed is None:
        # 비정상 상태인데 발생일자가 없는 데이터 — 보유하지 않은 것으로 간주
        return False
    return as_of < changed


@dataclass
class HoldingMatrix:
    species_list: list[str]
    duty_parts: list[str]
    counts: dict[tuple[str, str], int]   # (마종, 관리파트) -> 두수
    row_totals: dict[str, int]           # 마종 -> 합계
    col_totals: dict[str, int]           # 관리파트 -> 합계
    grand_total: int
    unassigned_count: int    # 보유 중인데 관리파트 미지정인 두수
    unassigned_by_species: dict[str, int]  # 추가: 마종 -> 미지정 두수
    unassigned_reasons: dict[tuple[str, str], int]  # 추가: (마종, 상태) -> 두수


def build_holding_matrix(as_of: date, repo: HorseRepository) -> HoldingMatrix:
    all_horses = repo.get_all()
    held = [h for h in all_horses if is_held_as_of(h, as_of)]

    counts: dict[tuple[str, str], int] = {}
    row_totals = {s: 0 for s in HORSE_SPECIES}
    col_totals = {p: 0 for p in HORSE_DUTY_PARTS}
    unassigned = 0
    unassigned_by_species: dict[str, int] = {}
    unassigned_reasons: dict[tuple[str, str], int] = {}

    for h in held:
        row_totals[h.마종] = row_totals.get(h.마종, 0) + 1
        if h.관리파트 in HORSE_DUTY_PARTS:
            key = (h.마종, h.관리파트)
            counts[key] = counts.get(key, 0) + 1
            col_totals[h.관리파트] = col_totals.get(h.관리파트, 0) + 1
        else:
            unassigned += 1
            unassigned_by_species[h.마종] = unassigned_by_species.get(h.마종, 0) + 1
            rkey = (h.마종, h.상태 or "미상")
            unassigned_reasons[rkey] = unassigned_reasons.get(rkey, 0) + 1

    return HoldingMatrix(
        species_list=HORSE_SPECIES,
        duty_parts=HORSE_DUTY_PARTS,
        counts=counts,
        row_totals=row_totals,
        col_totals=col_totals,
        grand_total=len(held),
        unassigned_count=unassigned,
        unassigned_by_species=unassigned_by_species,
        unassigned_reasons=unassigned_reasons,
    )