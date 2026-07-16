"""
horsepia.com 마적사항 스크래핑 서비스.

동작 방식 (Jay님이 실제로 브라우저 소스에서 확인한 구조):
- horsepia.com 마필 상세 페이지 HTML 안에 `initData`라는 JS 변수로 마적사항이 담겨 내려온다.
- 단, 순수 JSON이 아니라 HTML 엔티티로 인코딩된 문자열이 `fnReplaceAll()` 두 번을 거쳐
  런타임에 JSON으로 복원되는 구조다:
      var initData = fnReplaceAll(fnReplaceAll('{&#034;key&#034;:...}', "&#034;", "\""), "&#039;", "'");
  즉 서버가 JSP 단에서 HTML 이스케이프한 문자열을 그대로 스크립트에 박아넣은 것으로 보인다.
  파이썬에서는 굳이 JS를 실행하지 않고, 같은 두 번의 치환(&#034;→", &#039;→')을
  문자열 레벨에서 그대로 적용한 뒤 json.loads()하면 된다. Selenium 불필요.
- 네트워크 요청은 타임아웃을 넉넉히 잡고(연결 5초/읽기 30초), 실패 시 지수 백오프로
  최대 3회 재시도하며, 매 요청 사이 랜덤 딜레이를 둬 서버 부하를 줄인다.

⚠️ 확인 필요 (아직 미확정):
  1. hrsGbCd=00100이 모든 마종에 공통인지, 아니면 제주마/일반마 등에 따라 값이 다른지
  2. "마적사항"으로 보여줄 범위가 이 페이지(PAHH2040D01=개체식별) 하나로 충분한지,
     아니면 혈통정보(D02)/활용정보(D05, 경주성적 포함) 등 다른 탭도 같은 방식으로
     추가 조회해서 합쳐야 하는지
"""
from __future__ import annotations

import json
import random
import re
import time
from typing import Optional

import requests

from models.horse import Horse, HORSE_BREED_CODES, normalize_horse_number

# 확인된 실제 URL 패턴. {tab}은 상세 탭 코드(기본값: 개체식별 PAHH2040D01),
# hrsGbCd는 마종 구분코드 (현재 00100만 확인됨 — 다른 마종도 동일한지 확인 필요).
HORSEPIA_BASE_URL = "https://www.horsepia.com/hp/pa/hh/{tab}/detail.do"
DEFAULT_TAB = "PAHH2040D01"  # 개체식별
DEFAULT_HRS_GB_CD = "00100"

_INIT_DATA_PATTERN = re.compile(
    r"var\s+initData\s*=\s*fnReplaceAll\(fnReplaceAll\('(.*?)',\s*\"&#034;\"",
    re.DOTALL,
)

DEFAULT_TIMEOUT = (5, 30)  # (연결, 읽기)
MAX_RETRIES = 3
RETRY_BASE_DELAY_SEC = 2
REQUEST_DELAY_RANGE = (0.5, 1.5)  # 요청 사이 랜덤 딜레이


class ScrapingError(Exception):
    """
    스크래핑 실패 시 발생하는 예외.
    main_page(ui 레이어)에서 이 예외만 잡아서 사용자에게 친절한 에러 메시지를 보여주면 된다.
    """


# 세션(프로세스) 내 캐시. NiceGUI 서버가 떠 있는 동안 유지되어
# 동일 말 재조회 시 불필요한 외부 호출을 줄인다. (아키텍처 프롬프트 5장 참고)
_cache: dict[str, dict] = {}


def get_horse_detail_for(horse: Horse, use_cache: bool = True, tab: str = DEFAULT_TAB) -> dict:
    """
    Horse 모델 인스턴스로 바로 조회하는 편의 함수. main_page에서는 이 함수를 쓴다.
        data = await run.io_bound(scraping_service.get_horse_detail_for, horse)
    horse.품종코드가 비어 있으면(등록 시 입력 누락) 명확한 에러로 안내한다 —
    hrsGbCd는 목장 "마종"과 무관한 horsepia 품종 구분코드이므로 추측해서 채우지 않는다.
    """
    if not horse.품종코드:
        raise ScrapingError(
            f"'{horse.마명}'에 품종코드가 등록되어 있지 않아 조회할 수 없습니다. "
            "관리 화면에서 품종코드를 먼저 입력해 주세요."
        )
    return get_horse_detail(horse.마번, use_cache=use_cache, tab=tab, hrs_gb_cd=horse.품종코드)


