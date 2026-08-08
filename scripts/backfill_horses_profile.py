"""
일반 마종(씨수말·교육마·관상마·기타마)의 출생일·성별·부·모를
horsepia에서 한 번 조회해 horses 테이블에 캐시한다.

사용:
  python scripts/backfill_horses_profile.py
  python scripts/backfill_horses_profile.py --species 씨수말
  python scripts/backfill_horses_profile.py --dry-run

이미 profile_scraped_at이 있는 말은 건너뛴다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from models.horse import HORSE_SPECIES, STATUS_NORMAL
from repository.horse_repository import HorseRepository
from services.print_service import (
    SPECIES_ENTRUSTMENT,
    _cache_profile_from_basic_info,
    _fetch_basic_info,
)
from services.scraping_service import ScrapingError


def main() -> int:
    parser = argparse.ArgumentParser(description="horses 프로필 캐시 백필")
    parser.add_argument(
        "--species",
        choices=[s for s in HORSE_SPECIES if s != SPECIES_ENTRUSTMENT],
        help="특정 마종만 (미지정 시 위수탁마 제외 전체)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="조회·저장 없이 대상 건수만 출력",
    )
    args = parser.parse_args()

    repo = HorseRepository()
    targets = []
    species_list = [args.species] if args.species else [
        s for s in HORSE_SPECIES if s != SPECIES_ENTRUSTMENT
    ]

    for species in species_list:
        for horse in repo.get_active_names_by_species(species):
            if horse.has_cached_profile:
                continue
            if not horse.마번:
                continue
            targets.append(horse)

    print(f"대상 {len(targets)}두 (상태={STATUS_NORMAL}, 캐시 없음)")
    if args.dry_run:
        for h in targets:
            print(f"  - [{h.마종}] {h.마명} ({h.마번})")
        return 0

    ok = 0
    failed = 0
    for i, horse in enumerate(targets, start=1):
        try:
            basic_info = _fetch_basic_info(horse, repo)
            _cache_profile_from_basic_info(horse, basic_info, repo)
            ok += 1
            print(f"[{i}/{len(targets)}] OK  {horse.마명} ({horse.마번})")
        except ScrapingError as e:
            failed += 1
            print(f"[{i}/{len(targets)}] FAIL {horse.마명} ({horse.마번}): {e}")

    print(f"\n완료: 성공 {ok} / 실패 {failed} / 대상 {len(targets)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
