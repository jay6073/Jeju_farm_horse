"""
기존 auction_record에서 entrustment 4필드(최초/최종 상장일·결과)를 역산해 채운다.
엑셀 재이관 없이 DB에 이미 있는 경매기록만으로 UI 4컬럼을 채울 때 사용한다.

사용법:
  python scripts/backfill_entrustment_auction_fields.py          # dry-run (기본)
  python scripts/backfill_entrustment_auction_fields.py --apply  # 실제 반영
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from adapters.excel_adapter import build_entrustment_auction_fields_from_records
from db import repository
from repository.horse_repository import init_db


def main(apply: bool = False) -> None:
    init_db()
    horses = repository.list_horses()
    updated = 0
    skipped = 0

    for horse in horses:
        horse_id = horse["horse_id"]
        records = repository.list_auction_records(horse_id)
        fields = build_entrustment_auction_fields_from_records(records)

        already = {
            "first_listed_date": horse.get("first_listed_date"),
            "first_result": horse.get("first_result"),
            "final_listed_date": horse.get("final_listed_date"),
            "final_result": horse.get("final_result"),
        }
        if already == fields:
            skipped += 1
            continue

        print(f"  {horse_id}: {already} -> {fields}")
        if apply:
            repository.update_horse(horse_id, fields)
        updated += 1

    mode = "반영" if apply else "dry-run"
    print(f"\n[{mode}] 대상 {len(horses)}두 / 변경 {updated}두 / 동일 {skipped}두")
    if not apply and updated:
        print("실제 반영: python scripts/backfill_entrustment_auction_fields.py --apply")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="DB에 실제 UPDATE")
    args = parser.parse_args()
    main(apply=args.apply)
