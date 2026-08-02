"""
엑셀(전기육성위수탁마 시트) -> 내부 dict 구조로 변환하는 순수 어댑터.
[지침 변경 포인트] 엑셀 컬럼명/순서가 바뀌면 COLUMN_* 상수만 수정하면 되도록 구성.
규칙: 이 파일은 DB(repository)를 호출하지 않는다. 순수 파싱/정제만 담당하고,
      실제 저장은 services/import_service.py가 담당한다.

[경매결과 파싱 규칙 - 갱신]
- 최초경매결과 / 최종경매결과 두 컬럼은 각각 "결과" 슬롯이다.
  - 숫자만 들어있으면 낙찰(그 숫자가 낙찰가)
  - "유찰" 텍스트면 유찰
  - 공란이면 그 슬롯은 이벤트 없음 (상장 자체가 없었거나 재상장이 없었음)
- 두 슬롯이 모두 공란이면(=상장 이력이 아예 없음) "미상장" 레코드를 명시적으로 1건 생성한다.
  (예전 로직은 이 경우 auction_record 자체를 안 만들어서 미상장 말이 통째로 누락되는 버그가 있었음)
- is_final은 "낙찰"인 이벤트 중 가장 나중 슬롯(최종이 있으면 최종, 없으면 최초)에만 부여한다.
- 경매요약 컬럼은 더 이상 파싱에 쓰이지 않는다. 존재할 경우 교차검증(불일치 시 warning)에만 사용한다.
"""
from __future__ import annotations
from shared.horse_number import normalize_horse_number

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from config.constants import STATUS_ENTRUSTED, STATUS_ENDED

SHEET_NAME = "전기육성위수탁마"

# 이관 대상 컬럼만 정의 (구분/순번/수득상금 이후 컬럼은 애초에 여기 포함하지 않음)
# 경매요약은 결과 컬럼에서 100% 유도 가능한 파생값이라 필수 컬럼에서 제외 (있으면 교차검증에만 사용)
REQUIRED_COLS = [
    "사업연도", "지역", "신청인", "목장명", "마명", "현재마명", "마번", "부마", "성별",
    "출생일", "입사일", "퇴사일", "위탁기간", "위탁비(부가세포함)",
    "최초경매상장", "최초경매결과", "최종경매상장", "최종경매결과",
]

OPTIONAL_COLS = ["경매요약"]

KNOWN_AUCTION_RESULTS = {"낙찰", "유찰", "미상장"}


@dataclass
class ParsedRow:
    """엑셀 한 행을 정제한 결과. 유효한 행이면 horse가 채워지고, 스킵되면 skip_reason이 채워진다."""

    row_number: int  # 엑셀상 행 번호 (헤더=1 기준, 사용자에게 보여줄 때 사용)
    horse: Optional[dict[str, Any]] = None
    auctions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skip_reason: Optional[str] = None


def read_excel_sheet(file) -> pd.DataFrame:
    """
    file: 파일 경로, 파일류 객체(Streamlit UploadedFile 포함), 또는 bytes.
    마번은 선행 0 보존을 위해 반드시 문자열로 읽는다.
    """
    if isinstance(file, (bytes, bytearray)):
        file = io.BytesIO(file)
    df = pd.read_excel(file, sheet_name=SHEET_NAME, dtype={"마번": str})
    return df


