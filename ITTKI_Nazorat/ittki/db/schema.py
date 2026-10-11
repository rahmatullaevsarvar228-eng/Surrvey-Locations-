"""SQLite schema (TZ section 5) and migrations.

Journal entries, schedules and decisions are NOT stored — they are recomputed by the engine.
Money: INTEGER (so'm), enforced with typeof() checks. Dates: ISO 'YYYY-MM-DD' text.
Immutable tables (no UPDATE / DELETE, enforced by triggers): audit_log, stage_events,
assessments, assessment_answers, evidence_documents.
"""

SCHEMA_VERSION = 1

_MONEY = "CHECK ({c} IS NULL OR (typeof({c}) = 'integer' AND {c} >= 0))"

MIGRATIONS = {
    1: f"""
CREATE TABLE projects (
    id                   INTEGER PRIMARY KEY,
    code                 TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    scope                TEXT NOT NULL DEFAULT 'rnd'
                         CHECK (scope IN ('rnd', 'mineral_exploration', 'contract_for_customer')),
    department           TEXT NOT NULL DEFAULT '',
    leader               TEXT NOT NULL DEFAULT '',
    start_date           TEXT,
    budget               INTEGER {_MONEY.format(c='budget')},
    status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ready', 'abandoned')),
    phases_separable     INTEGER NOT NULL DEFAULT 1 CHECK (phases_separable IN (0, 1)),
    development_start    TEXT,
    available_for_use    TEXT,
    abandoned_on         TEXT,
    useful_life_months   INTEGER NOT NULL DEFAULT 0 CHECK (useful_life_months >= 0),
    expected_net_benefit INTEGER {_MONEY.format(c='expected_net_benefit')},
    note                 TEXT NOT NULL DEFAULT '',
    is_demo              INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL
);

CREATE TABLE stage_events (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    from_stage  TEXT,
    to_stage    TEXT NOT NULL CHECK (to_stage IN ('research', 'development', 'ready', 'abandoned')),
    on_date     TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL,
    role        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE evidence_documents (
    id          INTEGER PRIMARY KEY,
    doc_type    TEXT NOT NULL,
    number      TEXT NOT NULL,
    doc_date    TEXT NOT NULL,
    file_path   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE assessments (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    on_date     TEXT NOT NULL,
    is_draft    INTEGER NOT NULL DEFAULT 0,
    note        TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL,
    role        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE assessment_answers (
    id             INTEGER PRIMARY KEY,
    assessment_id  INTEGER NOT NULL REFERENCES assessments(id),
    criterion_key  TEXT NOT NULL,
    answer         TEXT NOT NULL CHECK (answer IN ('yes', 'no', 'expert')),
    evidence_id    INTEGER REFERENCES evidence_documents(id),
    UNIQUE (assessment_id, criterion_key)
);

CREATE TABLE costs (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    on_date     TEXT NOT NULL,
    amount      INTEGER NOT NULL {_MONEY.format(c='amount')},
    category    TEXT NOT NULL,
    document    TEXT NOT NULL DEFAULT '',
    comment     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE INDEX costs_project ON costs(project_id, on_date);

-- v1: the engine supports one impairment event per project
CREATE TABLE impairment_events (
    id                  INTEGER PRIMARY KEY,
    project_id          INTEGER NOT NULL UNIQUE REFERENCES projects(id),
    on_date             TEXT NOT NULL,
    recoverable_amount  INTEGER NOT NULL {_MONEY.format(c='recoverable_amount')}
);

CREATE TABLE impairment_tests (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    on_date     TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL            -- JSON
);

CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    role        TEXT NOT NULL,
    action      TEXT NOT NULL,      -- create | update | delete
    entity      TEXT NOT NULL,
    entity_id   INTEGER,
    before      TEXT,               -- JSON
    after       TEXT                -- JSON
);
""" + "".join(f"""
CREATE TRIGGER {t}_no_update BEFORE UPDATE ON {t}
BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;
CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t}
BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;
""" for t in ("audit_log", "stage_events", "assessments", "assessment_answers", "evidence_documents")),
}


def migrate(conn) -> int:
    """Create / upgrade the schema. Returns the resulting version."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] or 0
    for v in sorted(MIGRATIONS):
        if v > current:
            conn.executescript("BEGIN;" + MIGRATIONS[v] + f"INSERT INTO schema_version VALUES ({v}); COMMIT;")
            current = v
    return current
