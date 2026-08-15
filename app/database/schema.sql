CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    slug TEXT NOT NULL UNIQUE,
    icon TEXT,
    color TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    template_code TEXT NOT NULL DEFAULT 'EMPTY',
    profile_code TEXT NOT NULL DEFAULT 'EMPTY',
    storage_plan_code TEXT NOT NULL DEFAULT 'PERSONAL_10GB',
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED'))
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    parent_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    color TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED')),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (parent_id) REFERENCES folders(id),
    UNIQUE (organization_id, parent_id, name)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS cloud_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL CHECK (provider IN ('ONEDRIVE', 'GOOGLE_DRIVE')),
    email TEXT,
    display_name TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    token_ref TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    phone TEXT,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_superuser INTEGER NOT NULL DEFAULT 0 CHECK (is_superuser IN (0, 1)),
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
    ,avatar_path TEXT
    ,avatar_initials TEXT
    ,avatar_color TEXT
    ,must_change_password INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_activity_at TEXT,
    revoked_at TEXT,
    device_name TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS password_recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code_lookup TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('OWNER', 'ADMIN', 'EDITOR', 'VIEWER')),
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    invited_by_user_id INTEGER,
    joined_at TEXT,
    deactivated_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    organization_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS organization_transport_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('NAS','HTTPS','LAN')),
    endpoint TEXT NOT NULL,
    credential_ref TEXT,
    verify_tls INTEGER NOT NULL DEFAULT 1 CHECK (verify_tls IN (0,1)),
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RETIRED')),
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS organization_transport_settings (
    organization_id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'LOCAL' CHECK (mode IN ('LOCAL','NAS','HTTPS','LAN')),
    endpoint TEXT,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    verify_tls INTEGER NOT NULL DEFAULT 1 CHECK (verify_tls IN (0,1)),
    credential_ref TEXT,
    current_target_id INTEGER,
    updated_by_user_id INTEGER,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id),
    FOREIGN KEY (current_target_id) REFERENCES organization_transport_targets(id)
);

CREATE TABLE IF NOT EXISTS organization_feature_settings (
    organization_id INTEGER NOT NULL,
    feature_code TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    updated_by_user_id INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (organization_id, feature_code),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS transport_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('UPLOAD','DELETE')),
    transport_mode TEXT NOT NULL CHECK (transport_mode IN ('NAS','HTTPS','LAN')),
    transport_target_id INTEGER,
    reconciliation_status TEXT NOT NULL DEFAULT 'RESOLVED'
        CHECK (reconciliation_status IN ('RESOLVED','NEEDS_RECONCILIATION')),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','RUNNING','RETRY','COMPLETED','FAILED','CANCELLED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    remote_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (transport_target_id) REFERENCES organization_transport_targets(id)
);

