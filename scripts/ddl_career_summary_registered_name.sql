-- career_summary에 호스피아 등록 경주마명(RaceResult.hrNm) 저장 컬럼 추가
-- horses.마명(위탁·자마명)과 별개. 화면 표시는 이후 단계에서 붙인다.
-- 실행 순서: 이 DDL을 적용한 뒤 스크래퍼 코드를 배포한다. 기존 행은 재수집 전까지 NULL.

ALTER TABLE career_summary
    ADD COLUMN IF NOT EXISTS registered_name TEXT;
