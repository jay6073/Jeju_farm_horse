-- horses 테이블에 명단출력용 개체 프로필(출생일/성별/부·모) 캐시 컬럼 추가
-- 씨수말·교육마·관상마·기타마는 최초 1회 horsepia 조회 후 DB에 저장하고,
-- 이후 명단출력은 위수탁마와 같이 DB만 읽는다.
-- 실행 순서: 이 DDL을 Supabase에 적용(앱 init_db도 동일 ALTER를 수행) 후 코드 배포.

ALTER TABLE horses
    ADD COLUMN IF NOT EXISTS 출생일              DATE,
    ADD COLUMN IF NOT EXISTS 성별                TEXT,
    ADD COLUMN IF NOT EXISTS 부마명              TEXT,
    ADD COLUMN IF NOT EXISTS 모마명              TEXT,
    ADD COLUMN IF NOT EXISTS profile_scraped_at  TIMESTAMPTZ;
