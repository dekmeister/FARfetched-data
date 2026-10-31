# 01 — Findings

Severity:
- **High:** produces wrong data, or blocks planned work.
- **Medium:** an integrity or fail-loud gap that will bite later.
- **Low:** hygiene.

Line numbers refer to `build.py` at commit `20d6289`. Queries can be run
against a freshly built `cert_basis.sqlite`. They are collected in
[checks.sql](checks.sql).

## Summary

| ID | Sev | Area | Finding |
|---|---|---|---|
| F-01 | High | cert basis | One TCDS line is exploded into N rows, so the stated interpretation is lost |
| F-02 | High | cert basis | "Except" / override clauses resolve to two versions of the same section |
| F-03 | High | cert basis | Non-contiguous amendment sets ("23-1 thru 23-38, 23-40") are not representable |
| F-04 | High | extensibility | Model is CFR-specific (part/section/amendment/FR cite) |
| F-05 | High | extensibility | Special conditions / ELOS / exemptions can't be resolution targets |
| F-06 | Medium | normalisation | Rulemaking actions are stored per section, but they are per amendment |
| F-07 | Medium | sentinels | `'Initial Adoption'` in `federal_register_cite`; `'TEXT MISSING'` has no derived flag |
| F-08 | Medium | integrity | Cross-part pairings are enforced only in Python, not in the DB |
| F-09 | Medium | integrity | `UNIQUE (authority_id, title_number, part)` with a nullable `title_number` |
| F-10 | Medium | fail-loud | `_insert_cb_row` swallows `IntegrityError` |
| F-11 | Medium | fail-loud | Range references never checked against `amendments`; `from_amendment_ordinal` ignored |
| F-12 | Medium | fail-loud | `INSERT OR IGNORE INTO tcds` silently discards conflicting TCDS metadata |
| F-13 | Medium | fail-loud | Unknown category / authority codes silently become new lookup rows |
| F-14 | Medium | types | No type or date enforcement; 36 action dates are in the 2060s |
| F-15 | Medium | authoring | Range references use ordinals, single references use designators |
| F-16 | Medium | authority | Authority codes such as `"CAA (FAA)"` mix identity with succession |
| F-17 | Medium | extensibility | Sections are flat; paragraph-level citations can't be expressed |
| F-18 | Medium | extensibility | Designator regex rejects AC / MIL-HDBK / EASA designators |
| F-19 | Low | indexes | Two redundant indexes, two missing FK indexes, one low-selectivity index |
| F-20 | Low | contract | No schema version or build metadata in the DB |
| F-21 | Low | deploy | WAL mode on a read-only distributed artifact |
| F-22 | Low | semantics | `latest_amendments` has no notion of repeal / `[Reserved]` |
| F-23 | Low | provenance | `provenance` is validated in JSON but dropped by the build |
| F-24 | Low | aircraft | TCDS ↔ model shape: one revision per TCDS, no serial applicability, basis duplicated per model file |
| F-25 | Low | docs | `plan.md` / `README.md` / `CLAUDE.md` have drifted from `build.py` |
| F-26 | — | data | Data defects seen during the review (not schema issues) |

---

## F-01 — One TCDS line is exploded into N rows (High)

`cert_basis_entries` is both "a line on the TCDS" and "one resolved section
version". `_expand_and_insert_entry` (`build.py:595`) inserts one row per
resolved `section_amendment` and copies `entry_type`, `raw_reference`,
`applicability_notes` and `display_order` into each row.

Evidence: the Cessna 172 basis has 2 TCDS lines. The DB has 22 rows, 21 of
which carry the same `raw_reference`.

```sql
SELECT display_order, count(*) FROM cert_basis_entries GROUP BY 1;
-- 1|21
-- 2|1
```

Consequences:
- `display_order` cannot be unique, so duplicate or misnumbered TCDS lines
  aren't caught.
- The interpretation (range, from/to, document) is not stored. The DB can't
  reproduce "the cert basis as the TCDS states it". Only the expansion is
  there, and the expansion depends on how much of the part has been
  transcribed at build time.
- The CSV/JSON export in `plan.md` ("same schema as data repo") can't be
  reconstructed from the DB.

This is the classic mistake of mixing two entities with different grain in
one table.

## F-02 — "Except" / override clauses double-resolve (High)

`plan.md` presents `single` as the way to express per-section exceptions
("through 25-62 except §25.1309 at 25-58"). The build has no override logic.
The range branch (`build.py:625`) resolves §25.1309 to its latest version
≤ 25-62, and the single branch (`build.py:607`) adds §25.1309 @ 25-58. Both
rows are inserted. The consumer sees two certification levels for one
section with nothing to say which wins.

