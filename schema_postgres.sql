/*
 * Copyright 2026 Murisphere Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

-- Generated from schema.sql by generate_postgres_schema.py

CREATE TABLE IF NOT EXISTS facilities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    pi_name TEXT NOT NULL,
    facility_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    facility_id INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS racks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    room_id INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS iacuc_protocols (
    id SERIAL PRIMARY KEY,
    protocol_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    expires_on TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cages (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    cage_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    UNIQUE(project_id, cage_id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS project_genotype_targets (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    genotype_pattern TEXT NOT NULL,
    target_count INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, genotype_pattern),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS genotype_target_templates (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS genotype_target_template_rules (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL,
    genotype_pattern TEXT NOT NULL,
    target_count INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    UNIQUE(template_id, genotype_pattern),
    FOREIGN KEY(template_id) REFERENCES genotype_target_templates(id)
);

CREATE TABLE IF NOT EXISTS litters (
    id SERIAL PRIMARY KEY,
    cage_id INTEGER NOT NULL,
    birth_date TEXT NOT NULL,
    litter_size INTEGER NOT NULL,
    survived_count INTEGER NOT NULL,
    weaned_on TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS animals (
    id SERIAL PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS project_animal_assignments (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    animal_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'reserved',
    notes TEXT,
    assigned_at TEXT NOT NULL,
    assigned_by INTEGER,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(assigned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS project_animal_assignment_events (
    id SERIAL PRIMARY KEY,
    assignment_id INTEGER,
    project_id INTEGER NOT NULL,
    animal_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    notes TEXT,
    actor_user_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(assignment_id) REFERENCES project_animal_assignments(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS project_cohort_closeouts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'partial', 'cancelled')),
    outcome_code TEXT NOT NULL DEFAULT 'other',
    completed_animals INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    notes TEXT,
    closed_by INTEGER,
    closed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(closed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    animal_id INTEGER NOT NULL,
    result TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(animal_id) REFERENCES animals(id)
);

CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    lab_id INTEGER,
    room_id INTEGER,
    line_type TEXT NOT NULL CHECK (line_type IN ('per_diem', 'service')),
    rate DOUBLE PRECISION NOT NULL,
    service_name TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS billing_periods (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    cage_id INTEGER,
    line_type TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    rate DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(period_start, period_end, lab_id, cage_id, line_type, description),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id)
);

CREATE TABLE IF NOT EXISTS facility_requests (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS billing_reviews (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    qualification_code TEXT NOT NULL,
    granted_on TEXT NOT NULL,
    expires_on TEXT,
    UNIQUE(user_id, qualification_code),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS task_assignments (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    signer_user_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    signature_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(signer_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS health_rounds (
    id SERIAL PRIMARY KEY,
    room_id INTEGER,
    performed_by INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed')),
    notes TEXT,
    FOREIGN KEY(room_id) REFERENCES rooms(id),
    FOREIGN KEY(performed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS health_observations (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    cage_id INTEGER NOT NULL,
    finding TEXT NOT NULL,
    severity TEXT,
    action_taken TEXT,
    observed_at TEXT NOT NULL,
    observed_by INTEGER NOT NULL,
    FOREIGN KEY(round_id) REFERENCES health_rounds(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(observed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS protocol_deviations (
    id SERIAL PRIMARY KEY,
    protocol_id INTEGER NOT NULL,
    cage_id INTEGER,
    reported_by INTEGER NOT NULL,
    reported_at TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    capa_plan TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'under_review', 'closed')),
    resolved_at TEXT,
    resolved_by INTEGER,
    FOREIGN KEY(protocol_id) REFERENCES iacuc_protocols(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(reported_by) REFERENCES users(id),
    FOREIGN KEY(resolved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS euthanasia_records (
    id SERIAL PRIMARY KEY,
    animal_id INTEGER,
    cage_id INTEGER,
    protocol_id INTEGER,
    method TEXT NOT NULL,
    reason TEXT,
    disposition TEXT,
    performed_by INTEGER NOT NULL,
    performed_at TEXT NOT NULL,
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(protocol_id) REFERENCES iacuc_protocols(id),
    FOREIGN KEY(performed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cage_wash_events (
    id SERIAL PRIMARY KEY,
    cage_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'in_wash', 'returned')),
    requested_by INTEGER NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(requested_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quarantine_intakes (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER NOT NULL,
    project_id INTEGER,
    cage_id INTEGER,
    vendor TEXT,
    strain TEXT,
    sex TEXT,
    quantity INTEGER NOT NULL,
    arrival_date TEXT NOT NULL,
    quarantine_end_on TEXT,
    status TEXT NOT NULL CHECK (status IN ('planned', 'arrived', 'in_quarantine', 'cleared', 'blocked')),
    notes TEXT,
    created_by INTEGER NOT NULL,
    reviewed_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(created_by) REFERENCES users(id),
    FOREIGN KEY(reviewed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mortality_records (
    id SERIAL PRIMARY KEY,
    animal_id INTEGER,
    cage_id INTEGER NOT NULL,
    protocol_id INTEGER,
    count_male INTEGER NOT NULL DEFAULT 0,
    count_female INTEGER NOT NULL DEFAULT 0,
    cause TEXT,
    found_at TEXT NOT NULL,
    reported_by INTEGER NOT NULL,
    necropsy_required INTEGER NOT NULL DEFAULT 0,
    necropsy_status TEXT NOT NULL CHECK (necropsy_status IN ('not_required', 'pending', 'completed')),
    notes TEXT,
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(protocol_id) REFERENCES iacuc_protocols(id),
    FOREIGN KEY(reported_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS alert_notifications (
    id SERIAL PRIMARY KEY,
    alert_key TEXT NOT NULL UNIQUE,
    lab_id INTEGER,
    cage_id INTEGER,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'acknowledged', 'resolved')),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    acked_by INTEGER,
    acked_at TEXT,
    escalation_level INTEGER NOT NULL DEFAULT 0,
    last_notified_at TEXT,
    next_notify_at TEXT,
    meta_json TEXT,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(acked_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notification_channels (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    lab_id INTEGER,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('in_app', 'webhook', 'email')),
    target TEXT,
    min_severity TEXT NOT NULL CHECK (min_severity IN ('low', 'medium', 'high')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lab_id) REFERENCES labs(id)
);

CREATE TABLE IF NOT EXISTS notification_dispatch_log (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    dispatched_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'simulated')),
    response_summary TEXT,
    FOREIGN KEY(alert_id) REFERENCES alert_notifications(id),
    FOREIGN KEY(channel_id) REFERENCES notification_channels(id)
);

CREATE TABLE IF NOT EXISTS breeding_pairs (
    id SERIAL PRIMARY KEY,
    sire_id INTEGER NOT NULL,
    dam_id INTEGER NOT NULL,
    cage_id INTEGER NOT NULL,
    lab_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'retired')),
    started_on TEXT NOT NULL,
    ended_on TEXT,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(sire_id) REFERENCES animals(id),
    FOREIGN KEY(dam_id) REFERENCES animals(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS animal_tags (
    id SERIAL PRIMARY KEY,
    animal_id INTEGER NOT NULL,
    tag_type TEXT NOT NULL CHECK (tag_type IN ('ear_tag', 'microchip', 'tube', 'well', 'custom')),
    tag_value TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    applied_on TEXT NOT NULL,
    applied_by INTEGER,
    UNIQUE(tag_type, tag_value),
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(applied_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sample_records (
    id SERIAL PRIMARY KEY,
    animal_id INTEGER NOT NULL,
    cage_id INTEGER,
    sample_type TEXT NOT NULL,
    sample_code TEXT NOT NULL UNIQUE,
    provider TEXT,
    status TEXT NOT NULL CHECK (status IN ('collected', 'shipped', 'received', 'resulted', 'rejected')),
    tracking_number TEXT,
    collected_on TEXT NOT NULL,
    collected_by INTEGER,
    notes TEXT,
    FOREIGN KEY(animal_id) REFERENCES animals(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(collected_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sample_events (
    id SERIAL PRIMARY KEY,
    sample_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    actor_user_id INTEGER,
    details_json TEXT,
    FOREIGN KEY(sample_id) REFERENCES sample_records(id),
    FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS genotyping_orders (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER NOT NULL,
    project_id INTEGER,
    provider TEXT NOT NULL,
    order_ref TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('draft', 'submitted', 'received', 'closed', 'failed')),
    requested_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(requested_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS genotyping_order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    sample_id INTEGER,
    animal_id INTEGER NOT NULL,
    marker_panel TEXT,
    result TEXT,
    result_at TEXT,
    FOREIGN KEY(order_id) REFERENCES genotyping_orders(id),
    FOREIGN KEY(sample_id) REFERENCES sample_records(id),
    FOREIGN KEY(animal_id) REFERENCES animals(id)
);

CREATE TABLE IF NOT EXISTS workflow_recommendations (
    id SERIAL PRIMARY KEY,
    rec_type TEXT NOT NULL,
    lab_id INTEGER NOT NULL,
    project_id INTEGER,
    cage_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('open', 'accepted', 'adjusted', 'ignored', 'completed')),
    rationale TEXT,
    payload_json TEXT,
    created_by INTEGER,
    acted_by INTEGER,
    acted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(cage_id) REFERENCES cages(id),
    FOREIGN KEY(created_by) REFERENCES users(id),
    FOREIGN KEY(acted_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS planner_scenarios (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    needed_by TEXT,
    target_animals INTEGER NOT NULL,
    max_new_cages INTEGER,
    assumptions_json TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'archived')),
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(lab_id) REFERENCES labs(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS planner_scenario_projects (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    animals_needed INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3,
    UNIQUE(scenario_id, project_id),
    FOREIGN KEY(scenario_id) REFERENCES planner_scenarios(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS planner_plans (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    estimated_litters INTEGER NOT NULL,
    estimated_cages INTEGER NOT NULL,
    projected_deficit INTEGER NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    recommendation_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(scenario_id) REFERENCES planner_scenarios(id)
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
CREATE INDEX IF NOT EXISTS idx_project_genotype_targets_project ON project_genotype_targets(project_id);
CREATE INDEX IF NOT EXISTS idx_genotype_target_templates_lab ON genotype_target_templates(lab_id);
CREATE INDEX IF NOT EXISTS idx_genotype_target_template_rules_template ON genotype_target_template_rules(template_id);
CREATE INDEX IF NOT EXISTS idx_project_animal_assignments_project ON project_animal_assignments(project_id);
CREATE INDEX IF NOT EXISTS idx_project_animal_assignments_status ON project_animal_assignments(status);
CREATE INDEX IF NOT EXISTS idx_project_assignment_events_project ON project_animal_assignment_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_project_assignment_events_animal ON project_animal_assignment_events(animal_id);
CREATE INDEX IF NOT EXISTS idx_project_closeouts_project ON project_cohort_closeouts(project_id, closed_at);
CREATE INDEX IF NOT EXISTS idx_billing_entries_period ON billing_entries(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_facility_requests_lab ON facility_requests(lab_id);
CREATE INDEX IF NOT EXISTS idx_census_scan_session ON cage_census_scans(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_lab ON animal_orders(lab_id, status);
CREATE INDEX IF NOT EXISTS idx_vet_cases_lab ON vet_cases(lab_id, case_status);
CREATE INDEX IF NOT EXISTS idx_task_due ON task_assignments(due_on, status);
CREATE INDEX IF NOT EXISTS idx_attach_entity ON record_attachments(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_health_round_status ON health_rounds(status, started_at);
CREATE INDEX IF NOT EXISTS idx_protocol_dev_status ON protocol_deviations(status, reported_at);
CREATE INDEX IF NOT EXISTS idx_euthanasia_time ON euthanasia_records(performed_at);
CREATE INDEX IF NOT EXISTS idx_quarantine_status ON quarantine_intakes(status, arrival_date);
CREATE INDEX IF NOT EXISTS idx_mortality_found_at ON mortality_records(found_at);
CREATE INDEX IF NOT EXISTS idx_alert_status ON alert_notifications(status, severity, next_notify_at);
CREATE INDEX IF NOT EXISTS idx_alert_cage ON alert_notifications(cage_id, status);
CREATE INDEX IF NOT EXISTS idx_pair_lab_status ON breeding_pairs(lab_id, status);
CREATE INDEX IF NOT EXISTS idx_sample_status ON sample_records(status, collected_on);
CREATE INDEX IF NOT EXISTS idx_geno_order_status ON genotyping_orders(lab_id, status);
CREATE INDEX IF NOT EXISTS idx_recommendation_status ON workflow_recommendations(lab_id, status);
CREATE INDEX IF NOT EXISTS idx_planner_lab ON planner_scenarios(lab_id, status);
