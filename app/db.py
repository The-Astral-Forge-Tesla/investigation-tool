import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

-- =========================
-- Documents (one row per file/page)
-- =========================
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    page INTEGER NOT NULL DEFAULT 1,
    content TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_documents_page ON documents(page);

-- =========================
-- FTS5: keyword search
-- =========================
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
USING fts5(
  content,
  content='documents',
  content_rowid='id',
  tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, content) VALUES ('delete', old.id, old.content);
  INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
END;

-- =========================
-- Entities (spaCy + regex)
-- =========================
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    label TEXT NOT NULL,
    normalized TEXT NOT NULL,
    UNIQUE(normalized, label)
);

CREATE INDEX IF NOT EXISTS idx_entities_label ON entities(label);
CREATE INDEX IF NOT EXISTS idx_entities_text ON entities(text);
CREATE INDEX IF NOT EXISTS idx_entities_norm ON entities(normalized);

CREATE TABLE IF NOT EXISTS doc_entities (
    doc_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(doc_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_entities_doc ON doc_entities(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_entities_entity ON doc_entities(entity_id);

-- =========================
-- Assets (e.g., aircraft reg, IMO, hull ids)
-- =========================
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    asset_type TEXT NOT NULL,     -- e.g., AIRCRAFT_REG, IMO, TAIL, OTHER
    asset_value TEXT NOT NULL,    -- raw
    normalized TEXT NOT NULL,
    UNIQUE(asset_type, normalized)
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_norm ON assets(normalized);

CREATE TABLE IF NOT EXISTS doc_assets (
    doc_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    UNIQUE(doc_id, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_assets_doc ON doc_assets(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_assets_asset ON doc_assets(asset_id);

-- =========================
-- Events (lightweight: derived from DATE + LOCATION within doc/page)
-- =========================
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    event_key TEXT NOT NULL,      -- stable hashable key (date_norm|loc_norm|filename|page)
    date_text TEXT,
    date_norm TEXT,
    location_text TEXT,
    location_norm TEXT,
    filename TEXT NOT NULL,
    page INTEGER NOT NULL,
    UNIQUE(event_key)
);

CREATE INDEX IF NOT EXISTS idx_events_date_norm ON events(date_norm);
CREATE INDEX IF NOT EXISTS idx_events_loc_norm ON events(location_norm);

CREATE TABLE IF NOT EXISTS event_entities (
    event_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(event_id, entity_id)
);

CREATE TABLE IF NOT EXISTS event_assets (
    event_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    UNIQUE(event_id, asset_id)
);

-- =========================
-- Registry records (offline-first)
-- =========================
CREATE TABLE IF NOT EXISTS registry_records (
    id INTEGER PRIMARY KEY,
    registry_name TEXT NOT NULL,          -- e.g., AIRCRAFT_REGISTRY_UK
    record_type TEXT NOT NULL,            -- e.g., AIRCRAFT, COMPANY, OFFICER
    subject_type TEXT NOT NULL,           -- ENTITY or ASSET
    subject_norm TEXT NOT NULL,           -- normalized entity or asset value
    field_key TEXT NOT NULL,              -- e.g., OWNER, ADDRESS, OFFICER
    field_value TEXT NOT NULL,
    statement_type TEXT NOT NULL,         -- FACT (registry data)
    confidence REAL NOT NULL DEFAULT 1.0,
    primary_source TEXT NOT NULL,         -- file path / dataset name
    secondary_source TEXT,                -- optional citation url (stored as text)
    UNIQUE(registry_name, record_type, subject_type, subject_norm, field_key, field_value)
);

CREATE INDEX IF NOT EXISTS idx_registry_subject ON registry_records(subject_type, subject_norm);
"""

def init_db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    conn.close()

def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
