# 02 — Proposal

The target DDL is in [proposed_schema.sql](proposed_schema.sql). This file
explains it. Each `P-nn` lists the findings it addresses.

Design constraints carried over unchanged from the repo rules: JSON is the
source of truth; SQLite is a disposable build output; stdlib `sqlite3`, no
ORM; `build.py` stays a single file; fail loud; `raw_reference` is verbatim;
`TEXT MISSING` stays as the gap marker; no untranscribed-placeholder status.

## Name map (old → new)

| Current | Proposed | Notes |
|---|---|---|
| `naa_authorities` | `issuers` | + `kind`, `successor_id` |
| `regulation_parts` | `documents` | + `doc_kind`, `code`, `slug`; `title_number` folded into `code` |
| `amendments` | `document_revisions` | + `cancelled_on`, `provenance` |
| `amendment_actions` | `revision_actions` | moved from per-section to per-revision |
| `regulations` | `provisions` | `section` → `number`; + `parent_id`, `sort_key`; `current_subpart` → `current_grouping` |
| `section_amendments` | `provision_versions` | `federal_register_cite` → `publication_cite`; `same_as_designator` → `same_as_version_id` FK; + `text_missing`, `provenance` |
| — | `provision_relations` | new |
| `cert_basis_entries` | `cert_basis_entries` + `cert_basis_refs` + `cert_basis_ref_provisions` + `cert_basis_ref_skips` + `cert_basis_resolved` | split by grain |
| `latest_amendments` view | `latest_versions` view | |
| — | `build_info`, `PRAGMA user_version` | new |

Unchanged in shape: `manufacturers`, `categories`, `aircraft_models`,
`model_categories`, `tcds` (`authority_id` → `issuer_id`), `tcb`.

## P-01 — Generic issuer → document → revision → provision model

*Addresses F-04, F-05, F-16, F-18.*

- **`issuers`**: who publishes. `kind` ∈ `naa | military | standards_body`
  covers FAA, EASA, US DoD (MIL-HDBK-516) and RTCA/SAE. Historical bodies
  get their own clean code (`CAA`, `CAB`) with `successor_id → FAA`. This
  replaces `"CAA (FAA)"`. Codes are constrained to `[A-Z0-9_-]`.
- **`documents`**: a citable body of text with its own revision history.
  `doc_kind` is a CHECK list (closed and small, so no lookup table):
  `regulation`, `certification_spec`, `amc_gm`, `advisory_circular`,
  `handbook`, `special_condition`, `elos`, `exemption`, `standard`.
  `code` is the human citation ('14 CFR 23', 'CS-25', 'AC 25.1309',
  'MIL-HDBK-516'). `slug` is the path segment.
- **`document_revisions`**: `designator` as printed ('23-62', 'Amdt 27',
  '1A', 'C'). There's no global regex; per-kind validation happens in the
  JSON Schema (P-02). `ordinal` is the sort key and must be unique per
  document. `cancelled_on` covers cancelled ACs and superseded handbooks.

Every planned source maps onto this without new tables:

| Source | issuer | doc_kind | document.code | revision.designator | provision.number |
|---|---|---|---|---|---|
| 14 CFR 23 | FAA | regulation | 14 CFR 23 | 23-62 | 1309 |
| CAR 3 | CAA | regulation | CAR 3 | CAR3-0 | 61 |
| EASA CS-25 | EASA | certification_spec | CS-25 | Amdt 27 | 1309 |
| EASA AMC 25 | EASA | amc_gm | AMC-25 | Amdt 27 | 1309 |
| AC 25.1309 | FAA | advisory_circular | AC 25.1309 | 1A | 5.a (or a single '1' for the whole AC) |
| MIL-HDBK-516 | DOD | handbook | MIL-HDBK-516 | C | 4.1.1.1 (with `parent_id`) |
| Special condition | FAA | special_condition | 23-236-SC | 0 | 1 |

AMC/GM is a separate document from the CS, not extra rows in it. They have
different issuance and different text, and they're linked through
`provision_relations` (P-07).

## P-02 — JSON format and file layout

*Addresses F-04, F-15, F-16, F-18, F-25.*

Layout: same depth as today, generic name.

```
data/documents/{issuer-lower}/{document-slug}/_document.json
data/documents/{issuer-lower}/{document-slug}/{provision-number}.json
data/aircraft/{manufacturer-slug}/{model-slug}.json      (unchanged; see Q-06)
```

