"""
Phase 0: 엑셀 이관 오케스트레이션.
excel_adapter(순수 파싱)의 결과를 받아 검증 후 repository에 저장한다.
규칙: ui -> services(이 파일) -> repository 순서만 호출한다.

[통합 시 변경사항]
- 기존에는 이 파일이 "말 자체"(Horse)를 생성/덮어쓰기(upsert_horse)까지 담당했으나,
  통합 후 "말 개체"는 A의 horses 테이블이 유일한 출처가 되므로 이 로직을 제거.
- 대신 엑셀의 마번이 A의 horses에 실제로 존재하는지 확인(a_horse_exists)한 뒤,
  존재하는 말에 대해서만 위탁 계약(entrustment)과 경매기록만 저장하도록 축소.
- 존재하지 않는 마번은 스킵 처리하고 skip_details에 "A에 먼저 등록 필요"로 남긴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from adapters import excel_adapter
from db import repository
from models.schemas import Horse
from services.entrustment_service import _ENTRUSTMENT_FIELDS
from pydantic import ValidationError
from models.horse import Horse as AHorse
from repository.horse_repository import HorseRepository

_a_horse_repo = HorseRepository()

@dataclass
class ImportResult:
    total_rows: int = 0
    success_count: int = 0
    skipped_count: int = 0
    overwritten_count: int = 0
    skip_details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_horse_ids: list[str] = field(default_factory=list)


def preview_excel(file) -> tuple[pd.DataFrame, list[str]]:
    """
    업로드된 엑셀을 미리보기용으로 파싱만 하고 저장은 하지 않는다.
    반환: (미리보기 DataFrame, 컬럼 누락 경고 리스트)
    """
    df = excel_adapter.read_excel_sheet(file)
    missing_cols = excel_adapter.validate_columns(df)
    return df, missing_cols


def import_horses_from_excel(file, overwrite_existing: bool = False) -> ImportResult:
    """
    실제 이관 실행. overwrite_existing=False이면 이미 존재하는 마번은 스킵하고 경고에 남긴다.
    [통합 시 변경] 말 자체 생성 대신, A에 이미 등록된 마번에 대해서만 위탁 계약+경매기록을 저장.
    """
    df = excel_adapter.read_excel_sheet(file)

    missing_cols = excel_adapter.validate_columns(df)
    if missing_cols:
        raise ValueError(
            f"엑셀에 필수 컬럼이 없습니다: {', '.join(missing_cols)}. "
            "원본 시트 구조가 변경되었는지 확인하세요."
        )

    parsed_rows = excel_adapter.parse_rows(df)

    result = ImportResult(total_rows=len(parsed_rows))

    for parsed in parsed_rows:
        if parsed.skip_reason:
            result.skipped_count += 1
            result.skip_details.append(f"{parsed.row_number}행: {parsed.skip_reason}")
            continue

        result.warnings.extend(parsed.warnings)

        horse_dict = parsed.horse
        horse_id = horse_dict["horse_id"]

        try:
            horse_model = Horse(**horse_dict)
        except ValidationError as e:
            messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            result.skipped_count += 1
            result.skip_details.append(
                f"{parsed.row_number}행 (마번 {horse_id}): 검증 오류 - {'; '.join(messages)}"
            )
            continue

        # [A/B 정합성 수정] A에 마번이 없으면, 엑셀의 마명으로 위수탁마를 새로 생성한다
        # (개별 등록의 register_horse()와 동일한 정책).
        a_horse = _a_horse_repo.get_by_마번(horse_id)
        if a_horse is None:
            _a_horse_repo.insert(AHorse(
                마번=horse_id,
                마명=horse_model.name,
                마종="위수탁마",
            ))

        already_exists = repository.horse_exists(horse_id)
        if already_exists and not overwrite_existing:
            result.skipped_count += 1
            result.skip_details.append(
                f"{parsed.row_number}행 (마번 {horse_id}): 이미 위탁 계약이 존재함 (덮어쓰기 미선택으로 스킵)"
            )
            continue

        db_dict = _horse_model_to_entrustment_dict(horse_model)
        repository.upsert_horse(db_dict)

        # 재이관 시 중복 방지를 위해 기존 경매 기록을 지우고 새로 넣는다 (idempotent).
        existing_auctions = repository.list_auction_records(horse_id)
        for a in existing_auctions:
            repository.delete_auction_record(a["id"])

        for auction in parsed.auctions:
            auction_to_save = {
                k: v for k, v in auction.items() if not k.startswith("_")
            }
            auction_to_save["horse_id"] = horse_id
            # [통합 시 변경] PostgreSQL 네이티브 date/boolean 타입 사용, isoformat/int 변환 제거
            repository.insert_auction_record(auction_to_save)

        if already_exists:
            result.overwritten_count += 1
        else:
            result.success_count += 1
        result.created_horse_ids.append(horse_id)

    return result


def _horse_model_to_entrustment_dict(horse: Horse) -> dict[str, Any]:
    """
    [통합 시 변경] entrustment 테이블 컬럼만 추려서 반환.
    entrustment_service._ENTRUSTMENT_FIELDS를 그대로 재사용.
    """
    full = horse.model_dump()
    return {k: v for k, v in full.items() if k in _ENTRUSTMENT_FIELDS}