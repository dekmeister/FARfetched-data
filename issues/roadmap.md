# Roadmap (ROADMAP-)

Planned data-repo work, not defects. The app's roadmap is in the FARFETCHed
repo's `plan.md`. [Index](../ISSUES.md)

### ROADMAP-2. Deviation records: FAA, TCDS links, text

Schema v14 holds special conditions, ELOS/ESF, exemptions and deviations as
link-only records (`data/deviations/`, docs/DATA_FORMAT.md §Deviation file).
EASA's consulted publications are emitted (429 on 2026-11-13). Design and
decisions: [reviews/2026-11-13-deviations-as-documents-proposal.md](../reviews/2026-11-13-deviations-as-documents-proposal.md).
Outstanding:

- **FAA records.** Every ELOS and SC (final + proposed, ~3,600) and the
  certification-relevant or TCDS-cited exemptions (~2,400), from the DRS
  catalogue. Re-run the catalogue first: it holds only exemptions today
  (tools/s00_docs/FAA_DEVIATIONS.md). Needs `final_id` (proposed SC → final),
  `key` ≠ number (DRS numbers repeat), and citations from the DRS regulation
  field, with `regulation_ref` verbatim. Each is a contract change.
- **TCDS line → record links** (`cert_basis_entry_deviations`, computed by
  identifier, verbatim line always shown). EASA: only 3 of 40 TCDS lines with a
  public-style identifier match a record (2026-11-13): the generic CS-23 SCs
  they cite (`SC-F23.1309-02`, `SC-F23.1353-02`) are not in EASA's consultation
  listing. FAA: about 240 of 461 lines name a DRS number.
- **EASA CRI lines → published proposals.** ~90 EASA publications name a
  product ("… Applicable to Boeing 787"). No publication carries the CRI label,
  so a link needs product + subject + cited section and is a reviewed override
  row with evidence, never a match.
- **Text (Phase 3)** for FAA SC finals (Federal Register HTML). Sample ~20 first.
- **Search.** Records are not in the FTS tables yet.
- **EASA numbers.** 301 of 429 records print no identifier on the listing; the
  downloaded PDFs (input/Deviations/EASA/) may. Reading them is OCR/extraction
  work, judged from a sample.

### ROADMAP-3. More regulation sources

Non-FAA issuers beyond EASA (TCCA, …), SFARs, and JAR (low priority).

### ROADMAP-4. Related provisions

Needs a schema decision.

- Hand-confirmed `provision_relations` and explicit cross-citations (e.g.
  MIL-HDBK-516 citing 14 CFR sections). The computed half is
  `provision_similarity` (v5).
- Reviewed "related references" on TCDS entries. Schema v11 holds what ELOS,
  special condition and exemption lines cite, as computed citations. A reviewed
  statement that a deviation applies to a section remains open.
- Identifier pages (one page per FAA special condition or ELOS memo number).
  Not built: on 2026-11-10 none of about 131 FAA identifiers appeared on two FAA
  TCDS, so a page would only repeat one TCDS. Revisit as FAA coverage grows. EASA
  CRI and ESF labels are numbered per project and must never be joined across
  TCDS.
- Citation reading leaves some real citations unlinked or partial, always with
  the verbatim line shown: shorthand lists (`CS 23.1301, .1309`, EASA.IM.A.502),
  paragraph lists split by a table column (`(c)(2), and 2017: (c)(5)`, A00072CE),
  JAR citations until JAR is ingested (ROADMAP-3), and EASA's section-bearing
  identifiers (`SC-F23.1309-02`).
- Merges and splits between editions. Schema v7 records each key's history
  but not that two keys became one. MIL-HDBK-516 cases: 516C §14 → 516D §4.4,
  §10 → §11, §18 → §9, 8.7 → new §10. Evidence: the 516B Appendix A.3 table,
  the 516D foreword ¶3, the `renumber_candidate` report (DOD-7); NATO-5.
- Cross-document links from 516B's `FAA Doc: 14CFR references` lines, the
  516/516A appendix table (DOD-2) and STANAG 4671 Annex C (NATO-3).

### ROADMAP-5. Structured serial applicability

Today `applicability` is verbatim (schema review Q-04). Bears on TCDS-1.

### ROADMAP-6. Deferred schema items

From the 2026-10-31 schema review:

- `document_revisions.cancelled_on`.
- `provisions.parent_id` (until a hierarchical document arrives).
- Per-TCDS files (F-24/Q-06). "Decide before a second model on an existing
  TCDS" has now happened: 3A12 models share a TCDS, kept consistent by the
  build's metadata check.
- `drs_guid` as a field (only in `_diag` today).

### ROADMAP-7. Find the official DRS API Technical Documentation PDF

The alfId is in `tools/s00_docs/FAA_DRS.md` §3.5. If found, it supersedes the
reverse-engineered notes.

### ROADMAP-8. CI and releases

The workflows exist (`.github/workflows/`, README §Publishing) but have never run
on GitHub.

**To close:** push `main`, push a `data-*-test` tag, fetch the pre-release with the
app's `scripts/fetch_db.py --url` (also from NFSN), then publish a first full
release when the maintainer judges the data ready.

### ROADMAP-9. Widen EASA TCDS coverage

The parser, coverage and cross-regulator assemble cover CS-23/25 aeroplanes
(open gaps: ETCDS-). Next: rotorcraft (CS-27/29), and downloading the noise
TCDS (TCDSN), recorded today only in the catalogue's `noise_*` columns.

### ROADMAP-10. Rotorcraft on the aircraft side

14 CFR 27 and 29 are ingested (1,267 versions), but no aircraft references
them, and ROADMAP-9 covers only the EASA half. Staging FAA rotorcraft TCDS
would put that data to use.

### ROADMAP-11. Decide whether FAA policy documents belong with the deviations

DRS doc type `AIR_POLICY` ("AIR Policy Statements, Memos and Deviations", 337
Current rows on 2026-11-10) and its siblings `POLICY` (23), `AVP_POLICY` (1) and
`FS_POLICY` (42) are not catalogued by the FAA deviations pipeline
(tools/s00_docs/FAA_DEVIATIONS.md). The one row sampled, a `Deviation Memo`, was
a deviation from FAA Order 8000.95 rather than from an airworthiness rule, but
the rest haven't been surveyed and `Policy Type` has other values.

**To close:** survey `Policy Type` and the cited rules, then decide whether any
of these documents bear on a certification basis.
