"""
Phase 4: 통합 대시보드 집계 로직.
Horse/AuctionRecord/RaceRecord/CareerSummary 데이터를 한 화면에서 종합적으로 보여주기 위한
집계 함수 모음. 개별 CRUD는 각 Phase의 repository/service를 그대로 재사용하고,
여기서는 "여러 테이블을 엮어서 요약"하는 로직만 다룬다.
규칙: 이 파일은 db.repository / services.entrustment_service / services.auction_service /
services.racing_service를 호출한다. ui를 import하지 않는다.

[통합 시 변경사항] horse_service -> entrustment_service로 import 경로만 변경.
나머지 로직은 repository 원자료 집계 방식 그대로 재사용 (수정 없음).
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from config.constants import STATUS_ENTRUSTED, STATUS_ENDED
from db import repository
from services import auction_service, entrustment_service, racing_service


def _auction_summary_by_horse() -> pd.DataFrame:
    """
    말(horse) 단위로 경매요약(낙찰/유찰/미상장)과 낙찰가(말당 1건)를 집계한다.
    """
    auctions = repository.list_all_auction_record_rows_with_horse()
    if not auctions:
        return pd.DataFrame(columns=["horse_id", "auction_summary", "total_hammer_price", "연도"])

    results_by_horse: dict[str, set[str]] = {}
    year_by_horse: dict[str, Any] = {}
    for row in auctions:
        hid = row["horse_id"]
        name = row.get("auction_name")
        if name:
            results_by_horse.setdefault(hid, set()).add(name)
        if hid not in year_by_horse:
            year_by_horse[hid] = row.get("application_year")

    prices = auction_service.hammer_price_per_horse(auctions)

    rows = []
    for hid in results_by_horse:
        rows.append({
            "horse_id": hid,
            "auction_summary": auction_service.summarize_auction_result(results_by_horse[hid]),
            "total_hammer_price": prices.get(hid, 0),
            "연도": year_by_horse.get(hid),
        })

    return pd.DataFrame(rows)


def overview_kpis() -> dict[str, Any]:
    """대시보드 최상단 핵심 지표."""
    horses = repository.fetch_all_horses_df_rows()
    auctions = repository.list_all_auction_record_rows_with_horse()
    summaries = repository.list_all_career_summaries_with_horse()

    total_horses = len(horses)
    status_counts = {
        STATUS_ENTRUSTED: 0,
        STATUS_ENDED: 0,
    }
    total_entrustment_fee = 0
    for h in horses:
        status_counts[h.get("status")] = status_counts.get(h.get("status"), 0) + 1
        if h.get("entrustment_fee"):
            total_entrustment_fee += h["entrustment_fee"]

    total_auctions = len(auctions)

    by_horse = _auction_summary_by_horse()
    won = by_horse[by_horse["auction_summary"] == "낙찰"]
    final_auction_count = len(won)
    total_hammer_price = int(won["total_hammer_price"].sum()) if not won.empty else 0

    total_starts = sum(s.get("total_starts") or 0 for s in summaries)
    total_wins = sum(s.get("total_wins") or 0 for s in summaries)
    total_prize_money = sum(s.get("total_prize_money") or 0 for s in summaries)

    unverified_race_count = len(entrustment_service.list_unverified_ended_horses())

    return {
        "total_horses": total_horses,
        "status_counts": status_counts,
        "total_entrustment_fee": total_entrustment_fee,
        "total_auctions": total_auctions,
        "final_auction_count": final_auction_count,
        "total_hammer_price": total_hammer_price,
        "total_race_starts": total_starts,
        "total_race_wins": total_wins,
        "total_prize_money": total_prize_money,
        "unverified_race_count": unverified_race_count,
    }


def status_breakdown_df() -> pd.DataFrame:
    kpis = overview_kpis()
    rows = [{"상태": k, "두수": v} for k, v in kpis["status_counts"].items()]
    return pd.DataFrame(rows)


def year_trend_df() -> pd.DataFrame:
    """년도별 위탁 두수 추이 (entrustment_service의 기존 통계 재사용)."""
    return entrustment_service.get_statistics_by_year()


def top_applicants_df(top_n: int = 10) -> pd.DataFrame:
    df = entrustment_service.get_statistics_by_applicant()
    return df.head(top_n)


def auction_price_by_year_df() -> pd.DataFrame:
    """사업연도별 낙찰(말 단위) 두수/낙찰가 합계/평균."""
    by_horse = _auction_summary_by_horse()
    won = by_horse[by_horse["auction_summary"] == "낙찰"].copy()
    if won.empty:
        return pd.DataFrame(columns=["연도", "낙찰건수", "낙찰가합계", "평균낙찰가"])

    won["연도"] = pd.to_numeric(won["연도"], errors="coerce")
    won = won.dropna(subset=["연도"])
    won["연도"] = won["연도"].astype(int)

    grouped = (
        won.groupby("연도")
        .agg(
            낙찰건수=("horse_id", "count"),
            낙찰가합계=("total_hammer_price", "sum"),
        )
        .reset_index()
        .sort_values("연도", ascending=False)
    )
    grouped["평균낙찰가"] = (grouped["낙찰가합계"] / grouped["낙찰건수"]).round(0).astype(int)
    grouped["낙찰가합계"] = grouped["낙찰가합계"].astype(int)

    grouped["낙찰가합계"] = grouped["낙찰가합계"].apply(lambda x: f"{x:,}")
    grouped["평균낙찰가"] = grouped["평균낙찰가"].apply(lambda x: f"{x:,}")

    return grouped[["연도", "낙찰건수", "낙찰가합계", "평균낙찰가"]]


def get_horse_full_profile(horse_id: str) -> Optional[dict[str, Any]]:
    """
    말 하나에 대한 통합 프로필: 기본정보 + 경매이력 + 경주성적 + 통산요약을 한번에 반환.
    """
    horse = entrustment_service.get_horse(horse_id)
    if horse is None:
        return None

    return {
        "horse": horse,
        "auctions": auction_service.list_records_for_horse(horse_id),
        "race_records": racing_service.get_race_records(horse_id),
        "career_summary": racing_service.get_career_summary(horse_id),
    }