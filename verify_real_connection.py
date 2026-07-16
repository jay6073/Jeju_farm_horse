"""
horsepia.com 실제 연동 확인용 스크립트 (Jeju-farm_horse 프로젝트).

전체 보유마를 다 돌리기 전에, 이미 정보를 알고 있는 말 몇 마리만 골라
실제로 데이터가 잘 내려오는지 눈으로 확인하는 용도.

실행 위치: Jeju-farm_horse 폴더 안에서
    python verify_real_connection.py

⚠️ 이 스크립트는 실제로 horsepia.com에 네트워크 요청을 보낸다.
   Claude 샌드박스 환경은 외부 네트워크가 제한돼 있어 여기서는 실행할 수 없고,
   Jay님 로컬 컴퓨터(또는 실제 네트워크가 열린 서버)에서 돌려야 한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services import scraping_service as svc
from services.scraping_service import ScrapingError
from models.horse import breed_label


# ---------------------------------------------------------------------------
# 여기에 실제로 존재한다고 확인된 말 2~3마리를 적어둔다.
# 품종코드(hrsGbCd)를 아는 경우 넣고, 모르면 None으로 두면 자동탐지로 시도한다.
# ---------------------------------------------------------------------------
SAMPLE_HORSES = [
    {"마명": "닉스고", "마번": "0041819", "품종코드": "00100"},
    {"마명": "산방미인 자마", "마번": "0060446", "품종코드": "00100"},
]


def try_known_code(마명: str, 마번: str, 품종코드: str) -> None:
    print(f"\n[{마명} / 마번 {마번} / 품종코드 {품종코드}({breed_label(품종코드)})]")
    try:
        data = svc.get_horse_detail(마번, use_cache=False, hrs_gb_cd=품종코드)
    except ScrapingError as e:
        print(f"  ❌ 실패: {e}")
        return

    print("  ✅ 응답 수신 성공. 최상위 키:", list(data.keys()))
    basic = svc.extract_basic_info(data, hrs_gb_cd=품종코드)
    print("  개체이력 기본정보:")
    for label, value in basic.items():
        print(f"    - {label}: {value}")


def try_auto_detect(마명: str, 마번: str) -> None:
    print(f"\n[{마명} / 마번 {마번} / 품종코드 미상 → 자동탐지 시도]")
    from models.horse import Horse
    horse = Horse(마명=마명, 마종="기타마", 마번=마번)  # 마종은 임시값, 조회엔 영향 없음

    from repository.horse_repository import HorseRepository
    repo = HorseRepository(Path(__file__).resolve().parent / "data" / "verify_test.db")
    horse.id = repo.insert(horse)

    try:
        data = svc.get_horse_detail_auto(horse, repo, use_cache=False)
    except ScrapingError as e:
        print(f"  ❌ 자동탐지 실패: {e}")
        return

    print(f"  ✅ 자동탐지 성공! 찾아낸 품종코드: {horse.품종코드} ({breed_label(horse.품종코드)})")
    basic = svc.extract_basic_info(data, hrs_gb_cd=horse.품종코드)
    print("  개체이력 기본정보:")
    for label, value in basic.items():
        print(f"    - {label}: {value}")


def main() -> None:
    print("=" * 60)
    print("horsepia.com 실제 연동 확인 시작")
    print("=" * 60)

    for h in SAMPLE_HORSES:
        if h["품종코드"]:
            try_known_code(h["마명"], h["마번"], h["품종코드"])
        else:
            try_auto_detect(h["마명"], h["마번"])

    print("\n" + "=" * 60)
    print("확인 끝. 위에 ✅가 정상적으로 뜨고 실제 정보(출생일/성별/품종 등)가")
    print("맞게 나오면 전체 배치 스크래핑으로 넘어가도 됩니다.")
    print("=" * 60)


if __name__ == "__main__":
    main()