def validate_columns(df: pd.DataFrame) -> list[str]:
    """필수 컬럼 누락 여부를 확인하고, 누락된 컬럼명 리스트를 반환한다 (P1 #5 대응)."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return missing


def parse_rows(df: pd.DataFrame) -> list[ParsedRow]:
    """DataFrame 전체를 순회하며 행 단위로 정제한다."""
    results: list[ParsedRow] = []
    for idx, row in df.iterrows():
        excel_row_number = idx + 2  # 헤더가 1행이므로 데이터는 2행부터
        results.append(_parse_single_row(excel_row_number, row))
    return results


def _parse_single_row(row_number: int, row: pd.Series) -> ParsedRow:
    parsed = ParsedRow(row_number=row_number)

    horse_id = _clean_horse_id(row.get("마번"))
    if not horse_id:
        parsed.skip_reason = "마번(horse_id)이 없어 스킵"
        return parsed

    name = _clean_str(row.get("마명"))
    if not name:
        parsed.skip_reason = f"마번 {horse_id}: 마명이 없어 스킵"
        return parsed

    current_name = _clean_str(row.get("현재마명")) or name

    farm_in_date = _clean_date(row.get("입사일"))
    farm_out_date = _clean_date(row.get("퇴사일"))
    birth_date = _clean_date(row.get("출생일"))

    entrustment_fee, fee_warning = _clean_currency(row.get("위탁비(부가세포함)"))
    if fee_warning:
        parsed.warnings.append(f"마번 {horse_id}: {fee_warning}")

    entrustment_period = _clean_str(row.get("위탁기간"))

    auctions, auction_warnings = _build_auction_events(
        horse_id=horse_id,
        first_date=row.get("최초경매상장"),
        first_result=row.get("최초경매결과"),
        final_date=row.get("최종경매상장"),
        final_result=row.get("최종경매결과"),
        excel_summary=row.get("경매요약") if "경매요약" in row.index else None,
    )
    parsed.warnings.extend(auction_warnings)

    status = _compute_status(farm_out_date)

    application_year = _clean_int(row.get("사업연도"))

    horse = {
        "horse_id": horse_id,
        "name": name,
        "current_name": current_name,
        "sex": _clean_str(row.get("성별")),
        "birth_date": birth_date,
        "sire_name": _clean_str(row.get("부마")),
        "region": _clean_str(row.get("지역")),
        "application_year": application_year,
        "applicant_name": _clean_str(row.get("신청인")),
        "farm_name": _clean_str(row.get("목장명")),
        "farm_in_date": farm_in_date,
        "farm_out_date": farm_out_date,
        "entrustment_period": entrustment_period,
        "entrustment_fee": entrustment_fee,
        "status": status,
    }

    parsed.horse = horse
    parsed.auctions = auctions
    return parsed


def _compute_status(farm_out_date: Optional[date]) -> str:
    """
    엑셀 이관 시점 상태 계산.
    farm_out_date(출식일)가 없으면 '위탁중', 있으면 '위탁종료'로 판정한다.
    """
    if farm_out_date is None:
        return STATUS_ENTRUSTED
    return STATUS_ENDED


def _parse_result_slot(date_value: Any, result_value: Any) -> Optional[dict[str, Any]]:
    """
    최초/최종 경매결과 슬롯 하나를 해석해 이벤트 dict로 변환한다.
    - 순수 숫자(쉼표/공백/'원' 허용)만 있으면 낙찰(그 숫자가 낙찰가)
    - "취소" 또는 "유찰" 텍스트가 포함되어 있으면 유찰
      (예: "경매취소(50,000,000)"처럼 숫자가 섞여 있어도 취소는 유찰로 간주)
    - 그 외 텍스트가 있으면 예상치 못한 표기로 간주해 원문을 auction_name에 그대로 남김
    - 공란이면 이 슬롯은 이벤트 없음 (None 반환)
    """
    result_text = _clean_str(result_value)
    if result_text is None:
        return None

    auction_date = _clean_date(date_value)

    if "취소" in result_text or "유찰" in result_text:
        hammer_price = None
        auction_name = "유찰"
    elif re.fullmatch(r"[\d,.\s원]+", result_text):
        # 순수 숫자(구분자 포함)로만 구성된 경우에만 낙찰로 판정
        digits = re.sub(r"[^\d]", "", result_text)
        hammer_price = int(digits) if digits else None
        auction_name = "낙찰"
    else:
        # 예상 못한 표기(오타 등) - 원문 그대로 유지, 호출부에서 warning 처리
        hammer_price = None
        auction_name = result_text

    return {
        "auction_date": auction_date,
        "auction_name": auction_name,
        "hammer_price": hammer_price,
        "buyer_name": None,
        "is_final": False,
    }


def _build_auction_events(
    horse_id: str,
    first_date: Any,
    first_result: Any,
    final_date: Any,
    final_result: Any,
    excel_summary: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """최초/최종 경매결과 슬롯을 해석해 auction_record 리스트를 만들고, 검증 warning을 함께 반환한다."""
    warnings: list[str] = []

    first_event = _parse_result_slot(first_date, first_result)
    final_event = _parse_result_slot(final_date, final_result)
    events = [e for e in (first_event, final_event) if e is not None]

    if not events:
        # 최초/최종 모두 이벤트가 없음 = 상장 이력 자체가 없는 말 -> 미상장으로 명시 기록
        events = [
            {
                "auction_date": None,
                "auction_name": "미상장",
                "hammer_price": None,
                "buyer_name": None,
                "is_final": False,
            }
        ]

    # 낙찰 이벤트 중 가장 나중 슬롯에만 is_final=True 부여 (최종 있으면 최종, 없으면 최초)
    won_indices = [i for i, e in enumerate(events) if e["auction_name"] == "낙찰"]
    if won_indices:
        events[won_indices[-1]]["is_final"] = True

    # 예상치 못한 표기 경고
    for e in events:
        if e["auction_name"] not in KNOWN_AUCTION_RESULTS:
            warnings.append(
                f"마번 {horse_id}: 예상치 못한 경매결과 표기 '{e['auction_name']}'"
            )

    # 경매요약 컬럼이 있으면 교차검증 (있을 때만, 없으면 스킵)
    summary_text = _clean_str(excel_summary)
    if summary_text:
        derived = _derive_summary(events)
        if summary_text != derived:
            warnings.append(
                f"마번 {horse_id}: 경매요약 불일치 (엑셀='{summary_text}', 계산='{derived}')"
            )

    return events, warnings


def _derive_summary(events: list[dict[str, Any]]) -> str:
    """이벤트 목록으로부터 낙찰 > 유찰 > 미상장 우선순위로 요약 결과를 계산한다."""
    names = {e["auction_name"] for e in events}
    if "낙찰" in names:
        return "낙찰"
    if "유찰" in names:
        return "유찰"
    return "미상장"


# ── 값 정제 헬퍼 ─────────────────────────────────────────────────────


def _is_missing(value: Any) -> bool:
    """None, NaN, NaT 등 pandas가 결측치로 취급하는 모든 값을 True로 판정."""
    try:
        result = pd.isna(value)
        return bool(result)
    except (TypeError, ValueError):
        return False


def _clean_str(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text if text else None

def _clean_horse_id(value: Any) -> Optional[str]:
    """마번 전용 정제 함수. None/결측치 처리 후 정규화는 공유 유틸에 위임."""
    if _is_missing(value):
        return None
    return normalize_horse_number(str(value).strip()) or None

def _clean_int(value: Any) -> Optional[int]:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _clean_date(value: Any) -> Optional[date]:
    if _is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean_str(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _clean_currency(value: Any) -> tuple[Optional[int], Optional[str]]:
    """쉼표/공백/'원' 등 텍스트가 섞인 금액을 정수로 변환. 실패 시 (None, 경고메시지)."""
    text = _clean_str(value)
    if text is None:
        return None, None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        # "유찰", "미상장" 처럼 숫자 자체가 없는 결과 텍스트는 경고 없이 None 처리
        return None, None
    try:
        return int(digits), None
    except ValueError:
        return None, f"금액 변환 실패: 원본값 '{text}'"