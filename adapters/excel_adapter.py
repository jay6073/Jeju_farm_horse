"""
엑셀(전기육성위수탁마 시트) -> 내부 dict 구조로 변환하는 순수 어댑터.
[지침 변경 포인트] 엑셀 컬럼명/순서가 바뀌면 COLUMN_* 상수만 수정하면 되도록 구성.
규칙: 이 파일은 DB(repository)를 호출하지 않는다. 순수 파싱/정제만 담당하고,
      실제 저장은 services/import_service.py가 담당한다.
"""
from __future__ import annotations
from shared.horse_number import normalize_horse_number

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from config.constants import STATUS_ENTRUSTED, STATUS_ENDED

SHEET_NAME = "전기육성위수탁마"

# 이관 대상 컬럼만 정의 (구분/순번/수득상금 이후 컬럼은 애초에 여기 포함하지 않음)
REQUIRED_COLS = [
    "사업연도", "지역", "신청인", "목장명", "마명", "현재마명", "마번", "부마", "성별",
    "출생일", "입사일", "퇴사일", "위탁기간", "위탁비(부가세포함)",
    "최초경매상장", "최초경매결과", "최종경매상장", "최종경매낙찰", "경매요약",
]


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
    file: 파일 경로 또는 파일류 객체 (Streamlit UploadedFile 포함).
    마번은 선행 0 보존을 위해 반드시 문자열로 읽는다.
    """
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

    auction_first = _extract_auction(
        row.get("최초경매상장"), row.get("최초경매결과"), is_final=False
    )
    auction_final = _extract_auction(
        row.get("최종경매상장"), row.get("최종경매낙찰"), is_final=True
    )
    auction_summary = _clean_str(row.get("경매요약"))

    auctions = []
    for a in (auction_first, auction_final):
        if a is not None:
            if auction_summary:
                a["auction_name"] = auction_summary
            auctions.append(a)

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


def _extract_auction(
    date_value: Any, price_or_result: Any, is_final: bool
) -> Optional[dict[str, Any]]:
    """
    최초경매상장/최초경매결과 또는 최종경매상장/최종경매낙찰 한 쌍을 AuctionRecord dict로 변환.
    둘 다 비어있으면 None 반환 (해당 경매 이벤트 없음).
    """
    auction_date = _clean_date(date_value)
    price_text = _clean_str(price_or_result)

    if auction_date is None and not price_text:
        return None

    hammer_price, _ = _clean_currency(price_or_result)

    return {
        "auction_date": auction_date,
        "hammer_price": hammer_price,
        "buyer_name": None,  # 엑셀에 없음 -> 공란, 추후 수기 보완
        "is_final": is_final,
        "_raw_result_text": price_text,  # 숫자 변환 실패시(예: "유찰") 참고용, DB 저장 전 제거됨
    }


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
