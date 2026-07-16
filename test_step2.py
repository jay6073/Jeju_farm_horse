"""
2단계(스크래핑 서비스) 검증용 테스트.
실제 horsepia.com 네트워크 호출 없이, requests.get을 mock으로 대체해
- initData 파싱 로직
- 재시도(retry) 로직
- 캐싱 로직
- 예외 처리
가 의도대로 동작하는지 확인한다.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from services import scraping_service as svc


def check(label, condition):
    status = "OK " if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def make_response(text="", status_ok=True):
    resp = MagicMock()
    resp.text = text
    if status_ok:
        resp.raise_for_status = MagicMock()
    else:
        resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError("500"))
    return resp


# 실제 horsepia.com 응답 구조 재현: HTML 엔티티로 인코딩된 JSON이
# fnReplaceAll() 두 번을 거쳐 JSON.parse되는 형태 (Jay님이 확인해준 실제 소스 기반)
SAMPLE_HTML_OK = (
    "<html><script>\n"
    "\tvar initData = fnReplaceAll(fnReplaceAll('"
    '{&#034;마명&#034;:&#034;천리마&#034;,&#034;마번&#034;:&#034;0012345&#034;,'
    '&#034;경주성적&#034;:[{&#034;일자&#034;:&#034;2026-04-11&#034;,&#034;순위&#034;:2}]}'
    "', \"&#034;\", \"\\\"\"), \"&#039;\", \"'\");\n"
    "\tgData = JSON.parse(initData);\n"
    "</script></html>"
)

SAMPLE_HTML_NO_INITDATA = "<html><body>데이터 없음</body></html>"


def main():
    svc.clear_cache()

    # --- 파싱 성공 ---
    with patch("services.scraping_service.requests.get", return_value=make_response(SAMPLE_HTML_OK)):
        data = svc.get_horse_detail("12345", use_cache=False)
        check("initData 파싱 성공: 마명 필드 확인", data["마명"] == "천리마")
        check("initData 파싱 성공: 경주성적 리스트 확인", data["경주성적"][0]["순위"] == 2)

    # --- initData 없는 경우 ScrapingError ---
    with patch("services.scraping_service.requests.get", return_value=make_response(SAMPLE_HTML_NO_INITDATA)):
        try:
            svc.get_horse_detail("99999", use_cache=False)
            check("initData 없으면 ScrapingError 발생해야 함", False)
        except svc.ScrapingError:
            check("initData 없을 때 ScrapingError 정상 발생", True)

    # --- 마번 없는 경우 즉시 실패 (네트워크 호출 없이) ---
    with patch("services.scraping_service.requests.get") as mock_get:
        try:
            svc.get_horse_detail("", use_cache=False)
            check("마번 없으면 ScrapingError 발생해야 함", False)
        except svc.ScrapingError:
            check("마번 없을 때 ScrapingError 정상 발생", True)
        check("마번 없을 땐 네트워크 호출 자체를 안 함", mock_get.call_count == 0)

    # --- 재시도 로직: 처음 2번 실패 후 3번째 성공 ---
    call_count = {"n": 0}

    def flaky_get(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise requests.exceptions.ConnectionError("일시적 네트워크 오류")
        return make_response(SAMPLE_HTML_OK)

    with patch("services.scraping_service.requests.get", side_effect=flaky_get), \
         patch("services.scraping_service.time.sleep"):  # 테스트 속도를 위해 대기시간 스킵
        data = svc.get_horse_detail("55555", use_cache=False)
        check("재시도 끝에 성공적으로 데이터 획득", data["마명"] == "천리마")
        check("정확히 3번 시도함 (2번 실패 + 1번 성공)", call_count["n"] == 3)

    # --- 재시도 모두 실패 시 ScrapingError ---
    with patch("services.scraping_service.requests.get",
               side_effect=requests.exceptions.ConnectionError("계속 실패")), \
         patch("services.scraping_service.time.sleep"):
        try:
            svc.get_horse_detail("66666", use_cache=False)
            check("모든 재시도 실패 시 ScrapingError 발생해야 함", False)
        except svc.ScrapingError:
            check("모든 재시도 실패 후 ScrapingError 정상 발생", True)

    # --- 캐싱 동작 ---
    svc.clear_cache()
    call_log = []

    def counting_get(*args, **kwargs):
        call_log.append(1)
        return make_response(SAMPLE_HTML_OK)

    with patch("services.scraping_service.requests.get", side_effect=counting_get):
        svc.get_horse_detail("77777", use_cache=True)
        svc.get_horse_detail("77777", use_cache=True)  # 캐시로 인해 네트워크 호출 없어야 함
        check("동일 마번 재조회 시 캐시로 1회만 호출됨", len(call_log) == 1)

        svc.get_horse_detail("77777", use_cache=False)  # 캐시 무시하고 강제 재호출
        check("use_cache=False면 캐시 무시하고 다시 호출됨", len(call_log) == 2)

    svc.clear_cache("0077777")
    with patch("services.scraping_service.requests.get", side_effect=counting_get):
        svc.get_horse_detail("77777", use_cache=True)
        check("캐시 초기화 후 다시 호출됨", len(call_log) == 3)

    # --- 마번 정규화가 캐시 키에도 적용되는지 ---
    svc.clear_cache()
    with patch("services.scraping_service.requests.get", side_effect=counting_get):
        before = len(call_log)
        svc.get_horse_detail("88888", use_cache=True)
        svc.get_horse_detail("0088888", use_cache=True)  # 정규화하면 동일한 키
        check("정규화 전/후 마번이 같은 캐시 항목으로 취급됨", len(call_log) == before + 1)

    # --- 여러 개의 initData 블록이 있는 페이지 (마체특징 + 개체이력 기본정보) ---
    svc.clear_cache()
    MULTI_BLOCK_HTML = (
        "<html><script>\n"
        "\tvar initData = fnReplaceAll(fnReplaceAll('"
        '{&#034;JejuHrsInfo&#034;:null,&#034;HrsChticInfo&#034;:{&#034;hrno&#034;:&#034;0041819&#034;}}'
        "', \"&#034;\", \"\\\"\"), \"&#039;\", \"'\");\n"
        "\tgData = JSON.parse(initData);\n"
        "</script>\n"
        "<script>\n"
        "\tvar initData = fnReplaceAll(fnReplaceAll('"
        '{&#034;hrnmGrtDt&#034;:&#034;2019-01-26&#034;,&#034;foalgDt&#034;:&#034;2016-01-29&#034;,'
        '&#034;ppseNm&#034;:&#034;번식용&#034;,&#034;gndrGbNm&#034;:&#034;수&#034;,'
        '&#034;horseCtcolNm&#034;:&#034;회색&#034;,&#034;spcsNm&#034;:&#034;더러브렛&#034;}'
        "', \"&#034;\", \"\\\"\"), \"&#039;\", \"'\");\n"
        "\tgData = JSON.parse(initData);\n"
        "</script></html>"
    )
    with patch("services.scraping_service.requests.get", return_value=make_response(MULTI_BLOCK_HTML)):
        merged = svc.get_horse_detail("41819", use_cache=False)
        check("여러 initData 블록이 하나로 병합됨 (마체특징 쪽 필드)", merged["HrsChticInfo"]["hrno"] == "0041819")
        check("여러 initData 블록이 하나로 병합됨 (기본정보 쪽 필드)", merged["hrnmGrtDt"] == "2019-01-26")

        basic = svc.extract_basic_info(merged, hrs_gb_cd="00300")  # 씨수말(추정) 조건
        check("hrsGbCd=00300일 때 마명부여일은 제외됨(00100/00200 전용 필드)", "마명부여일" not in basic)
        check("hrsGbCd 무관 공통 필드 출생일은 포함됨", basic["출생일"] == "2016-01-29")
        check("값 없는 필드는 '-'로 채워짐", basic["퇴사일"] == "-")

        basic_100 = svc.extract_basic_info(merged, hrs_gb_cd="00100")
        check("hrsGbCd=00100일 때 마명부여일 포함됨", basic_100["마명부여일"] == "2019-01-26")
        check("hrsGbCd=00100일 때는 퇴사일 필드 자체가 없음", "퇴사일" not in basic_100)

    print("\n모든 검증 통과 ✅ (단, 실제 URL/응답 구조는 HORSEPIA_DETAIL_URL 교체 후 별도 실네트워크 확인 필요)")


def test_auto_detect():
    """
    B안(엑셀 품종코드 비워도 됨) 검증: 품종코드 없는 말을 조회하면
    여러 코드를 순서대로 시도해 맞는 코드를 찾고, DB에 자동 저장되는지 확인한다.
    """
    import tempfile
    from repository.horse_repository import HorseRepository
    from models.horse import Horse

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "test_auto.db"
        repo = HorseRepository(db_path)

        horse = Horse(마명="자동탐지말", 마종="위수탁마", 마번="99999")  # 품종코드 없음
        horse.id = repo.insert(horse)

        EMPTY_HTML = (
            "<html><script>\n"
            "\tvar initData = fnReplaceAll(fnReplaceAll('{&#034;HrsChticInfo&#034;:{&#034;hrno&#034;:&#034;-&#034;}}"
            "', \"&#034;\", \"\\\"\"), \"&#039;\", \"'\");\n"
            "\tgData = JSON.parse(initData);\n"
            "</script></html>"
        )
        MATCHING_HTML = (
            "<html><script>\n"
            "\tvar initData = fnReplaceAll(fnReplaceAll('"
            '{&#034;HrsChticInfo&#034;:{&#034;hrno&#034;:&#034;0099999&#034;},&#034;spcsNm&#034;:&#034;제주마&#034;}'
            "', \"&#034;\", \"\\\"\"), \"&#039;\", \"'\");\n"
            "\tgData = JSON.parse(initData);\n"
            "</script></html>"
        )

        # 00100, 00200, 00210은 빈 데이터, 00300에서 진짜 데이터가 나온다고 가정
        def fake_get(url, params=None, timeout=None):
            code = params["hrsGbCd"]
            html = MATCHING_HTML if code == "00300" else EMPTY_HTML
            return make_response(html)

        call_order = []

        def tracking_get(url, params=None, timeout=None):
            call_order.append(params["hrsGbCd"])
            return fake_get(url, params, timeout)

        with patch("services.scraping_service.requests.get", side_effect=tracking_get):
            data = svc.get_horse_detail_auto(horse, repo, use_cache=False)
            check("자동탐지: 올바른 코드(00300)에서 데이터 획득", data["spcsNm"] == "제주마")
            check("자동탐지: 알려진 코드 순서대로(00100→00200→00210→00300) 시도함",
                  call_order == ["00100", "00200", "00210", "00300"])
            check("자동탐지: horse 객체의 품종코드가 갱신됨", horse.품종코드 == "00300")

        fetched = repo.get_by_id(horse.id)
        check("자동탐지: DB에도 품종코드가 저장됨", fetched.품종코드 == "00300")

        # 두 번째 조회부터는 이미 품종코드가 있으니 바로 그 코드로만 요청해야 함
        call_order.clear()
        with patch("services.scraping_service.requests.get", side_effect=tracking_get):
            svc.get_horse_detail_auto(horse, repo, use_cache=False)
            check("품종코드 확보 후 재조회 시 추측 없이 바로 1회만 요청", call_order == ["00300"])

        # 모든 코드가 실패하는 경우
        horse2 = Horse(마명="미확인말", 마종="기타마", 마번="88888")
        horse2.id = repo.insert(horse2)
        with patch("services.scraping_service.requests.get", return_value=make_response(EMPTY_HTML)):
            try:
                svc.get_horse_detail_auto(horse2, repo, use_cache=False)
                check("모든 코드 실패 시 ScrapingError 발생해야 함", False)
            except svc.ScrapingError:
                check("모든 코드 실패 시 ScrapingError 정상 발생", True)
        fetched2 = repo.get_by_id(horse2.id)
        check("모든 코드 실패 시 DB 품종코드는 그대로 None", fetched2.품종코드 is None)

    print("\n자동탐지 검증 통과 ✅")


if __name__ == "__main__":
    main()
    test_auto_detect()
