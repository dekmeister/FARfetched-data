---
name: promote-staged
description: Review what promoting tools/out/staged/ (documents, aircraft and deviation records) into data/ would change and promote it if there are no major problems. Diffs staged against data/, verifies mechanical field changes by script, runs automated checks, has Sonnet subagents read only what changed (plus new content) against the local source copies within a token budget, holds back files that regress, promotes the rest and logs remaining problems to reviews/DATA_FINDINGS.md. Use when the user asks to review, check or promote the staged tree. Never changes the pipeline.
---

# promote-staged

Decide whether the staged tree is fit to promote, then promote what is.
The bar is **"no worse than data/, and no major new damage"**, not
perfection. Problems that don't block go in the findings log for a later
session.

The question is always **"what did this promotion change, and is the change
right?"** Pre-existing problems don't block promotion, so readers don't
look for them: whole-tree auditing is the `audit-data` skill's job. Scripts
answer what scripts can (field values, layout-only, identical-apart-from-X);
readers get only the changes and new content, with source slices.

## Rules

- **Don't change the pipeline.** No edits to `tools/` (code or `overrides/`),
  `certbuild/`, `schemas/` or `docs/`. Don't run extract, emit or assemble.
  Don't fetch anything. The staged tree is what it is. If it's broken, log it
  and stop.
- Only `tools.s03_promote.promote` writes `data/`. Never copy files into
  `data/` yourself, and never pass `--delete-orphans`. Orphans are listed for
  the user.
- Never `git add`, `commit` or `push`. The user commits.
- The only repo file you write is `reviews/DATA_FINDINGS.md` (append only;
  see `.claude/skills/audit-data/reference/LOG.md`). Keep everything else in
  `$S`, a fresh folder in the session scratchpad (`$S=<scratchpad>/promote-<date>`).
- Reading against the source is done by Sonnet subagents, not by you or the
  user. Your job is the scripts, the dispatch, the decision and the log.
- A script `ok` means "matches our copy of the source", not "verified". Say
  "checked by script" in the log, never "verified", unless a reader read it.

Scripts (run from the repo root):

```bash
D=.claude/skills/promote-staged/scripts
A=.claude/skills/audit-data/scripts
export PYTHONPATH=.:$A
```

## 1. Is there anything to promote?

```bash
uv run python $D/delta.py > $S/delta.jsonl 2> $S/delta_summary.txt
uv run python -m tools.s03_promote.promote --dry-run </dev/null > $S/dry_docs.txt 2>&1
uv run python -m tools.s03_promote.promote --aircraft --dry-run </dev/null > $S/dry_aircraft.txt 2>&1
uv run python -m tools.s03_promote.promote --deviations --dry-run </dev/null > $S/dry_deviations.txt 2>&1
```

If `delta.py` reports `0 files that would change`, **stop**. Tell the user
there is nothing to promote, mention any orphans the dry runs list, and do
nothing else. Don't write a log entry.

Otherwise, read `delta_summary.txt`. Each row in `delta.jsonl` also lists its
scalar `fields` changes and a `residual` flag (anything else changed).

| Class | Question | Answered by |
|---|---|---|
| `fields-only` | is each changed field value right? (the file is otherwise identical to data/) | `fields.py`; readers get only its flags plus a sample |
| `metadata` | some field changed (alongside other changes, or alone) | `fields.py`, as above |
| `words` | does each word hunk move towards the source? | reader, diff mode: every one |
| `versions-added` / `new-file` | is the new content faithful? | reader, full mode (new documents sampled, see 3) |
| `versions-removed` | why did it go? | you: find the reason (dry-run flag, `suppress` row) |
| `markup-lost` | was data/'s markup wrong? | **hold back** unless reading shows it was |
| `markup-only` / `layout-only` | words unchanged (machine-checked): is the new markup or layout right? | reader, diff mode, a sample |
| `basis-lines` / `references` | is each added, removed or re-parsed line right? | reader, diff mode: every one |
| `tcds-revision` | the TCB's revision, date or URL changed | `fields.py` for the fields; any basis change is `basis-lines` |
| deviation `new-file` | is the record what its listing says? | `fields.py`, every field (and every field the listing prints that the record leaves out); readers get a sample of whole records plus field samples |
| deviation `fields-only` | is each changed field (citations included) right? | `fields.py`, as above |

