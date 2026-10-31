-- Proposed target schema for cert_basis.sqlite.
-- See 02-proposal.md for rationale (P-nn) and 01-findings.md (F-nn).
-- Requires SQLite >= 3.37 (STRICT tables) and >= 3.31 (generated columns).
-- All tables STRICT; all dates TEXT 'YYYY-MM-DD' with CHECK (date(x) IS x).
-- Use IS, not =: date() returns NULL for invalid input (e.g. '2064-13-01'),
-- NULL = x is NULL, and a CHECK that evaluates to NULL passes.

PRAGMA user_version = 2;  -- P-08: bump on any contract change

-- ---------------------------------------------------------------------------
-- Build metadata (P-08)

CREATE TABLE build_info (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    git_sha        TEXT,
    built_at       TEXT NOT NULL            -- ISO 8601 UTC timestamp
) STRICT;

-- ---------------------------------------------------------------------------
-- Issuers and documents (P-01, P-02)

CREATE TABLE issuers (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE
                 CHECK (code GLOB '[A-Z0-9]*' AND code NOT GLOB '*[^A-Z0-9_-]*'),
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL
                 CHECK (kind IN ('naa', 'military', 'standards_body')),
    country      TEXT,
    successor_id INTEGER REFERENCES issuers(id),
    CHECK (successor_id IS NULL OR successor_id <> id)
) STRICT;

CREATE TABLE documents (
    id          INTEGER PRIMARY KEY,
    issuer_id   INTEGER NOT NULL REFERENCES issuers(id),
    doc_kind    TEXT NOT NULL
                CHECK (doc_kind IN (
                    'regulation',          -- 14 CFR parts, CAR
                    'certification_spec',  -- EASA CS
                    'amc_gm',              -- EASA AMC/GM
                    'advisory_circular',   -- FAA AC
                    'handbook',            -- MIL-HDBK-516
                    'special_condition',
                    'elos',
                    'exemption',
                    'standard'             -- RTCA DO-xxx, SAE ARP, etc.
                )),
    code        TEXT NOT NULL,             -- '14 CFR 23', 'CAR 3', 'CS-25', 'AC 25.1309', 'MIL-HDBK-516'
    slug        TEXT NOT NULL,             -- path segment: '23', 'car-3', 'cs-25', 'ac-25-1309'
    title       TEXT,
    UNIQUE (issuer_id, code),
    UNIQUE (issuer_id, slug)
) STRICT;

CREATE TABLE document_revisions (
    id             INTEGER PRIMARY KEY,
    document_id    INTEGER NOT NULL REFERENCES documents(id),
    designator     TEXT NOT NULL,          -- '23-62', 'Amdt 27', '1A', 'C'
    ordinal        INTEGER NOT NULL CHECK (ordinal >= 0),  -- 0 = original issue
    effective_date TEXT NOT NULL CHECK (date(effective_date) IS effective_date),
    cancelled_on   TEXT CHECK (cancelled_on IS NULL OR date(cancelled_on) IS cancelled_on),
    provenance     TEXT NOT NULL DEFAULT 'scraped'
                   CHECK (provenance IN ('scraped', 'ocr', 'manual')),
    UNIQUE (document_id, designator),
    UNIQUE (document_id, ordinal),
    UNIQUE (document_id, id),              -- target for composite FKs (P-03)
    CHECK (cancelled_on IS NULL OR cancelled_on >= effective_date)
) STRICT;

-- P-05: rulemaking actions belong to the revision, not to each provision.
CREATE TABLE revision_actions (
    id          INTEGER PRIMARY KEY,
    revision_id INTEGER NOT NULL REFERENCES document_revisions(id),
    seq         INTEGER NOT NULL,
    action_type TEXT NOT NULL
                CHECK (action_type IN (
                    'nprm', 'final_rule', 'direct_final_rule', 'interim_final_rule',
                    'easa_npa', 'easa_opinion', 'easa_decision',
                    'jar_npa', 'jar_change', 'other'
                )),
    reference   TEXT,
    issued_on   TEXT CHECK (issued_on IS NULL OR date(issued_on) IS issued_on),
    source_url  TEXT,
    notes       TEXT,
    UNIQUE (revision_id, seq)
) STRICT;

-- ---------------------------------------------------------------------------
-- Provisions and their versions (P-03, P-04)

