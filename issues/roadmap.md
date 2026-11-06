# Roadmap (ROADMAP-)

Planned data-repo work, not defects. The app's roadmap is in the FARFETCHed
repo's `plan.md`. [Index](../ISSUES.md)

### ROADMAP-2. Special conditions, ELOS and exemptions as documents

`doc_kind` already allows them; they need ingestion and a provision model.
FAA special conditions are on DRS.

### ROADMAP-3. More regulation sources

Non-FAA issuers beyond EASA (TCCA, …), SFARs, and JAR (low priority).

### ROADMAP-4. Related provisions

Needs a schema decision.

- Hand-confirmed `provision_relations` and explicit cross-citations (e.g.
  MIL-HDBK-516 citing 14 CFR sections). The computed half is
  `provision_similarity` (v5).
- "Related references" on TCDS entries, e.g. an exemption that applies to a
  regulation in the basis, without making it part of the basis.
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

There is no `.github/workflows/` yet.

- On push to `main`: validate, build, test.
- On tags: upload `cert_basis.sqlite` and `cert_basis_report.json` as release
  assets for the app's deploy to fetch.
- Dry-run the release fetch with a placeholder DB first (NFSN).

### ROADMAP-9. Widen EASA TCDS coverage

The parser, coverage and cross-regulator assemble cover CS-23/25 aeroplanes
(open gaps: ETCDS-). Next: rotorcraft (CS-27/29), and downloading the noise
TCDS (TCDSN), recorded today only in the catalogue's `noise_*` columns.
