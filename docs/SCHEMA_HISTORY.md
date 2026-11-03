# Schema history and design rationale

How the data contract got to where it is. The contract itself is in
[DATA_FORMAT.md](DATA_FORMAT.md) (JSON) and [SQLITE.md](SQLITE.md) (SQLite).
`SCHEMA_VERSION` in [build.py](../build.py) is written to
`PRAGMA user_version` and `build_info.schema_version`, and is bumped on every
change to the SQLite contract.

## Versions

| Version | Date | Commit | Change |
|---|---|---|---|
| 1 | 2026-10-31 | `7569c83` | Generic issuer → document → revision → provision model, and the three-layer cert basis (entries, refs, resolved). Came out of the [2026-10-31 schema review](../reviews/2026-10-31-db-schema/). |
| 2 | 2026-10-31 | `bf2d14a` | `deleted: true` versions and `provision_versions.deleted`, added for EASA CS-23 Amdt 5, where every old-numbered paragraph is deleted. |
| 3 | 2026-11-01 | `402cd00` | Label-line paragraph text ([Text format](DATA_FORMAT.md#text-format)) and the `provision_paragraphs` table. |
| 4 | 2026-11-02 | `a429789` | `manual` dropped from the `provenance` enum and CHECKs: `data/` is built from source. |
| 5 | 2026-11-03 | (uncommitted at the time of writing) | `provision_similarity`, computed by the build ([Similarity](SQLITE.md#similarity)). |

## Changes in the v1 schema

The 2026-10-31 review replaced the first, regulation-only format. These names
and fields went away in that change:

- `title_number` + `part` became `documents.code` (`"14 CFR 23"`), so a CAR
  or a CS fits the same column.
- The `"Initial Adoption"` placeholder `publication_cite` was removed. The
  cite is optional, and the schema rejects that sentinel.
- `CAA (FAA)` became issuer `CAA`, with successor `FAA` recorded in the
  `issuers` table.
- References name designators, not ordinals, and have no `from`: "as amended
  by 23-1 thru 23-38" always includes the base revision.

The review's [README](../reviews/2026-10-31-db-schema/README.md) records
what was implemented, what changed from the proposal, what was rejected
(per-revision actions) and what was deferred.

## Standing design decisions

- **No `status` column on versions.** Every provision version has real text
  (or is a deletion or an alias). An aircraft that cites an untranscribed
  revision can't be added until that revision is transcribed, so the app
  never shows a cert basis with placeholder text. `TEXT MISSING` covers a
  different case: a pair the source manifest says exists but whose source is
  unreadable. It stays a loud, searchable gap. (Schema review 02-proposal,
  design constraints; 04-open-questions Q-03.)
- **Actions stay per provision version** (`version_actions`), not per
  revision. DRS records them per section, and the per-section lists for one
  amendment don't always agree. (Schema review F-06/P-05, rejected.)
- **Flat document paths.** Issuer, document and provision number are the
  only stable parts of a citation. Grouping (subpart) and the CFR title are
  fields, so a re-subparted provision keeps its file.
- **Resolution within one TCDS line.** Overrides never cross cert-basis
  entries, so two serial ranges may hold one provision at different levels.
- **DELETE journal mode.** The shipped DB is a single read-only file with no
  `-wal`/`-shm` sidecars (schema review F-21).
- **Build from source (v4).** `data/` is an output of `tools/`. A correction
  is an override row with evidence, never a hand edit, so there is no
  `manual` provenance.
- **Similarity is computed, not authored (v5).** It suggests related
  provisions. Hand-confirmed relations (`provision_relations`) remain
  deferred: see ISSUES.md `ROADMAP-`.