CREATE TABLE provisions (
    id               INTEGER PRIMARY KEY,
    document_id      INTEGER NOT NULL REFERENCES documents(id),
    number           TEXT NOT NULL,        -- '1309', '4.1.1.1'
    parent_id        INTEGER,              -- NULL for flat documents (CFR)
    sort_key         TEXT NOT NULL,        -- build-computed natural order, e.g. '0001309' / '0004.0001.0001'
    canonical_title  TEXT NOT NULL,
    current_grouping TEXT,                 -- was current_subpart; display only
    subject_group    TEXT,
    UNIQUE (document_id, number),
    UNIQUE (document_id, id),
    FOREIGN KEY (document_id, parent_id) REFERENCES provisions (document_id, id),
    CHECK (parent_id IS NULL OR parent_id <> id)
) STRICT;

CREATE TABLE provision_versions (
    id                 INTEGER PRIMARY KEY,
    document_id        INTEGER NOT NULL,
    provision_id       INTEGER NOT NULL,
    revision_id        INTEGER NOT NULL,
    grouping_at_time   TEXT,               -- was subpart_at_time
    title_at_revision  TEXT NOT NULL,
    text               TEXT NOT NULL,
    text_missing       INTEGER GENERATED ALWAYS AS (text = 'TEXT MISSING') VIRTUAL,
    same_as_version_id INTEGER,            -- alias target (was same_as_designator)
    publication_cite   TEXT,               -- '35 FR 5665'; NULL if unknown or ordinal 0 (P-03, F-07)
    source_url         TEXT,
    provenance         TEXT NOT NULL DEFAULT 'scraped'
                       CHECK (provenance IN ('scraped', 'ocr', 'manual')),
    provenance_notes   TEXT,
    UNIQUE (provision_id, revision_id),
    UNIQUE (provision_id, id),
    FOREIGN KEY (document_id, provision_id) REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, revision_id)  REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (provision_id, same_as_version_id) REFERENCES provision_versions (provision_id, id),
    CHECK (same_as_version_id IS NULL OR same_as_version_id <> id)
) STRICT;

CREATE INDEX idx_pv_revision ON provision_versions (revision_id);

-- P-07: typed relations between provisions (AC -> reg, CS-25.1309 <-> 25.1309).
CREATE TABLE provision_relations (
    id                INTEGER PRIMARY KEY,
    from_provision_id INTEGER NOT NULL REFERENCES provisions(id),
    to_provision_id   INTEGER NOT NULL REFERENCES provisions(id),
    relation          TEXT NOT NULL
                      CHECK (relation IN (
                          'guidance_for',   -- AC/AMC/GM provides means of compliance for
                          'equivalent_to',  -- harmonised counterpart (symmetric; store once, from < to)
                          'supersedes',
                          'modifies',       -- SC/ELOS/exemption modifies or replaces
                          'references'      -- generic citation
                      )),
    origin            TEXT NOT NULL CHECK (origin IN ('manual', 'derived')),
    notes             TEXT,
    UNIQUE (from_provision_id, to_provision_id, relation),
    CHECK (from_provision_id <> to_provision_id),
    CHECK (relation <> 'equivalent_to' OR from_provision_id < to_provision_id)
) STRICT;

CREATE INDEX idx_rel_to ON provision_relations (to_provision_id);

-- ---------------------------------------------------------------------------
-- Aircraft

CREATE TABLE manufacturers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE categories (                  -- seeded from a closed list in build.py (F-13)
    id   INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
) STRICT;

CREATE TABLE aircraft_models (
    id                INTEGER PRIMARY KEY,
    manufacturer_id   INTEGER NOT NULL REFERENCES manufacturers(id),
    model_designation TEXT NOT NULL,
    common_name       TEXT,
    notes             TEXT,
    UNIQUE (manufacturer_id, model_designation)
) STRICT;