e.g. `data/documents/faa/23/1309.json`, `data/documents/caa/car-3/61.json`,
`data/documents/dod/mil-hdbk-516/4.1.1.1.json`.

This changes the CLAUDE.md path rule's *names*, not its principle: still
flat, and grouping or subpart stays inside the file. See Q-01.

`_document.json` (replaces `_part.json`):

```json
{
  "issuer": "FAA",
  "doc_kind": "regulation",
  "code": "14 CFR 23",
  "slug": "23",
  "title": "Airworthiness Standards: Normal Category Airplanes",
  "revisions": [
    {
      "designator": "23-62",
      "ordinal": 62,
      "effective_date": "2012-01-31",
      "actions": [
        { "type": "nprm", "reference": "09-12", "issued_on": "2009-07-23",
          "source_url": null, "notes": null }
      ],
      "provenance": { "source": "scraped" }
    }
  ]
}
```

Provision file (replaces the section file):

```json
{
  "issuer": "FAA",
  "document": "23",
  "number": "1309",
  "parent": null,
  "canonical_title": "Equipment, systems, and installations.",
  "current_grouping": "F",
  "subject_group": "General",
  "versions": [
    {
      "designator": "23-62",
      "grouping_at_time": "F",
      "title_at_revision": "Equipment, systems, and installations.",
      "text": "...",
      "publication_cite": "76 FR 75736",
      "source_url": "https://drs.faa.gov/...",
      "provenance": { "source": "scraped" }
    }
  ]
}
```

Schema-level rules:
- `issuer` is an enum in a single `$defs` shared by all schemas, so the
  aircraft and regulation enums can't drift apart again (F-25).
- The `designator` pattern is selected by `doc_kind` via `if/then`, e.g.
  `regulation` from FAA: `^[A-Z0-9]+-[0-9]+$`. The DB relies only on
  uniqueness.
- `actions` moves from versions to revisions (P-05).
- `same_as_designator` stays in JSON as authoring convenience. The build
  resolves it to `same_as_version_id`.
- `publication_cite` is absent or `null` when unknown or for an ordinal-0
  revision. The `"Initial Adoption"` literal is removed (F-07), and the
  build rejects it.

Aircraft cert-basis entry (replaces `resolved_references` with `references`):

```json
{
  "display_order": 3,
  "entry_type": "regulation",
  "raw_reference": "525-0600 thru 525-0684 ... 14 CFR Part 23 effective February 1, 1965, as amended by Amendments 23-1 thru 23-38, 23-40; except the following paragraphs ...: 23.611, 23.777 ... as amended through Amendment 23-1 thru 23-38, and 23-40 thru 23-54. 14 CFR 23.1309(a) as amended through Amendments 23-62, for Portable Electronic Device (PED) tolerance only.",
  "applicability": "525-0600 thru 525-0684, 525-0686 thru 525-0701",
  "applicability_notes": null,
  "references": [
    { "kind": "range",  "issuer": "FAA", "document": "23",
      "from": "23-0", "to": "23-40", "skip": ["23-39"] },
    { "kind": "range",  "issuer": "FAA", "document": "23",
      "from": "23-0", "to": "23-54", "skip": ["23-39"],
      "provisions": ["611", "777", "..."] },
    { "kind": "single", "issuer": "FAA", "document": "23",
      "provision": "1309", "to": "23-62", "paragraph": "(a)" }
  ]
}
```

- References use **designators** (`from`/`to`), never ordinals (F-15).
- `kind: "document"` targets a whole document, e.g. a special condition:
  `{ "kind": "document", "issuer": "FAA", "document": "23-236-SC" }`.
- `effect: "exclude"` (default `"include"`) removes a provision:
  `{ "kind": "single", "issuer": "FAA", "document": "23", "provision": "1419", "effect": "exclude" }`.
- `title_number` disappears because it's part of `document.code`. This
  removes F-09 by construction.

## P-03 — Integrity enforced in the schema, not only in Python

*Addresses F-07, F-08, F-09, F-14, F-23.*

