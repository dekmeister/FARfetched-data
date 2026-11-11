# Prompt: the open questions blocking multi-model TCDS step 3

Paste this into a new session started in
`/mnt/server/Projects/2026/FARfetched-data`.

---

The multi-model TCDS work (towards the Boeing 737, A16WE) has done steps 1–2
and built step 3, proven on FAA **A2NM** (Boeing 757, Rev 32,
`input/TCDS/FAA/A2NM_Rev32.pdf`, 13 pages). Step 3 can't finish until five
questions are answered. This session is **exploration and a recommendation per
question**, not implementation. Don't change the parser, schema, overrides or
`data/` until I've agreed. Put scratch output in your scratchpad, never in
`tools/out/`, and don't re-download anything.

Read first: `CLAUDE.md`, `tools/CLAUDE.md`, the handover at the top of
`reviews/2026-11-10-multi-model-tcds-proposal.md`, and
`reviews/2026-11-11-a2nm-reading.md` (the line-by-line reading with Q1–Q5).
Then `tools/s00_docs/FAA_TCDS.md`, `docs/DATA_FORMAT.md` (aircraft section,
resolution rules) and `docs/SQLITE.md`. The source PDF is the truth; the
parser, `data/`, the docs, issue text and my earlier readings are evidence that
may be wrong. Other agents may be editing this tree: don't revert changes
you didn't make, and tell me if they get in your way.

## Questions

1. **Category when a TCDS states none (blocking).** A2NM never says
   "Transport" (or any category). Its headings give only approval dates, and
   the parser refuses a model with "no category on heading", so nothing
   stages. `categories` is required and non-empty in the schema.
   - How common is this? TCDS-5 counted 227 "no category on heading" skips
     (2026-11-01, before the step 2 heading fixes): re-count on the corpus and
     sort them into kinds (category stated elsewhere on the TCDS, implied only
     by the basis, absent).
   - What evidence is there for A2NM? The DRS catalogue row
     (`tools/out/work/tcds_catalogue.tsv`, Rev 32) has `cfr_part_reference`
     "Part 25" and `product_subtype` "Large Airplane". The basis is 14 CFR
     Part 25, which is the transport category standard. Is either acceptable
     evidence under "reproducible is not correct" and the rule that a
     correction is an override row with evidence?
   - Options to compare: (a) a reviewed per-TCDS row (new override file, or
     a TCDS-2 corrections action from step 4); (b) a parser rule from the
     airworthiness Part of the basis (Part 25 → transport, Part 23 → ?: say
     why Part 23 does not map to one category); (c) taking it from the DRS
     catalogue; (d) proving step 3 on another TCDS that states its category
     (search the corpus for shared-basis TCDS with a stated category).
     Recommend one, with what it costs in docs and tests. Say whether it
     changes any published file.

2. **Basis statements outside the basis blocks (A2NM p. 7).** "Compliance with
   14 CFR §26" says Part 26 provisions "are included in the certification
   basis" (26.11 at 26-0; 26.43, 26.45, 26.47, 26.49 at 26-1; 26.33 at 26-3),
   in the all-models data before the "Certification Basis for …" labels.
   How often do TCDS put Part 26 (or other basis statements) outside the basis
   field? Should such lines join every model's basis, and how would the parser
   find them without catching prose? Part 26 is not in the dataset (TCDS-13).

3. **Item boundaries in an exemption list (A2NM p. 8).** The PDF prints
   "Exemption No. 5613 was granted on March 5, 1993" on its own line, then
   "Exemption from FAR 25.1415(c) for survival kit attachment requirements.
   (Subject to Operational Procedures)". I joined them as one exemption
   (5613A on the 757-300 is the same §25.1415(c)). Check the rendered page and
   any outside source in `input/` (deviation documents, if 5613 is there) and
   say whether one item or two is right. Then: should the list rule change?

4. **One table row, two amendment levels** (757-300 "25.783 Doors. 23, 85\*\*",
   "25.813 … 75, 88\*\*\*"). Now: two entries with the same verbatim row, the
   level as `applicability`. The footnote says which parts of the airplane
   each level covers. Compare with putting the footnote reference in
   `applicability_notes`, or one entry. Check DATA_FORMAT ("one entry may not
   hold one provision at two versions") and what the app shows for two
   entries with identical `raw_reference`.

5. **A paragraph "not part of the TC basis"** (757-300 "25.858(a) Cargo
   Compartment Fire Detection System"). An `exclude` ref takes no paragraph
   (DATA_FORMAT), so the headline "Part 25 … through 25-85 with the exceptions
   listed below" still holds 25.858 at 25-85, (a) included. Options: accept
   and leave the row visible with `references: []`; or a contract change
   (paragraph-level excludes: JSON schema, `certbuild/resolve.py`, the
   `SCHEMA_VERSION` bump and SCHEMA_HISTORY row, the app). How many TCDS
   lines in `data/` and in the corpus need a paragraph exclude? Recommend.

Also look at, briefly, because steps 4–8 need them:

6. **Rule 5's headline guard.** The proposal wanted a guard that fails when a
   model section holds "more than one headline basis" (the old A16WE -600
   held three). Counting basis blocks doesn't work (A00003SE and A78EU really
   have two). Propose a definition of a headline line that is testable on the
   selected TCDS, A16WE and A2NM.
7. **Relative designations in line scope.** "For
   737-100/-200/-200C/-300/-400/-500: 14 CFR §25.1415(d)" (A16WE pp. 20–21).
   Block labels expand through `sections.expand_group`; line scope goes
   through `scope_models`, which can't read short forms. Say where the
   expansion belongs and what it must refuse.

## Deliverable

A short note in `reviews/` with, per question: what you read (pages, files,
counts), the options, a recommendation, and what it would change (code, docs,
tests, contract, published files). Mark anything not read against a source as
such. Don't `git add`, `git commit` or `git push`. Work on `main`.
