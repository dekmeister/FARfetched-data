# build.py structure review (2026-11-08)

An exploratory review of how the data repo's code is structured, with a
proposed refactor of `build.py`. Nothing here has been implemented. The aims,
in priority order:

1. **Minimise regression risk** while the code keeps growing to absorb edge
   cases.
2. **Make Claude Code edits reliable**: a typical change should need one
   small file plus its doc section and its test file, not a 2,400-line module.
3. Keep the repo's principles: stdlib first, fail loud, parameterised SQL,
   one maintainer.

Scope: the data repo (`build.py`, `tests/`, `pyproject.toml`, repo layout).
`tools/` is only covered where it constrains `build.py` (§7). Its own issues
are logged as PROC-11 and PROC-12 in [issues/tooling.md](../issues/tooling.md).

This is a plan, so the repo's rule for plans applies: it is temporary. When
the refactor is done or rejected, delete it in a dedicated commit and move
anything still open into [ISSUES.md](../ISSUES.md) (BUILD-9 tracks it).

---

## 1. Summary

The repo is laid out well: data, schemas, contract docs and issues are
separate, `data/` has one writer, and the build fails loud. **The main
problem is `build.py`.** It is 2,433 lines (92 KB, about 23k tokens) and holds
six unrelated concerns. Two of them are now shared libraries in practice:
`tools/` imports 15 names from it.

**Recommendation: lift the CLAUDE.md rule "Keep `build.py` a single file. No
package layout until it earns it."** It has earned it. Split the code into a
small package, `certbuild/`, of about 15 modules of 30–350 lines each. Keep
`build.py` as the CLI entry point and a temporary re-export shim. Do it in
**move-only steps, each gated by a byte-identical golden dump of the real
build** (§5). Builds are deterministic: two runs on the same `data/` gave
identical `.dump` output, ignoring `build_info`. So every step can be
checked exactly, not just against "tests pass".

After the split, in separate steps, untangle the few hotspots that actually
need it: `parse_paragraphs` (CC 59), `resolve_entry` / `_insert_ref`, and
`build()`. Also:

- split the duplicated test helpers into one factory module;
- add a complexity ratchet in ruff;
- optionally, cut the 52 s real-data build, 80% of which is similarity
  scoring (§6).

---

## 2. Measurements

### 2.1 Sizes

| File | Lines | Notes |
|---|---:|---|
| `build.py` | 2,433 | 76 functions, 17 classes, 1 SQL DDL string (296 lines) |
| `tests/test_build.py` | 892 | 48 tests: integration, contract, atomic write, git, real data |
| `tests/test_paragraphs.py` | 691 | 59 tests |
| `tests/test_similarity.py` | 344 | |
| `tests/test_provision_key.py` | 280 | |
| other `tests/*.py` | 668 | |
| `docs/DATA_FORMAT.md` | 461 | field-level contract |

Quality gates today: `ruff check` passes. `mypy` (default) passes.
`mypy --strict` reports 13 errors, all bare `dict` or `Any` returns from
`fetchone()[0]`.

### 2.2 Complexity hotspots in `build.py`

McCabe cyclomatic complexity (CC) and maximum nesting depth, from an AST
pass. `ruff --select C901,PLR0912,PLR0915` agrees on the same five
functions.

| Function | Lines | CC | Depth | What it does |
|---|---:|---:|---:|---|
| `parse_paragraphs` | 152 | **59** | 7 | label-line text parser: flat text, tables, formulas, section headings, labels |
| `resolve_entry` | 86 | **34** | 4 | cert-basis resolution rules 1–4 |
| `_insert_ref` | 90 | 19 | 3 | resolves designators and numbers **and** inserts the ref rows |
| `_choose` | 37 | 17 | 2 | picks a label reading from the style stack |
| `_insert_provisions` | 112 | 17 | **6** | provision + version + action + paragraph inserts + text stats |
| `table_width` | 25 | 16 | 5 | |
| `parse_table_row` | 26 | 14 | 3 | |
| `build` | 77 | 13 | 2 | orchestration, 56 statements |
| `_similarity_vectors` / `compute_similarity` | 33 / 37 | 12 / 11 | 3 | |
| `_insert_aircraft` | 85 | 9 | **6** | model → tcb → entry → refs → resolve → insert |

The other 66 functions are small (median 11 lines, CC ≤ 10). Most of the
file is fine code. The problem is that it is all in one file, plus a few
over-long functions.

### 2.3 Where changes land (git hotspots)

Counting the function named in each diff hunk across the 23 commits that
touched `build.py`, the most-edited areas are:

1. Provision/regulation inserts (old and new names, about 50 hunks)
2. Cert-basis expansion and resolution (`_expand_and_insert_entry`,
   `_insert_ref`, `resolve_entry`, `DocIndex`, about 35)
3. `build` / `main` / `_build_report` / `BuildReport` (about 60 together)
4. `parse_paragraphs` (16)

Item 3 is **shotgun surgery**: adding one report counter means editing a
stats dataclass, `BuildReport`, `_build_report`, `build` and often `main`.
Item 4 is where new edge cases arrive: tables, formulas and roman headings
were each new branches in the same function.

### 2.4 Runtime

Real `data/` is 6,236 JSON files and 40 MB. A real build takes about 52 s,
and the `real_db` session fixture pays that on every `pytest` run, so 52 s
of the 64 s `tests/` run is that one fixture.

| Stage | Share of build | Notes |
|---|---:|---|
| `compute_similarity` | **~80%** (~40 s) | 138 M posting-pair visits in pure Python; 8,527 terms, longest posting list 2,156 |
| `validate_data_dir` (jsonschema) | ~13% (~7 s) | every file is then read and parsed a second time by the loaders |
| `_insert_provisions` incl. `parse_paragraphs` | ~6% (~3 s) | |
| everything else | <2% | per-row lookup queries (N+1) are cheap at this scale; leave them |

---

## 3. Findings

### F1. `build.py` is a library with no declared API (high)

`tools/` imports these names from `build`:

- **Text format:** `parse_paragraphs`, `TextFormatError`, `flatten_text`,
  `plain_text`, `inline_error`, `strip_inline`, `FORMULA_MARK`,
  `label_values`, `heading_section`, `SECTION_HEADING_RE`
- **Tables:** `TableCell`, `parse_table_row`, `table_width`, `TABLE_OPEN`,
  `TABLE_CLOSE`, `TABLE_ROW_SEP`
- **Other:** `sort_key`; `build` (the e2e tests)

The direction is right: tools validates its output with the build's own
parser, so the two can't disagree. But nothing marks these names as
public, and nothing in this repo tests that they still exist. Because
`tools/` is a separate git repo, renaming something like `label_values`
passes `tests/` and breaks tools quietly. A refactor that doesn't plan for
this will cause exactly the regression the user wants to avoid.

### F2. One file, six concerns, different change rates (high, for edit reliability)

The concerns are:

1. DDL and contract version
2. Schema validation and loading
3. The label-line text format, plus tables and inline markup
4. Document/provision inserts and their checks
5. Cert-basis resolution
6. Similarity, and the report/CLI

To change one similarity weight or one resolution rule, Claude Code has to
find its place in a 23k-token file. In practice it reads large chunks or
greps and then edits with partial context. Edits made with partial context
are where unintended coupling gets missed: `_insert_provisions` both counts
text stats and silently skips alias parse errors, and that is easy to break
from outside.

### F3. `parse_paragraphs` is one 152-line state machine (high)

Its state is `stack`, `section`, `sections`, `roman`, `table` and `out`,
kept as locals across a loop with five line kinds handled inline:
table-block, heading, unlabelled/formula, labelled, and compound-label.

- The "innermost owner by indentation" (Rule 5) is written out twice,
  identically.
- The single-line branch repeats four of the multi-line checks (table
  markup, `$$`, inline markup, indentation) in its own wording.

Every new layout edge case will add another branch to this function.

### F4. Resolution logic is tangled with SQL (medium-high)

`resolve_entry` is pure and well documented, which is good. But:

- `_insert_ref` resolves designators, skips and printed numbers
  (`DocIndex.provision_at`) **and** inserts rows, in one function that
  returns `(Ref | None, errors)`.
- `DocIndex` is built from SQL (`_doc_index`).

So every resolution test has to stage a JSON tree, run a full build and
query the DB. 48 of the tests in `test_build.py` work this way. They are
good regression tests but slow and indirect as unit tests. A rule change
can't be tested in isolation.

### F5. Untyped `dict` records everywhere (medium)

`Source.doc` is `dict`. Versions flow through `_resolve_alias_versions` as
`{**v, "text": ..., "same_as_designator": ...}`, and refs stay raw dicts.
Schema validation guarantees the shape, so this isn't a correctness bug
today. But a mistyped key is a runtime `KeyError` that mypy can't catch,
and the repo's own CLAUDE.md says "Dataclasses or Pydantic for structured
data. Not dicts."

### F6. Inconsistent error conventions (medium)

Four styles exist side by side:

- `raise BuildError([...])` on the first error (alias checks, the number
  mismatch, a missing `_document.json`, TCDS conflicts)