CREATE TABLE model_categories (
    model_id    INTEGER NOT NULL REFERENCES aircraft_models(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (model_id, category_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE tcds (
    id            INTEGER PRIMARY KEY,
    issuer_id     INTEGER NOT NULL REFERENCES issuers(id),
    tcds_number   TEXT NOT NULL,
    revision      TEXT,
    revision_date TEXT CHECK (revision_date IS NULL OR date(revision_date) IS revision_date),
    source_url    TEXT,
    UNIQUE (issuer_id, tcds_number)
) STRICT;

CREATE TABLE tcb (
    id       INTEGER PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES aircraft_models(id),
    tcds_id  INTEGER NOT NULL REFERENCES tcds(id),
    notes    TEXT,
    UNIQUE (model_id, tcds_id)
) STRICT;

-- P-06: three layers. Entry = one TCDS line, verbatim.
CREATE TABLE cert_basis_entries (
    id                  INTEGER PRIMARY KEY,
    tcb_id              INTEGER NOT NULL REFERENCES tcb(id),
    display_order       INTEGER NOT NULL CHECK (display_order >= 1),
    entry_type          TEXT NOT NULL
                        CHECK (entry_type IN
                            ('regulation', 'special_condition', 'elos',
                             'exemption', 'other')),
    raw_reference       TEXT NOT NULL,     -- sacred, verbatim
    applicability       TEXT,              -- verbatim serial / config scope, e.g. '525-0600 thru 525-0684'
    applicability_notes TEXT,
    UNIQUE (tcb_id, display_order)
) STRICT;

-- Ref = one machine-readable interpretation clause of an entry.
CREATE TABLE cert_basis_refs (
    id               INTEGER PRIMARY KEY,
    entry_id         INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    seq              INTEGER NOT NULL,
    ref_kind         TEXT NOT NULL CHECK (ref_kind IN ('range', 'single', 'document')),
    effect           TEXT NOT NULL DEFAULT 'include'
                     CHECK (effect IN ('include', 'exclude')),
    document_id      INTEGER NOT NULL,
    provision_id     INTEGER,              -- required for 'single'; a 'range' is scoped via cert_basis_ref_provisions instead
    from_revision_id INTEGER,
    to_revision_id   INTEGER,
    paragraph        TEXT,                 -- verbatim qualifier '(a)', '(c)(2)'; never resolved
    UNIQUE (entry_id, seq),
    FOREIGN KEY (document_id, provision_id)     REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, from_revision_id) REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (document_id, to_revision_id)   REFERENCES document_revisions (document_id, id),
    CHECK (
        (ref_kind = 'range'    AND provision_id IS NULL     AND from_revision_id IS NOT NULL AND to_revision_id IS NOT NULL)
     OR (ref_kind = 'single'   AND provision_id IS NOT NULL AND from_revision_id IS NULL
         AND (to_revision_id IS NOT NULL OR effect = 'exclude'))
     OR (ref_kind = 'document' AND provision_id IS NULL     AND from_revision_id IS NULL)
    ),
    CHECK (effect = 'include' OR paragraph IS NULL)
) STRICT;

-- Optional provision scope for a range ref ("except the following
-- paragraphs ...: 23.611, 23.777 ... as amended through 23-54").
CREATE TABLE cert_basis_ref_provisions (
    ref_id       INTEGER NOT NULL REFERENCES cert_basis_refs(id),
    provision_id INTEGER NOT NULL REFERENCES provisions(id),
    PRIMARY KEY (ref_id, provision_id)
) STRICT, WITHOUT ROWID;

-- Revisions explicitly skipped inside a range ("23-1 thru 23-38, 23-40").
CREATE TABLE cert_basis_ref_skips (
    ref_id      INTEGER NOT NULL REFERENCES cert_basis_refs(id),
    revision_id INTEGER NOT NULL REFERENCES document_revisions(id),
    PRIMARY KEY (ref_id, revision_id)
) STRICT, WITHOUT ROWID;

-- Resolved = build-computed expansion. One row per (entry, version) after
-- applying the resolution rules in 02-proposal.md P-06.
CREATE TABLE cert_basis_resolved (
    entry_id            INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    via_ref_id          INTEGER NOT NULL REFERENCES cert_basis_refs(id),
    paragraph           TEXT,              -- copied from ref; NULL = whole provision
    PRIMARY KEY (entry_id, provision_version_id)
) STRICT, WITHOUT ROWID;

CREATE INDEX idx_cbr_version ON cert_basis_resolved (provision_version_id);

-- ---------------------------------------------------------------------------
-- Views

CREATE VIEW latest_versions AS
SELECT pv.*, dr.designator, dr.ordinal, dr.effective_date
FROM provision_versions pv
JOIN document_revisions dr ON dr.id = pv.revision_id
WHERE dr.ordinal = (
    SELECT MAX(dr2.ordinal)
    FROM provision_versions pv2
    JOIN document_revisions dr2 ON dr2.id = pv2.revision_id
    WHERE pv2.provision_id = pv.provision_id
);
