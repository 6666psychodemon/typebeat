-- TypeBeat Radio auth store (separate from catalog). Applied by radio/auth_db.init_db().

CREATE TABLE IF NOT EXISTS invite_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'invited', 'denied')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invite_requests_email ON invite_requests(email);
CREATE INDEX IF NOT EXISTS idx_invite_requests_status ON invite_requests(status);

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'redeemed')),
    request_id INTEGER REFERENCES invite_requests(id),
    created_at TEXT NOT NULL,
    redeemed_at TEXT,
    redeemed_by_user_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_invites_status ON invites(status);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name TEXT,
    picture TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    video_id TEXT NOT NULL,
    genre TEXT,
    reaction TEXT NOT NULL CHECK (reaction IN ('like', 'dislike')),
    created_at TEXT NOT NULL,
    UNIQUE (user_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id, created_at);
