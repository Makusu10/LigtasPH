import sqlite3
from pathlib import Path
from flask import g, current_app

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS administrators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login TEXT,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TEXT
);
CREATE INDEX IF NOT EXISTS idx_admin_username ON administrators(username);

CREATE TABLE IF NOT EXISTS evacuation_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    barangay TEXT,
    city TEXT NOT NULL,
    municipality TEXT,
    province TEXT,
    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng REAL NOT NULL CHECK (lng BETWEEN -180 AND 180),
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    current_occupancy INTEGER NOT NULL DEFAULT 0 CHECK (current_occupancy >= 0),
    food_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (food_status IN ('Unknown','Low','Adequate','High')),
    water_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (water_status IN ('Unknown','Low','Adequate','High')),
    medicine_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (medicine_status IN ('Unknown','Low','Adequate','High')),
    hygiene_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (hygiene_status IN ('Unknown','Low','Adequate','High')),
    basic_needs_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (basic_needs_status IN ('Unknown','Low','Adequate','High')),
    operational_status TEXT NOT NULL DEFAULT 'Open' CHECK (operational_status IN ('Open','Closed','Temporarily Unavailable')),
    contact_number TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
    UNIQUE(name, address)
);
CREATE INDEX IF NOT EXISTS idx_center_city ON evacuation_centers(city);
CREATE INDEX IF NOT EXISTS idx_center_archived ON evacuation_centers(archived);
CREATE INDEX IF NOT EXISTS idx_center_updated ON evacuation_centers(updated_at);

CREATE TABLE IF NOT EXISTS center_status_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_id INTEGER NOT NULL REFERENCES evacuation_centers(id) ON DELETE CASCADE,
    prev_occupancy INTEGER,
    new_occupancy INTEGER,
    food_status TEXT,
    water_status TEXT,
    medicine_status TEXT,
    hygiene_status TEXT,
    basic_needs_status TEXT,
    notes TEXT,
    admin_id INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_status_center ON center_status_updates(center_id);

CREATE TABLE IF NOT EXISTS emergency_hotlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agency TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('National','DRRMO','Police','Fire','Medical','Rescue','Hospital','Utility')),
    contact_number TEXT NOT NULL,
    city TEXT NOT NULL,
    address_area TEXT,
    verification_note TEXT,
    last_verified TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_hotline_city ON emergency_hotlines(city);
CREATE INDEX IF NOT EXISTS idx_hotline_category ON emergency_hotlines(category);

CREATE TABLE IF NOT EXISTS weather_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT,
    lat REAL,
    lng REAL,
    source TEXT CHECK (source IN ('cached','openweather','open-meteo','noaa','air-quality','open-meteo-air','openweather-air')) DEFAULT 'cached',
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_weather_city ON weather_cache(city);
CREATE INDEX IF NOT EXISTS idx_weather_latlng ON weather_cache(lat, lng);
CREATE INDEX IF NOT EXISTS idx_weather_source ON weather_cache(source);

CREATE TABLE IF NOT EXISTS emergency_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invite_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT 'Group',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_group_invite ON emergency_groups(invite_code);

CREATE TABLE IF NOT EXISTS live_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES emergency_groups(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng REAL NOT NULL CHECK (lng BETWEEN -180 AND 180),
    accuracy REAL CHECK (accuracy IS NULL OR accuracy >= 0),
    shared_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_group ON live_locations(group_id);
CREATE INDEX IF NOT EXISTS idx_live_expires ON live_locations(expires_at);

CREATE TABLE IF NOT EXISTS hazards_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_hazards_key ON hazards_cache(cache_key);

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'all' CHECK (scope IN ('all','city','radius')),
    city TEXT,
    center_lat REAL CHECK (center_lat IS NULL OR (center_lat BETWEEN -90 AND 90)),
    center_lng REAL CHECK (center_lng IS NULL OR (center_lng BETWEEN -180 AND 180)),
    radius_km REAL CHECK (radius_km IS NULL OR radius_km > 0),
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warning','critical')),
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_by INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (datetime(starts_at) < datetime(ends_at))
);
CREATE INDEX IF NOT EXISTS idx_ann_active_time ON announcements(is_active, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS idx_ann_scope ON announcements(scope);
"""

def get_db():
    db_path = current_app.config["DATABASE"]
    # handle :memory: for tests — use shared file to persist across requests
    if db_path == ":memory:":
        db_path = "file:memdb_sprint1?mode=memory&cache=shared"
        if not hasattr(current_app, "_memory_db"):
            conn = sqlite3.connect(db_path, uri=True, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            current_app._memory_db = conn
        # also store in g for close handling (but don't close shared)
        if "db" not in g:
            g.db = current_app._memory_db
        return g.db
    if "db" not in g:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        g.db = conn
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is None:
        return
    # don't close shared memory db (TestingConfig)
    if hasattr(current_app, "_memory_db") and db is current_app._memory_db:
        return
    try:
        db.close()
    except Exception:
        pass

def _migrate_weather_cache(db):
    try:
        row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='weather_cache'").fetchone()
        if row and row["sql"] and "open-meteo-air" not in row["sql"]:
            db.executescript("""
                ALTER TABLE weather_cache RENAME TO weather_cache_old;
                CREATE TABLE weather_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT,
                    lat REAL,
                    lng REAL,
                    source TEXT CHECK (source IN ('cached','openweather','open-meteo','noaa','air-quality','open-meteo-air','openweather-air')) DEFAULT 'cached',
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_weather_city ON weather_cache(city);
                CREATE INDEX IF NOT EXISTS idx_weather_latlng ON weather_cache(lat, lng);
                CREATE INDEX IF NOT EXISTS idx_weather_source ON weather_cache(source);
                INSERT INTO weather_cache (id, city, lat, lng, source, payload, fetched_at)
                SELECT id, city, lat, lng, source, payload, fetched_at FROM weather_cache_old;
                DROP TABLE weather_cache_old;
            """)
            db.commit()
    except Exception:
        pass

def init_db():
    db = get_db()
    _migrate_weather_cache(db)
    db.executescript(SCHEMA)
    db.commit()