CREATE TABLE IF NOT EXISTS document_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_uuid TEXT NOT NULL UNIQUE,
    organization_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    requested_by_user_id INTEGER,
    assigned_to_user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN','IN_PROGRESS','ATTENDED','DELIVERING','DELIVERED','COMPLETED','CANCELLED')),
    due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    attended_at TEXT,
    delivered_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    origin_instance_id TEXT,
    target_instance_id TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (requested_by_user_id) REFERENCES users(id),
    FOREIGN KEY (assigned_to_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS smartfile_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL UNIQUE,
    organization_id INTEGER NOT NULL,
    device_name TEXT NOT NULL,
    owner_user_id INTEGER,
    current_ip TEXT NOT NULL,
    http_port INTEGER NOT NULL CHECK (http_port BETWEEN 1024 AND 65535),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    is_local INTEGER NOT NULL DEFAULT 0 CHECK (is_local IN (0,1)),
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS document_request_documents (
    request_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    linked_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (request_id, document_id),
    FOREIGN KEY (request_id) REFERENCES document_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (linked_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS document_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_uuid TEXT NOT NULL UNIQUE,
    protocol_number TEXT NOT NULL UNIQUE,
    organization_id INTEGER NOT NULL,
    request_id INTEGER,
    sender_user_id INTEGER,
    recipient_user_id INTEGER,
    sender_instance_id TEXT NOT NULL,
    recipient_instance_id TEXT NOT NULL,
    recipient_host TEXT NOT NULL,
    recipient_port INTEGER NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('OUTGOING','INCOMING')),
    message TEXT,
    status TEXT NOT NULL CHECK (status IN ('CREATED','QUEUED','SENDING','DELIVERED','VIEWED','ACKNOWLEDGED','FAILED','CANCELLED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    queued_at TEXT,
    sent_at TEXT,
    delivered_at TEXT,
    viewed_at TEXT,
    viewed_by_user_id INTEGER,
    acknowledged_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (request_id) REFERENCES document_requests(id),
    FOREIGN KEY (sender_user_id) REFERENCES users(id),
    FOREIGN KEY (recipient_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS document_delivery_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_uuid TEXT NOT NULL UNIQUE,
    delivery_id INTEGER NOT NULL,
    document_id INTEGER,
    logical_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    transfer_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (transfer_status IN ('PENDING','SENDING','RECEIVED','VERIFIED','FAILED')),
    received_path TEXT,
    sent_at TEXT,
    received_at TEXT,
    FOREIGN KEY (delivery_id) REFERENCES document_deliveries(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS delivery_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    request_id INTEGER,
    delivery_id INTEGER,
    event_type TEXT NOT NULL,
    actor_user_id INTEGER,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (request_id) REFERENCES document_requests(id),
    FOREIGN KEY (delivery_id) REFERENCES document_deliveries(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_delivery_org_direction_status ON document_deliveries(organization_id, direction, status);
CREATE INDEX IF NOT EXISTS idx_delivery_retry ON document_deliveries(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery ON document_delivery_items(delivery_id);
CREATE INDEX IF NOT EXISTS idx_delivery_history_request ON delivery_history(request_id, created_at);

CREATE TABLE IF NOT EXISTS cloud_settings (
    organization_id INTEGER PRIMARY KEY,
    cloud_account_id INTEGER,
    sync_mode TEXT NOT NULL DEFAULT 'LOCAL',
    remote_root_id TEXT,
    last_sync TEXT,
    delta_token TEXT,
    paused INTEGER NOT NULL DEFAULT 0 CHECK (paused IN (0, 1)),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (cloud_account_id) REFERENCES cloud_accounts(id)
);

CREATE TABLE IF NOT EXISTS cloud_folder_mappings (
    organization_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('ONEDRIVE', 'GOOGLE_DRIVE')),
    remote_id TEXT NOT NULL,
    remote_parent_id TEXT,
    remote_name TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    PRIMARY KEY (organization_id, folder_id, provider),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (folder_id) REFERENCES folders(id)
);

INSERT INTO organizations (
    name, description, slug, icon, color, created_at, updated_at, is_default, status
) SELECT 'Minha Organização', 'Organização padrão do SmartFile', 'minha-organizacao',
         'organization', '#2563eb', datetime('now'), datetime('now'), 1, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM organizations);

INSERT OR IGNORE INTO app_settings (key, value)
SELECT 'active_organization_id', CAST(id AS TEXT)
FROM organizations WHERE is_default = 1 ORDER BY id LIMIT 1;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    source_path TEXT,
    storage_path TEXT,
    internal_name TEXT,
    managed INTEGER NOT NULL DEFAULT 0 CHECK (managed IN (0, 1)),
    extension TEXT NOT NULL,
    file_type TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    checksum TEXT NOT NULL,
    category TEXT,
    description TEXT,
    favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'TRASHED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed_at TEXT,
    organization_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizations(id),
    folder_id INTEGER REFERENCES folders(id)
    ,cloud_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY'
    ,cloud_provider TEXT
    ,remote_id TEXT
    ,remote_version TEXT
    ,last_synced_at TEXT
    ,source_type TEXT NOT NULL DEFAULT 'IMPORT'
    ,tags TEXT
    ,document_date TEXT
    ,notes TEXT
);

CREATE TABLE IF NOT EXISTS storage_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    quota_bytes INTEGER NOT NULL CHECK (quota_bytes >= 0),
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO storage_plans
    (code, name, quota_bytes, description, is_active, created_at, updated_at)
VALUES
    ('PERSONAL_10GB', 'Pessoal 10 GB', 10737418240, 'Cota lógica pessoal de 10 GB', 1, datetime('now'), datetime('now')),
    ('STUDENT_20GB', 'Estudante 20 GB', 21474836480, 'Cota lógica estudantil de 20 GB', 1, datetime('now'), datetime('now')),
    ('BUSINESS_60GB', 'Empresarial 60 GB', 64424509440, 'Cota lógica empresarial de 60 GB', 1, datetime('now'), datetime('now'));

CREATE TABLE IF NOT EXISTS organization_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE,
    storage_plan_id INTEGER NOT NULL,
    quota_bytes INTEGER NOT NULL CHECK (quota_bytes >= 0),
    used_bytes INTEGER NOT NULL DEFAULT 0 CHECK (used_bytes >= 0),
    reserved_bytes INTEGER NOT NULL DEFAULT 0 CHECK (reserved_bytes >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (storage_plan_id) REFERENCES storage_plans(id)
);

CREATE TABLE IF NOT EXISTS storage_reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL UNIQUE,
    organization_id INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    status TEXT NOT NULL CHECK (status IN ('RESERVED', 'COMMITTED', 'RELEASED', 'EXPIRED')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    committed_at TEXT,
    released_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

INSERT OR IGNORE INTO organization_storage
    (organization_id, storage_plan_id, quota_bytes, used_bytes, reserved_bytes, created_at, updated_at)
SELECT o.id, p.id, p.quota_bytes, 0, 0, datetime('now'), datetime('now')
FROM organizations o JOIN storage_plans p ON p.code='PERSONAL_10GB';

CREATE TABLE IF NOT EXISTS sync_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    operation TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

INSERT OR IGNORE INTO cloud_settings (organization_id, sync_mode, paused)
SELECT id, 'LOCAL', 0 FROM organizations;

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    action TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(name);
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);
CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum);
CREATE INDEX IF NOT EXISTS idx_documents_favorite ON documents(favorite);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_storage_path ON documents(storage_path);
CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization_id);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_documents_org_checksum ON documents(organization_id, checksum);
CREATE INDEX IF NOT EXISTS idx_documents_cloud_status ON documents(cloud_status);
CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
CREATE INDEX IF NOT EXISTS idx_folders_organization ON folders(organization_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_sibling_name
    ON folders(organization_id, COALESCE(parent_id, 0), lower(name))
    WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_document ON sync_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_cloud_accounts_provider ON cloud_accounts(provider, status);
CREATE INDEX IF NOT EXISTS idx_cloud_folder_remote
    ON cloud_folder_mappings(organization_id, provider, remote_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, revoked_at);
CREATE INDEX IF NOT EXISTS idx_password_recovery_user
    ON password_recovery_codes(user_id, used_at, expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_password_recovery_lookup
    ON password_recovery_codes(user_id, code_lookup);
CREATE INDEX IF NOT EXISTS idx_members_user ON organization_members(user_id, status);
CREATE INDEX IF NOT EXISTS idx_members_organization ON organization_members(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_organization ON audit_log(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_storage_reservations_status ON storage_reservations(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_storage_reservations_organization ON storage_reservations(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_document_requests_org_status_due
    ON document_requests(organization_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_organization_features_enabled
    ON organization_feature_settings(organization_id, enabled, feature_code);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_status
    ON transport_jobs(status, attempts, created_at, id);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_organization
    ON transport_jobs(organization_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_document
    ON transport_jobs(document_id, operation, status);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_created
    ON transport_jobs(created_at, id);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_target
    ON transport_jobs(transport_target_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_transport_jobs_reconciliation
    ON transport_jobs(organization_id, reconciliation_status, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transport_jobs_active_operation
    ON transport_jobs(organization_id, document_id, operation)
    WHERE status IN ('PENDING','RUNNING','RETRY');
CREATE INDEX IF NOT EXISTS idx_transport_targets_organization
    ON organization_transport_targets(organization_id, status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transport_targets_one_active
    ON organization_transport_targets(organization_id) WHERE status='ACTIVE';
CREATE INDEX IF NOT EXISTS idx_documents_smart_search
    ON documents(organization_id, status, file_type, source_type, created_at);
CREATE INDEX IF NOT EXISTS idx_documents_org_category
    ON documents(organization_id, category COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_documents_org_favorite
    ON documents(organization_id, favorite, status);