Real cases (from `TODO.md`, Cessna 525 TCDS): "Part 23 … thru 23-38, 23-40;
except the following paragraphs …: 23.611, 23.777, … as amended through
23-54", and "23.1309(a) as amended through 23-62, for PED tolerance only".
The second case is a legitimate *additional* level that applies to one
paragraph only. It is not an override. So "override" and "additional
paragraph-scoped" need different semantics (see P-06).

## F-03 — Non-contiguous amendment sets (High)

"Amendments 23-1 thru 23-38, 23-40" excludes 23-39. A range is one
`(from, to)` pair, and expansion uses only `to` (F-11). If 23-39 is the
latest change to a section ≤ 23-40, the build resolves that section to
23-39, which is the wrong text. Two ranges don't help either, because each
range resolves independently and they double-resolve as in F-02.

## F-04 — Model is CFR-specific (High, extensibility)

Table and column names encode CFR terms: `regulation_parts.part`,
`title_number`, `regulations.section`, `current_subpart`,
`amendments.designator` (format `^[A-Za-z0-9]+-[0-9]+$`) and
`federal_register_cite`. The underlying concepts are generic:

| Concept | 14 CFR | EASA | AC | MIL-HDBK-516 |
|---|---|---|---|---|
| Issuer | FAA | EASA | FAA | US DoD |
| Document | Part 23 | CS-25 | AC 25.1309 | MIL-HDBK-516 |
| Revision | Amdt 23-62 | Amendment 27 | -1A | Rev C |
| Provision | §23.1309 | CS 25.1309 | ¶ 5.a | 4.1.1.1 |
| Publication cite | 35 FR 5665 | ED Decision 2023/021/R | — | — |

Adding ACs or MIL-HDBK-516 to the current tables means either putting
"AC 25.1309" in a column called `part`, or adding parallel table families
(`ac_documents`, `ac_revisions`, …). Parallel families break every
cross-document query (comparison, "what references §25.1309").

Also: `naa_authorities` can't hold the US DoD, SAE or RTCA under its name.

## F-05 — SC / ELOS / exemptions can't be resolution targets (High)

