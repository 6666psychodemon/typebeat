-- TypeBeat catalog (beats). Matches producer_harvester_v2 + live radio queue columns.
-- Apply to local SQLite or sync to Turso via your migration workflow.

CREATE TABLE IF NOT EXISTS beats (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    artist_style TEXT,
    channel_name TEXT,
    url TEXT,
    views INTEGER,
    published_time TEXT,
    scraped_at TEXT,
    genre TEXT,
    parent_genre TEXT,
    is_free INTEGER,
    free_for_profit INTEGER DEFAULT 0,
    jev_genre TEXT,
    jev_genre_confidence REAL,
    is_single_beat REAL,
    commercial_use REAL,
    jev_model TEXT,
    jev_tagged_at TEXT,
    jev_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_beats_genre_views ON beats(genre, views);
CREATE INDEX IF NOT EXISTS idx_beats_views_vid ON beats(views, video_id);
CREATE INDEX IF NOT EXISTS idx_beats_parent_genre_views_vid
    ON beats(parent_genre, views, video_id)
    WHERE parent_genre IS NOT NULL;
