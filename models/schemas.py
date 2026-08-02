"""
핵심 데이터 모델 정의.
[지침 변경 포인트] Horse/AuctionRecord/RaceRecord/CareerSummary 필드가 추가/변경되면
이 파일과 db/database.py의 CREATE TABLE 문을 함께 수정해야 한다.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from shared.horse_number import normalize_horse_number
from config.constants import HORSE_STATUS_OPTIONS, STATUS_ENTRUSTED



class Horse(BaseModel):
    """위수탁마 핵심 엔티티. 마번(horse_id)이 PK."""

    horse_id: str = Field(..., description="마번 (7자리, 선행 0 보존)")
    name: str = Field(..., description="마명")
    current_name: Optional[str] = Field(None, description="현재마명")
    sex: Optional[str] = None
    birth_date: Optional[date] = None
    breeder_name: Optional[str] = Field(None, description="생산자명")
    sire_name: Optional[str] = Field(None, description="부마")
    region: Optional[str] = None

    application_year: Optional[int] = Field(None, description="사업연도")
    applicant_name: Optional[str] = Field(None, description="신청인")
    farm_name: Optional[str] = None
    farm_in_date: Optional[date] = None
    farm_out_date: Optional[date] = None

    entrustment_period: Optional[str] = Field(
        None, description="위탁기간 (원본 텍스트 그대로 보존 가능)"
    )
    entrustment_fee: Optional[int] = Field(None, description="위탁비(부가세포함)")
    status: str = Field(STATUS_ENTRUSTED, description="위탁중/위탁종료")

    first_listed_date: Optional[date] = Field(None, description="최초경매상장일")
    first_result: Optional[str] = Field(None, description="최초경매결과 (표시용 정규화 텍스트)")
    final_listed_date: Optional[date] = Field(None, description="최종경매상장일")
    final_result: Optional[str] = Field(None, description="최종경매결과 (표시용 정규화 텍스트)")

    @field_validator("horse_id")
    @classmethod
    def validate_horse_id(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("horse_id(마번)는 필수입니다.")
        return normalize_horse_number(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in HORSE_STATUS_OPTIONS:
            raise ValueError(f"status는 {HORSE_STATUS_OPTIONS} 중 하나여야 합니다.")
        return v

    @field_validator("current_name")
    @classmethod
    def strip_current_name(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class AuctionRecord(BaseModel):
    """경매 낙찰 기록. Horse 1:N. 한 마리가 3건 이상일 수 있음."""

    id: Optional[int] = Field(None, description="자동 증가 PK")
    horse_id: str
    auction_date: Optional[date] = None
    auction_name: Optional[str] = Field(None, description="경매명 또는 경매요약 텍스트")
    hammer_price: Optional[int] = Field(None, description="낙찰가")
    buyer_name: Optional[str] = None
    is_final: bool = Field(
        False, description="가장 마지막에 낙찰된 건인지 여부(최종경매 플래그)"
    )


class RaceRecord(BaseModel):
    """경주 성적 1건. Horse 1:N. Phase 3 스크래핑으로 채워짐."""

    id: Optional[int] = None
    horse_id: str
    race_date: Optional[date] = None
    race_name: Optional[str] = None
    distance: Optional[int] = None
    grade: Optional[str] = None
    horse_number: Optional[int] = None
    rank: Optional[str] = Field(None, description="예: '2/12' 형태 원본 보존")
    jockey: Optional[str] = None
    record_time: Optional[str] = None
    weight: Optional[str] = Field(None, description="부담중량 (wgbudam)")
    horse_weight: Optional[int] = Field(None, description="마체중 절대값(kg), wghr")
    track_condition: Optional[str] = None


class CareerSummary(BaseModel):
    """RaceRecord 누적으로 자동 계산되는 통산 요약. Horse 1:1. 엑셀 이관 대상 아님."""

    horse_id: str
    total_starts: int = 0
    total_wins: int = 0
    win_rate: float = 0.0
    total_prize_money: int = 0
    rating: Optional[str] = Field(None, description="통산 레이팅, RaceResult.rating")
    data_source: str = Field("scraping", description="데이터 출처")
    last_scraped_at: Optional[str] = Field(None, description="마지막 스크래핑 시각 ISO 문자열")