- collect, then raise after the stage (text format, number clashes,
  future dates)
- return `(value | None, errors)` (`_insert_ref`, `resolve_entry`)
- return `ParsedText | str` (`check_text`)

As a result, a run sometimes lists every problem and sometimes stops at
the first. For a new check, it isn't obvious which style to use.

### F7. `check()` and `build()` share steps by copy (medium)

`check()` re-lists the pre-insert steps (validate, load, paths, text
format). A new pre-insert check added to `build()` will be missing from
`--check` unless someone remembers to add it there too.

### F8. Tests: duplicated factories, one big file, slow default run (medium)

- The helpers `_provision` (5 copies), `_stage` (4), `_ref` (4), `_aircraft`
  (4), `_version`, `_document`, `_resolved` and `_build` (3 each) are
  redefined across test files. A schema change, say a new required field,
  means editing every copy. Missing one makes the tests drift from the
  schema.
- `test_build.py` mixes five suites.
- Every `pytest` run pays the 52 s real-data build. There is no marker to
  skip it in the edit-test loop.

### F9. Repo layout drift (low)

- `CLAUDE.md` and `README.md` both describe a `reviews/` directory that does
  not exist. Either create it when the next review lands, or drop the
  references.
- No ruff rule selection beyond the defaults, and no mypy config. Complexity
  can grow back unnoticed after a refactor.
- The module name `build` shadows the PyPA `build` package (`python -m
  build`). It isn't installed in `.venv` today, but a package with a
  distinct name (`certbuild`) avoids the risk.

---

## 4. Proposed structure

```
build.py                    CLI: argparse + main(); re-exports (temporary, see §5)
certbuild/
  __init__.py               empty
  errors.py                 BuildError, ValidationError                       ~30
  ddl.py                    SCHEMA_SQL, SCHEMA_VERSION                        ~310
  lookups.py                ISSUERS, CATEGORY_NAMES, seed_lookups, id lookups ~70
  sources.py                validate, load (parse once), path checks,
                            typed records (phase 3)                           ~200
  text/                     THE LABEL-LINE FORMAT, a public API for tools/
    __init__.py             __all__ = the names in F1 (the declared API)
    labels.py               label_values, roman numerals, _Level/_Reading,
                            _choose, SECTION_HEADING_RE, heading_section      ~150
    markup.py               inline_error, formula_body, strip_inline          ~40
    tables.py               TableCell, parse_table_row, table_width, consts   ~90
    paragraphs.py           Paragraph, ParsedText, TextFormatError,
                            parse_paragraphs (as a small parser class)        ~250
    flat.py                 flatten_text, plain_text, paragraph_ref_paths     ~80
  provisions.py             insert documents/provisions/versions/paragraphs,
                            alias resolution, number clashes, TextStats       ~330
  resolve.py                DocIndex, Ref, resolve_ref, resolve_entry: PURE,
                            no sqlite3 import                                 ~250
  aircraft.py               insert models/tcds/tcb/entries/refs, call resolve,
                            paragraph-ref checks                              ~220
  similarity.py             pure TF-IDF; one SQL function for its sources     ~210
  report.py                 BuildReport, build_report, git sha/dirty          ~150
  pipeline.py               build(), check(): steps listed once               ~130
tests/
  factories.py              the single copy of document/provision/aircraft/
                            ref/stage builders
  test_text_*.py            mirrors certbuild/text/
  test_resolve.py           pure rule tests, no DB
  test_build_*.py           integration (contract, failures, atomic, git)
  test_real_data.py         @pytest.mark.slow
  test_tools_api.py         imports every name tools/ uses (F1)
```

Design rules behind the layout:

- **One module per reason to change.** Each module maps to one doc section:

  | Module | Doc section |
  |---|---|
  | `text/` | DATA_FORMAT §Text format |
  | `resolve.py` | DATA_FORMAT resolution rules |
  | `ddl.py` | SQLITE.md |
  | `similarity.py` | SQLITE §Similarity |

  Each module's docstring names its section, its invariants and what it
  must not do (for example "`resolve.py` never imports `sqlite3`").
- **Pure core, imperative shell.** Text parsing, resolution and similarity
  take and return plain data. Only `provisions.py`, `aircraft.py`,
  `report.py` and `pipeline.py` touch the connection. Pure modules get fast,
  exact unit tests. DB modules keep the integration tests.
- **The tools-facing API is explicit.** `certbuild/text/__init__.py` lists
  it in `__all__`, and `tests/test_tools_api.py` imports each name. A rename
  then fails *here*, in the repo being edited. Moving `sort_key` into
  `text/` or a small `certbuild/keys.py` is a judgement call; keep it
  importable either way.
