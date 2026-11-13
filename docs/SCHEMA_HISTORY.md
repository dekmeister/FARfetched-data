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
| 11 | 2026-11-10 | `61e557d` | `cert_basis_citations` and `cert_basis_citation_gaps`: the sections an ELOS, special condition or exemption line explicitly cites ([Citations](DATA_FORMAT.md#citations)), with optional `citations` and `citation_gaps` on those entries. Separate from `references` so a deviation can name a section without making it part of the basis (ROADMAP-4). The version to link is computed by the build and `version_basis` records why, because a cited section may be in the basis at one version, at several, or not at all. |
| 12 | 2026-11-11 | `39a4ca2` | `search_text`, `search_current` and `search_aircraft`: FTS5 full-text search ([Search](SQLITE.md#search)). Inside `cert_basis.sqlite` rather than a second file because index rows point at `provision_versions.id`, which changes on every build, and two files can't be swapped atomically. An ordinary FTS5 table over plain text costs about 33 MB against 12 MB for contentless or external-content, and buys `snippet()` and correct matching of subscripted symbols (`VMO` for `V_{MO}`). |
| 13 | 2026-11-13 | | Three manufacturer names: `tcds.holder` (as each TCDS prints it; JSON `tcb[].tcds.holder`), the legal holder (`manufacturers.name`, unchanged) and `manufacturers.group_name` (JSON `manufacturer_group`), a display name shared by companies a user thinks of as one, legally separate ones included. `search_aircraft.manufacturer` holds all three. Before this, the printed holder was dropped at assemble and the app could only list legal names (or hard-code aliases). A column rather than a groups table: the group has no attributes, and one value per manufacturer is checked by the build. Grouping by name matching was rejected: in the 738 current catalogue holders most same-first-word families are unrelated companies ("American …", "Dornier Luftfahrt" / "Dornier Seawings"), so every group is a reviewed row (design proposal removed from reviews/ once built; in git history). |
| 14 | 2026-11-13 | | `deviations`, `deviation_citations` and `deviation_citation_gaps`, from new JSON files `data/deviations/{issuer}/{key}.json` ([Deviation file](DATA_FORMAT.md#deviation-file-datadeviationseasa120960json)): special conditions, ELOS/ESF, exemptions and deviations as link-only records, with the sections their title or identifier names. EASA's consulted publications first; FAA later. A separate entity rather than documents and provisions: they are one-off (no revision series), and most are letters or scans that can't meet the rule that every provision version has text; one-provision documents would also crowd the documents list, search and similarity. `doc_kind` loses `special_condition`, `elos` and `exemption`, reserved for this and never used. A citation links the provision, not a version, because a record states no amendment (design proposal removed from reviews/ once built; in git history). |
| 15 | 2026-11-13 | | FAA deviation records (DRS ELOS, special conditions final and proposed, certification-relevant exemptions). `deviations` gains `applicant`, `make`, `model`, `regulation_ref`, `disposition` (as listed, verbatim, NULL when not) and `final_id` (a proposed record → the final it became, CHECK `stage = 'proposed'`); `title` becomes nullable because DRS lists no subject for exemptions, and a placeholder title would be text the source doesn't print. Citations and gaps may now come from `regulation_ref`, which for FAA is the structured DRS field and names far more sections than titles do. Columns rather than a key-value table: each is one printed listing field, and the app shows them. `final_id` is computed (shared docket, agreeing titles), since DRS's own Special Condition Reference field is empty on every record (design proposal removed from reviews/ once built; in git history. D2, D3). |

The `NATO` issuer (STANAG 4671 / AEP-4671) was added on 2026-11-06 without a
version bump: it is one more row in the closed `issuers` set and one more value
of the `issuer` enum, and nothing a reader of v7 depends on changes.

Grouping values took one style on 2026-11-12, also without a version bump
([Grouping labels](DATA_FORMAT.md#grouping-labels), GitHub #19):
`Subpart B — Flight`, `Subpart C — Reserved`, `Section 7 — Propulsion`,
`Appendices`. Before it, FAA values were names only (`Flight`, `Appendix`,
`Reserved`), EASA's were title-cased (`Design And Construction`), NATO's used
an en dash, MIL-HDBK-516's read `7. PROPULSION`, and CAR's held the finer
heading with the subpart in `subject_group`. No table, column or type
changed, and the app's code reads the new values unchanged; a bump would
only have forced an app release. The rule is enforced by the build
(`check_groupings`), not the JSON Schema, so it lives in one place. Group
links in the app keyed on the old values (`?open=Powerplant`) stop matching.

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
- **A shared basis is copied per model (no version change).** When one TCDS
  block applies to several models (the 737-600/-700/-800 basis, a "Data
  Pertinent to all Models" section), each model's TCB holds its own copy of
  the lines that apply to it, with the verbatim `raw_reference`, and
  `display_order` stays 1..N per TCB. TCDS scope lines individually ("For
  737-400 and 737-500 only", "Additional cert basis items for 737-800BCF"),
  so a shared-basis object would need per-line model masks and per-model
  overrides anyway, at the cost of a contract change and an app release, and
  one record per section can't hold different amendment levels per model
  (737 MAX Table A-1). Copying needs no change to the JSON or SQLite
  contract. The model is the TCDS's section-heading designation; customer
  codes and configurations are not models. (reviews/2026-11-10
  multi-model TCDS proposal, Decisions 1 and 2.)
- **Similarity is computed, not authored (v5).** It suggests related
  provisions. Hand-confirmed relations (`provision_relations`) remain
  deferred: see ISSUES.md `ROADMAP-`.
