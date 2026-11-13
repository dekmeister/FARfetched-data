# Prompt: set up the database for confirmed section relations

**Status (2026-11-14): not started.** A task prompt, kept here until a session
runs it; tracked as ROADMAP-4 in `issues/roadmap.md`. One fact below has
changed: Part 23 from Amdt 23-64 is now staged and promoted as its own
document `faa/23-amdt64` (FAA-29; joining it to Part 23 is still open), so the
§23.2xxx side of source 1 may now resolve. Check that first. Current contract
version is 15, not 11. Delete this file when the work lands.

Paste this into a new session started in
`/mnt/server/Projects/2026/FARfetched-data`.

---

I want the dataset to hold **published** relations between provisions: tables
where an authority itself says "this section became that one" or "this
section differs from that one". Today the only cross-document link is
`provision_similarity`, which is computed and is shown on the site as
"≈ Computed". These would be the confirmed half that sits beside it.

This task is to design and set up the storage and the ingestion path, and to
load the first source end to end as proof. It is mostly data-repo and tools
work, with a small app change at the end.

Repos (read each CLAUDE.md before working in it):

- Data: `/mnt/server/Projects/2026/FARfetched-data` (owns the SQLite contract)
- Tools: `/mnt/server/Projects/2026/FARfetched-data/tools` (its own git repo;
  the only thing that writes `data/`)
- App: `/mnt/server/Projects/2026/FARfetched`

## The three sources I have in mind

I'm describing these from memory. **Locate each one, confirm it exists in the
form described, and tell me what you actually found** before designing
around it.

1. **Part 23 Amendment 23-64 cross-reference** (the 2017 rewrite): old
   §23.xxx → new §23.2xxx, published with the final rule in the Federal
   Register. **And the CS-23 Amendment 5 equivalent** from EASA: old CS 23.xxx
   → CS 23.2xxx.
2. **FAA/EASA Significant Standards Differences (SSD) lists:** 14 CFR 25 ↔
   CS-25, published per pair of amendment levels for validation projects.
3. **The 1965 recodification:** CAR 3 → 14 CFR 23, published as a derivation
   or distribution table with the recodification rule.

## What makes this harder than one table of pairs

- **The relation types differ.** Sources 1 and 3 say "became" (renumbered,
  merged, split, removed with no successor). Source 2 says "these differ
  significantly", which is nearly the opposite of equivalence. One `kind`
  column must not blur them.
- **Cardinality.** One old section can map to several new ones and several
  old to one. Some rows map to nothing. Some map at paragraph level
  (`23.1309(b)` → `23.2510(a)`).
- **Revision scope.** A recodification row holds between one revision of the
  old document and one of the new. An SSD row holds for one *pair* of
  amendment levels (Part 25 at 25-x vs CS-25 at Amdt y) and a different list
  exists for another pair. Decide whether a relation attaches to provisions,
  to provision versions, or to provisions plus a revision on each side.
- **Missing targets.** 14 CFR 23 in `data/` stopped at 23-63 when this was written (FAA-29;
  23-64 is now a separate `23-amdt64` document), so the §23.2xxx side of source 1
  may not resolve through Part 23 itself. CS-23 does
  have its Amendment 5 sections (CS 23.2000 onward). Decide: fail the build,
  hold the row out, or keep it as an unresolved relation that is counted in
  the report. I lean towards not publishing dangling rows, but show me the
  trade-off.
- **Provenance.** Every row needs its source: document, cite, page or table
  row, `source_url`. The site will show these as "✓ Confirmed" and must be
  able to say confirmed by whom, where.
- **Rights.** Add each source to docs/RIGHTS.md with what its issuer says
  about reuse. The Federal Register is a US Government work. The SSD lists
  and the EASA table need checking; EASA terms are already an open question
  there.
- **Related existing work.** ROADMAP-4 in `issues/roadmap.md` covers this
  area and lists further sources of the same shape: MIL-HDBK-516 merges and
  splits between editions, 516B's `FAA Doc: 14CFR references` lines, the
  516/516A appendix table (DOD-2) and STANAG 4671 Annex C (NATO-3). Schema
  v7 records each key's own history but not that two keys became one.
  docs/SCHEMA_HISTORY.md notes `provision_relations` as deferred. The design
  should be able to carry those later sources without another schema change,
  but don't ingest them now.

## What I want to end up with

1. A relations store in the data contract: JSON format and schema under
   `schemas/`, DDL in `certbuild/ddl.py`, a contract version bump, and
   docs/DATA_FORMAT.md, docs/SQLITE.md and docs/SCHEMA_HISTORY.md updated.
2. A tools path that turns a source table into `data/` through the usual
   extract, emit and promote steps, with override rows for corrections and a
   per-source guide in `tools/s00_docs/`. A hand-typed table is not
   acceptable as the source of record: keep the source file in `input/` and
   extract from it, even if extraction needs overrides.
3. Build checks: every relation endpoint resolves to a real provision (and
   revision, if the design uses one); duplicates and self-relations fail;
   the report counts relations by source and kind, and counts held or
   unresolved rows.
4. **One source loaded end to end.** Choose whichever of the three is best
   supported by what is already in `data/` and tell me why. My guess is the
   CS-23 Amendment 5 table or the 1965 recodification, since both ends exist.
5. The app updated just enough to stay in step: `SUPPORTED_SCHEMA`, the
   vendored `tests/fixtures/schema.sql`, the test database builder, and a
   minimal "✓ Confirmed" list beside "Related sections" on view S, with the
   source cited. The full lineage view (D in the design handoff) is a later
   task; read
   `design/farfetched-frontend-handoff/docs/views/D-lineage.md` so the schema
   can serve it.

## How to work

1. Read the CLAUDE.md files, then docs/DATA_FORMAT.md, docs/SQLITE.md and
   docs/SCHEMA_HISTORY.md, `issues/roadmap.md`, and `tools/README.md` with
   `tools/s00_docs/PIPELINE.md`.
2. Find the three sources. For each, report: where it is published, its
   format, its row count and shape, its reuse terms, and how much of it can
   resolve against the current `data/`. If one doesn't exist as I described,
   say so plainly.
3. Write a design note in `reviews/` (the data repo's place for temporary
   design reviews): the relation kinds, what a relation attaches to, the JSON
   and SQL shapes, how each of the three sources and the ROADMAP-4 sources
   fit, the handling of missing targets, and two or three worked example
   rows per source. **Stop and wait for my go-ahead.** The schema is the part
   that is hard to undo.
4. Build it and load the one source. Show me the promote dry-run before
   promoting. Don't edit `data/` by hand.
5. Run every check in all three repos. Don't `git add`, commit or push in any
   of them.

Finish with: what changed in each repo, the report counts, how many rows of
the loaded source resolved, and what is needed to load the other two.