- **Size budget: about 350 lines per module**, enforced socially and by the
  complexity ratchet (§5, step 7), not by tooling.
- **Stdlib only, no new dependencies, no ORM.** Insert SQL stays explicit
  and parameterised. A generic `_insert(table, row)` helper would cut
  boilerplate but hide the column lists that the DDL review relies on, so
  don't add one.

### 4.1 Specific restructurings (after the move)

**`parse_paragraphs` (F3)** becomes a small `_Parser` class. Its state
(stack, section, roman, open table, output) is held as attributes, with:

- `classify(content) -> LineKind`, an enum: `TABLE`, `HEADING`,
  `LABELLED`, `UNLABELLED`, `FORMULA`;
- one method per kind;
- a shared `_owner(indent)` that replaces the duplicated Rule 5 block;
- a shared `_check_line(content)` used by both the flat and the structured
  paths.

A new layout edge case then means one classifier branch, one method and
one test class. Target: no method over CC 10. The output must stay
identical, which the golden dump checks over all 71,419 real paragraphs.

**Resolution (F4)** splits `_insert_ref` into:

- `resolve_ref(ref, doc, exclude_at) -> Ref | list[str]` in `resolve.py`
  (pure: designators, skips, printed numbers);
- `insert_ref(conn, entry_id, seq, ref) -> int` in `aircraft.py`
  (SQL only).

`DocIndex` gets a `from_rows(...)` constructor. The SQL that feeds it stays
in `aircraft.py`. `resolve_entry` can be broken into its four rules as
private functions (`_includes`, `_apply_excludes`, `_merge_paragraphs`),
keeping the numbered docstring as the index.

**Errors (F6).** Adopt one rule and write it in `errors.py`'s docstring:
**collect within a stage, raise between stages.** Each stage function
returns `list[str]`, or a result plus errors, and `pipeline.py` raises a
`BuildError` once the stage ends. Immediate raises are kept only where
carrying on would cascade nonsense errors, for example an undeclared
revision. This turns several first-error stops into full lists, which is
an improvement in itself.

**Pipeline (F7).** `pipeline.py` holds:

```python
PRE_INSERT_CHECKS = (check_paths, check_text_format)
POST_INSERT_CHECKS = (number_clashes, future_dates, foreign_key_check)
```

`check()` runs the first tuple, and `build()` runs both around the
inserts. A new check is then a function plus one registration line, and
`--check` can't drift from the build.

**Report (§2.3).** Let each stage return a small stats dataclass, and let
`report.py` merge them into `BuildReport`. `main()` prints a fixed subset.
Adding a counter then touches the stage and the TypedDict only.

**Typed records (F5), later and optional.** After validation, convert each
`Source.doc` once into frozen dataclasses (`DocumentRec`, `ProvisionRec`,
`VersionRec`, `AircraftRec`, `EntryRec`, `RefRec`). To keep the schema and
the dataclasses from drifting, add a test asserting that each dataclass's
fields equal the schema's `properties`. This is the largest change and the
smallest immediate payoff, so do it last, or only for `VersionRec` and
`RefRec`, where the dict-merging lives.

---

## 5. Migration plan (regression-first)

Each step is one commit by the developer, with all gates green before the
next step starts. **Gates for every step:** `uv run pytest`, which includes
`tools/s99_tests`, so the tools' imports are exercised; `ruff`; `mypy`; and
the golden dump.

**Step 0: Safety net (no production code change).**

- Add `tests/test_golden.py` (marked slow). It builds the real `data/` and
  compares a canonical dump against a committed hash. The dump is
  `sqlite3 .dump` excluding `build_info`, or per-table row hashes so a
  failure names the table. Verified today: two builds give the same dump
  hash (`e441e0db…`).
- Regenerate the hash only when data or the contract *intentionally*
  changes. The commit message says so.
- Add `tests/test_tools_api.py` (F1).
- Register the `slow` marker in `pyproject.toml` and tag the `real_db`
  tests, so `uv run pytest -m "not slow"` gives a ~12 s inner loop.

**Step 1: Mechanical move.** Create `certbuild/` and move code verbatim.
No renames, no logic edits. `build.py` keeps `main()` and re-exports every
name the tests and tools import, so nothing else changes in this commit.
Diff review is "only moved lines" (`git diff --color-moved`), and the
golden hash must not change.

