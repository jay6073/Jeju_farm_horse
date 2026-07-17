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

# 마종 옵션 (main_page, manage_page의 select 옵션과 동일하게 유지)
HORSE_SPECIES: list[str] = ["씨수말", "교육마", "관상마", "위수탁마", "기타마"]

# 상태 옵션
STATUS_NORMAL: str = "정상"
NON_NORMAL_STATUSES: list[str] = ["폐사", "위수탁종료", "매각", "기타"]
ALL_STATUSES: list[str] = [STATUS_NORMAL] + NON_NORMAL_STATUSES

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


def normalize_horse_number(raw: Optional[str]) -> Optional[str]:
    """
    horsepia 등록번호(마번)를 7자리로 정규화한다.
    과거 프로젝트에서 확인된 "엑셀에서 선행 0이 소실되는" 이슈를 방지하기 위함.
    빈 값/None은 그대로 None으로 둔다 (마번은 선택 입력 항목).
    """
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    # 엑셀에서 숫자로 읽혀 "12345.0" 형태로 들어오는 경우 방지
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]
    if not cleaned.isdigit():
        # 숫자가 아닌 값이 섞여 있으면 정규화하지 않고 원본을 그대로 반환한다.
        # (호출부에서 검증 실패로 처리할 수 있도록 예외를 던지지 않는다)
        return cleaned
    return cleaned.zfill(7)


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
        if self.상태 not in ALL_STATUSES:
            raise ValueError(
                f"유효하지 않은 상태입니다: {self.상태!r} "
                f"(허용값: {', '.join(ALL_STATUSES)})"
            )
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