`cert_basis_entries.section_amendment_id` can only point at regulation
text. Special conditions are on the roadmap ("Extend to parse and scrape
special conditions", `TODO.md`), as are ELOS and exemptions. The tempting
fix, `target_type TEXT, target_id INTEGER`, is the polymorphic-association
anti-pattern: no FK enforcement, and no joins without CASE. The proposal
avoids it by making those documents of their own kind (P-01, P-06).

## F-06 — Actions stored per section, not per amendment (Medium)

`amendment_actions` hangs off `section_amendments`. The data shows every
amendment has exactly the same actions on all its sections:

```sql
SELECT a.designator, count(DISTINCT sa.id) AS sections,
       count(DISTINCT aa.type||'|'||ifnull(aa.reference,'')||'|'||ifnull(aa.issued_on,'')) AS distinct_actions
FROM amendment_actions aa
JOIN section_amendments sa ON sa.id = aa.section_amendment_id
JOIN amendments a ON a.id = sa.amendment_id
GROUP BY 1;
-- 23-0|15|2   23-7|5|2   23-34|7|2   23-50|6|2   ... (all ≤ 2)
```

That's 100 rows holding about 36 facts. Duplicated facts drift (one section
gets a corrected NPRM date and the others don't). Same reasoning as
`effective_date` living on `amendments`.

Caveat for the implementer: before moving the data, confirm that
`tools/regulations/*` never produces actions that legitimately differ per
section. The build should fail if per-section actions for one amendment
disagree during the transition (see 03-migration-plan Phase 1).

## F-07 — Sentinels in data columns (Medium)

- `federal_register_cite = 'Initial Adoption'` (8 rows). That's a sentinel
  in a citation column. It's also redundant: "initial adoption" is already
  `amendments.ordinal = 0`.
- `text = 'TEXT MISSING'` is a deliberate repo rule and is **not**
  challenged here. But it has no derived flag. Consumers have to
  string-compare, and a future FTS5 index would index the sentinel. A
  generated column keeps the rule and makes it queryable (P-03).

## F-08 — Cross-part integrity only in Python (Medium)

`section_amendments (regulation_id, amendment_id)` has two independent FKs.
Nothing in the DB stops a row that pairs a Part 23 section with a Part 25
amendment. `_resolve_alias_amendments` prevents it at build time, but the
build is meant to be the last line of defence, not the only one. The same
goes for `same_as_designator`: it's free text, not an FK, and isn't
constrained to the same section. A composite FK through `part_id` /
`document_id` enforces this in the schema (P-03).

## F-09 — Nullable column in a UNIQUE key (Medium)

`regulation_parts`: `title_number INTEGER` (nullable, `build.py:41`) with
`UNIQUE (authority_id, title_number, part)` (`build.py:44`). SQLite treats
NULLs as distinct, so two `(EASA, NULL, 'CS-25')` rows would both be
accepted. Also:
- `_part_id()` (`build.py:338`) looks up by `(authority, part)` only and
  ignores `title_number`.
- `resolved_references[].title_number` is required by the aircraft schema
  but never read by the build. A wrong value passes silently.

## F-10 — `IntegrityError` swallowed (Medium)

`_insert_cb_row` (`build.py:591`): `except sqlite3.IntegrityError: pass`.
That directly contradicts "fail loud on any … duplicate key". Today there's
no UNIQUE on `cert_basis_entries`, so the handler only hides FK and CHECK
failures. Once F-01 adds uniqueness, it would hide duplicates as well.

## F-11 — Range references not validated (Medium)

`README.md` build step 6: "Fails if a range references an amendment not
present in the data." This isn't implemented. The range branch
(`build.py:625-648`):
- never checks that `from_amendment_ordinal` / `to_amendment_ordinal`
  exist in `amendments`. A typo `to: 620` resolves to "latest of
  everything" without error.
- never reads `from_amendment_ordinal`.
- never checks `from <= to`.
- `if sa_id is None: continue` (`build.py:642`). Silently skipping a
  section with no version ≤ `to` is correct (the section didn't exist
  yet). But combined with the missing ordinal check, it means a bad range
  can produce an empty or partial expansion with no error.

## F-12 — Conflicting TCDS metadata silently discarded (Medium)

`INSERT OR IGNORE INTO tcds` (`build.py:678`) is keyed on
`(authority_id, tcds_number)`. One TCDS covers many models (3A12 covers the
172 family). When a second model file declares the same TCDS with a
different `revision`, `revision_date` or `source_url`, the first one wins
silently.

## F-13 — Lookup values invented silently (Medium)

- `_upsert_category` (`build.py:299`): unknown codes get `code.title()` as
  the name. `categories` has no enum in `aircraft_model.schema.json`, so
  `"nromal"` creates a new category.
- `_upsert_authority` (`build.py:277`): an unknown code falls back to
  `(code, None)`. This is partly masked by the schema enum, but the enums
  differ: aircraft allows only `FAA`, while regulations allow four values.

Closed sets should be closed in both the schema and the build.

## F-14 — No type or date enforcement (Medium)

`DATE` isn't a SQLite storage class. It gets NUMERIC affinity and nothing
checks the format. `amendment_actions.issued_on` is `TEXT` with a regex in
JSON only (`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`, which accepts `2026-13-45`).

Evidence:
```sql
SELECT count(*) FROM amendment_actions WHERE issued_on > date('now');  -- 36
SELECT issued_on FROM amendment_actions WHERE issued_on > date('now') LIMIT 3;
-- 2064-03-25, 2064-09-28, 2067-04-05
```
These are two-digit-year parsing errors upstream (see F-26). `STRICT`
tables, `CHECK (date(x) = x)`, and a plausibility check would have rejected
them.

## F-15 — Ordinals in authored data (Medium)

Range references use `from_amendment_ordinal` / `to_amendment_ordinal`,
while single references use `amendment_designator`. The TCDS cites
designators, and the ordinal is an internal sort key on `_part.json`.
Authors (and `tools/aircraft/faa_tcds.py`) shouldn't have to translate.
The drift is already visible: the 172's `raw_reference` says "23-0 through
23-13" while `from_amendment_ordinal` is `1`.

## F-16 — Authority codes mix identity with succession (Medium)

`"CAA (FAA)"`, `"CAB (FAA)"`: the code encodes "who issued it" plus "who
is responsible now" in one string with spaces and parentheses. It's used
as a JSON enum value and as a directory name (`data/regulations/faa/car-3`
lives under `faa/` even though its authority is `CAA (FAA)`). Model it as
separate issuers with a `successor_id` (P-01).

## F-17 — Flat sections; no paragraph qualifier (Medium)

- MIL-HDBK-516 is hierarchical (4 → 4.1 → 4.1.1 → 4.1.1.1). EASA AMC is
  numbered against the CS paragraph.
- TCDS cite paragraphs (`23.1309(a)`, `23.1305(c)(2)(5)`). There's nowhere
  to record the paragraph, so it's lost after `raw_reference`.

Modelling every paragraph as a row isn't proposed (text is stored per
section, and paragraphs are re-lettered between amendments). P-04 adds an
optional `parent_id` for documents that really are hierarchical, and P-06
adds a verbatim `paragraph` qualifier on references.

