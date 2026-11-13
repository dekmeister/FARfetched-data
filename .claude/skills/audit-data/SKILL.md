---
name: audit-data
description: Audit a random, spread-out sample of the published data/ against its local source copies. By default 80 provision versions (round-robin across every document and era) and 20 TCDS. Runs whole-tree automated checks, has Sonnet subagents read the sample against the source PDFs/HTML for the typical pdftotext/regex/OCR failures, and logs findings to reviews/DATA_FINDINGS.md. Use when the user asks to audit, spot-check or sample the data. Takes an optional focus (documents, issuers, TCDS issuer, an error type, sample sizes).
argument-hint: "[focus, e.g. 'CS-25 and CAR 3 formulas, 40 regs, EASA TCDS only']"
---

# audit-data

Estimate how good the published data is, find defects the scripts miss, and
turn repeated defects into candidate checks. Read-only, apart from the
findings log.

## Rules

- **Don't change anything.** No edits to `data/`, `tools/` (code or
  `overrides/`), `certbuild/`, `scripts/`, `issues/` or `docs/`. Don't fetch
  anything. Sources are the local copies under `input/` (CLAUDE.md
  "Reproducible is not correct").
- The only repo file you write is `reviews/DATA_FINDINGS.md` (append only;
  format in `reference/LOG.md`). Keep everything else in `$S`, a fresh folder
  in the session scratchpad (`$S=<scratchpad>/audit-<date>`).
- Reading is done by Sonnet subagents, not by you or the user. Scripts cover
  the whole tree. Reading covers the sample.
- Never call anything verified unless a reader checked it against the source.

Scripts (run from the repo root): `A=.claude/skills/audit-data/scripts`.

## 1. Turn the focus into a sample

With no focus: `--regs 80 --tcds 20`, over everything. Otherwise map the
user's words onto `sample.py` flags, and keep the rest of the request as an
instruction for the readers:

| Focus | Flags |
|---|---|
| a document ("CS-25", "Part 23") | `--document easa/cs-25`, `--document faa/23` |
| an issuer ("CAR", "EASA", "NATO") | `--issuer caa --issuer cab`, `--issuer easa`, `--issuer nato` |
| TCDS from one authority | `--tcds-issuer FAA` / `EASA` |
| an error type ("formulas", "tables", "V-speeds") | `--grep` with a regex that finds candidates (`'\$\$\|=\|_\{'`, `'\{\|'`, `'\bV_?\{?[A-Z]'`), plus a reader instruction to concentrate on it |
| sizes ("50 regs", "only TCDS") | `--regs N`, `--tcds N` (0 skips) |

Document directories: `faa/{23,25,27,29,36}`, `easa/cs-{23,25,27,29}`,
`caa/car-3`, `cab/car-3-reissue`, `nato/stanag-4671`, `dod/mil-hdbk-516`.
If the focus can't be mapped, ask the user. Otherwise just go.

```bash
uv run python $A/sample.py --regs 80 --tcds 20 [flags] --out-dir $S
```

Note the printed seed. It goes in the log so the sample can be redrawn.

## 2. Automated checks

The whole tree, for counts, plus the sample, for the readers:

```bash
PYTHONPATH=. uv run python $A/checks.py --root data > $S/checks_all.tsv 2> $S/checks_counts.txt
uv run python -m scripts.scan_data --all > $S/scan_all.tsv 2> $S/scan_counts.txt
PYTHONPATH=. uv run python $A/checks.py --paths $S/paths.txt > $S/checks_sample.tsv
uv run python build.py --check
```

`checks.py --list` and `scan_data --list` explain each check. Compare the
counts with the last `audit-data` run in `reviews/DATA_FINDINGS.md` (if there
is one) or with git history, and note any check whose count moved. Don't log
whole-tree hits one by one. Log counts per check, and examples only for a
check that's new or growing.

## 3. Reading

Split the sample into batches: provision versions in batches of 8, TCDS in
batches of 3 (each needs the whole basis section of a PDF). Give each batch
the `checks_sample.tsv` lines for its files.

```bash
mkdir -p $S/batches $S/findings
split -l 8 -d --additional-suffix=.jsonl $S/regs.jsonl $S/batches/regs_
split -l 3 -d --additional-suffix=.jsonl $S/tcds.jsonl $S/batches/tcds_
```

Dispatch one **Sonnet** subagent per batch (`model: "sonnet"`,
general-purpose), several at once. Prompt:

> Read `.claude/skills/audit-data/reference/READER.md` and follow it in
> **full mode**. Your batch is `$S/batches/<name>.jsonl`, items sampled from
> the published data/.
> Write your findings to `$S/findings/<name>.jsonl`. Automated hits for these
> files (leads only; confirm them in the source): <lines>. [Focus from the
> user, if any.]

Wait for every reader to finish. Collect `$S/findings/*.jsonl`. Drop findings
with no source excerpt or reference. Send each low-confidence `blocker` to a
second Sonnet reader with just that item before you log it as a blocker.

## 4. Log

Append one run to `reviews/DATA_FINDINGS.md` (`reference/LOG.md`). It holds:

- **Scope:** seed, focus, sample spread (versions per document, TCDS per
  issuer).
- **Result:** items clean, with issues, or could not be checked, **per
  document and for TCDS**. This is the error rate the audit is for.
- **Automated:** counts per check and how they moved.
- **Findings:** grouped by cause, blocker → major → minor, each with an area
  file. Name an existing ISSUES item when one covers it, and say "already
  ISSUES X" rather than raising a duplicate.
- **Check candidates:** every pattern the readers flagged as regex-catchable,
  with the check it would add to `scripts/scan_data.py` or `checks.py`, and an
  example. Automation is the point. A defect class found by reading that a
  script could find across the whole tree is the most valuable output.

## 5. Report

Tell the user, briefly: the sample and seed, the error rate per document and
for TCDS, the top causes, and the check candidates. Point to the log entry.
Don't paste the findings.
