# Findings log: reviews/DATA_FINDINGS.md

`promote-staged` and `audit-data` both append to one file,
`reviews/DATA_FINDINGS.md`. It's the inbox for a later triage session. That
session moves each finding into `issues/<area>.md` (or GitHub), fixes it, or
dismisses it, and then deletes the entry. Once the file is empty, it's deleted
like any other finished review: in a dedicated commit, with the user's
confirmation (CLAUDE.md).

The skills only **append**. Never edit or delete earlier runs, and never edit
`issues/`. That's the triage session's job.

## File header (when creating the file)

```markdown
# Data findings log

Inbox of data problems found by the `promote-staged` and `audit-data` skills,
waiting for triage. Triage moves each entry into `issues/<area>.md` (or a
GitHub issue), fixes it, or dismisses it, then deletes the entry here. Each
finding is a lead read by a subagent against the local source copy; confirm it
against the source before acting. Delete this file when it is empty.
```

## One run

```markdown
## 2026-11-12 audit-data (seed 482113)

- **Scope:** 80 versions from 13 documents, 20 TCDS (10 FAA, 10 EASA). Focus: none.
- **Reading:** 100 items read by 13 Sonnet subagents; 4 could not be checked.
- **Result:** 9 blocker, 14 major, 6 minor findings in 21 items.
- **Automated (whole tree):** checks.py and scan_data.py counts per check:
  `regulation-no-refs 1174, cite-suspect 184, …` (compare with the last run).
- **Check candidates:** patterns a regex could catch, with an example each.

### F-20261112-01 · blocker · formula · documents/easa/cs-25/331.json CS25-18

ω formula read in row order.
- Data: `πV ω = 2V A`
- Source: `ω = πV / (2 V_A)` (input/Regs/EASA/CS-25/CS25-18.pdf p.1-C-4)
- Suggested area: issues/text-layout.md (TEXT-)
- Promotion: held back | promoted (pre-existing) | n/a
```

- IDs are `F-<run date>-<NN>`, numbered within the run. Add a letter if two
  runs fall on the same date (`F-20261112b-01`).
- Group the same defect across many items into **one** finding. List the
  affected files under it, or put the count and a few examples when there are
  many.
- Order the findings blocker → major → minor.
- For a promote run, the header also lists files promoted, files held back
  (each with its finding ID) and orphans left for the user, plus:
  - **Scripts:** fields.py counts (`tcds.holder 119 ok, 3 flag, …`) and
    `not_read.tsv` grouped by reason (`fields: verified by script 295, …`).
  - **Reading:** items by reason, read / available (from `plan.json`),
    and which were samples.
  - **Cost:** estimated vs actual subagent tokens, readers, waves.
- **Log a defect once.** A problem already in an open issue, or already
  logged as an F- entry in an earlier run still in this file, is not a new
  finding. Count it in one header line instead:
  `- **Pre-existing seen:** en-dash ranges 4 (already F-20261113-07), empty
  references 31 (already ISSUES TCDS-12), …`. Write an F- entry only for a
  defect nothing open covers yet. Promotion readers in diff mode shouldn't
  report unchanged text at all, so this line should be short.
- **Check candidates:** list a pattern once. Leave out any already in an
  earlier run's line still in this file; say `(seen again)` after one that
  recurs, instead of repeating it with a new example.
- Suggested area: one of the files in ISSUES.md's table. If an open issue
  already covers the finding, name it: `already ISSUES CAR-3`.
