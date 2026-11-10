"""The SQLite contract: DDL and its version (docs/SQLITE.md).

Bump SCHEMA_VERSION on every change to SCHEMA_SQL, and add a row to
docs/SCHEMA_HISTORY.md in the same commit. Integrity belongs in the DDL
(STRICT, CHECKs, composite FKs), not only in Python.
"""

from __future__ import annotations


# Bump on every change to the SQLite contract. Consumers require an exact match.
SCHEMA_VERSION = 11


SCHEMA_SQL = """
CREATE TABLE build_info (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    git_sha        TEXT,
    built_at       TEXT NOT NULL
) STRICT;

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
    id        INTEGER PRIMARY KEY,
    issuer_id INTEGER NOT NULL REFERENCES issuers(id),
    doc_kind  TEXT NOT NULL
              CHECK (doc_kind IN (
                  'regulation', 'certification_spec', 'amc_gm',
                  'advisory_circular', 'handbook', 'special_condition',
                  'elos', 'exemption', 'standard'
              )),
    code      TEXT NOT NULL,
    slug      TEXT NOT NULL,
    title     TEXT,
    UNIQUE (issuer_id, code),
    UNIQUE (issuer_id, slug)
) STRICT;

CREATE TABLE document_revisions (
    id               INTEGER PRIMARY KEY,
    document_id      INTEGER NOT NULL REFERENCES documents(id),
    designator       TEXT NOT NULL,
    ordinal          INTEGER NOT NULL CHECK (ordinal >= 0),
    effective_date   TEXT NOT NULL CHECK (date(effective_date) IS effective_date),
    provenance       TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr')),
    provenance_notes TEXT,
    UNIQUE (document_id, designator),
    UNIQUE (document_id, ordinal),
    UNIQUE (document_id, id)
) STRICT;

-- `key` is the provision's identity; `number` is the label printed at its
-- latest version. A document may reuse a number for another provision, or
-- renumber one, so `number` is not unique (docs/SCHEMA_HISTORY.md, v7).
CREATE TABLE provisions (
    id               INTEGER PRIMARY KEY,
    document_id      INTEGER NOT NULL REFERENCES documents(id),
    key              TEXT NOT NULL,
    number           TEXT NOT NULL,
    sort_key         TEXT NOT NULL,
    canonical_title  TEXT NOT NULL,
    current_grouping TEXT,
    subject_group    TEXT,
    UNIQUE (document_id, key),
    UNIQUE (document_id, id)
) STRICT;

CREATE INDEX idx_provisions_number ON provisions (document_id, number);

CREATE TABLE provision_versions (
    id                 INTEGER PRIMARY KEY,
    document_id        INTEGER NOT NULL,
    provision_id       INTEGER NOT NULL,
    revision_id        INTEGER NOT NULL,
    -- The number as printed at this revision.
    number             TEXT NOT NULL,
    grouping_at_time   TEXT,
    title_at_revision  TEXT NOT NULL,
    text               TEXT,
    -- 1 = the revision deleted the provision; such a version has no text.
    deleted            INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
    text_missing       INTEGER GENERATED ALWAYS AS
                           (IFNULL(text = 'TEXT MISSING', 0)) VIRTUAL,
    same_as_version_id INTEGER,
    publication_cite   TEXT,
    source_url         TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr')),
    provenance_notes   TEXT,
    UNIQUE (provision_id, revision_id),
    UNIQUE (provision_id, id),
    FOREIGN KEY (document_id, provision_id)
        REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, revision_id)
        REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (provision_id, same_as_version_id)
        REFERENCES provision_versions (provision_id, id),
    CHECK (same_as_version_id IS NULL OR same_as_version_id <> id),
    CHECK ((deleted = 1) = (text IS NULL)),
    CHECK (deleted = 0 OR same_as_version_id IS NULL)
) STRICT;

CREATE INDEX idx_pv_revision ON provision_versions (revision_id);

-- Two versions printed at one revision can't share a number. A deletion is
-- exempt: the revision that deletes a provision may reuse its number for a
-- new one. (That a number names at most one provision in force at every
-- revision is checked in Python: versions are sparse.)
CREATE UNIQUE INDEX idx_pv_printed_number ON provision_versions
    (document_id, revision_id, number) WHERE deleted = 0;

-- A version's text split into blocks (docs/DATA_FORMAT.md §Text format). Every version
-- that has text has rows; a flat (single-line) text is one unlabelled row.
CREATE TABLE provision_paragraphs (
    id                   INTEGER PRIMARY KEY,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    seq                  INTEGER NOT NULL CHECK (seq >= 0),
    depth                INTEGER NOT NULL CHECK (depth >= 0),
    label                TEXT,
    path                 TEXT,
    section              TEXT,
    heading              INTEGER NOT NULL CHECK (heading IN (0, 1)),
    -- 'table': one line of a table block (its open line, a row, or its close
    -- line), with the markup kept in `text` (docs/DATA_FORMAT.md §Tables).
    -- 'formula': a display formula line, `$$ … $$` kept in `text`
    -- (docs/DATA_FORMAT.md §Inline markup).
    kind                 TEXT NOT NULL CHECK (kind IN ('text', 'table', 'formula')),
    text                 TEXT NOT NULL,
    UNIQUE (provision_version_id, seq),
    CHECK ((depth = 0) = (path IS NULL)),
    CHECK (label IS NULL OR depth >= 1),
    -- A heading row opens a section: top level, unlabelled, naming it.
    CHECK (heading = 0 OR (depth = 0 AND label IS NULL AND section IS NOT NULL)),
    CHECK (kind = 'text' OR (label IS NULL AND heading = 0)),
    -- Inside a section, paths carry the section number: 'G23.3(a)(1)'.
    CHECK (path IS NULL OR section IS NULL
           OR substr(path, 1, length(section) + 1) = section || '(')
) STRICT;

CREATE INDEX idx_pp_path ON provision_paragraphs (provision_version_id, path);

-- Rulemaking actions stay per version: DRS records them per section, and the
-- per-section lists for one amendment do not always agree.
CREATE TABLE version_actions (
    id                   INTEGER PRIMARY KEY,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    seq                  INTEGER NOT NULL,
    action_type          TEXT NOT NULL
                         CHECK (action_type IN (
                             'nprm', 'final_rule', 'direct_final_rule',
                             'interim_final_rule', 'easa_npa', 'easa_opinion',
                             'easa_decision', 'jar_npa', 'jar_change', 'other'
                         )),
    reference            TEXT,
    issued_on            TEXT CHECK (issued_on IS NULL OR date(issued_on) IS issued_on),
    source_url           TEXT,
    notes                TEXT,
    UNIQUE (provision_version_id, seq)
) STRICT;

CREATE INDEX idx_actions_reference ON version_actions (reference);

-- Build-computed text similarity between provisions (docs/SQLITE.md §Similarity).
-- Directed: the best matches *for* provision_id, ranked within each document
-- of similar_provision_id. Computed, never hand-checked.
CREATE TABLE provision_similarity (
    provision_id         INTEGER NOT NULL REFERENCES provisions(id),
    similar_provision_id INTEGER NOT NULL REFERENCES provisions(id),
    rank                 INTEGER NOT NULL CHECK (rank >= 1),
    score                INTEGER NOT NULL CHECK (score BETWEEN 1 AND 1000),
    PRIMARY KEY (provision_id, similar_provision_id),
    CHECK (provision_id <> similar_provision_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE manufacturers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE categories (
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

CREATE TABLE tcds (
    id            INTEGER PRIMARY KEY,
    issuer_id     INTEGER NOT NULL REFERENCES issuers(id),
    tcds_number   TEXT NOT NULL,
    revision      TEXT,
    revision_date TEXT
                  CHECK (revision_date IS NULL OR date(revision_date) IS revision_date),
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

-- Categories as stated on one TCDS for one model (regulators can differ).
CREATE TABLE tcb_categories (
    tcb_id      INTEGER NOT NULL REFERENCES tcb(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (tcb_id, category_id)
) STRICT, WITHOUT ROWID;

-- One row per TCDS line, verbatim.
CREATE TABLE cert_basis_entries (
    id                  INTEGER PRIMARY KEY,
    tcb_id              INTEGER NOT NULL REFERENCES tcb(id),
    display_order       INTEGER NOT NULL CHECK (display_order >= 1),
    entry_type          TEXT NOT NULL
                        CHECK (entry_type IN
                            ('regulation', 'special_condition', 'elos',
                             'exemption', 'other')),
    raw_reference       TEXT NOT NULL,
    applicability       TEXT,
    applicability_notes TEXT,
    UNIQUE (tcb_id, display_order)
) STRICT;

-- One row per machine-readable interpretation clause of an entry.
CREATE TABLE cert_basis_refs (
    id             INTEGER PRIMARY KEY,
    entry_id       INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    seq            INTEGER NOT NULL,
    effect         TEXT NOT NULL CHECK (effect IN ('include', 'exclude')),
    document_id    INTEGER NOT NULL REFERENCES documents(id),
    to_revision_id INTEGER,
    paragraph      TEXT,
    UNIQUE (entry_id, seq),
    UNIQUE (entry_id, id),
    UNIQUE (document_id, id),
    FOREIGN KEY (document_id, to_revision_id)
        REFERENCES document_revisions (document_id, id),
    CHECK (
        (effect = 'include' AND to_revision_id IS NOT NULL)
     OR (effect = 'exclude' AND to_revision_id IS NULL AND paragraph IS NULL)
    )
) STRICT;

-- Optional provision scope of a ref. No rows = the whole document.
CREATE TABLE cert_basis_ref_provisions (
    ref_id       INTEGER NOT NULL,
    document_id  INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    PRIMARY KEY (ref_id, provision_id),
    FOREIGN KEY (document_id, ref_id) REFERENCES cert_basis_refs (document_id, id),
    FOREIGN KEY (document_id, provision_id) REFERENCES provisions (document_id, id)
) STRICT, WITHOUT ROWID;

-- Revisions skipped by a ref ("23-1 thru 23-38, 23-40" skips 23-39).
CREATE TABLE cert_basis_ref_skips (
    ref_id      INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    PRIMARY KEY (ref_id, revision_id),
    FOREIGN KEY (document_id, ref_id) REFERENCES cert_basis_refs (document_id, id),
    FOREIGN KEY (document_id, revision_id)
        REFERENCES document_revisions (document_id, id)
) STRICT, WITHOUT ROWID;

-- Build-computed expansion of an entry's refs.
CREATE TABLE cert_basis_resolved (
    entry_id             INTEGER NOT NULL,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    via_ref_id           INTEGER NOT NULL,
    paragraph            TEXT,
    PRIMARY KEY (entry_id, provision_version_id),
    FOREIGN KEY (entry_id, via_ref_id) REFERENCES cert_basis_refs (entry_id, id)
) STRICT, WITHOUT ROWID;

CREATE INDEX idx_cbr_version ON cert_basis_resolved (provision_version_id);

-- What an ELOS, special condition or exemption line explicitly cites, read by
-- the tools (docs/SQLITE.md §Citations). Not part of the basis: nothing here
-- feeds cert_basis_resolved. `provision_version_id` is the version to link;
-- NULL when the basis holds the section at several and the line doesn't say.
CREATE TABLE cert_basis_citations (
    id                   INTEGER PRIMARY KEY,
    entry_id             INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    seq                  INTEGER NOT NULL CHECK (seq >= 0),
    document_id          INTEGER NOT NULL,
    provision_id         INTEGER NOT NULL,
    paragraph            TEXT,
    stated_revision_id   INTEGER,
    provision_version_id INTEGER,
    version_basis        TEXT NOT NULL
                         CHECK (version_basis IN
                             ('stated', 'basis', 'basis_several', 'latest')),
    UNIQUE (entry_id, seq),
    FOREIGN KEY (document_id, provision_id)
        REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, stated_revision_id)
        REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (provision_id, provision_version_id)
        REFERENCES provision_versions (provision_id, id),
    CHECK ((version_basis = 'stated') = (stated_revision_id IS NOT NULL)),
    CHECK ((version_basis = 'basis_several') = (provision_version_id IS NULL))
) STRICT;

CREATE INDEX idx_cit_provision ON cert_basis_citations (provision_id);

-- Section-like citations on a line that are not linked, and why.
CREATE TABLE cert_basis_citation_gaps (
    entry_id INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    seq      INTEGER NOT NULL CHECK (seq >= 0),
    cited    TEXT NOT NULL,
    reason   TEXT NOT NULL
             CHECK (reason IN (
                 'doc_not_in_dataset', 'section_not_in_document',
                 'document_undetermined', 'range_not_expanded',
                 'withheld_basis_list'
             )),
    PRIMARY KEY (entry_id, seq)
) STRICT, WITHOUT ROWID;

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
"""
