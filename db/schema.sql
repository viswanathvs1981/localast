-- SQLite schema for a fully local LocalAST deployment.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Multi-repository support
CREATE TABLE IF NOT EXISTS repo (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    path TEXT NOT NULL,
    default_branch TEXT,
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_commit TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    lang TEXT,
    hash TEXT,
    modname TEXT,
    UNIQUE(repo_id, path)
);

-- Configuration files (JSON, YAML, XML, etc.)
CREATE TABLE IF NOT EXISTS config_files (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    format TEXT NOT NULL,
    content_json TEXT NOT NULL,
    hash TEXT,
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_id, path)
);

-- Configuration keys/values hierarchy
CREATE TABLE IF NOT EXISTS config_nodes (
    id INTEGER PRIMARY KEY,
    config_id INTEGER REFERENCES config_files(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES config_nodes(id) ON DELETE CASCADE,
    key_path TEXT NOT NULL,
    key TEXT,
    value TEXT,
    value_type TEXT,
    line_number INTEGER
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    fqn TEXT,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    start_line INTEGER,
    start_col INTEGER,
    end_line INTEGER,
    end_col INTEGER,
    sig TEXT,
    doc TEXT
);

-- Edge types: DOCS (symbol->doc), CALLS (symbol->symbol), IMPORTS (file->file), CONTAINS (symbol->symbol), IMPLEMENTS (symbol->symbol)
CREATE TABLE IF NOT EXISTS edges (
    src INTEGER NOT NULL,
    etype TEXT NOT NULL,
    dst INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blob (
    blob_id INTEGER PRIMARY KEY,
    kind TEXT,
    text TEXT,
    lang TEXT,
    fqn TEXT,
    path TEXT,
    anchors TEXT
);

CREATE TABLE IF NOT EXISTS version (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    commit_id TEXT NOT NULL,
    blob_id INTEGER,
    path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    ts TEXT,
    author TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS change_event (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    commit_id TEXT NOT NULL,
    parent_commit_id TEXT,
    path TEXT,
    kind TEXT,
    blob_old INTEGER,
    blob_new INTEGER,
    hunk TEXT,
    summary TEXT,
    categories TEXT,
    ts TEXT
);

CREATE TABLE IF NOT EXISTS emb (
    id INTEGER PRIMARY KEY,
    blob_id INTEGER,
    dim INTEGER,
    vec BLOB,
    index_kind TEXT,
    file_id INTEGER,
    symbol_id INTEGER,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    fqn TEXT,
    start_line INTEGER,
    end_line INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS ident_fts USING fts5(
    token,
    symbol_id UNINDEXED
);

CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
    text,
    symbol_id UNINDEXED
);

-- Prompt Lab additions
CREATE TABLE IF NOT EXISTS prompt_template (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    task TEXT NOT NULL,
    template TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS prompt_experiment (
    id INTEGER PRIMARY KEY,
    template_id INTEGER REFERENCES prompt_template(id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    context_spec TEXT,
    model TEXT,
    metrics TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS golden_task (
    id INTEGER PRIMARY KEY,
    goal TEXT NOT NULL,
    oracle TEXT,
    constraints TEXT
);

-- Review policy tables
CREATE TABLE IF NOT EXISTS review_policy (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    rules_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_run (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repo(id) ON DELETE CASCADE,
    from_commit TEXT,
    to_commit TEXT,
    policy_id INTEGER REFERENCES review_policy(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS review_finding (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES review_run(id) ON DELETE CASCADE,
    severity TEXT,
    path TEXT,
    fqn TEXT,
    rule_id TEXT,
    message TEXT,
    suggestion TEXT,
    hunk TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_fqn ON symbols(fqn);
CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_id);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(etype);
CREATE INDEX IF NOT EXISTS idx_config_files_repo ON config_files(repo_id);
CREATE INDEX IF NOT EXISTS idx_config_files_path ON config_files(path);
CREATE INDEX IF NOT EXISTS idx_config_nodes_config ON config_nodes(config_id);
CREATE INDEX IF NOT EXISTS idx_config_nodes_parent ON config_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_config_nodes_path ON config_nodes(key_path);
CREATE INDEX IF NOT EXISTS idx_version_repo ON version(repo_id);
CREATE INDEX IF NOT EXISTS idx_version_commit ON version(commit_id);
CREATE INDEX IF NOT EXISTS idx_change_event_repo ON change_event(repo_id);
CREATE INDEX IF NOT EXISTS idx_change_event_commit ON change_event(commit_id);
CREATE INDEX IF NOT EXISTS idx_emb_repo ON emb(repo_id);
CREATE INDEX IF NOT EXISTS idx_emb_symbol ON emb(symbol_id);
