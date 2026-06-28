-- ============================================================
-- ARGUS v0.0 — SQLite Schema
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. INVESTIGATIONS
-- Root object. Everything belongs to an investigation.
-- notes column removed — use the notes table instead.
-- ============================================================

CREATE TABLE IF NOT EXISTS investigations (
    id              TEXT PRIMARY KEY,           -- INV-XXXXXX
    target          TEXT NOT NULL,              -- example.com
    program         TEXT,                       -- HackerOne / Bugcrowd / private
    platform        TEXT,                       -- hackerone / bugcrowd / intigriti / other
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'paused', 'completed')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_activity   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- 2. ASSETS
-- Unified table for all infrastructure and recon data.
-- type drives T-Intel grouping in the UI:
--   Infrastructure → domain, subdomain, ip, url, port, service
--   Technology     → framework, cdn, waf, cms, cloud_provider, language
--   Recon          → endpoint, parameter, header, observation
-- status allows ignoring/archiving assets without deletion.
-- ============================================================

CREATE TABLE IF NOT EXISTS assets (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type                TEXT NOT NULL CHECK(type IN (
                            -- Infrastructure
                            'domain', 'subdomain', 'ip', 'url', 'port', 'service',
                            -- Technology
                            'framework', 'cdn', 'waf', 'cms', 'cloud_provider', 'language',
                            -- Recon
                            'endpoint', 'parameter', 'header'
                        )),
    value               TEXT NOT NULL,
    parent_id           TEXT REFERENCES assets(id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active', 'ignored', 'out_of_scope', 'archived')),
    notes               TEXT,
    source              TEXT NOT NULL DEFAULT 'manual'
                            CHECK(source IN ('manual', 'imported', 'committed', 'discovered')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assets_investigation ON assets(investigation_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_parent ON assets(parent_id);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);

-- ============================================================
-- 3. SCOPE
-- In-scope and out-of-scope entries for the target program.
-- Imported from HackerOne JSON, plain text, or entered manually.
-- Used by /review to evaluate finding scope alignment.
-- ============================================================

CREATE TABLE IF NOT EXISTS scope (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type                TEXT NOT NULL CHECK(type IN ('in_scope', 'out_of_scope', 'rule', 'reward')),
    value               TEXT NOT NULL,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scope_investigation ON scope(investigation_id);
CREATE INDEX IF NOT EXISTS idx_scope_type ON scope(type);

-- ============================================================
-- 4. FINDINGS
-- Vulnerability records. Core of the reporting workflow.
-- Review history lives in finding_reviews — not here.
-- ============================================================

CREATE TABLE IF NOT EXISTS findings (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description         TEXT,
    severity            TEXT NOT NULL DEFAULT 'medium'
                            CHECK(severity IN ('critical', 'high', 'medium', 'low', 'informational')),
    status              TEXT NOT NULL DEFAULT 'open'
                            CHECK(status IN ('open', 'submitted', 'resolved', 'duplicate', 'na')),
    reproduction_steps  TEXT,
    remediation         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_findings_investigation ON findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);

-- ============================================================
-- 5. FINDING_REVIEWS
-- Each /review run creates a new record.
-- History is preserved — never overwritten.
-- confidence is 0-100. AI should never assert, only suggest.
-- ============================================================

CREATE TABLE IF NOT EXISTS finding_reviews (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    finding_id          TEXT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    scope_alignment     TEXT NOT NULL
                            CHECK(scope_alignment IN ('in_scope', 'out_of_scope', 'unclear')),
    suggested_severity  TEXT NOT NULL
                            CHECK(suggested_severity IN ('critical', 'high', 'medium', 'low', 'informational')),
    confidence          INTEGER NOT NULL DEFAULT 0
                            CHECK(confidence BETWEEN 0 AND 100),
    evidence_quality    TEXT NOT NULL
                            CHECK(evidence_quality IN ('strong', 'moderate', 'weak', 'insufficient')),
    missing_evidence    TEXT,                   -- what the AI thinks is still needed
    submission_readiness TEXT NOT NULL
                            CHECK(submission_readiness IN ('ready', 'needs_work', 'not_ready')),
    reasoning           TEXT NOT NULL,          -- full AI reasoning in markdown
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_finding ON finding_reviews(finding_id);

-- ============================================================
-- 6. FINDING_ASSETS
-- Many-to-many: one finding can affect multiple assets.
-- ============================================================

CREATE TABLE IF NOT EXISTS finding_assets (
    finding_id          TEXT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    asset_id            TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    PRIMARY KEY (finding_id, asset_id)
);

-- ============================================================
-- 7. NOTES
-- Research notes. manual = researcher wrote it, ai = agent wrote it,
-- committed = came from /commit note in terminal.
-- ============================================================

CREATE TABLE IF NOT EXISTS notes (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'manual'
                            CHECK(source IN ('manual', 'ai', 'committed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notes_investigation ON notes(investigation_id);

-- ============================================================
-- 8. REPORTS
-- AI-generated and manual Markdown reports.
-- author replaces type — distinguishes who created the report
-- without locking the schema to current assumptions.
-- ============================================================

CREATE TABLE IF NOT EXISTS reports (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    author              TEXT NOT NULL DEFAULT 'researcher'
                            CHECK(author IN ('ai', 'researcher')),
    content             TEXT NOT NULL DEFAULT '',   -- Markdown
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_investigation ON reports(investigation_id);

-- ============================================================
-- 9. TIMELINE
-- Append-only event log. Never updated, only inserted.
-- meta is always JSON. Add new event shapes there, not new columns.
-- ============================================================

CREATE TABLE IF NOT EXISTS timeline (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    event_type          TEXT NOT NULL CHECK(event_type IN (
                            'investigation_created',
                            'investigation_status_changed',
                            'scope_imported',
                            'file_imported',
                            'asset_committed',
                            'finding_committed',
                            'finding_status_changed',
                            'finding_reviewed',
                            'note_committed',
                            'technology_committed',
                            'endpoint_committed',
                            'report_generated',
                            'report_created',
                            'agent_interaction'
                        )),
    description         TEXT NOT NULL,              -- human-readable log line
    meta                TEXT,                       -- JSON blob. always JSON, never new columns.
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_timeline_investigation ON timeline(investigation_id);
CREATE INDEX IF NOT EXISTS idx_timeline_event_type ON timeline(event_type);

-- ============================================================
-- 10. IMPORTS
-- Tracks files imported into an investigation.
-- Imported content is parsed into assets and scope.
-- raw_content kept for re-parsing if schema changes.
-- ============================================================

CREATE TABLE IF NOT EXISTS imports (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    investigation_id    TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    filename            TEXT NOT NULL,
    file_type           TEXT NOT NULL CHECK(file_type IN (
                            'json', 'txt', 'xml', 'md', 'screenshot', 'other'
                        )),
    file_path           TEXT NOT NULL,
    parsed              INTEGER NOT NULL DEFAULT 0 CHECK(parsed IN (0, 1)),
    raw_content         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_imports_investigation ON imports(investigation_id);

-- ============================================================
-- 11. SESSION_SUMMARY
-- AI memory cache. One record per investigation.
-- Derived from all investigation data — never source of truth.
-- Rebuilt on state change. Injected as agent system prompt prefix.
-- ============================================================

CREATE TABLE IF NOT EXISTS session_summary (
    investigation_id    TEXT PRIMARY KEY REFERENCES investigations(id) ON DELETE CASCADE,
    content             TEXT NOT NULL DEFAULT '',
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- 12. SETTINGS
-- Local config. Single-row enforced via CHECK.
-- ============================================================

CREATE TABLE IF NOT EXISTS settings (
    id                  INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
    anthropic_api_key   TEXT,
    default_model       TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    theme               TEXT NOT NULL DEFAULT 'dark',
    workspace_path      TEXT NOT NULL DEFAULT '~/.argus',
    provider            TEXT NOT NULL DEFAULT 'anthropic',
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO settings (id) VALUES (1);

-- ============================================================
-- TRIGGERS
-- ============================================================

-- updated_at maintenance
CREATE TRIGGER IF NOT EXISTS trg_investigations_updated
    AFTER UPDATE ON investigations
    BEGIN
        UPDATE investigations SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_findings_updated
    AFTER UPDATE ON findings
    BEGIN
        UPDATE findings SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_notes_updated
    AFTER UPDATE ON notes
    BEGIN
        UPDATE notes SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_reports_updated
    AFTER UPDATE ON reports
    BEGIN
        UPDATE reports SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

-- last_activity auto-update on any investigation activity
CREATE TRIGGER IF NOT EXISTS trg_last_activity_findings
    AFTER INSERT ON findings
    BEGIN
        UPDATE investigations SET last_activity = datetime('now')
        WHERE id = NEW.investigation_id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_last_activity_assets
    AFTER INSERT ON assets
    BEGIN
        UPDATE investigations SET last_activity = datetime('now')
        WHERE id = NEW.investigation_id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_last_activity_notes
    AFTER INSERT ON notes
    BEGIN
        UPDATE investigations SET last_activity = datetime('now')
        WHERE id = NEW.investigation_id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_last_activity_timeline
    AFTER INSERT ON timeline
    BEGIN
        UPDATE investigations SET last_activity = datetime('now')
        WHERE id = NEW.investigation_id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_last_activity_reviews
    AFTER INSERT ON finding_reviews
    BEGIN
        UPDATE investigations SET last_activity = datetime('now')
        WHERE id = (SELECT investigation_id FROM findings WHERE id = NEW.finding_id);
    END;

