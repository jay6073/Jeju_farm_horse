"""
엑셀 업로드 파싱/검증/일괄 등록 서비스 (아키텍처 프롬프트 4-2절 "엑셀 일괄 업로드").

- 필수 컬럼(마명/마종/등록번호) 누락 시 즉시 명확한 에러로 업로드 자체를 중단한다
  (조용히 None 처리하지 않는다).
- 행 단위 오류(마종 오타 등)는 전체를 막지 않고, 미리보기에서 그 행만 "등록 제외"로 표시한다.
- 중복(마명 또는 마번이 이미 존재)도 미리보기 단계에서 표시하고, 기본은 건너뛴다.
- 실제 등록은 미리보기 확인 후 별도 commit_rows() 호출로만 이뤄진다(오등록 방지).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from models.horse import HORSE_SPECIES, Horse, normalize_horse_number

REQUIRED_COLS = ["마명", "마종", "등록번호"]
OPTIONAL_COLS = ["품종코드"]


class ImportValidationError(Exception):
    """엑셀 컬럼 누락 등, 업로드 자체를 중단시켜야 하는 오류."""


@dataclass
class ImportRow:
    """미리보기 화면에 한 줄로 표시될 행 하나."""

    row_no: int  # 엑셀상 몇 번째 행인지 (헤더=1행, 데이터는 2행부터)
    마명: str
    마종: str
    마번: Optional[str]
    품종코드: Optional[str]
    is_duplicate: bool
    error: Optional[str] = None  # 있으면 등록 대상에서 제외 (미리보기에서 사유 표시)

    @property
    def will_register(self) -> bool:
        return self.error is None and not self.is_duplicate


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def parse_excel(file_bytes: bytes, repository) -> list[ImportRow]:
    """
    엑셀 바이트를 읽어 검증하고 미리보기용 ImportRow 리스트를 반환한다.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        raise ImportValidationError(f"엑셀 파일을 읽을 수 없습니다: {e}") from e

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ImportValidationError(
            f"필수 컬럼이 없습니다: {', '.join(missing)}. "
            f"엑셀에 {', '.join(REQUIRED_COLS)} 컬럼이 모두 있어야 합니다."
        )

    # -------------------------------------------------------------
    # ⚡ [속도 개선 핵심] 1. DB에서 기존 마명/마번 세트를 '단 1번'만 일괄 조회
    # (repository에 해당 메서드가 없다면 아래 💡 팁 참고)
    # -------------------------------------------------------------
    existing_pairs = repository.get_all_existing_마명_and_마번() 
    # 반환 형식 예시: {("닉스고", "0031234"), ("한센", "0025678"), ...} 집합(Set)

    rows: list[ImportRow] = []
    for i, record in enumerate(df.to_dict(orient="records")):
        row_no = i + 2  # 헤더가 1행이므로 데이터는 2행부터 시작
        마명 = _clean(record.get("마명")) or ""
        마종 = _clean(record.get("마종")) or ""
        raw_마번 = _clean(record.get("등록번호"))
        품종코드 = _clean(record.get("품종코드")) if "품종코드" in df.columns else None

        # Horse 모델과 동일하게 미리 마번(등록번호)을 7자리 정규화
        마번 = normalize_horse_number(raw_마번)

        error: Optional[str] = None
        if not 마명:
            error = "마명이 비어 있습니다."
        elif 마종 not in HORSE_SPECIES:
            error = f"유효하지 않은 마종입니다: {마종!r} (허용값: {', '.join(HORSE_SPECIES)})"
        elif 품종코드 is not None and not (품종코드.isdigit() and len(품종코드) == 5):
            error = f"품종코드 형식이 올바르지 않습니다: {품종코드!r} (5자리 숫자)"

        is_dup = False
        if error is None:
            # ⚡ [속도 개선 핵심] 2. DB 접속 없이 메모리 상의 Set에서 0.0001초만에 바로 체크!
            is_dup = repository.is_duplicate_in_memory(마명, 마번, existing_pairs)

        rows.append(
            ImportRow(
                row_no=row_no,
                마명=마명,
                마종=마종,
                마번=마번,
                품종코드=품종코드,
                is_duplicate=is_dup,
                error=error,
            )
        )
    return rows


def commit_rows(rows: list[ImportRow], repository) -> int:
    """
    미리보기에서 확정된 rows를 실제로 등록한다.
    error가 있거나 중복인 행은 제외한다. 등록된 건수를 반환한다.
    """
    horses = [
        Horse(마명=r.마명, 마종=r.마종, 마번=r.마번, 품종코드=r.품종코드)
        for r in rows
        if r.will_register
    ]
    if not horses:
        return 0
    return repository.insert_many(horses)