- **All tables `STRICT`.** SQLite 3.46.1 is in use; STRICT needs ≥ 3.37.
- **Dates:** `TEXT` with `CHECK (date(x) IS x)`. Use `IS`, not `=`:
  `date('2064-13-01')` is NULL, `NULL = x` is NULL, and a NULL CHECK
  *passes*. The proposed DDL was tested against both cases. Plausibility
  (no future dates; actions not after the revision's effective date) is a
  build check, not a CHECK, because `date('now')` in a CHECK is
  non-deterministic.
- **Composite FKs** give same-document integrity: `provision_versions
  (document_id, provision_id) → provisions (document_id, id)` and
  `(document_id, revision_id) → document_revisions (document_id, id)`.
  Pairing a Part 23 provision with a Part 25 revision is rejected by the
  DB (tested). The same pattern is used on `cert_basis_refs`, and
  `same_as_version_id` is constrained to the same provision.
- **`text_missing`** is a VIRTUAL generated column. It keeps the
  `TEXT MISSING` rule and makes it queryable and reportable.
- **`provenance`** is carried into `document_revisions` and
  `provision_versions` so the app can mark OCR or manual text.
- Every UNIQUE key is over NOT NULL columns.

## P-04 — Hierarchy and ordering

*Addresses F-17.*

- `provisions.parent_id` is nullable and used only by documents that
  really are hierarchical (MIL-HDBK-516). CFR stays flat. It's a
  same-document composite FK.
- `provisions.sort_key` is computed by the build: each dot- or
  letter-separated segment zero-padded, so §23.175 sorts before §23.1309
  and 4.2 before 4.10. Authors never write it.
- **Paragraphs aren't rows.** They're re-lettered between amendments and
  text is stored per provision version. A reference can carry a verbatim
  `paragraph` qualifier ('(a)', '(c)(2)') for display, and it's never
  resolved.

## P-05 — Actions belong to the revision

*Addresses F-06.*

`revision_actions.revision_id → document_revisions`. In JSON, `actions`
moves into `_document.json` revisions. During migration the build must
check that the per-section copies of each amendment's actions agree, and
fail if they don't, before collapsing them (03-migration-plan Phase 1).

## P-06 — Cert basis in three layers, with defined resolution rules

*Addresses F-01, F-02, F-03, F-05, F-10, F-11.*

| Table | Grain | Authored? |
|---|---|---|
| `cert_basis_entries` | one TCDS line | yes: verbatim `raw_reference`, `applicability`, `display_order` (UNIQUE per TCB) |
| `cert_basis_refs` (+ `_ref_provisions`, `_ref_skips`) | one interpretation clause | yes: what the line *means* |
| `cert_basis_resolved` | one (entry, provision version) | no, computed by the build |

Targets are always `provision_versions`. SCs, ELOS and exemptions are
documents (P-01), so there's no polymorphic FK.

### Resolution rules

These need maintainer sign-off (Q-02). They're written so the build can
implement them deterministically and fail when they don't settle a case.

For each include ref:

1. **Revision set S.**
   - `range`: revisions of D with `ordinal(from) ≤ ordinal ≤ ordinal(to)`,
     minus `skip`.
   - `single`: revisions with `ordinal ≤ ordinal(to)`.
   - `document`: all revisions, or `≤ to` if given.
2. **Provision scope.** For a `range` or `document`: all provisions of D,
   or the `provisions` list if one is given. For a `single`: that one
   provision.
3. **Version.** For each provision p in scope, take the version of p with
   the highest-ordinal revision in S. If there's none, p is not part of
   the basis through this ref (it didn't exist yet). This handles gaps
   correctly: if p changed only at the skipped 23-39, its 23-0 text
   applies.

Then, within a **conflict group**, defined as one TCB plus one
`applicability` value (entries with NULL applicability belong to every
group):

4. **Scoped overrides wide.** A whole-provision result from a
   provision-scoped ref (a `single`, or a `range` with `provisions`)
   replaces the result for that provision from document-wide refs.
5. **Paragraph-scoped refs add, never override.** A ref with `paragraph`
   adds a row (23.1309(a) @ 23-62 alongside 23.1309 @ 23-54). If it
   resolves to the same version as the whole-provision row, the
   whole-provision row wins and the paragraph row is dropped.
6. **Exclude** removes p from the results of document-wide refs.
7. **Fail the build** on:
   - two provision-scoped whole-provision results for the same p with
     different versions;
   - exclude together with a provision-scoped include for the same p;
   - any `from`/`to`/`skip` designator not in the document;
   - `from` after `to`;
   - a `skip` outside `[from, to]`;
   - an include ref that resolves to zero provisions.

Note that rule 3 makes the current 172 data mean "23-1 … 23-13 without the
base". The migration sets `from` to `"23-0"` to match `raw_reference`
(F-15, F-26).

### Worked example (Cessna 525 line above, simplified)

| Provision | Ref 1 (range 0–40, skip 39) | Ref 2 (range 0–54, skip 39, scoped) | Ref 3 (1309(a) @ 62) | Resolved |
|---|---|---|---|---|
| 23.611 | latest ≤ 23-40 | latest ≤ 23-54 | — | Ref 2 (rule 4) |
| 23.1309 | latest ≤ 23-40 | latest ≤ 23-54 | latest ≤ 23-62, para (a) | Ref 2 whole, plus Ref 3 para (a) (rule 5) |
| 23.143 | latest ≤ 23-40 | out of scope | — | Ref 1 |

("Latest ≤ X" always excludes the skipped 23-39.)

## P-07 — Typed relations between provisions

*Addresses the F-04 comparison limit, the TODO "related references" item,
and TODO "Updates: intersection table".*

`provision_relations(from, to, relation, origin)`, with `relation` ∈
`guidance_for | equivalent_to | supersedes | modifies | references` and
`origin` ∈ `manual | derived`.

- AC 25.1309-1A `guidance_for` §25.1309.
- CS 25.1309 `equivalent_to` §25.1309. Symmetric, so it's stored once with
  `from < to`, enforced by CHECK.
- SC 23-236-SC `modifies` §23.1353.
- Part-vs-part comparison (§23.1309 vs §25.1309) uses `equivalent_to`
  instead of matching section-number strings. Derived rows for
  same-number FAA parts can be generated by the build with
  `origin = 'derived'`.

Relations are at the **provision** level, not version (per TODO: "typically
against the reg and not the amendment"). JSON home: Q-07.

TODO also asks for "related references" on cert-basis entries (an
exemption relates to a reg without bringing it into the basis). That is a
`provision_relations` row from the exemption's provision, not a cert-basis
ref, so it stays out of `cert_basis_resolved`.

## P-08 — Contract versioning and journal mode

*Addresses F-20, F-21.*

- `PRAGMA user_version = <schema_version>`. Bump it on every contract
  change. FARFETCHed checks it at startup and refuses a DB it doesn't know.
- `build_info` is a single row: `schema_version`, `git_sha` (from
  `git rev-parse HEAD` if available, otherwise NULL), `built_at`.
- Journal mode: recommend `DELETE` for the shipped file, with readers
  using `file:cert_basis.sqlite?mode=ro` or `immutable=1`. Q-05.

## P-09 — Build behaviour changes

*Addresses F-10 to F-13, F-19.*

- Remove `except sqlite3.IntegrityError: pass`. Integrity errors propagate
  as `BuildError` with file context.
- Validate every reference designator, as in rule 7.
- `tcds`: insert once. On a repeat, compare `revision`, `revision_date`
  and `source_url`, and fail on mismatch. (Or move to one file per TCDS,
  Q-06.)
- Categories: closed enum in the JSON Schema. `categories` is seeded from
  the build's constant table. Drop the `.title()` fallback and the issuer
  `(code, None)` fallback.
- Indexes: drop the redundant two. Add `provision_versions(revision_id)`
  and `cert_basis_resolved(provision_version_id)`. Drop
  `idx_actions_type`.
- Build report gains counts for every new table, plus
  `text_missing_count`, provenance counts, and the list of rule-7
  failures, which must be empty.

## Deliberately not proposed

- **EAV / generic attribute tables** for per-source fields. Add real
  columns, or a per-`doc_kind` side table if one kind grows many.
- **Polymorphic `target_type` + `target_id`.** Avoided by making every
  target a `provision_version`.
- **A "one true lookup table"** merging categories, doc kinds, entry
  types and so on. Small closed sets are CHECKs; open sets are their own
  tables.
- **Paragraph rows.** See P-04.
- **TCDS revision history** and FTS5. Both can be added later without
  breaking the above. For FTS5, use an external-content table over
  `provision_versions.text`, filtering `text_missing = 0`.
- **Storing `sort_key` or ordinals in authored references.** They're
  computed.
