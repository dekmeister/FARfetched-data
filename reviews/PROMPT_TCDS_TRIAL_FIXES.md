The TCDS parser (`tools/aircraft/faa_tcds.py`) was run unchanged over 20 current
Part 23 TCDS. It has the defects listed below, and each one needs a fix. This
prompt names the problems only. How to fix them, and in what order, is for you
to decide after reading the code.

## Read first
- `reviews/TCDS_TRIAL_20.md`: evidence, per-TCDS outcomes, exact strings and
  filenames for every item below. Treat it as the source for repro cases.
- `ISSUES.md` items 16–25: the same list in short form.
- `CLAUDE.md`, `README.md`, `tools/CLAUDE.md`, `tools/README.md`,
  `tools/docs/FAA_TCDS.md`.
- `reviews/PROMPT_TCDS_PARSER.md`: a separate, larger refactor brief. Check
  whether any item here is already covered there, and say so rather than
  duplicating work.

## Defects needing a fix

### Silent: wrong or incomplete output, no warning
1. `resolve_regulation` returns the wrong `to` for amendment numbers written
   without the part prefix ("Amendments 1 through 62" → `23-2`;
   "10 through 20" → `23-0`; "23-38, 40" drops the 40).
2. Zero-entry models are staged as a schema-valid placeholder row. The build
   accepts them and `promote --aircraft` would copy them into `data/`.
3. `classify()` types a base Part 23 line as `exemption` or
   `special_condition` when the line mentions those words (Cessna 525B, 525C),
   so its references are never resolved.
4. Outline mode discards text before the first numbered item, so Cessna
   172R/172S/T206H lose their Part 23 and Part 36 basis and keep only the
   equivalent-safety list.
5. A shared "Data Pertinent to …" basis is attached to the last model block
   only (Cessna 172, 206, 208, Cirrus, Kodiak).
6. Models that share a heading block are never emitted (172B, 172E–H, 172K,
   P206D/E, …), and nothing compares the cover-page model list with what was
   emitted.
7. TBM 700 (A60EU): variant scopes are lost (`applicability` is null on all 24
   entries), a page break truncates a bullet, and a line with overriding
   sections still resolves as if fully understood.
8. Duplicate model designations in one TCDS (A37CE `208B` twice) share a
   filename.

### Loud failures (the parser warns, but it should handle these)
9. Model heading regex only matches `I.  Model` (dash, en dash, `I. -`,
   `IA. -`, capitals, no numeral, no "Model" word all fail). Aviat A8SO
   emitted 1 of 7 models with no warning about the other six.
10. Heading parsing: categories without parentheses, `6/7/8PCLM`,
    `Malibu Matrix`, and seat codes inside designations (`AT-504 2 PCLM`).
11. Certification Basis label variants (`Certification Basis.`, a doubled
    label, `(NOTE 16)`), and a second basis block inside one model being ignored.
12. Tokenisers produce zero entries for `1)` numbering (PC-24, PC-12),
    unmarked prose (KC-100, P2006T, Kodiak) and deeply indented numbering
    (Bristell B23, Cessna 208). Table-style "additions" rows are folded into
    one entry.
13. Header parsing: manufacturer becomes `Unknown` when there is no
    `Holder␣␣Name` line; revision dates not in `Month D, YYYY` form or past
    the first 2000 characters give a null date with no warning; `Revison` /
    `Rev. No.` give a null revision.
14. `14 CFR part 21.29, … 14 CFR Part 23` resolves the cited part as 21;
    `14 CFR 23`, `FAR Part 23` and `Amendments 23-59` (no range) are not
    recognised.

### Needs a decision from the maintainer, not just a fix
15. Restricted-category TCDS (Air Tractor A17SW) have no certification basis,
    which the schema cannot represent.
16. Re-parsing 3A12 at rev 89 conflicts in `build.py` with the existing
    `data/aircraft/cessna-aircraft-company/172.json` (rev 42), and the
    manufacturer would change from "Cessna Aircraft Company" to "Textron
    Aviation Inc.". Do not overwrite the existing file; raise it.
17. Per-TCDS exit code and stderr summary don't signal that a file was staged
    despite zero entries.

## Rules that apply
- Stage only. Only `tools/regulations/promote.py` writes to `data/`.
- `raw_reference` stays verbatim. Unclear references keep `references: []`
  and appear in the report. Never guess.
- Write a failing test for each defect before fixing it. Don't break the
  existing A47CE/DA 40 output or the manual-provenance tripwire.
- Do not `git add`, `git commit` or `git push`.
- Check `git status` before editing. Other uncommitted changes exist in the
  repo (`CLAUDE.md`, `README.md`, `build.py`, `plan.md`,
  `schemas/provision.schema.json`, `tests/test_deletion.py`); leave them alone.
- Any new data or tooling issue found along the way goes into `ISSUES.md`.
- Items 15 and 16 need the maintainer's input; ask rather than assume.
- Finish with `uv run ruff check .`, `uv run mypy .` and `uv run pytest`
  (including `tests/test_build.py`).
