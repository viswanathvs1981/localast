-- SQLite schema for a fully local LocalAST deployment.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    lang TEXT,
    hash TEXT,
    modname TEXT
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    fqn TEXT,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    start_line INTEGER,
    start_col INTEGER,
    end_line INTEGER,
    end_col INTEGER,
    sig TEXT,
    doc TEXT
);

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
    repo TEXT,
    commit_id TEXT,
    blob_id INTEGER,
    path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    ts TEXT
);

CREATE TABLE IF NOT EXISTS change_event (
    repo TEXT,
    commit_id TEXT,
    parent_commit_id TEXT,
    path TEXT,
    kind TEXT,
    blob_old INTEGER,
    blob_new INTEGER,
    hunk TEXT,
    summary TEXT,
    categories TEXT
);

CREATE TABLE IF NOT EXISTS emb (
    blob_id INTEGER,
    dim INTEGER,
    vec BLOB,
    index_kind TEXT,
    file_id INTEGER,
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
    repo TEXT NOT NULL,
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
