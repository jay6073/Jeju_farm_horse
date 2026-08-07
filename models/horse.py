"""
보유마 데이터 모델.

설계 원칙 (아키텍처 프롬프트 2장 참고):
- 물리 삭제(DELETE)는 어디서도 하지 않는다. 모든 "삭제"는 `상태` 값을 바꾸는 것으로 표현한다.
- 재등록(위탁 종료 후 재위탁 등)이 실무상 없으므로 이력 테이블 없이 상태 + 상태발생일자만으로 관리한다.
- 모든 내부 매칭은 마명이 아닌 `id` 기준으로 한다 (마명 중복 가능성 대비).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Optional
from shared.horse_number import normalize_horse_number  # noqa: F401

# 마종 옵션 (main_page, manage_page의 select 옵션과 동일하게 유지)
HORSE_SPECIES: list[str] = ["씨수말", "교육마", "관상마", "위수탁마", "기타마"]

# 상태 옵션
STATUS_NORMAL: str = "정상"
# UI 전용 선택값. DB에는 저장하지 않고, 사용자가 입력한 사유 문자열이 상태로 저장된다.
STATUS_CUSTOM_OPTION: str = "직접 입력"
# 레거시 '기타'는 기존 데이터 표시용으로 ALL_STATUSES에만 남긴다.
NON_NORMAL_STATUSES: list[str] = ["폐사", "위수탁종료", "매각", "기타"]
FIXED_MANAGEABLE_STATUSES: list[str] = [STATUS_NORMAL, "폐사", "매각"]
# 관리 화면 선택지: 고정 상태 + 직접 입력 (위수탁종료·기타 제외)
MANAGEABLE_STATUSES: list[str] = FIXED_MANAGEABLE_STATUSES + [STATUS_CUSTOM_OPTION]
# 고정 상태값(뱃지·기존 데이터). 저장은 이 목록 외 짧은 사유 문자열도 허용한다.
ALL_STATUSES: list[str] = [STATUS_NORMAL] + NON_NORMAL_STATUSES
# 직접 입력 사유로 쓰면 안 되는 예약어 (UI 옵션명 포함)
STATUS_RESERVED_FOR_CUSTOM: frozenset[str] = frozenset(
    ALL_STATUSES + [STATUS_CUSTOM_OPTION]
)
STATUS_MAX_LENGTH: int = 30


def normalize_status(상태: str) -> str:
    """상태 문자열을 정리·검증한다. 고정값과 직접 입력 사유를 모두 허용."""
    if 상태 is None or not str(상태).strip():
        raise ValueError("상태는 비어 있을 수 없습니다.")
    cleaned = str(상태).strip()
    if len(cleaned) > STATUS_MAX_LENGTH:
        raise ValueError(
            f"상태는 {STATUS_MAX_LENGTH}자 이하여야 합니다: {cleaned!r}"
        )
    return cleaned


def normalize_custom_status(사유: str) -> str:
    """관리 화면 '직접 입력' 사유를 검증한다. 예약어·공백·길이 초과를 막는다."""
    cleaned = normalize_status(사유)
    if cleaned in STATUS_RESERVED_FOR_CUSTOM:
        raise ValueError(
            f"'{cleaned}'는 직접 입력 사유로 쓸 수 없습니다. "
            "다른 상태 옵션을 선택하거나 다른 사유를 입력하세요."
        )
    return cleaned

# horsepia.com의 hrsGbCd(품종 구분코드). 목장 "마종"(용도 분류)과는 별개 축의 값이며,
# 씨수말이든 위수탁마든 실제 품종에 따라 이 코드가 결정된다.
#
# ⚠️ 이 값은 우리가 추측/고정하지 않는다. 등록 시 horsepia에서 해당 말의 상세 페이지를
# 직접 열어 URL의 hrsGbCd를 그대로 복사해 입력하는 것이 원칙이다 (등록 화면/엑셀 템플릿
# 안내 문구 참고). 그래서 검증도 "알려진 코드 목록에 있는가"가 아니라 "5자리 숫자 형식인가"
# 정도로만 하고, 아래 매핑은 화면에 사람이 읽기 좋은 이름을 보여주는 용도로만 쓴다.
# 매핑에 없는 새 코드가 들어와도 등록/조회를 막지 않는다 (get_breed_label 참고).
HORSE_BREED_CODES: dict[str, str] = {
    "00100": "더러브렛",
    "00200": "일반마",
    "00210": "일반마(승용전환)",
    "00300": "제주마(경주용)",
    "00310": "제주마(축진원)",
}

_BREED_CODE_PATTERN = re.compile(r"^\d{5}$")


def get_breed_label(code: Optional[str]) -> str:
    """
    화면 표시용. HORSE_BREED_CODES에 없는(아직 확인 못한) 코드가 들어와도
    에러 없이 코드 자체를 보여준다 — 등록/조회 자체는 막지 않는다.
    """
    if not code:
        return "-"
    return HORSE_BREED_CODES.get(code, f"{code}(확인필요)")

@dataclass
class Horse:
    """
    horses 테이블 한 행과 대응하는 모델.
    id가 None이면 아직 저장되지 않은(insert 전) 인스턴스를 의미한다.
    """
    마명: str
    마종: str
    마번: Optional[str] = None
    품종코드: Optional[str] = None  # horsepia hrsGbCd. 스크래핑 시 필수, 목장 마종과는 별개 값.
    상태: str = STATUS_NORMAL
    상태발생일자: Optional[str] = None  # ISO 형식 문자열(YYYY-MM-DD), 정상이면 None
    id: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.마명 or not self.마명.strip():
            raise ValueError("마명은 비어 있을 수 없습니다.")
        if self.마종 not in HORSE_SPECIES:
            raise ValueError(
                f"유효하지 않은 마종입니다: {self.마종!r} "
                f"(허용값: {', '.join(HORSE_SPECIES)})"
            )
        if self.품종코드 is not None and not (
            self.품종코드.isdigit() and len(self.품종코드) == 5
        ):
            raise ValueError(
                f"품종코드 형식이 올바르지 않습니다: {self.품종코드!r} "
                "(horsepia 상세페이지 URL의 hrsGbCd 값, 5자리 숫자를 그대로 입력해야 합니다)"
            )
        self.상태 = normalize_status(self.상태)
        if self.상태 != STATUS_NORMAL and not self.상태발생일자:
            raise ValueError("정상이 아닌 상태는 상태발생일자가 반드시 필요합니다.")
        if self.상태 == STATUS_NORMAL and self.상태발생일자:
            raise ValueError("상태가 정상인 경우 상태발생일자는 비어 있어야 합니다.")

        self.마명 = self.마명.strip()
        self.마번 = normalize_horse_number(self.마번)

    @property
    def is_active(self) -> bool:
        """오늘 기준 보유 중(=정상)인지 여부. main_page 조회 필터링에 사용."""
        return self.상태 == STATUS_NORMAL

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()