def get_horse_detail_auto(
    horse: Horse,
    repository,  # HorseRepository. 타입힌트는 순환import 방지를 위해 문자열로 두지 않고 느슨하게 둠.
    use_cache: bool = True,
    tab: str = DEFAULT_TAB,
) -> dict:
    """
    엑셀 업로드 시 품종코드(hrsGbCd)를 비워둔 말을 위한 자동탐지 조회.

    - horse.품종코드가 이미 있으면 그대로 조회한다 (get_horse_detail_for와 동일 동작).
    - 없으면 HORSE_BREED_CODES에 등록된 코드를 순서대로 시도해서, 실제로 그 말의
      데이터가 채워지는 코드를 찾는다. 찾으면:
        1) 그 코드로 조회한 결과를 반환하고
        2) repository.update_breed_code()로 DB에 저장해 다음부터는 바로 그 코드로 조회되게 한다.
    - 5개 코드 모두 시도해도 유효한 데이터를 못 찾으면 ScrapingError를 던진다.

    main_page 호출 예:
        data = await run.io_bound(scraping_service.get_horse_detail_auto, horse, repo)
    """
    if horse.품종코드:
        return get_horse_detail_for(horse, use_cache=use_cache, tab=tab)

    last_error: Optional[Exception] = None
    for code in HORSE_BREED_CODES:
        try:
            data = get_horse_detail(horse.마번, use_cache=use_cache, tab=tab, hrs_gb_cd=code)
        except ScrapingError as e:
            last_error = e
            continue

        if _looks_valid(data, horse.마번):
            if horse.id is not None:
                repository.update_breed_code(horse.id, code)
            horse.품종코드 = code
            return data

        last_error = ScrapingError(f"hrsGbCd={code}로 조회했지만 유효한 데이터가 없습니다.")

    raise ScrapingError(
        f"'{horse.마명}'(마번 {horse.마번})의 품종코드를 자동으로 찾지 못했습니다. "
        f"모든 코드({', '.join(HORSE_BREED_CODES)}) 시도 실패. 마지막 오류: {last_error}"
    )


def _looks_valid(data: dict, 마번: str) -> bool:
    """
    hrsGbCd 추측이 맞았는지 판별하는 휴리스틱.
    1순위: HrsChticInfo.hrno가 요청한 마번과 일치하면 확실히 맞는 코드로 간주한다.
    2순위(그 블록이 없는 페이지일 경우): 응답 안에 '-'/빈값이 아닌 필드가 하나라도
    있으면 데이터가 채워진 것으로 간주한다. (완전히 빈 응답 = 잘못된 코드로 추정)

    ⚠️ 실제 horsepia가 잘못된 hrsGbCd에 어떻게 응답하는지(빈 값 vs 에러 vs 다른 말 데이터)는
    아직 실네트워크로 확인하지 못했다. 실제 연동 시 표본 몇 건으로 이 휴리스틱이
    맞는지 검증 필요.
    """
    normalized = normalize_horse_number(마번)
    hrs_info = data.get("HrsChticInfo")
    if isinstance(hrs_info, dict) and hrs_info.get("hrno") == normalized:
        return True

    def _has_meaningful_value(obj) -> bool:
        if isinstance(obj, dict):
            return any(_has_meaningful_value(v) for v in obj.values())
        return obj not in (None, "-", "")

    return _has_meaningful_value(data)


def get_horse_detail(
    마번: str,
    use_cache: bool = True,
    tab: str = DEFAULT_TAB,
    hrs_gb_cd: str = DEFAULT_HRS_GB_CD,
) -> dict:
    """
    마번 하나에 대한 마적사항(dict)을 반환한다.

    main_page에서는 UI를 블로킹하지 않도록 다음과 같이 호출한다:
        data = await run.io_bound(scraping_service.get_horse_detail, horse.마번)
    (이 함수 자체는 동기 함수로 둔다 — run.io_bound가 스레드풀에서 실행해준다.)
    """
    normalized = normalize_horse_number(마번)
    if not normalized:
        raise ScrapingError("마번이 등록되어 있지 않아 마적사항을 조회할 수 없습니다.")

    cache_key = f"{tab}:{normalized}"
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    data = _fetch_with_retry(normalized, tab, hrs_gb_cd)
    _cache[cache_key] = data
    return data


