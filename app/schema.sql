CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_path TEXT NOT NULL,
    distance REAL,
    duration REAL,
    pace REAL,
    run_at TEXT,
    note TEXT,
    calories INTEGER,
    incline REAL,
    exif_date_missing INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