## F-18 — Designator regex too narrow (Medium)

`^[A-Za-z0-9]+-[0-9]+$` (all three schemas) rejects `AC 25.1309-1A`,
`MIL-HDBK-516C`, `Amendment 27`, `CS-25 Amdt 27`, `ED Decision 2023/021/R`.
`(document, designator)` uniqueness plus `ordinal` already give identity
and order, so the regex should be per document kind or removed.

## F-19 — Indexes (Low)

- Redundant: `idx_sa_reg (regulation_id)` (`build.py:80`) is the leading
  column of `UNIQUE (regulation_id, amendment_id)`.
  `idx_amendments_part_ordinal` (`build.py:81`) duplicates
  `UNIQUE (part_id, ordinal)`.
- Missing: `section_amendments (amendment_id)` ("all sections changed by
  23-62"), and `cert_basis_entries (section_amendment_id)` ("which aircraft
  use §23.1309 @ 23-62", the reverse lookup the app will want).
- Low selectivity: `idx_actions_type` (about 10 distinct values).

## F-20 — No contract version in the DB (Low)

The DB is a cross-repo contract (consumed by FARFETCHed from a GitHub
release), but it carries no schema version, git SHA or build time. The app
can't refuse a DB it doesn't understand, and a bug report can't be traced
to a data commit. Use `PRAGMA user_version` plus a one-row `build_info`
table (P-08).

## F-21 — WAL on a read-only artifact (Low)

`build.py:782` sets `journal_mode = WAL`, as required by `CLAUDE.md`.
Readers of a WAL database need write access to create or update `-shm`.
Opening it on read-only media fails unless the `-shm` file already exists
or the connection uses `immutable=1`. For a file that's built once and
read many times, `journal_mode = DELETE` plus readers opening
`file:cert_basis.sqlite?mode=ro` (or `immutable=1`) is simpler and has no
sidecar files. **Conflicts with a stated repo rule. Maintainer decision
(Q-05).**

## F-22 — No repeal semantics (Low)

`latest_amendments` returns the highest-ordinal row per section. A section
that was removed or reserved (most of old Part 23 at 23-64, the 2017
rewrite) will show its last text as "latest" forever. Range expansion has
the same problem: a range "through 23-64" would include sections that 23-64
removed. Needs a representation before 23-64 is ingested (Q-03).

## F-23 — Provenance dropped by the build (Low)

`provenance.source` (`scraped` / `ocr` / `manual`) is validated in JSON but
not written to the DB. OCR'd text is the kind of thing a public reader
should be able to see, and the app can't show it.

## F-24 — TCDS ↔ model shape (Low, design)

- `tcds` holds one revision per TCDS number. Fine for now, but the
  revision is a property of where the data came from, not of the TCDS's
  identity.
- No structured serial-number applicability. `TODO.md` item 1 needs it:
  "525-0600 thru 525-0684 …".
- One file per *model*, while one TCDS defines the basis for many models
  (3A12 covers 172, 172A … 172S). Shared basis lines get copied into each
  model file, and they drift.

## F-25 — Documentation drift (Low)

- `plan.md` schema: `federal_register_cite NOT NULL`,
  `title_number NOT NULL`, no `amendment_actions`, no `same_as_designator`.
  None of that matches `build.py`.
- `README.md` says "twelve tables". There are 13. It doesn't document
  `same_as_designator` (column or JSON field).
- `CLAUDE.md` says the build emits `build_report.json`. `build.py:805`
  writes `cert_basis_report.json`.
- `README.md`, aircraft schema: `authority` enum is `["FAA"]`, while
  regulation schemas allow `EASA` etc.

## F-26 — Data defects observed (not schema issues; for tools/)

- 36 `actions[].issued_on` values in 2064–2067 (two-digit year → 20xx).
  Source: whatever parses DRS NPRM/final-rule dates in
  `tools/regulations/faa/`.
- `data/aircraft/cessna-aircraft-company/172.json`:
  `from_amendment_ordinal: 1` vs `raw_reference` "23-0 through 23-13".
- 41 of 89 `section_amendments` have NULL `federal_register_cite` (known,
  `TODO.md` "FR cite drop").
- §23.1201 @ 23-62 has two `type: "other"` actions with no reference or
  date: one with `notes: "-"` (a parse placeholder) and one with
  `notes: "Amendment 23-62, Published 12/2/2011"`. The publication date is
  a fact about the revision, not an action, and the `"-"` row is noise.
- `data/regulations/faa/25/` exists but is empty.
