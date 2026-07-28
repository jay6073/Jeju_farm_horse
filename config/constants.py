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