**Deviation records** (`data/deviations/{issuer}/{key}.json`) are link-only
metadata from the regulator's listing (docs/DATA_FORMAT.md §Deviation file),
so every change to one is a field change, named `deviation.<key>`. The source
is the cached listing, not the PDF: for FAA the DRS listing entry
(`input/cache/drs/deviations/{type}/pNNNN.json`, matched by docUniqueId), for
EASA the detail page (`input/cache/easa_deviations/detail/{key}.html`). See
`listing.py`.

The dry runs flag `VERSIONS n → m` (also in
`tools/out/reports/promote_version_counts.tsv`). Each one needs a reason (a
spurious version collapsing, a real amendment, a `suppress` row) before you
accept the file.

## 2. Automated checks

**a. Field values.**

```bash
uv run python $D/fields.py --delta $S/delta.jsonl > $S/fields.jsonl 2> $S/fields_summary.txt
```

Each line is one distinct check (the same value against the same source in
many files is one line): `ok`, `flag` or `unverifiable` (no verifier for that
field, or no source text). Verifier kinds are in `fields.py` (`FIELDS`). A
new field the schema gains is `unverifiable` until it gets a line there, so
it is read. That is the safe default. If a run shows a new field read many
times over, suggest a verifier to the user (it's a skill change, not a
pipeline change).

Deviation fields use two kinds from `listing.py`. `listed` (title, number,
applicant, make, model, regulation_ref, disposition, published_on): equal to
the value under the field's DRS label, or on the EASA page; an absent field
passes only when the listing prints nothing there. `derived` (kind, stage,
source_url, final, citations, citation_gaps): the listing type, the DRS view
URL or canonical link, a `final` that names a final record of the same kind
and docket, citation numbers that the title, number or regulation_ref names.
EASA `stage` can't be decided by script (EASA labels files inconsistently),
so it passes with a note unless the page says "with final publication", and
is sampled. Many deviation flags with one note mean a verifier or a pipeline
bug: look at `fields_summary.txt` before planning the reading.

**b. Does the result build?** Overlay staged on a copy of data/ (orphans
stay, as with promote) and build it. Build data/ as well for comparison:

```bash
cp -r data $S/cand
cp -r tools/out/staged/documents/. $S/cand/documents/
[ -d tools/out/staged/aircraft ] && cp -r tools/out/staged/aircraft/. $S/cand/aircraft/
[ -d tools/out/staged/deviations ] && mkdir -p $S/cand/deviations && cp -r tools/out/staged/deviations/. $S/cand/deviations/
uv run python build.py --data-dir $S/cand --out $S/cand.sqlite   # report: $S/cand_report.json
uv run python build.py --out $S/base.sqlite                     # report: $S/base_report.json
```

If the candidate fails to build, or has more unresolved references than
data/, **promote nothing**. Log a blocker with the build error and stop.
Compare the two reports' row counts, and explain any big drop.

**c. New damage.** Find hits the staged tree adds over data/:

```bash
uv run python $A/checks.py --root tools/out/staged --baseline-root data > $S/new_checks.tsv
uv run python -m scripts.scan_data --root tools/out/staged > $S/new_scan.tsv   # only hits not in the baseline
```

These cover documents and aircraft only; deviation records are covered by
`fields.py` and by the build (path vs identity, citations resolve, `cited`
slices printed, `final` is a final record of the same kind).

