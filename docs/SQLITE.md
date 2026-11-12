# SQLite contract (`cert_basis.sqlite`)

`cert_basis.sqlite` is the contract between this repo and the
[FARfetched app](https://github.com/DEK-DEBIAN/FARFETCHed). `build.py`
compiles it from the JSON in `data/` (format: [DATA_FORMAT.md](DATA_FORMAT.md)).
The authoritative DDL is `SCHEMA_SQL` in
[certbuild/ddl.py](../certbuild/ddl.py), and changes
between versions are listed in [SCHEMA_HISTORY.md](SCHEMA_HISTORY.md).

Contents: [Consuming](#consuming-the-sqlite-artifact) ·
[Contract metadata](#contract-metadata) · [Documents](#documents) ·
[Aircraft / TCB](#aircraft--tcb-tables) ·
[Certification basis](#certification-basis-three-layers) ·
[Citations](#citations) ·
[Similarity](#similarity) · [latest_versions](#latest_versions-view) ·
[Build pipeline](#build-pipeline)

## Consuming the SQLite artifact

`cert_basis.sqlite` ships as a single file in `journal_mode = DELETE` — no
`-wal`/`-shm` sidecars, so it works from read-only storage. Open it
read-only and check the contract version:

```python
import sqlite3

SUPPORTED_SCHEMA = 7

conn = sqlite3.connect("file:cert_basis.sqlite?mode=ro", uri=True)
conn.execute("PRAGMA foreign_keys = ON")
if conn.execute("PRAGMA user_version").fetchone()[0] != SUPPORTED_SCHEMA:
    raise RuntimeError("cert_basis.sqlite schema version not supported")
```

## Tables

`build.py` compiles the JSON into 25 tables plus one view. Every table but the
FTS5 virtual tables is `STRICT`; every date column is `TEXT` with `CHECK (date(x) IS x)`; every
UNIQUE key is over NOT NULL columns. The authoritative DDL is `SCHEMA_SQL`
in [certbuild/ddl.py](../certbuild/ddl.py).

### Contract metadata

`PRAGMA user_version` is the schema version (currently **13**). It is bumped
on every contract change, and consumers should refuse a DB whose version
they don't know (see [SCHEMA_HISTORY.md](SCHEMA_HISTORY.md)). `build_info`
is a single row: `schema_version`, `git_sha` of the data repo at build time
(NULL if unavailable), `built_at` (UTC).

### Documents

`issuers` — closed set seeded by the build: `code`, `name`, `kind`
(`naa` / `military` / `standards_body`), `country`, `successor_id`.

`documents` — `(issuer_id, doc_kind, code, slug, title)`.

`document_revisions` — `(document_id, designator, ordinal, effective_date,
provenance, provenance_notes)`.

`provisions` — `(document_id, key, number, sort_key, canonical_title,
current_grouping, subject_group)`. `current_grouping` (and
`provision_versions.grouping_at_time`) follow one style in every document,
`Subpart B — Flight`, `Section 7 — Propulsion` or `Appendices`
([Grouping labels](DATA_FORMAT.md#grouping-labels)): group by the label
before ` — ` to join a subpart's names across revisions. `key` is the provision's identity,
unique per document; `number` is the number printed at its latest version
and is **not** unique: a document may have reused it for another provision
(index on `(document_id, number)`). For FAA, CAR and EASA `key = number`.
`sort_key` is computed from `number` (digit runs zero-padded) so §23.175
sorts before §23.1309: `ORDER BY sort_key`. To find "the provision numbered
X" as of a revision, match `provision_versions.number` at that revision, not
`provisions.number`.

`provision_versions` — one row per (provision × revision): `number` (as
printed at that revision; show this, not `provisions.number`, for a
historical version), `text`,
`title_at_revision`, `grouping_at_time`, `publication_cite`, `source_url`,
`provenance`, `provenance_notes`, `same_as_version_id`, `deleted` (1 = the
revision deleted the provision; `text` is NULL exactly when `deleted = 1`),
and the generated `text_missing` flag. A partial unique index stops two
versions printed at one revision from sharing a number (deletions exempt:
the revision that deletes a provision may reuse its number), and the build
checks that at every revision a number names at most one provision in
force. Composite foreign keys through `document_id` make it
impossible to pair a provision with another document's revision, or alias a
version of another provision.

`provision_paragraphs` — a version's text split into blocks by the
[text format](DATA_FORMAT.md#text-format): `provision_version_id`, `seq` (document order),
`depth` (0 = top level, otherwise the number of labels in `path`), `label`
(verbatim, e.g. `(ii)` or `[(4)`; NULL when unlabelled), `path` (e.g.
`(a)(1)(ii)`; for an unlabelled block, its enclosing item's path; NULL at top
level), `section` and `heading`, and `text` (`''` for a label-only block such
as `(c)` in `(c)(1)`). In a text with section headings (rule 7 of the text
format), `section` is the section a block belongs to (`F23.2`; NULL before
the first heading and in texts without one), `heading` is 1 on the heading
block itself (top level, unlabelled), and every path starts with the section
(`F23.2(b)(1)`), so paths stay unique within the version. CHECKs enforce
both.
`kind` is `table` for each line of a table block (rule 8: its `{|` open
line, each row, its `|}` close line), with the markup kept in `text`, and
`text` otherwise. Table rows are unlabelled and carry the path of the item
the table belongs to. A consumer that renders tables groups consecutive
`table` rows from `{|` to `|}` and parses each row with the
[table syntax](DATA_FORMAT.md#tables); one that doesn't can show the rows as
lines and still read every word.
`kind` is `formula` for a display formula line (rule 9: a whole line
`$$ … $$`), with the `$$` marks kept in `text`. A formula row is unlabelled
and carries the path of the item it belongs to.
Any `text` (formula, table row or ordinary block) may hold the
[inline markup](DATA_FORMAT.md#inline-markup) `_{…}` (subscript) and `^{…}`
(superscript). A consumer that shows text renders them (as `<sub>`/`<sup>`)
or removes the markup; never shows it raw to readers by accident.
Every version that has text has rows, aliases and `TEXT MISSING` included; a
flat text is one unlabelled row, so the app has a single rendering path.
`provision_versions.text` keeps the label-line string unchanged. Index on
`(provision_version_id, path)`. Labels must be shown as stored, never
generated: real regulations skip and repeat them.

`version_actions` — rulemaking actions per provision version, ordered by
`seq`.

### Aircraft / TCB tables

`manufacturers` (`name`: the legal TC holder, one per company;
`group_name`: the name to show and group by, shared by companies a user
thinks of as one, e.g. both Gulfstream companies as "Gulfstream"),
`categories` (closed set), `aircraft_models`, `tcds` (`holder`: the holder
exactly as that TCDS prints it, which can differ from the model's
manufacturer and between the TCDS of one model), and
`tcb` — one row per (model, TCDS) pair, owning the cert basis. A model has
one TCB per TCDS that covers it, e.g. the State-of-Design TCDS and a
validating one from another regulator. `tcb_categories` (M:N) holds the
categories as stated on that TCDS; regulators can differ, so categories
belong to the TCB, not the model (v6).

### Certification basis (three layers)

| Table | Grain | Source |
|---|---|---|
| `cert_basis_entries` | one TCDS line | authored, verbatim |
| `cert_basis_refs` (+ `cert_basis_ref_provisions`, `cert_basis_ref_skips`) | one interpretation clause | authored |
| `cert_basis_resolved` | one (entry, provision version) | computed by the build |

`cert_basis_resolved.via_ref_id` names the ref that produced each row and
`paragraph` carries the qualifier (NULL = whole provision). Index on
`provision_version_id` serves "which aircraft use §23.1309 @ 23-62".

### Citations

What ELOS, special condition and exemption lines explicitly cite
([Citations](DATA_FORMAT.md#citations)). These are not part of the basis:
nothing here feeds `cert_basis_resolved`. They are read from the line by a
parser, so show the verbatim line beside them and mark them as computed.

`cert_basis_citations` — one row per citation: `entry_id`, `seq`, `document_id`,
`provision_id`, `paragraph` (as cited; it may not exist in the linked version),
`stated_revision_id` (the amendment the line states), `version_basis` (`stated`,
`basis`, `basis_several`, `latest`) and `provision_version_id`, the version to
link. That is NULL exactly when `version_basis` is `basis_several`: join
`cert_basis_resolved` through the entry's TCB for the versions it holds. Index
on `provision_id` serves "which aircraft cite §23.1309".

`cert_basis_citation_gaps` — section-like citations that are not linked:
`entry_id`, `seq`, `cited` (an exact substring of the line), `reason`.

### Similarity

`provision_similarity` — computed by the build, never authored or
hand-checked: `(provision_id, similar_provision_id, rank, score)`. For each
provision it holds its best matches **in every document** (its own
included): up to `SIMILARITY_TOP_PER_DOCUMENT` (3) per document, `rank` 1 =
best in that document, `score` = cosine similarity × 1000 (an integer, so
rebuilds are byte-stable), and only pairs scoring at least
`SIMILARITY_MIN_SCORE` (0.25 → 250). Rows are directed: B being among A's
matches does not imply the reverse. Present these as computed suggestions,
never as authoritative equivalences.

Method (`certbuild/similarity.py`, stdlib only): one TF-IDF vector per **provision**, not
per version, built from
- the text of its latest version that has text (aliases followed; deleted
  versions and `TEXT MISSING` skipped, so a deleted provision is described by
  its last text; a provision with no usable text gets no rows),
- every title it has carried, each word counted `SIMILARITY_TITLE_WEIGHT` (5)
  times, and its `current_grouping` words once.

Words are lower-cased, stemmed by crude suffix stripping, and stopwords,
numbers, paragraph labels and roman numerals are dropped. A term in more
than `SIMILARITY_MAX_DF` (half) of all provisions is dropped. So is a term in
more than half of one document's provisions (documents of at least
`SIMILARITY_MIN_DOC_SIZE` provisions), for that document only: that is the
document's boilerplate ("airplane", "rotorcraft", a handbook's fixed block
labels), and it would otherwise make every section of the document look
alike. The method needs nothing from a document beyond provisions with text,
so it applies unchanged to documents structured differently from the CFR
(handbooks such as MIL-HDBK-516). `tests/test_similarity.py` holds a golden
set of known equivalents that must rank first; extend it when adding a
document and re-tune the constants against it.

### Search

Full-text search for the app, built last from rows already inserted
(`certbuild/search.py`). FTS5 is required at build time and in the consumer.

- `search_text(title, body)`: `rowid` = `provision_versions.id`, one row per
  version with text of its own. Aliases share their target's row and deleted
  versions have none. A `TEXT MISSING` version has its title and an empty body,
  so it can be found and labelled. `body` is the plain form of `text`
  (`certbuild.text.flat.plain_text`, control characters removed): no table
  marks, `_{ }`, `^{ }` or `$$`, so `VMO` finds `V_{MO}` and a snippet can't
  cut through markup. Porter stemming, `unicode61 remove_diacritics 2`.
- `search_current(version_id)`: the versions holding the current text of each
  provision in force, following an alias to the version with the text. Join it
  to `search_text` to search current text only.
- `search_aircraft(designation, common_name, manufacturer, tcds_number, basis)`:
  `rowid` = `tcb.id`. `manufacturer` is the group name, the manufacturer and
  this TCB's printed holder, each once, joined by newlines, so "Gulfstream",
  "GALP" and every printed spelling find the model. `basis` is the entry's `raw_reference` lines joined by
  newlines. `unicode61 remove_diacritics 2`, no stemming.

The tokenizers split on dots and hyphens, so `25.1309` is the phrase
`"25 1309"`. A consumer must quote user text: unquoted `25.1309`, `foo-bar` or
`(x` are FTS5 syntax errors.

### `latest_versions` view

For each provision, the `provision_versions` row at its highest-ordinal
revision, joined with `designator`, `ordinal` and `effective_date`. For a
deleted provision that row has `deleted = 1`; filter on it to list only
provisions in force.


## Build pipeline

```bash
uv run python build.py                     # reads data/, writes cert_basis.sqlite
uv run python build.py --data-dir X --out Y.sqlite
uv run python build.py --check             # steps 1–2 and the text layout only
```

`build.py` (the steps are `certbuild/pipeline.py`):
1. Validates every JSON file against its schema. Fails on any mismatch.
2. Checks every document/provision path against the identity fields inside,
   and parses every version text by the [text format](DATA_FORMAT.md#text-format).
   Path and text faults are listed together.
3. Seeds the closed lookup sets (`issuers`, `categories`).
4. Inserts documents and revisions, then provisions, versions, actions and
   paragraphs. Fails if a version names an undeclared revision or a duplicate
   one, if the top-level `number` is not the latest version's, or if an
   alias doesn't point at an earlier, non-deleted version of the same
   provision, or a deletion doesn't follow a version in force (every such
   file is listed). Then fails if a number names two provisions in force at
   some revision.
5. Computes `provision_similarity` (see [Similarity](#similarity)).
6. Inserts aircraft, TCDS (once each, metadata must agree), TCBs and
   entries; inserts each entry's refs, resolves them by the
   [resolution rules](DATA_FORMAT.md#resolution-rules), and checks
   paragraph qualifiers. Then, per TCB, resolves its
   [citations](DATA_FORMAT.md#citations). Fails listing every unresolved
   reference, unresolved citation and TCDS metadata conflict.
7. Fills the [search](#search) tables. Then fails on any date after the build
   day, and on any foreign-key violation.
8. Writes `cert_basis_report.json` alongside the SQLite file: row counts for
   every table but FTS5's shadow tables, `documents` (per `ISSUER/slug`: revisions, provisions,
   versions, and `renumbered` = provisions with a version printed under
   another number), `text_missing` and `deleted` counts, provenance counts,
   `structured_versions` / `flat_versions` / `label_gaps`,
   `paragraph_refs_verified` / `paragraph_refs_unverifiable`, `similarity`
   (provisions with matches and score bands), `search` (`text_rows`,
   `title_only_rows`, `current_rows`, `aircraft_rows`), `coverage` (below), `citations`
   (below), `promotion` (the
   tools commit behind each tree, from `data/promotion.json`), `source_checks` (per
   document, when its upstream listing was last read, or null if no check covers
   it; this says nothing about the text), `git_dirty` /
   `git_dirty_paths` (see below), and `unresolved_references` (always empty
   on a successful build).

`coverage` shows how much of each certification basis has references at all,
which `unresolved_references` can't: an entry with `references: []` never counts
as unresolved. `entries` gives `entries`, `with_references` and
`without_references` per issuer and `entry_type`. `tcbs` (per issuer) and `models`
give `total` and `resolve_to_nothing`, and `models_resolving_to_nothing` lists
those models. These figures say whether references exist, not whether they are
right: a model with references can still point at the wrong provision.

`citations` counts what the citation parser read: `by_issuer_and_type` (`entries`,
`entries_with_citations`, `entries_with_gaps`, `citations`, `gaps`),
`version_basis`, `gaps_by_reason`, `entries_withheld` and `paragraphs`
(`verified`, `unverifiable`, `unmatched`, `unchecked`). Like `coverage`, these
figures say how much was read, not whether it is right.

`build_info.git_sha` records HEAD of the repo holding `data/`. It doesn't
say whether the build also read uncommitted files. The report does:
`git_dirty` is `true` when anything under `data/` is modified, added or
untracked, with the repo-relative paths in `git_dirty_paths`; `false` when
clean; `null` when `data/` isn't in a git work tree. A dirty build also
prints a warning. This is deliberately report-only, not part of the SQLite
contract: a DB to ship should be built from a committed tree.

Every constraint violation fails the build with the offending file named.
Output is atomic: the build writes `cert_basis.sqlite.new` and
`cert_basis_report.json.new` in full, then `os.replace()`s the DB and then
the report into place, removing any stale `-wal`/`-shm` sidecars. A failed
write leaves the previous pair untouched.

Each step lists every fault it finds and the build stops after the first
step that has any (`certbuild/errors.py`).

`--check` runs steps 1 and 2 (the same code as the build), without writing
anything. Checks that need the whole tree in a database (revisions,
aliases, references, dates, foreign keys) only run in a full build.

