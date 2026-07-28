"""
위탁 등록 및 년도별/신청인별 통계 비즈니스 로직.
[지침 변경 포인트] 상태 자동계산 규칙, 위탁기간 계산 방식이 바뀌면 이 파일만 수정한다.
규칙: 이 파일은 db.repository만 호출하고, ui 모듈을 import하지 않는다.

[통합 시 변경사항] 원래 horse_service.py였으나, "말 개체"는 A의 horses 테이블이
전담하고 이 파일은 "위탁 계약 정보"(entrustment 테이블)만 다루는 것으로 역할이
명확해져 entrustment_service.py로 이름을 바꿈. 대상 테이블도 horse -> entrustment.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
from pydantic import ValidationError

from config.constants import (
    HORSE_STATUS_OPTIONS,
    STATUS_ENTRUSTED,
    STATUS_ENDED,
)
from db import repository
from models.schemas import Horse
from repository.horse_repository import _get_connection as _a_get_connection


def a_horse_exists(horse_id: str) -> bool:
    """A의 horses 테이블(전체 말 관리)에 해당 마번이 존재하는지 확인."""
    with _a_get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM horses WHERE 마번 = %s", (horse_id,))
            return cur.fetchone() is not None

RECHECK_INTERVAL_DAYS = 7  # 위탁종료된 말은 이 기간마다 경주기록을 다시 확인한다


class EntrustmentServiceError(Exception):
    """서비스 레이어에서 발생하는 검증/비즈니스 오류를 UI에 전달하기 위한 예외."""


# ── 상태/파생값 계산 ─────────────────────────────────────────────────


def compute_status(farm_out_date: Optional[date]) -> str:
    """
    위탁 상태 자동 계산 규칙 (등록/이관 시점 기준):
    - 퇴사일이 없으면 '위탁중'
    - 퇴사일이 있으면 '위탁종료'
    """
    if farm_out_date is None:
        return STATUS_ENTRUSTED
    return STATUS_ENDED


def compute_entrustment_period(
    farm_in_date: Optional[date], farm_out_date: Optional[date]
) -> Optional[str]:
    """입사일~퇴사일 기준 위탁기간(개월 수)을 계산한다. 둘 중 하나라도 없으면 None."""
    if not farm_in_date or not farm_out_date:
        return None
    months = (farm_out_date.year - farm_in_date.year) * 12 + (
        farm_out_date.month - farm_in_date.month
    )
    if farm_out_date.day < farm_in_date.day:
        months -= 1
    months = max(months, 0)
    return f"{months}개월"


# ── 등록/수정 ────────────────────────────────────────────────────────


def register_horse(raw: dict[str, Any], overwrite: bool = False) -> Horse:
    """
    신규 위탁 계약 등록. raw는 UI 폼에서 넘어온 dict.
    status/entrustment_period는 값이 없으면 자동 계산해서 채운다.
    [통합 시 추가] horse_id가 A의 horses 테이블에 실제로 등록된 말인지 먼저 확인한다.
    """
    raw = dict(raw)  # 원본 훼손 방지

    horse_id = raw.get("horse_id")
    if not horse_id or not a_horse_exists(horse_id):
        raise EntrustmentServiceError(
            f"마번 {horse_id}는 전체 말 관리(A)에 먼저 등록되어야 위탁 계약을 등록할 수 있습니다."
        )

    if not raw.get("current_name"):
        raw["current_name"] = raw.get("name")

    if not raw.get("entrustment_period"):
        raw["entrustment_period"] = compute_entrustment_period(
            raw.get("farm_in_date"), raw.get("farm_out_date")
        )

    if not raw.get("status"):
        raw["status"] = compute_status(raw.get("farm_out_date"))

    try:
        horse = Horse(**raw)
    except ValidationError as e:
        raise EntrustmentServiceError(_format_validation_error(e)) from e

    horse_dict = _horse_to_db_dict(horse)

    if repository.horse_exists(horse.horse_id):
        if not overwrite:
            raise EntrustmentServiceError(
                f"마번 {horse.horse_id}는 이미 위탁 계약이 등록되어 있습니다. "
                "덮어쓰려면 overwrite=True로 다시 시도하세요."
            )
        repository.update_horse(horse.horse_id, horse_dict)
    else:
        repository.insert_horse(horse_dict)

    return horse


def update_horse_fields(horse_id: str, fields: dict[str, Any]) -> None:
    if not repository.horse_exists(horse_id):
        raise EntrustmentServiceError(f"마번 {horse_id}에 해당하는 위탁 계약을 찾을 수 없습니다.")
    repository.update_horse(horse_id, fields)


def set_status(horse_id: str, new_status: str) -> None:
    """위탁 계약 화면에서 사용자가 상태를 수동으로 변경할 때 사용하는 범용 함수."""
    if new_status not in HORSE_STATUS_OPTIONS:
        raise EntrustmentServiceError(f"status는 {HORSE_STATUS_OPTIONS} 중 하나여야 합니다.")
    update_horse_fields(horse_id, {"status": new_status})


def delete_horse(horse_id: str) -> None:
    """
    위탁 계약을 삭제한다. 연관된 경매기록/경주기록/통산요약도 함께 삭제한다
    (실수로 잘못 등록한 위탁 계약을 되돌리는 용도이므로 연쇄 삭제가 자연스럽다).
    정상 종료된 위탁은 삭제가 아니라 set_status로 '위탁종료' 처리해야 한다.
    """
    if not repository.horse_exists(horse_id):
        raise EntrustmentServiceError(f"마번 {horse_id}에 해당하는 위탁 계약을 찾을 수 없습니다.")

    for record in repository.list_auction_records(horse_id):
        repository.delete_auction_record(record["id"])
    repository.delete_race_records_by_horse(horse_id)
    repository.delete_career_summary(horse_id)
    repository.delete_horse(horse_id)


def get_horse(horse_id: str) -> Optional[Horse]:
    row = repository.get_horse(horse_id)
    return Horse(**row) if row else None


def list_horses(
    status: Optional[str] = None,
    applicant_name: Optional[str] = None,
    application_year: Optional[int] = None,
) -> list[Horse]:
    rows = repository.list_horses(status, applicant_name, application_year)
    return [Horse(**r) for r in rows]


def list_unverified_ended_horses() -> list[str]:
    """
    위탁종료 상태이면서 아래 조건을 만족하는 마번 목록:
    - 경주기록을 한 번도 확인하지 않은 경우
    - 마지막 확인 후 RECHECK_INTERVAL_DAYS일이 지난 경우 (재확인 주기)

    [성능 개선] 말 한 마리당 개별 조회하던 N+1 쿼리를 제거하고,
    전체 통산요약을 한 번에 가져와 메모리에서 매칭하도록 변경.
    """
    horses = list_horses()
    ended = [h for h in horses if h.status == STATUS_ENDED]
    if not ended:
        return []

    all_summaries = repository.list_all_career_summaries_with_horse()
    summary_map = {s["horse_id"]: s for s in all_summaries}

    cutoff = datetime.now() - timedelta(days=RECHECK_INTERVAL_DAYS)

    unverified = []
    for h in ended:
        summary = summary_map.get(h.horse_id)
        if summary is None or summary.get("last_scraped_at") is None:
            unverified.append(h.horse_id)
            continue

        last_scraped = _coerce_datetime(summary["last_scraped_at"])
        if last_scraped is None or last_scraped < cutoff:
            unverified.append(h.horse_id)

    return unverified


# ── 통계 (년도별 / 신청인별) ────────────────────────────────────────


def _is_unverified_race(horse_id: str, status: str, summary_map: dict) -> bool:
    """위탁종료 상태이면서 경주기록 확인이 안 됐거나 재확인 주기가 지난 경우 True"""
    if status != STATUS_ENDED:
        return False
    summary = summary_map.get(horse_id)
    if summary is None or summary.get("last_scraped_at") is None:
        return True

    last_scraped = _coerce_datetime(summary["last_scraped_at"])
    if last_scraped is None:
        return True

    cutoff = datetime.now() - timedelta(days=RECHECK_INTERVAL_DAYS)
    return last_scraped < cutoff


def get_statistics_by_year() -> pd.DataFrame:
    """
    년도별 위탁 통계: 신청 두수, 위탁중/위탁종료/경주기록확인필요 두수, 평균 위탁비.
    """
    rows = repository.fetch_all_horses_df_rows()
    if not rows:
        return pd.DataFrame(
            columns=[
                "사업연도",
                "신청두수",
                "위탁중",
                "위탁종료",
                "경주기록확인필요",
                "평균위탁비",
            ]
        )

    df = pd.DataFrame(rows)
    all_summaries = repository.list_all_career_summaries_with_horse()
    summary_map = {s["horse_id"]: s for s in all_summaries}
    df["_unverified_race"] = df.apply(
        lambda r: _is_unverified_race(r["horse_id"], r["status"], summary_map), axis=1
    )

    grouped = (
        df.groupby("application_year")
        .agg(
            신청두수=("horse_id", "count"),
            위탁중=("status", lambda s: (s == STATUS_ENTRUSTED).sum()),
            위탁종료=("status", lambda s: (s == STATUS_ENDED).sum()),
            경주기록확인필요=("_unverified_race", "sum"),
            평균위탁비=("entrustment_fee", "mean"),
        )
        .reset_index()
        .rename(columns={"application_year": "사업연도"})
        .sort_values("사업연도", ascending=False)
    )
    grouped["평균위탁비"] = grouped["평균위탁비"].round(0)
    return grouped


def get_statistics_by_applicant() -> pd.DataFrame:
    """
    신청인별 위탁 통계: 신청 두수, 상태별 두수, 최초/최근 신청연도.
    """
    rows = repository.fetch_all_horses_df_rows()
    if not rows:
        return pd.DataFrame(
            columns=[
                "신청인",
                "신청두수",
                "위탁중",
                "위탁종료",
                "경주기록확인필요",
                "최초신청연도",
                "최근신청연도",
            ]
        )

    df = pd.DataFrame(rows)
    all_summaries = repository.list_all_career_summaries_with_horse()
    summary_map = {s["horse_id"]: s for s in all_summaries}
    df["_unverified_race"] = df.apply(
        lambda r: _is_unverified_race(r["horse_id"], r["status"], summary_map), axis=1
    )

    grouped = (
        df.groupby("applicant_name")
        .agg(
            신청두수=("horse_id", "count"),
            위탁중=("status", lambda s: (s == STATUS_ENTRUSTED).sum()),
            위탁종료=("status", lambda s: (s == STATUS_ENDED).sum()),
            경주기록확인필요=("_unverified_race", "sum"),
            최초신청연도=("application_year", "min"),
            최근신청연도=("application_year", "max"),
        )
        .reset_index()
        .rename(columns={"applicant_name": "신청인"})
        .sort_values("신청두수", ascending=False)
    )
    return grouped


# ── 내부 헬퍼 ────────────────────────────────────────────────────────


_ENTRUSTMENT_FIELDS = {
    "horse_id",
    "application_year",
    "applicant_name",
    "farm_name",
    "farm_in_date",
    "farm_out_date",
    "entrustment_period",
    "entrustment_fee",
    "status",
}


def _horse_to_db_dict(horse: Horse) -> dict[str, Any]:
    """
    Pydantic 모델 -> entrustment 테이블 저장용 dict.
    [통합 시 변경] Horse 모델에는 말 자체 속성(name 등)도 섞여 있지만,
    entrustment 테이블은 위탁 계약 필드만 가지므로 걸러서 반환한다.
    PostgreSQL은 date 네이티브 타입을 지원하므로 .isoformat() 변환은 하지 않는다.
    """
    full = horse.model_dump()
    return {k: v for k, v in full.items() if k in _ENTRUSTMENT_FIELDS}


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """
    [통합 시 추가] last_scraped_at이 PostgreSQL TIMESTAMP 컬럼이라 psycopg가 이미
    datetime 객체로 반환하는 경우와, 혹시 문자열로 넘어오는 경우를 모두 방어적으로 처리.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _format_validation_error(e: ValidationError) -> str:
    messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
    return "입력값 오류 - " + "; ".join(messages)