def clear_cache(마번: Optional[str] = None) -> None:
    """캐시 초기화. 마번을 주면 해당 항목(모든 탭)만, 안 주면 전체를 지운다."""
    if 마번:
        normalized = normalize_horse_number(마번)
        for key in [k for k in _cache if k.endswith(f":{normalized}")]:
            del _cache[key]
    else:
        _cache.clear()


def _fetch_with_retry(마번: str, tab: str, hrs_gb_cd: str, max_retries: int = MAX_RETRIES) -> dict:
    """
    실패 시 지수 백오프로 재시도한다. 최종 실패하면 ScrapingError를 던진다.
    (initData가 아예 없는 경우, 즉 파싱 실패는 재시도해도 결과가 같으므로 즉시 실패 처리한다.)
    """
    url = HORSEPIA_BASE_URL.format(tab=tab)
    params = {"hrNo": 마번, "hrsGbCd": hrs_gb_cd, "eqsthrConvYn": "N"}
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            return _parse_init_data(response.text, 마번)

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(attempt * RETRY_BASE_DELAY_SEC)
                continue
        finally:
            time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

    raise ScrapingError(
        f"마번 {마번} 조회에 {max_retries}회 재시도 후에도 실패했습니다: {last_error}"
    )


def _parse_init_data(html: str, 마번: str) -> dict:
    """
    HTML 응답에서 initData 블록(들)을 추출해 하나의 dict로 병합해 반환한다.

    확인 결과, horsepia 상세 페이지는 섹션(개체이력 기본정보, 마체특징 등)마다
    `var initData = fnReplaceAll(...); gData = JSON.parse(initData);` 블록을
    반복해서 재선언하는 구조다. 그래서 첫 번째 매치만 잡으면 안 되고, 페이지 안의
    모든 initData 블록을 찾아 병합해야 gData.hrnmGrtDt 같은 최상위 필드와
    HrsChticInfo처럼 중첩된 필드를 모두 확보할 수 있다.
    각 블록은 HTML 엔티티로 인코딩된 JSON 문자열이 fnReplaceAll() 두 번을 거쳐
    복원되는 구조이므로, 동일한 치환(&#034;→", &#039;→')을 문자열 레벨에서 적용한다.
    """
    matches = list(_INIT_DATA_PATTERN.finditer(html))
    if not matches:
        raise ScrapingError(
            f"마번 {마번}: 응답에서 마적사항(initData)을 찾을 수 없습니다. "
            "등록번호가 잘못됐거나 horsepia 페이지 구조가 변경됐을 수 있습니다."
        )

    merged: dict = {}
    for m in matches:
        raw = m.group(1)
        decoded = raw.replace("&#034;", '"').replace("&#039;", "'")
        try:
            block = json.loads(decoded)
        except json.JSONDecodeError:
            # 일부 섹션 블록이 깨져 있어도 나머지 블록은 살리기 위해 건너뛴다.
            continue
        if isinstance(block, dict):
            merged.update(block)

    if not merged:
        raise ScrapingError(f"마번 {마번}: initData 블록을 찾았지만 모두 파싱에 실패했습니다.")

    return merged


# ---------------------------------------------------------------------------
# "개체이력 기본정보" 필드 매핑 (Jay님이 확인해준 실제 JS 렌더링 코드 기반).
#
# ⚠️ 미확정: 화면 캡처에는 있지만 아직 JS 코드를 확인 못한 필드가 있다.
#   경주마등록일, 통합전마번, 부마명, 경주마취소일, 통합전마명, 모마명, 이전마번
#   → 나머지 JS 코드(hrsInfo += ... 이어지는 부분)를 확인하는 대로 매핑 추가 필요.
#
# hrsGbCd 별 조건부 표시 필드 (JS의 if(sHrsGbCd == ...) 분기 그대로 반영):
#   00100 또는 00200일 때만: 마명부여일, 원마명, 기초등록일, 번식등록일,
#                             생산국, 수입국, 패스포트, 혈통서
#   00300일 때만: 퇴사일
#   공통: 출생일, 최종용도, 성별, 폐사일, 털색, 품종, 국제마번, 혈통등록일
# ---------------------------------------------------------------------------
_BASIC_INFO_FIELD_MAP: dict[str, str] = {
    "hrnmGrtDt": "마명부여일",
    "imphrEngHrnm": "원마명",
    "foalgDt": "출생일",
    "ppseNm": "최종용도",
    "gndrGbNm": "성별",
    "stallRsntDt": "퇴사일",
    "orcpyDt": "폐사일",
    "horseCtcolNm": "털색",
    "spcsNm": "품종",
    "ihrno": "국제마번",
    "fdtRegDt": "기초등록일",
    "bldlnRegDtrmDt": "혈통등록일",
    "bredgRegDt": "번식등록일",
    "pctyNm": "생산국",
    "iptCtryNm": "수입국",
    "ctfIsueDt": "패스포트",
    "studbook": "혈통서",
}