Every hit in these two files is new. `batches.py` attaches them to their
items (by designator for versions, by file for aircraft) and makes those
items must-read. A confirmed one is a blocker for its file. Hits that are
plainly expected (e.g. `regulation-no-refs` on a Part with no document in
data/) can be noted and dismissed without reading.

## 3. Plan the reading, within a budget

```bash
uv run python $D/batches.py --delta $S/delta.jsonl --fields $S/fields.jsonl \
    --hits $S/new_checks.tsv --hits $S/new_scan.tsv --out-dir $S/batches
```

It builds items in three modes (see `items.py`, and the modes in READER.md):

- **field**: every field flag and unverifiable field, plus a sample of 20
  passes per verbatim/date field, stratified by manufacturer or document.
  No miss in 20 means a script missing ≥15% of bad values would have gone
  unnoticed about 4% of the time (0.85²⁰).
- **diff**: each changed version or TCB, with only the changed hunks or
  lines, the data/ side, and a source slice (page and lines) for each.
  Identical changes across files (one TCDS shared by many models) are one
  item.
- **full**: new content (new or added versions, a TCB not in data/, a new
  deviation record with its listing excerpt). A new TCB that is
  byte-identical to one already in data/ is skipped.

Always read: words, versions-added, basis-line diffs, new or added TCBs,
field flags (deviation ones included), anything with a new hit. Sampled:
field passes (20 per field; deviation `listed` fields share one pool of 20,
and deviation stage, final and citations get 20 each), layout-only and
markup-only (8 each), new-file document versions (all when ≤24, else 24
stratified), new deviation records (`--dev-sample 16`, stratified by issuer,
kind and stage). Never read: verified fields beyond the sample, new
deviation records beyond the sample, markup-lost (held), TCBs identical to
data/.

**Before dispatching**, read `$S/batches/plan.json` and tell the user in one
line: items, batches, estimated tokens, and any downscale steps. The budget
is `--budget 400000` (target), `--hard-stop 800000`. Over the budget,
`batches.py` shrinks the samples (layout/markup, then field passes, then
new documents, then deviation records). If the must-read alone is over the hard stop, it writes no
batches and exits 3. Then **stop and ask the user**: the change is
pipeline-sized, and should be split (e.g. promote aircraft and documents
separately, or one issuer at a time) or given an explicit larger budget.

`$S/batches/not_read.tsv` lists every changed file no item covers, and why.
That goes in the log.

Dispatch one **Sonnet** subagent per batch (`model: "sonnet"`,
general-purpose), at most 16 at once (`plan.json` `waves`; the harness
allows 20). Start the next wave as readers finish. Prompt:

> Read `.claude/skills/audit-data/reference/READER.md`: *Core*, *Output* and
> the sections for **<mode> mode**. Your batch is `$S/batches/<name>.jsonl`:
> staged changes about to be promoted into data/. Write your findings to
> `$S/findings/<name>.jsonl`. Patterns already known (don't suggest them as
> candidates): <the last run's Check candidates line from
> reviews/DATA_FINDINGS.md>.

Wait for all of them to finish. Collect `$S/findings/*.jsonl`. Note each
reader's token use from its completion notice, for the log. Drop findings
with no source excerpt or reference. If a blocker has low confidence, send it
to a second Sonnet reader with just that item before you act on it.

**Field-sample misses.** If a reader finds a `field-sample` value wrong, the
script missed it. Log a finding against the verifier, then re-run
`batches.py` with `--field-sample 40 --seed 1` and read the new field batch
only (one more reader). Two misses: say in the log that the script's passes
for that field can't be relied on, and suggest a fix.

## 4. Decide

Hold back a file when it has any of:

- a confirmed `blocker` that isn't `pre_existing` (the staged version
  regresses, or new content is wrong);
- `markup-lost` that no reading justifies;
- versions removed, or a `VERSIONS` flag, with no reason found;
- a confirmed new hit from step 2c;
- (deviation) a field a reader confirms the listing contradicts, when it
  misleads (wrong number, title, stage or `final` link).

