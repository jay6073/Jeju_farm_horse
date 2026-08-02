-- entrustment 테이블에 경매 4필드 추가 (마번당 1건, 엑셀 최초/최종 슬롯 저장)
-- 실행 순서: 이 DDL을 가장 먼저 적용한 뒤 애플리케이션 코드를 배포한다.

ALTER TABLE entrustment
    ADD COLUMN IF NOT EXISTS first_listed_date  DATE,
    ADD COLUMN IF NOT EXISTS first_result       TEXT,
    ADD COLUMN IF NOT EXISTS final_listed_date  DATE,
    ADD COLUMN IF NOT EXISTS final_result       TEXT;
