-- 1. horses.마번에 UNIQUE 제약 추가 (FK 참조를 위해 필요)
ALTER TABLE horses ADD CONSTRAINT uq_horses_mabeon_constraint UNIQUE (마번);

-- 2. B(위탁/경매/성적) 테이블 생성
CREATE TABLE IF NOT EXISTS auction_record (
    id              SERIAL PRIMARY KEY,
    horse_id        TEXT NOT NULL,
    auction_date    DATE,
    auction_name    TEXT,
    hammer_price    INTEGER,
    buyer_name      TEXT,
    is_final        BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (horse_id) REFERENCES horses(마번) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS race_record (
    id              SERIAL PRIMARY KEY,
    horse_id        TEXT NOT NULL,
    race_date       DATE,
    race_name       TEXT,
    distance        INTEGER,
    grade           TEXT,
    horse_number    INTEGER,
    rank            TEXT,
    jockey          TEXT,
    record_time     TEXT,
    weight          TEXT,
    horse_weight    INTEGER,
    track_condition TEXT,
    FOREIGN KEY (horse_id) REFERENCES horses(마번) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS career_summary (
    horse_id            TEXT PRIMARY KEY,
    total_starts        INTEGER NOT NULL DEFAULT 0,
    total_wins          INTEGER NOT NULL DEFAULT 0,
    win_rate            REAL NOT NULL DEFAULT 0.0,
    total_prize_money   INTEGER NOT NULL DEFAULT 0,
    rating              TEXT,
    registered_name     TEXT,
    data_source         TEXT NOT NULL DEFAULT 'scraping',
    last_scraped_at     TIMESTAMP,
    FOREIGN KEY (horse_id) REFERENCES horses(마번) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auction_horse_id ON auction_record(horse_id);
CREATE INDEX IF NOT EXISTS idx_race_horse_id ON race_record(horse_id);