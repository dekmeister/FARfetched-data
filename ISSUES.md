# ISSUES.md

> **Outstanding items only.** When an issue is done, delete it from its area
> file in the same change that closes it; git history keeps the record. When
> an area file has no issues left, delete the file and its row below. No
> "Closed" sections, no change logs, no "fixed on" notes for finished work.

Outstanding data, pipeline and build issues for FARfetched-data and its
`tools/` sub-repo, plus the data-repo roadmap. The app's issues and roadmap
are in the FARFETCHed repo.

This page is the index. The items live in one file per area under
[issues/](issues/). Nothing listed is a known build failure unless the item
says so.

## Areas

| File | IDs | Covers |
|---|---|---|
| [issues/faa-regs.md](issues/faa-regs.md) | `FAA-` | 14 CFR Parts 23, 25, 27, 29, 36: revisions, dates, missing text, extraction |
| [issues/car.md](issues/car.md) | `CAR-` | CAR 3 (CAA and CAB reissue): OCR damage |
| [issues/easa-cs.md](issues/easa-cs.md) | `EASA-` | EASA CS-23/25/27/29: extraction, titles, tables |
| [issues/dod-hdbk.md](issues/dod-hdbk.md) | `DOD-` | MIL-HDBK-516 |
| [issues/nato-usar.md](issues/nato-usar.md) | `NATO-` | STANAG 4671 / AEP-4671 (USAR) |
| [issues/faa-tcds.md](issues/faa-tcds.md) | `TCDS-` | FAA TCDS parsing and aircraft files |
| [issues/easa-tcds.md](issues/easa-tcds.md) | `ETCDS-` | EASA TCDS download, parsing and FAA links |
| [issues/text-layout.md](issues/text-layout.md) | `TEXT-` | Label-line paragraph structure, tables, formulas (all issuers) |
| [issues/build.md](issues/build.md) | `BUILD-` | The build (`build.py`, `certbuild/`) and the SQLite contract |
| [issues/tooling.md](issues/tooling.md) | `PROC-` | Pipeline tooling, caches, process |
| [issues/roadmap.md](issues/roadmap.md) | `ROADMAP-` | Planned work, not defects |

Cross-cutting groups:

- **Flattened tables:** EASA-17, NATO-6, DOD-8, CAR-4, FAA-25 (and the format
  limits in TEXT-11).
- **Recoverable `TEXT MISSING`:** FAA-3, FAA-15, FAA-18, FAA-23, FAA-28, EASA-8.
- **Backups of `input/`:** PROC-10, ETCDS-1.
- **Part 36 references on aircraft:** TCDS-12 (FAA), ETCDS-15 (EASA).
- **Certification-basis coverage:** BUILD-12, TCDS-13, FAA-29.
- **Reported by site readers:** NATO-7 (GitHub #18), TEXT-14 (GitHub #3).

## Conventions

- **IDs are stable.** Each area numbers its own items. Use the next free
  number; never reuse or renumber an ID, so gaps are expected.
- **One item, one shape:**

  ```markdown
  ### FAA-1. Short statement of the problem

  What is wrong and the evidence (file, report, PDF page, FR cite). Bullets
  where there are several cases.

  **To close:** what would resolve it, or the decision needed.
  ```

  Date an item (`2026-11-07`) only when the date matters, e.g. a count or a
  web check that can go stale.
- **Background** for an area (pipeline docs, report paths) goes in the short
  paragraph at the top of its file, not in the items.
- When an item is closed, also remove it from the cross-cutting groups above.
- Refer to items as `ISSUES FAA-1` from other docs; link to the area file
  when a link helps.
