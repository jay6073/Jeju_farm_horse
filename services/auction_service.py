"""
Phase 2: 경매관리 비즈니스 로직.
핵심 규칙: 한 말(Horse)당 경매는 여러 건(3건 이상도 가능) 등록될 수 있고,
그중 '최종 낙찰'로 지정된 건은 항상 최대 1건만 존재한다.

[중요 - 상태 결합 금지] AuctionRecord.is_final은 순수하게 "경매 이력상 마지막 낙찰건"이라는
사실만 기록하는 데이터이며, Horse.status를 자동으로 변경하지 않는다.

규칙: 이 파일은 db.repository만 호출한다.

[통합 시 변경사항] insert_auction_record + unset_final_flag_for_horse를 하나의
트랜잭션(get_connection 하나)으로 묶어 "최종건 1개만 존재" 정합성을 보장.
날짜/불리언 변환은 PostgreSQL 네이티브 타입 사용으로 제거.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from db.repository import get_connection
from db import repository
from models.schemas import AuctionRecord
from pydantic import ValidationError


class AuctionServiceError(Exception):
    """서비스 레이어에서 발생하는 검증/비즈니스 오류를 UI에 전달하기 위한 예외."""


# ── 등록/수정/삭제 ──────────────────────────────────────────────────


def add_auction_record(
    horse_id: str,
    auction_date: Optional[date],
    auction_name: Optional[str],
    hammer_price: Optional[int],
    buyer_name: Optional[str],
    is_final: bool = False,
) -> AuctionRecord:
    if not repository.horse_exists(horse_id):
        raise AuctionServiceError(f"마번 {horse_id}에 해당하는 위탁 계약을 찾을 수 없습니다.")

    try:
        record = AuctionRecord(
            horse_id=horse_id,
            auction_date=auction_date,
            auction_name=auction_name,
            hammer_price=hammer_price,
            buyer_name=buyer_name,
            is_final=is_final,
        )
    except ValidationError as e:
        raise AuctionServiceError(_format_validation_error(e)) from e

    db_dict = _record_to_db_dict(record)

    with get_connection() as conn:
        new_id = repository.insert_auction_record(db_dict, conn=conn)
        if is_final:
            # 최종 건은 한 말당 1개만 유지. insert와 같은 트랜잭션으로 묶어 정합성 보장.
            repository.unset_final_flag_for_horse(horse_id, except_id=new_id, conn=conn)

    return record


def update_auction_record(record_id: int, fields: dict[str, Any]) -> None:
    existing = repository.get_auction_record(record_id)
    if not existing:
        raise AuctionServiceError(f"경매 기록 ID {record_id}를 찾을 수 없습니다.")

    fields = dict(fields)

    with get_connection() as conn:
        repository.update_auction_record(record_id, fields, conn=conn)
        if fields.get("is_final") is True:
            horse_id = existing["horse_id"]
            repository.unset_final_flag_for_horse(horse_id, except_id=record_id, conn=conn)


def delete_auction_record(record_id: int) -> None:
    existing = repository.get_auction_record(record_id)
    if not existing:
        raise AuctionServiceError(f"경매 기록 ID {record_id}를 찾을 수 없습니다.")

    repository.delete_auction_record(record_id)


# ── 조회 ────────────────────────────────────────────────────────────


def list_records_for_horse(horse_id: str) -> list[AuctionRecord]:
    rows = repository.list_auction_records(horse_id)
    return [AuctionRecord(**r) for r in rows]


def list_all_records(status: str | None = None) -> list[dict[str, Any]]:
    """경매관리 화면 목록. 마번당 1행 + entrustment 4필드."""
    return repository.list_all_auction_records_with_horse(status)


def get_auction_summary(status: str | None = None) -> dict[str, Any]:
    """
    경매관리 요약 카드. 목록과 동일한 데이터(마번당 1행 + entrustment 4필드)를 기준으로 집계한다.
    분류·낙찰가 모두 first_result / final_result 텍스트에서 판단한다.
    """
    horses = repository.list_all_auction_records_with_horse(status)

    won = lost = unlisted = 0
    total_price = 0

    for h in horses:
        first_r = h.get("first_result")
        final_r = h.get("final_result")
        category = classify_horse_from_entrustment_fields(first_r, final_r)
        if category == "낙찰":
            won += 1
            total_price += hammer_price_from_entrustment_fields(first_r, final_r)
        elif category == "유찰":
            lost += 1
        else:
            unlisted += 1

    return {
        "total_count": len(horses),
        "won_count": won,
        "lost_count": lost,
        "unlisted_count": unlisted,
        "total_price": total_price,
    }


# ── entrustment 4필드 집계 (경매관리 UI와 동일 기준) ─────────────────────


_HAMMER_PRICE_RE = re.compile(r"낙찰\s*\(([\d,]+)\)")


def _normalize_display_result(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "-" else None


def classify_horse_from_entrustment_fields(
    first_result: Any,
    final_result: Any,
) -> str:
    """
    entrustment first/final result → 말 1두의 요약 분류.
    우선순위: 낙찰 > 유찰/계약해지 > 미상장 > (둘 다 공란 → 미상장)
    """
    slots = [
        _normalize_display_result(first_result),
        _normalize_display_result(final_result),
    ]
    active = [s for s in slots if s]
    if not active:
        return "미상장"
    if any(s.startswith("낙찰") for s in active):
        return "낙찰"
    if any(s in ("유찰", "계약해지") for s in active):
        return "유찰"
    return "미상장"


def hammer_price_from_entrustment_fields(
    first_result: Any,
    final_result: Any,
) -> int:
    """4컬럼 결과 텍스트에서 낙찰가 1건 추출. 최종 슬롯 우선, 없으면 최초 슬롯."""
    for r in (final_result, first_result):
        text = _normalize_display_result(r)
        if text and text.startswith("낙찰"):
            match = _HAMMER_PRICE_RE.search(text)
            if match:
                return int(match.group(1).replace(",", ""))
    return 0


# ── auction_record 집계 (통합 대시보드 등에서 재사용) ───────────────────


def _has_lost_result(names: set[str]) -> bool:
    for name in names:
        if name in ("유찰", "계약해지"):
            return True
        if name and ("취소" in name or "해지" in name):
            return True
    return False


def summarize_auction_result(names: set[str]) -> str | None:
    """말별 auction_name 집합에서 낙찰 > 유찰/계약해지 > 미상장 우선순위로 1개 반환."""
    if "낙찰" in names:
        return "낙찰"
    if _has_lost_result(names):
        return "유찰"
    if "미상장" in names:
        return "미상장"
    return None


def hammer_price_per_horse(records: list[dict[str, Any]]) -> dict[str, int]:
    """말당 낙찰가 1건만 인정. is_final 우선, 없으면 auction_date 최신."""
    by_horse: dict[str, tuple[bool, date | None, int]] = {}

    for r in records:
        if r.get("auction_name") != "낙찰":
            continue
        hid = r["horse_id"]
        price = r.get("hammer_price") or 0
        is_final = bool(r.get("is_final"))
        adate = r.get("auction_date")

        prev = by_horse.get(hid)
        if prev is None:
            by_horse[hid] = (is_final, adate, price)
            continue

        prev_final, prev_date, prev_price = prev
        if is_final and not prev_final:
            by_horse[hid] = (True, adate, price)
        elif is_final == prev_final and (adate or date.min) > (prev_date or date.min):
            by_horse[hid] = (is_final, adate, price)

    return {hid: price for hid, (_, _, price) in by_horse.items()}


# ── 내부 헬퍼 ────────────────────────────────────────────────────────


def _record_to_db_dict(record: AuctionRecord) -> dict[str, Any]:
    """[통합 시 변경] PostgreSQL 네이티브 date/boolean 타입 사용, 변환 불필요."""
    d = record.model_dump(exclude={"id"})
    return d


def _format_validation_error(e: ValidationError) -> str:
    messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
    return "입력값 오류 - " + "; ".join(messages)
