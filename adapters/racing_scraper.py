"""
horsepia.com 경주성적 스크래핑 어댑터.
[지침 변경 포인트] horsepia.com 페이지 구조(initData 변수명, 필드명)가 바뀌면 이 파일만 수정한다.
규칙: 이 파일은 DB(repository)를 호출하지 않는다. 순수 HTTP 요청 + 파싱만 담당하고,
      저장은 services/racing_service.py가 담당한다.

설계 근거 (위수탁마_관리시스템_설계프롬프트.md 7번 섹션 참고):
- 대상 마종은 모두 더러브렛(hrsGbCd=00100)이므로 제주 경마 등 별도 구조는 다루지 않는다.
- SBGrid가 화면에 보여주는 가상 스크롤 표는 실제로는 detail.do 페이지 HTML 안에
  JS 변수(initData)로 전체 데이터가 이미 박혀있다. 별도의 숨겨진 API가 없으므로
  Selenium 없이 requests + 정규식 + html.unescape + json.loads로 충분하다.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

DETAIL_URL = "https://www.horsepia.com/hp/pa/hh/PAHH2040D05/detail.do"
DEFAULT_HRS_GB_CD = "00100"  # 더러브렛

# var initData = fnReplaceAll(fnReplaceAll('{...}', "&#034;", "\""), "&#039;", "'");
_INIT_DATA_PATTERN = re.compile(
    r"var initData = fnReplaceAll\(fnReplaceAll\('(.+?)', \"&#034;\"",
    re.DOTALL,
)

# 연결 5초 / 읽기 30초. 서버 응답이 느릴 때 read timeout으로 끊기던 문제 완화.
REQUEST_TIMEOUT = (5, 30)
MAX_RETRIES = 3

# horsepia.com이 python-requests 기본 User-Agent를 감지해 연결을 끊는 문제(RemoteDisconnected)
# 완화를 위해 일반 브라우저처럼 보이는 헤더를 사용한다.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.horsepia.com/",
}


class ScrapingError(Exception):
    """네트워크 오류, 페이지 구조 변경 등 스크래핑 자체가 실패했을 때 발생."""


@dataclass
class ScrapedRaceData:
    """한 마리의 스크래핑 결과. 경주 이력이 없는 말이면 race_records가 빈 리스트."""

    horse_id: str
    race_records: list[dict[str, Any]] = field(default_factory=list)
    career_summary: Optional[dict[str, Any]] = None


def create_session() -> requests.Session:
    """
    racing_service.py에서 여러 마번을 순회할 때 재사용할 세션.
    헤더가 세션에 이미 실려있어 매 요청마다 다시 넣을 필요가 없다.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_race_data(
    hr_no: str, hrs_gb_cd: str = DEFAULT_HRS_GB_CD, session: Optional[requests.Session] = None
) -> ScrapedRaceData:
    """
    마번(hr_no) 하나에 대한 경주성적 전체를 가져온다.
    경주 이력이 없는 말이면 race_records=[] 로 정상 반환된다 (예외 아님).
    타임아웃/연결끊김 등 일시적 오류는 최대 MAX_RETRIES회 재시도한다.
    """
    http = session or requests
    headers = None if session is not None else DEFAULT_HEADERS

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = http.get(
                DETAIL_URL,
                params={"hrNo": hr_no, "hrsGbCd": hrs_gb_cd, "eqsthrConvYn": "N"},
                timeout=REQUEST_TIMEOUT,
                headers=headers,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)  # 2초, 4초 순차 대기 후 재시도
                continue
            raise ScrapingError(
                f"마번 {hr_no} 요청 실패 ({MAX_RETRIES}회 재시도 후): {last_error}"
            ) from last_error
        finally:
            # 서버 부하 완화 및 봇 탐지 회피용 랜덤 대기
            time.sleep(random.uniform(0.5, 1.5))

    raw_data = _extract_init_data(resp.text)
    if raw_data is None:
        # 페이지 구조가 바뀌었거나(initData 없음), 완전히 새로운 말이라 데이터 자체가 없는 경우
        return ScrapedRaceData(horse_id=hr_no, race_records=[], career_summary=None)

    race_result_list = raw_data.get("RaceResultList", []) or []
    race_result_summary = raw_data.get("RaceResult", {}) or {}

    race_records = [_map_race_record(hr_no, r) for r in race_result_list]
    career_summary = (
        _map_career_summary(hr_no, race_result_summary) if race_result_summary else None
    )

    return ScrapedRaceData(
        horse_id=hr_no, race_records=race_records, career_summary=career_summary
    )


def _extract_init_data(html_text: str) -> Optional[dict[str, Any]]:
    match = _INIT_DATA_PATTERN.search(html_text)
    if not match:
        return None
    raw_json = html.unescape(match.group(1))
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        return None


def _map_race_record(horse_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """
    필드 매핑 (설계문서 7.5절):
    race_date<-rcDate, race_name<-rcName, distance<-rcDist, grade<-rank,
    horse_number<-chulNo, rank<-chak, jockey<-jkName, record_time<-rctime,
    weight<-wgbudam, horse_weight<-wghr(절대값kg, 0이면 미측정으로 간주해 None),
    track_condition<-track
    """
    wghr = raw.get("wghr")
    horse_weight = None
    if isinstance(wghr, (int, float)) and wghr > 0:
        horse_weight = int(wghr)

    return {
        "horse_id": horse_id,
        "race_date": _clean(raw.get("rcDate")),
        "race_name": _clean(raw.get("rcName")),
        "distance": _to_int(raw.get("rcDist")),
        "grade": _clean(raw.get("rank")),
        "horse_number": _to_int(raw.get("chulNo")),
        "rank": _clean(raw.get("chak")),
        "jockey": _clean(raw.get("jkName")),
        "record_time": _clean(raw.get("rctime")),  # "출전취소" 같은 문자열도 그대로 보존
        "weight": _clean(raw.get("wgbudam")),
        "horse_weight": horse_weight,
        "track_condition": _clean(raw.get("track")),
    }


def _map_career_summary(horse_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """
    RaceResult(통산 요약, 말 1마리당 1건)을 CareerSummary 필드로 매핑.
    rating은 문자열에 공백 패딩이 있어 trim 처리.
    """
    rating = raw.get("rating")
    rating = rating.strip() if isinstance(rating, str) else rating

    total_starts = _to_int(raw.get("rcCnt")) or 0
    total_wins = _to_int(raw.get("fstCnt")) or 0
    win_rate = _parse_percent(raw.get("winRate"))
    total_prize_money = _parse_amount(raw.get("amt"))

    return {
        "horse_id": horse_id,
        "total_starts": total_starts,
        "total_wins": total_wins,
        "win_rate": win_rate,
        "total_prize_money": total_prize_money,
        "rating": rating,
        "data_source": "scraping",
    }


# ── 값 정제 헬퍼 ─────────────────────────────────────────────────────


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _parse_percent(value: Any) -> float:
    """'12%', '0%' 같은 문자열에서 숫자만 추출. 실패 시 0.0."""
    if value is None:
        return 0.0
    text = str(value).strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_amount(value: Any) -> int:
    """쉼표/공백 섞인 금액 문자열을 정수로 변환. 실패 시 0."""
    if value is None:
        return 0
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else 0