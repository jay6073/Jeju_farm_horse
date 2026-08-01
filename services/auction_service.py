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


def list_all_records() -> list[dict[str, Any]]:
    """경매관리 화면 전체 목록. Horse 정보(마명/신청인/상태)가 함께 조인되어 온다."""
    return repository.list_all_auction_records_with_horse()


# ── 내부 헬퍼 ────────────────────────────────────────────────────────


def _record_to_db_dict(record: AuctionRecord) -> dict[str, Any]:
    """[통합 시 변경] PostgreSQL 네이티브 date/boolean 타입 사용, 변환 불필요."""
    d = record.model_dump(exclude={"id"})
    return d


def _format_validation_error(e: ValidationError) -> str:
    messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
    return "입력값 오류 - " + "; ".join(messages)

def get_auction_summary(status: str | None = None) -> dict[str, Any]:
    """
    경매기록 요약: 전체 두수 / 낙찰 두수 / 낙찰가 합계.
    두수는 auction_record 건수가 아니라 마번(horse_id) 기준 유니크 카운트.
    한 말에 유찰/낙찰이 여러 건 있어도 1두로 집계된다.
    status가 주어지면 해당 위탁상태(위탁중/위탁종료)의 말로 한정.
    """
    records = repository.list_all_auction_records_with_horse()

    if status:
        records = [r for r in records if r.get("horse_status") == status]

    total_horses = {r["horse_id"] for r in records}
    won_records = [r for r in records if r.get("auction_name") == "낙찰"]
    won_horses = {r["horse_id"] for r in won_records}

    return {
        "total_count": len(total_horses),
        "won_count": len(won_horses),
        "total_price": sum(r["hammer_price"] for r in won_records),
    }