-- entrustment 테이블에 부마/성별/출생일 추가
-- (엑셀 일괄 이관 시 파싱은 되지만 저장되지 않던 속성을 DB에 남기기 위함)
-- 실행 순서: 이 DDL을 Supabase에 적용한 뒤, 저장 필드/조회·내보내기 코드를 배포한다.

ALTER TABLE entrustment
    ADD COLUMN IF NOT EXISTS sire_name   TEXT,
    ADD COLUMN IF NOT EXISTS sex         TEXT,
    ADD COLUMN IF NOT EXISTS birth_date  DATE;
