"""
프로젝트 전역에서 사용하는 상수 정의.
[지침 변경 포인트] 위탁/경매/경주 관련 상태값이나 정책 상수가 바뀌면 이 파일만 수정한다.
"""

from pathlib import Path

# ── DB 경로 ────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "horse_management.db"

# ── Horse.status 값 ────────────────────────────────────
STATUS_ENTRUSTED = "위탁중"
STATUS_ENDED = "위탁종료"

HORSE_STATUS_OPTIONS = [STATUS_ENTRUSTED, STATUS_ENDED]

# ── 성별 옵션 ───────────────────────────────────────────
SEX_OPTIONS = ["수", "암", "거세"]

# ── 마번 형식 ───────────────────────────────────────────
# 마번은 7자리 숫자 문자열이며 선행 0이 있을 수 있음 (예: "0022651")
HORSE_ID_LENGTH = 7

# ── 인력현황 / 보유마 관리파트 ──────────────────────────
# 인력현황(staff)의 수행업무파트 전체 목록. 단일 출처(single source of truth)로 두고
# staff_repository.py와 horses(보유마) 관리파트 쪽이 여기서 함께 가져다 쓴다.
DUTY_PARTS = ["지원파트", "씨수말파트", "전기육성파트", "교육파트"]
# 보유마 관리파트 선택지 (지원파트 제외 — 말을 직접 관리하지 않는 파트)
HORSE_DUTY_PARTS = [p for p in DUTY_PARTS if p != "지원파트"]