Deviation records depend on each other: holding back a final record means
holding back every proposed record whose `final` names it, or the build
fails. Citations name document provisions: a record citing a provision that
is held back (or not yet in data/) fails the build too, so check
`$S/cand_report.json` against what you hold.

Promote everything else, including files with `major`/`minor` problems and
field values a reader found wrong but not misleading (e.g. a holder missing
its legal suffix): staged is no worse than data/ there, and the findings go
in the log.

**Stop the whole promotion** (promote nothing) if the build failed, or if
blockers are systemic: the same cause across many files, or over about 10% of
the items read. That's a pipeline bug for another session, not a per-file
decision.

## 5. Promote

Build an approved tree that holds only the files to promote, and promote
from it. Every conflict is pre-accepted, and stdin is closed, so nothing can
prompt:

```bash
mkdir -p $S/approved/documents $S/approved/aircraft $S/approved/deviations
# copy each approved staged file to the same relative path under $S/approved/,
# plus the _document.json of every document directory you copy into
# (unless its own delta removes revisions you haven't explained)
uv run python -m tools.s03_promote.promote --staged $S/approved/documents \
    --accept <relpath> ... --dry-run </dev/null      # check: only the approved files
uv run python -m tools.s03_promote.promote --staged $S/approved/documents \
    --accept <relpath> ... </dev/null
uv run python -m tools.s03_promote.promote --aircraft --staged $S/approved/aircraft \
    --accept <relpath> ... </dev/null
uv run python -m tools.s03_promote.promote --deviations --staged $S/approved/deviations \
    --accept <relpath> ... </dev/null
```

`--accept` paths are relative to `data/documents/` (or `data/aircraft/`,
`data/deviations/`), one per changed file. New files need no `--accept`. The orphan list from a run
against the approved tree is meaningless, because the tree is partial. Use the
orphans from step 1.

Afterwards:

```bash
uv run python build.py                        # must pass, zero unresolved
uv run python -m tools.s03_promote.promote --dry-run </dev/null   # only held-back files left
uv run python -m tools.s03_promote.promote --deviations --dry-run </dev/null   # likewise
```

## 6. Log and report

Append one run to `reviews/DATA_FINDINGS.md` in the format in
`.claude/skills/audit-data/reference/LOG.md`. The header gives the delta
classes, what scripts checked (fields.py counts), what was read (items by
reason, from `plan.json`, and what was sampled), estimated and actual
subagent tokens, files promoted, files held back (each with its finding ID),
and orphans left for the user. Then list the findings, grouped by cause.

Tell the user, briefly:
- what was promoted and what was held back, and why;
- how many findings were logged (blockers first);
- estimated vs actual reading cost;
- that the changes in `data/` (and `data/promotion.json`) are uncommitted
  and ready for them to review and commit.

## Scripts

| Script | Does | Tests |
|---|---|---|
| `delta.py` | staged vs data/: classes, field changes, residual | `test_fields.py` |
| `fields.py` | verifies field changes by kind (verbatim, date, derived) | `test_fields.py` |
| `context.py` | finds a phrase in a local source copy; slice with page and lines | `test_fields.py` |
| `listing.py` | deviation records: cached listing entry, `listed` and `derived` verifiers | `test_fields.py` |
| `items.py` | builds field/diff/full items from a delta row (deviation records too); dedup | `test_batches.py` |
| `batches.py` | selection, sampling, cost estimate, downscale, packing | `test_batches.py` |

```bash
uv run pytest .claude/skills/promote-staged/scripts/   # with PYTHONPATH as above
```

Cost constants (`READER_OVERHEAD`, `BASE` in `batches.py`) are estimates
calibrated on the 2026-11-13 run. When a run's actual tokens differ from the
estimate by more than a third, say so in the log so they can be adjusted.
