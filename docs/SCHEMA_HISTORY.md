# Schema history and design rationale

How the data contract got to where it is. The contract itself is in
[DATA_FORMAT.md](DATA_FORMAT.md) (JSON) and [SQLITE.md](SQLITE.md) (SQLite).
`SCHEMA_VERSION` in [certbuild/ddl.py](../certbuild/ddl.py) is written to
`PRAGMA user_version` and `build_info.schema_version`, and is bumped on every
change to the SQLite contract.

## Versions

| Version | Date | Commit | Change |
|---|---|---|---|
| 1 | 2026-10-31 | `7569c83` | Generic issuer → document → revision → provision model, and the three-layer cert basis (entries, refs, resolved). Came out of the 2026-10-31 schema review (`reviews/2026-10-31-db-schema/`, removed; in git history at `a65ac16`). |
| 2 | 2026-10-31 | `bf2d14a` | `deleted: true` versions and `provision_versions.deleted`, added for EASA CS-23 Amdt 5, where every old-numbered paragraph is deleted. |
| 3 | 2026-11-01 | `402cd00` | Label-line paragraph text ([Text format](DATA_FORMAT.md#text-format)) and the `provision_paragraphs` table. |
| 4 | 2026-11-02 | `a429789` | `manual` dropped from the `provenance` enum and CHECKs: `data/` is built from source. |
| 5 | 2026-11-03 | `77bfeba` | `provision_similarity`, computed by the build ([Similarity](SQLITE.md#similarity)). |
| 6 | 2026-11-03 | `e7ee945` | Aircraft `categories` move from the model to each `tcb`; `model_categories` becomes `tcb_categories`. Needed to hold FAA and EASA bases on one model. |
| 7 | 2026-11-04 | `b29f1bd` | Provision `key` (identity, file name) separated from the printed `number`; optional per-version `number` and `provision_versions.number`; `UNIQUE (document_id, number)` dropped. Cert-basis `provisions` are printed numbers read at the ref's `to`. Issuer `DOD`. Needed for MIL-HDBK-516, which reuses and renumbers paragraph numbers between editions. |
| 8 | 2026-11-06 | `a6cfe23` | Section headings in label-line text (rule 7): a top-level `Sec. F23.2 …` line closes every open level, and labels restart under it. `provision_paragraphs` gains `section` and `heading`, and paths inside a section carry its number (`F23.2(b)(1)`). Needed for FAA appendices assembled from their DRS sections, whose `(a)…` runs restart per section (GitHub #11). |
| 9 | 2026-11-07 | `5fcc9c5` | Tables in label-line text (rule 8, [Tables](DATA_FORMAT.md#tables)): a `{|` … `|}` block with one row per line, `!`/`|` cells and `{rN cM}` spans. `provision_paragraphs` gains `kind` (`text`/`table`). Before this, every extractor flattened tables into a run of words and numbers (GitHub #9, the 14 CFR 29 Appendix E HIRF tables). Markup inside `text` rather than a separate `tables` field: `text` stays the one source of the words, rows are lines so the app's line diff keeps working, spans are needed for two-level headers, and a flat form (` |- ` between rows) lets an override row hold a whole table on one line. |
| 10 | 2026-11-08 | `41e0701` | Inline markup in label-line text ([Inline markup](DATA_FORMAT.md#inline-markup), rule 9): `_{…}` subscripts, `^{…}` superscripts, and `$$ … $$` display formula lines. `provision_paragraphs.kind` gains `formula`. Before this, every extractor flattened notation into words (`VA`, `tmax`, a stacked fraction read in row order: `πV ω = 2V A`; GitHub #4, CS-25 25.331). Linear markup rather than TeX or MathML: the raw text stays readable, the build and the app each need only a small strict parser, and nothing new is a dependency. The markup encodes meaning; presentation is the app's. Similarity uses the plain form. Also in v10: roman section headings (rule 7, `I. General.` … `IX.`) in label-line text, so paths of the helicopter IFR appendices (CS-27/29, FAA 27/29 Appendix B) read `IV(b)(1)`; no table change (GitHub #17). |
| 11 | 2026-11-10 | pending | `cert_basis_citations` and `cert_basis_citation_gaps`: the sections an ELOS, special condition or exemption line explicitly cites ([Citations](DATA_FORMAT.md#citations)), with optional `citations` and `citation_gaps` on those entries. Separate from `references` so a deviation can name a section without making it part of the basis (ROADMAP-4). The version to link is computed by the build and `version_basis` records why, because a cited section may be in the basis at one version, at several, or not at all. |

The `NATO` issuer (STANAG 4671 / AEP-4671) was added on 2026-11-06 without a
version bump: it is one more row in the closed `issuers` set and one more value
of the `issuer` enum, and nothing a reader of v7 depends on changes.

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

The review's README (in git history) records
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
- **One model, several TCDS; categories per TCB (v6).** A model is one type
  design under one TC lineage. The State-of-Design TCDS gives its identity
  (manufacturer, designation, file path); a validating TCDS from another
  regulator is a further `tcb`. A category is a regulator's statement (FAA
  "Normal", EASA "CS-23 Normal" or "Large Aeroplanes"), so it lives on the
  TCB. Two TCDS are linked to one model only by a reviewed link row with
  evidence, never by name: the same designation can be a different type
  design (DA 62 under A57CE, Diamond GmbH, and under A00012NY, Diamond Inc).
- **A number is a label; the key is the identity (v7).** A provision is one
  requirement followed through the revisions, and its `key` never changes.
  The printed number is recorded per version, because a document may reuse
  a number for an unrelated requirement (MIL-HDBK-516 4.1.3, 516 vs 516A) or
  renumber one that carries on (516B 5.2.3 → 5.2.2 at Change 1). A TCDS
  cites printed numbers, so references stay numbers and are read at their
  revision. Deciding that two editions' paragraphs are one requirement is a
  reviewed tools decision (`tools/overrides/dod_hdbk.tsv`); merges, splits
  and links between provisions remain deferred (ISSUES.md `ROADMAP-4`).
- **Similarity is computed, not authored (v5).** It suggests related
  provisions. Hand-confirmed relations (`provision_relations`) remain
  deferred: see ISSUES.md `ROADMAP-`.