# hrsGbCd별 조건부 필드 (JS 분기 그대로). 이 안에 없는 필드는 hrsGbCd 무관하게 항상 표시.
_CONDITIONAL_FIELDS: dict[str, set[str]] = {
    "hrnmGrtDt": {"00100", "00200"},
    "imphrEngHrnm": {"00100", "00200"},
    "fdtRegDt": {"00100", "00200"},
    "bredgRegDt": {"00100", "00200"},
    "pctyNm": {"00100", "00200"},
    "iptCtryNm": {"00100", "00200"},
    "ctfIsueDt": {"00100", "00200"},
    "studbook": {"00100", "00200"},
    "stallRsntDt": {"00300"},
}


def extract_basic_info(gData: dict, hrs_gb_cd: str = DEFAULT_HRS_GB_CD) -> dict[str, str]:
    """
    get_horse_detail()로 얻은 원본 dict(gData)에서 "개체이력 기본정보"에 해당하는
    필드만 한글 라벨로 추출한다. hrsGbCd 조건에 안 맞는 필드는 결과에서 제외한다.
    값이 없으면 '-'로 채운다 (horsepia 표기 관행과 동일).
    """
    result: dict[str, str] = {}
    for key, label in _BASIC_INFO_FIELD_MAP.items():
        allowed_codes = _CONDITIONAL_FIELDS.get(key)
        if allowed_codes is not None and hrs_gb_cd not in allowed_codes:
            continue
        value = gData.get(key)
        result[label] = value if value not in (None, "") else "-"
    return result
# main_page의 온디맨드 단건 조회에는 필요 없고, 필요 시 별도 스크립트에서
# `from services.scraping_service import scrape_multiple, retry_failed` 로 가져다 쓴다.
# ---------------------------------------------------------------------------
import os
from datetime import datetime
from pathlib import Path

_FAILED_FILE = Path(__file__).resolve().parent.parent / "data" / "failed_horses.json"


def scrape_multiple(마번_list: list[str]) -> tuple[dict[str, dict], list[dict]]:
    """여러 마번을 순회 조회. 실패한 마번은 failed_horses.json에 기록한다."""
    results: dict[str, dict] = {}
    failed: list[dict] = []

    for 마번 in 마번_list:
        try:
            results[마번] = get_horse_detail(마번, use_cache=False)
            print(f"마번 {마번}: 수집 완료")
        except ScrapingError as e:
            print(f"마번 {마번}: 최종 실패 - {e}")
            failed.append({"마번": 마번, "error": str(e)})

    if failed:
        _FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"\n실패한 마번 {len(failed)}건 → {_FAILED_FILE} 저장 완료")

    return results, failed


def retry_failed() -> dict[str, dict]:
    """failed_horses.json에 기록된 마번만 재시도한다."""
    if not _FAILED_FILE.exists():
        print("실패 기록 파일이 없습니다. 재시도할 마번이 없습니다.")
        return {}

    with open(_FAILED_FILE, "r", encoding="utf-8") as f:
        failed_list = json.load(f)
    마번_list = [item["마번"] for item in failed_list]

    print(f"재시도 대상: {len(마번_list)}건")
    results: dict[str, dict] = {}
    still_failed: list[dict] = []

    for 마번 in 마번_list:
        try:
            results[마번] = get_horse_detail(마번, use_cache=False)
            print(f"마번 {마번}: 재시도 성공")
        except ScrapingError as e:
            print(f"마번 {마번}: 재시도 실패 - {e}")
            still_failed.append(
                {"마번": 마번, "error": str(e), "last_attempt": datetime.now().isoformat()}
            )

    if still_failed:
        with open(_FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(still_failed, f, ensure_ascii=False, indent=2)
        print(f"\n여전히 실패: {len(still_failed)}건 → {_FAILED_FILE} 갱신")
    else:
        if _FAILED_FILE.exists():
            os.remove(_FAILED_FILE)
        print("\n모든 마번 재수집 성공 → failed_horses.json 삭제")

    return results
