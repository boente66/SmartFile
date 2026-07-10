CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    original_name TEXT,
    path TEXT NOT NULL,
    file_type TEXT,
    extension TEXT,
    size INTEGER,
    category TEXT,
    tags TEXT,
    favorite INTEGER DEFAULT 0,
    checksum TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_accessed_at TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    action TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);
