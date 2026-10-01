-- IGNITE Medical Imaging Suite v5.0.0
-- SQLite Database Schema for GDPR/DSGVO Audit-Trail and Session Management

PRAGMA foreign_keys = ON;

-- Pseudonymized Patient Records
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY, -- Salted SHA-256 hash (e.g. ANON-e3b0c442)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Clinical Examination Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    examiner TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    study_type TEXT DEFAULT 'PODIATRIC_SCREENING'
);

-- Algorithmic Evaluations
CREATE TABLE IF NOT EXISTS evaluations (
    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    image_path TEXT NOT NULL,
    image_hash TEXT NOT NULL,
    analysis_mode TEXT NOT NULL, -- 'INFLAMMATION', 'VASCULAR', 'PERFUSION', 'BILATERAL'
    threshold_mode TEXT NOT NULL, -- 'MAD' or 'GAUSSIAN'
    k_factor REAL NOT NULL,
    hotspot_count INTEGER NOT NULL,
    max_delta_t REAL,
    highest_risk TEXT NOT NULL,
    execution_time_ms REAL NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Individual Hotspot Detections
CREATE TABLE IF NOT EXISTS hotspot_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_id INTEGER NOT NULL REFERENCES evaluations(eval_id) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    area_pixels INTEGER NOT NULL,
    circularity REAL NOT NULL,
    max_val INTEGER NOT NULL,
    mean_val REAL NOT NULL,
    risk_level TEXT NOT NULL,
    recommendation TEXT NOT NULL
);

-- Immutable Tamper-Evident Audit Log (GDPR / DSGVO Art. 30 Compliance)
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,      -- e.g. 'ANALYZE_IMAGE', 'EXPORT_REPORT', 'CHANGE_LUA_RULE'
    operator_id TEXT NOT NULL,
    details TEXT,
    tamper_checksum TEXT
);

-- Pre-populate demo indices
CREATE INDEX IF NOT EXISTS idx_evaluations_session ON evaluations(session_id);
CREATE INDEX IF NOT EXISTS idx_hotspots_eval ON hotspot_records(eval_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
