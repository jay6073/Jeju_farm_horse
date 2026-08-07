"""
마종별 보유마 출력(미리보기)용 데이터 조립.

명단 컬럼:
- 공통: 마번, 마명, 출생일, 성별, 부마명, 모마명
- 위수탁마 추가: 신청인 (entrustment.applicant_name)
- 일반 마종: horsepia 스크래핑 / 위수탁마: entrustment DB만 (모마명은 '-')
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

from models.horse import HORSE_SPECIES, Horse
from repository.horse_repository import HorseRepository
from services import entrustment_service, scraping_service
from services.scraping_service import REQUEST_DELAY_RANGE, ScrapingError

PRINT_COLUMNS: tuple[str, ...] = (
    "마번",
    "마명",
    "출생일",
    "성별",
    "부마명",
    "모마명",
)

# 위수탁마 미리보기·인쇄용 (신청인 포함)
PRINT_COLUMNS_ENTRUSTMENT: tuple[str, ...] = (
    "마번",
    "마명",
    "출생일",
    "성별",
    "부마명",
    "모마명",
    "신청인",
)

SPECIES_ENTRUSTMENT = "위수탁마"
_EMPTY = "-"


@dataclass
class PrintRow:
    마번: str
    마명: str
    출생일: str
    성별: str
    부마명: str
    모마명: str
    신청인: str = _EMPTY
    horse_id: Optional[int] = None
    error: Optional[str] = None

    def as_dict(self) -> dict[str, str]:
        return {
            "마번": self.마번,
            "마명": self.마명,
            "출생일": self.출생일,
            "성별": self.성별,
            "부마명": self.부마명,
            "모마명": self.모마명,
            "신청인": self.신청인,
        }


def _fmt_date(value) -> str:
    if value is None or value == "":
        return _EMPTY
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _blank_row(horse: Horse, error: Optional[str] = None) -> PrintRow:
    return PrintRow(
        마번=horse.마번 or _EMPTY,
        마명=horse.마명,
        출생일=_EMPTY,
        성별=_EMPTY,
        부마명=_EMPTY,
        모마명=_EMPTY,
        horse_id=horse.id,
        error=error,
    )


def _row_from_basic_info(horse: Horse, basic_info: dict[str, str]) -> PrintRow:
    return PrintRow(
        마번=horse.마번 or _EMPTY,
        마명=horse.마명,
        출생일=basic_info.get("출생일") or _EMPTY,
        성별=basic_info.get("성별") or _EMPTY,
        부마명=basic_info.get("부마명") or _EMPTY,
        모마명=basic_info.get("모마명") or _EMPTY,
        horse_id=horse.id,
    )


def _fetch_basic_info(horse: Horse, repo: HorseRepository) -> dict[str, str]:
    if horse.품종코드:
        data = scraping_service.get_horse_detail_for(horse, use_cache=True)
    else:
        data = scraping_service.get_horse_detail_auto(horse, repo, use_cache=True)
    return scraping_service.extract_basic_info(data, hrs_gb_cd=horse.품종코드 or "")


def build_entrustment_print_rows(application_year: int) -> list[PrintRow]:
    """
    위수탁마 명단을 entrustment DB에서만 만든다 (horsepia 미접속).
    모마명은 스키마에 없어 '-'로 둔다.
    """
    if not application_year:
        raise ValueError("위수탁마 출력에는 사업연도가 필요합니다.")

    horses = entrustment_service.search_horses(application_year=application_year)
    rows: list[PrintRow] = []
    for h in horses:
        rows.append(
            PrintRow(
                마번=h.horse_id or _EMPTY,
                마명=h.name or _EMPTY,
                출생일=_fmt_date(h.birth_date),
                성별=(h.sex or _EMPTY),
                부마명=(h.sire_name or _EMPTY),
                모마명=_EMPTY,
                신청인=(h.applicant_name or _EMPTY),
            )
        )
    return rows


def build_owned_species_print_rows(
    species: str,
    repo: Optional[HorseRepository] = None,
) -> list[PrintRow]:
    """
    위수탁마가 아닌 마종의 상태=정상 보유마 명단.
    출생일·성별·부·모는 horsepia에서 조회한다.
    """
    if species not in HORSE_SPECIES or species == SPECIES_ENTRUSTMENT:
        raise ValueError(f"일반 마종만 조회할 수 있습니다: {species!r}")

    repository = repo or HorseRepository()
    horses = repository.get_active_names_by_species(species)
    rows: list[PrintRow] = []

    for i, horse in enumerate(horses):
        if not horse.마번:
            rows.append(_blank_row(horse, error="마번 없음"))
            continue

        if i > 0:
            time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

        try:
            basic_info = _fetch_basic_info(horse, repository)
            rows.append(_row_from_basic_info(horse, basic_info))
        except ScrapingError as e:
            rows.append(_blank_row(horse, error=str(e)))

    return rows


def build_species_print_rows(
    species: str,
    repo: Optional[HorseRepository] = None,
    application_year: Optional[int] = None,
) -> list[PrintRow]:
    """
    마종에 따라 명단을 만든다.
    - 위수탁마: application_year 필수, entrustment DB만 사용
    - 그 외: 상태=정상 + horsepia 스크래핑
    """
    if species not in HORSE_SPECIES:
        raise ValueError(f"유효하지 않은 마종입니다: {species!r}")

    if species == SPECIES_ENTRUSTMENT:
        if application_year is None:
            raise ValueError("위수탁마는 사업연도를 선택하세요.")
        return build_entrustment_print_rows(application_year)

    return build_owned_species_print_rows(species, repo=repo)
