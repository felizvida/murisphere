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

CREATE TABLE IF NOT EXISTS billing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_id INTEGER,
    room_id INTEGER,
    line_type TEXT NOT NULL CHECK (line_type IN ('per_diem', 'service')),
    rate REAL NOT NULL,
    service_name TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS billing_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    closed_by INTEGER,
    closed_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(period_start, period_end),
    FOREIGN KEY(closed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS billing_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    cage_id INTEGER,
    line_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    rate REAL NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(period_start, period_end, lab_id, cage_id, line_type, description),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS facility_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    project_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('submitted', 'approved', 'fulfilled', 'rejected')),
    details_json TEXT,
    requested_by INTEGER,
    reviewed_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(requested_by) REFERENCES users(id),
    FOREIGN KEY(reviewed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    target_url TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    payload_json TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cage_census_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER,
    started_by INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed')),
    notes TEXT,
    FOREIGN KEY(room_id) REFERENCES rooms(id),
    FOREIGN KEY(started_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cage_census_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    cage_id INTEGER NOT NULL,
    scanned_at TEXT NOT NULL,
    scanned_by INTEGER NOT NULL,
    observed_male_count INTEGER,
    observed_female_count INTEGER,
    observed_status TEXT,
    UNIQUE(session_id, cage_id),
    FOREIGN KEY(session_id) REFERENCES cage_census_sessions(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(scanned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS animal_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_id INTEGER NOT NULL,
    project_id INTEGER,
    vendor TEXT,
    strain TEXT,
    sex TEXT,
    quantity INTEGER NOT NULL,
    requested_date TEXT NOT NULL,
    needed_by TEXT,
    status TEXT NOT NULL CHECK (status IN ('submitted', 'approved', 'ordered', 'received', 'cancelled')),
    received_quantity INTEGER DEFAULT 0,
    created_by INTEGER NOT NULL,
    reviewed_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(created_by) REFERENCES users(id),
    FOREIGN KEY(reviewed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS protocol_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    details_json TEXT,
    effective_on TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(protocol_id, version_number),
    FOREIGN KEY(protocol_id) REFERENCES iacuc_protocols(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS billing_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS billing_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('draft', 'approved', 'rejected')),
    note TEXT,
    reviewed_by INTEGER NOT NULL,
    reviewed_at TEXT NOT NULL,
    UNIQUE(period_start, period_end, lab_id),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(reviewed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vet_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cage_id INTEGER,
    animal_id INTEGER,
    lab_id INTEGER NOT NULL,
    case_status TEXT NOT NULL CHECK (case_status IN ('open', 'closed')),
    severity TEXT,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    opened_by INTEGER,
    notes TEXT,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(opened_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vet_treatments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    treatment_name TEXT NOT NULL,
    schedule_rule TEXT,
    next_due_on TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'cancelled')),
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES vet_cases(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS staff_qualifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    qualification_code TEXT NOT NULL,
    granted_on TEXT NOT NULL,
    expires_on TEXT,
    UNIQUE(user_id, qualification_code),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS task_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    cage_id INTEGER,
    due_on TEXT NOT NULL,
    assigned_to INTEGER,
    required_qualification TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'done', 'blocked')),
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(assigned_to) REFERENCES users(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS record_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT,
    uploaded_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(uploaded_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS e_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signer_user_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    signature_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(signer_user_id) REFERENCES users(id)
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
CREATE INDEX IF NOT EXISTS idx_billing_entries_period ON billing_entries(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_facility_requests_lab ON facility_requests(lab_id);
CREATE INDEX IF NOT EXISTS idx_census_scan_session ON cage_census_scans(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_lab ON animal_orders(lab_id, status);
CREATE INDEX IF NOT EXISTS idx_vet_cases_lab ON vet_cases(lab_id, case_status);
CREATE INDEX IF NOT EXISTS idx_task_due ON task_assignments(due_on, status);
CREATE INDEX IF NOT EXISTS idx_attach_entity ON record_attachments(entity_type, entity_id);
