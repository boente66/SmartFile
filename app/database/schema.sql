CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    slug TEXT NOT NULL UNIQUE,
    icon TEXT,
    color TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
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
);

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
CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
CREATE INDEX IF NOT EXISTS idx_folders_organization ON folders(organization_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_sibling_name
    ON folders(organization_id, COALESCE(parent_id, 0), lower(name))
    WHERE status = 'ACTIVE';