**Step 2: Repoint imports.** Change `tests/` to import from `certbuild.*`,
and `tools/` to import from `certbuild.text`. The tools change is a
separate commit in the tools repo. Then shrink the shim in `build.py` to
`main` plus `build`, which the e2e tests use.

**Step 3: Test factories.** Create `tests/factories.py`, delete the
duplicate helpers, and split `test_build.py` along module lines. Test
count must not drop: compare `pytest --collect-only -q | tail -1` before
and after.

**Step 4: `parse_paragraphs` → `_Parser`** (§4.1). Gates: golden hash,
`test_paragraphs.py`, `tools/s99_tests/common/test_structure.py` (the
segmenter round-trips through it).

**Step 5: Resolution split** (§4.1). Gates: golden hash. Add pure
`test_resolve.py` cases that mirror the existing integration cases, and
keep the integration cases.

**Step 6: Error convention + pipeline step lists + report merge.** This
step may change error *output*: more errors per run, different order. Add
tests for the "collects all" behaviour. The DB is unaffected, so the golden
hash still holds.

**Step 7: Ratchet.** In `pyproject.toml`:

```toml
[tool.ruff.lint]
extend-select = ["C901", "PLR0912", "PLR0915", "SIM", "UP", "B"]
[tool.ruff.lint.mccabe]
max-complexity = 12
[tool.mypy]
strict = true
files = ["build.py", "certbuild"]
```

Leave per-function `# noqa: C901` only on documented exceptions, ideally
none.

**Step 8: Docs.**

- Replace CLAUDE.md's single-file rule with a **code map**: a table of
  "to change X, edit module Y, doc section Z, test file T". This is the
  single biggest lever for Claude Code loading the right context and
  nothing else.
- Update the README layout, the `docs/SQLITE.md` references to
  `SCHEMA_SQL in build.py`, and `tools/CLAUDE.md`.
- Delete this file in its own commit.

Steps 0–3 are low-risk and deliver most of the context win. Steps 4–6 are
optional, and each can be postponed until the next edge case lands in that
code.

---

## 6. Performance options

Similarity dominates every build and every test session. The options:

| Option | Lossless? | Measured / expected | Cost |
|---|---|---|---|
| A. Dense list accumulator (index provisions 0..n−1, `acc = [0.0]*n` per provision, parallel id/weight posting lists) | yes | ~40% faster in isolation (48.5 s → 28.7 s on the real vectors) | ~20 lines, local to `similarity.py` |
| B. Symmetric half: score each pair once, mirror it | yes | ~30 s accumulation alone; combined with A, expect roughly 15–20 s | moderate; ranking stays per direction |
| C. Cache the similarity rows keyed by a hash of the sources, the constants and `similarity.py`'s source | yes, if the key is complete | aircraft/TCDS-only rebuilds and repeat test runs skip it entirely (~12 s builds) | cache file in a gitignored dir. The risk is key incompleteness; make the key over-inclusive |
| D. Prune terms: lower `SIMILARITY_MAX_DF`, or cap terms per vector | **no**: changes `provision_similarity` rows | large | a data decision. Rows are "computed, never hand-checked", but the app shows them |
| E. Parse each JSON file once (validate and load the same object) | yes | ~1–2 s, plus simpler code | small; fits step 1 or 6 |

Recommendation: A, then E, then measure. Do C only if the inner loop is
still painful. Leave D to the developer. N+1 queries and jsonschema
validation aren't worth optimising at this scale, and parallelising them
would add more complexity than it saves.

---

## 7. Notes on `tools/`

Out of scope for refactoring here. Logged where it matters:

- **PROC-11:** tools imports 15 undeclared `build.py` internals (F1). The
  refactor's step 2 fixes it from both sides.
- **PROC-12:** tools has the same pattern as `build.py`, at larger scale.
  Its worst functions are well above anything in `build.py`:

  | Function | Lines | CC |
  |---|---:|---:|
  | `s00_common/tcds_refs.py:interpret` | 200 | 71 |
  | `s01_extract/easa/cs/extract.py:parse` | 168 | 68 |
  | `s02_emit/faa/tcds/parse.py:tokenize_bullet` | 227 | 66 |
  | `easa/cs/extract.py:_candidates` | 109 | 66 |
  | `faa/regs/manifest.py:build_amendments` | 179 | 63 |
  | `faa/regs/manifest.py:main` | 203 | 57 |
  | `s00_common/structure.py:_candidates` | 65 | 38 (nesting depth 12) |

  Five files exceed 1,000 lines. The approach in §4–§5 (golden output,
  move-only commits, then per-function untangling) transfers directly, with
  the staged tree in `tools/out/staged/` as the golden artefact.
