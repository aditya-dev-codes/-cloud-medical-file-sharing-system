-- SQLite Database Schema for Cloud File Sharing with AI-Powered Emergency Medical Profile

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Patient Medical Profile Table
CREATE TABLE IF NOT EXISTS medical_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    full_name TEXT,
    date_of_birth TEXT,
    blood_group TEXT,
    allergies TEXT,
    current_medications TEXT,
    existing_conditions TEXT,
    previous_surgeries TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Uploaded Medical Reports Metadata
CREATE TABLE IF NOT EXISTS medical_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    emergency_access_allowed INTEGER DEFAULT 1,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- AI Generated Medical Summaries
CREATE TABLE IF NOT EXISTS ai_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL UNIQUE,
    summary_text TEXT NOT NULL,
    extracted_conditions TEXT,
    extracted_allergies TEXT,
    extracted_medications TEXT,
    is_mock INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES medical_reports (id) ON DELETE CASCADE
);

-- Temporary Emergency Access Tokens (Secured with SHA-256 Hashes)
CREATE TABLE IF NOT EXISTS emergency_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    token_prefix TEXT NOT NULL,
    label TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Emergency Access Audit Logging
CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_id INTEGER,
    token_identifier TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    resource_type TEXT DEFAULT 'PROFILE',
    resource_id INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    report_id INTEGER,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (token_id) REFERENCES emergency_tokens (id) ON DELETE SET NULL,
    FOREIGN KEY (report_id) REFERENCES medical_reports (id) ON DELETE SET NULL
);

