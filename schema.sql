PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS facilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pi_name TEXT NOT NULL,
    facility_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_id INTEGER NOT NULL,
    project_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    target_animals INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS lab_profiles (
    lab_id INTEGER PRIMARY KEY,
    size_tier TEXT NOT NULL,
    staff_count INTEGER NOT NULL,
    expected_cage_load INTEGER NOT NULL,
    active_project_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    facility_id INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS racks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    room_id INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS iacuc_protocols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    expires_on TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Technician', 'PI', 'Admin')),
    lab_id INTEGER,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cage_code TEXT NOT NULL UNIQUE,
    strain TEXT NOT NULL,
    genotype_summary TEXT NOT NULL,
    breeding_status TEXT NOT NULL,
    dob TEXT,
    male_count INTEGER NOT NULL DEFAULT 0,
    female_count INTEGER NOT NULL DEFAULT 0,
    room_id INTEGER NOT NULL,
    rack_id INTEGER NOT NULL,
    lab_id INTEGER NOT NULL,
    protocol_id INTEGER,
    qr_token TEXT NOT NULL UNIQUE,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(room_id) REFERENCES rooms(id),
    FOREIGN KEY(rack_id) REFERENCES racks(id),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(protocol_id) REFERENCES iacuc_protocols(id)
);

CREATE TABLE IF NOT EXISTS project_cages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    cage_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    UNIQUE(project_id, cage_id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS litters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cage_id INTEGER NOT NULL,
    birth_date TEXT NOT NULL,
    litter_size INTEGER NOT NULL,
    survived_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS animals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_code TEXT NOT NULL UNIQUE,
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F', 'U')),
    dob TEXT,
    strain TEXT NOT NULL,
    genotype TEXT,
    status TEXT NOT NULL,
    cage_id INTEGER,
    litter_id INTEGER,
    sire_id INTEGER,
    dam_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(litter_id) REFERENCES litters(id),
    FOREIGN KEY(sire_id) REFERENCES animals(id),
    FOREIGN KEY(dam_id) REFERENCES animals(id)
);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cage_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT,
    event_date TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS breeding_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cage_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    details_json TEXT,
    assigned_to INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(assigned_to) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS genotype_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER NOT NULL,
    result TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(animal_id) REFERENCES animals(id)
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_cages_code ON cages(cage_code);
CREATE INDEX IF NOT EXISTS idx_cages_qr ON cages(qr_token);
CREATE INDEX IF NOT EXISTS idx_cages_room ON cages(room_id);
CREATE INDEX IF NOT EXISTS idx_animals_cage ON animals(cage_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_breeding_date ON breeding_events(event_date);
CREATE INDEX IF NOT EXISTS idx_projects_lab ON projects(lab_id);
CREATE INDEX IF NOT EXISTS idx_project_cages_project ON project_cages(project_id);
CREATE INDEX IF NOT EXISTS idx_project_cages_cage ON project_cages(cage_id);
