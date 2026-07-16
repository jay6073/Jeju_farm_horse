"""
1단계(데이터 계층) 동작 검증용 임시 스크립트.
실제 DB(data/horses.db)를 건드리지 않도록 임시 파일을 사용한다.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.horse import Horse, normalize_horse_number, HORSE_SPECIES, HORSE_BREED_CODES
from repository.horse_repository import HorseRepository


def check(label, condition):
    status = "OK " if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "test_horses.db"
        repo = HorseRepository(db_path)

        # --- 마번 정규화 ---
        check("zfill(7) 정규화: '12345' -> '0012345'", normalize_horse_number("12345") == "0012345")
        check("zfill(7) 정규화: 엑셀 float 형태 '12345.0' -> '0012345'", normalize_horse_number("12345.0") == "0012345")
        check("빈 값은 None 유지", normalize_horse_number("") is None)
        check("None은 None 유지", normalize_horse_number(None) is None)

        # --- Horse 모델 검증 ---
        h1 = Horse(마명="천리마", 마종="씨수말", 마번="12345", 품종코드="00100")
        check("Horse 생성 시 마번 자동 정규화", h1.마번 == "0012345")
        check("기본 상태는 정상", h1.상태 == "정상")
        check("정상 상태는 is_active True", h1.is_active is True)
        check("품종코드가 그대로 저장됨", h1.품종코드 == "00100")

        h_no_breed = Horse(마명="품종미상", 마종="기타마")
        check("품종코드는 선택 입력 — 생략 시 None", h_no_breed.품종코드 is None)

        try:
            Horse(마명="이상한품종", 마종="씨수말", 품종코드="9")  # 5자리 아님
            check("형식이 틀린 품종코드는 예외 발생해야 함", False)
        except ValueError:
            check("형식이 틀린 품종코드는 ValueError 발생", True)

        h_unknown_breed = Horse(마명="새품종말", 마종="씨수말", 품종코드="00999")
        check("HORSE_BREED_CODES에 없어도 형식만 맞으면 저장 허용됨 (방법 1)", h_unknown_breed.품종코드 == "00999")

        try:
            Horse(마명="이상한말", 마종="없는마종")
            check("잘못된 마종은 예외 발생해야 함", False)
        except ValueError:
            check("잘못된 마종은 ValueError 발생", True)

        try:
            Horse(마명="폐사말", 마종="씨수말", 상태="폐사")  # 상태발생일자 누락
            check("상태발생일자 없는 비정상 상태는 예외 발생해야 함", False)
        except ValueError:
            check("상태발생일자 누락 시 ValueError 발생", True)

        # --- Repository insert / 조회 ---
        h2 = Horse(마명="번개", 마종="위수탁마", 마번="22310", 품종코드="00100")
        h3 = Horse(마명="질풍", 마종="위수탁마", 품종코드="00300")
        h4 = Horse(마명="은하수", 마종="교육마")

        id1 = repo.insert(h1)
        id2 = repo.insert(h2)
        id3 = repo.insert(h3)
        id4 = repo.insert(h4)
        check("insert 후 id가 정수로 반환됨", all(isinstance(i, int) for i in [id1, id2, id3, id4]))

        fetched = repo.get_by_id(id2)
        check("get_by_id로 조회한 마번이 정규화된 값과 일치", fetched.마번 == "0022310")
        check("get_by_id로 조회한 품종코드가 보존됨", fetched.품종코드 == "00100")

        active_wsg = repo.get_active_names_by_species("위수탁마")
        check("위수탁마 오늘기준 조회 결과 2두", len(active_wsg) == 2)

        # --- 보유상태 변경 (다중) ---
        updated = repo.update_status_bulk([id2], "위수탁종료", "2026-06-10")
        check("update_status_bulk 반영 건수 1", updated == 1)

        active_wsg_after = repo.get_active_names_by_species("위수탁마")
        check("위수탁종료 처리 후 위수탁마 오늘기준 1두로 감소", len(active_wsg_after) == 1)
        check("남은 위수탁마는 질풍", active_wsg_after[0].마명 == "질풍")

        all_wsg = repo.get_all_by_species("위수탁마")
        check("상태 무관 전체 조회는 여전히 2두", len(all_wsg) == 2)

        # --- 대시보드 집계 ---
        counts = repo.count_active_by_species()
        check("모든 마종이 counts 딕셔너리에 포함됨", set(counts.keys()) == set(HORSE_SPECIES))
        check("씨수말 1두", counts["씨수말"] == 1)
        check("위수탁마 1두(위수탁종료 처리 반영됨)", counts["위수탁마"] == 1)
        check("교육마 1두", counts["교육마"] == 1)
        check("관상마 0두", counts["관상마"] == 0)
        total = sum(counts.values())
        check("합계 3두", total == 3)

        # --- 중복 체크 ---
        check("동일 마명 중복 감지", repo.exists_by_마명_or_마번("천리마", None) is True)
        check("동일 마번 중복 감지", repo.exists_by_마명_or_마번("다른이름", "0012345") is True)
        check("중복 없는 신규 데이터는 False", repo.exists_by_마명_or_마번("새말", "9999999") is False)

        # --- insert_many (엑셀 일괄 등록 시뮬레이션) ---
        batch = [
            Horse(마명="관상왕", 마종="관상마"),
            Horse(마명="기타A", 마종="기타마"),
        ]
        inserted = repo.insert_many(batch)
        check("insert_many 2건 삽입", inserted == 2)
        counts_after_batch = repo.count_active_by_species()
        check("일괄 등록 후 관상마 1두", counts_after_batch["관상마"] == 1)
        check("일괄 등록 후 합계 5두", sum(counts_after_batch.values()) == 5)

        print("\n모든 검증 통과 ✅")


if __name__ == "__main__":
    main()
