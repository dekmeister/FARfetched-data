# ISSUES.md

Open issues and review notes. Items are things a later review should check or
decide. Nothing here is a known build failure. Dates are 2026-10-31 unless noted.

Source: the "authority-only amendments" work (data commit `66a087b`, tools
commit `07c543c`). See `tools/docs/FAA_DRS.md` §3.8 and
`tools/regulations/faa/authority_only.py`.

## Data questions (need a human or a source)

1. **23-56 and 23-60 are undeclared and unexplained.** DRS has no document for
   either. A Federal Register full-text search found no rule naming them (the
   hits were airspace rules, ADs and part numbers), and eCFR and `regs.csv`
   don't list them. This is absence of evidence, not proof they were never
   issued. Not checked: a general web search, FAA's own amendment-history
   tables, FR rules published between 2002-03 and 2007-08 (23-56) and
   2008-12 and 2011-08 (23-60) read by hand. If a TCDS ever cites one as a
   range endpoint, the build will reject it ("unknown revision"); that is the
   intended behaviour until a source turns up.
2. **Existing `_document.json` dates disagree with the manifest** (reported in
   `tools/out/reports/incomplete_authority_only.tsv`, nothing was changed):
   - 23-43: data 1993-05-10, manifest 1996-01-04 (61 FR 252, doc 96-135). The
     manifest value comes from the `_rule_for` correction logic (report kind
     `fr_correction_names_designator`) and looks wrong to me: the 23-43 CITA
     cite is 58 FR 18970 (1993-04-09).
   - 23-51: data 1996-03-12, manifest 1996-03-11.
   - 23-58: data 2009-07-09, manifest 2008-04-07 (73 FR 12542, FR API).
   Decide which source is right per amendment, fix the manifest logic or the
   data, and promote any change with `emit --replace`.
3. **25-118** is a DRS `Sec. 0.0` document saying the number "was inadvertently
   skipped and will not be used". It is deliberately not declared. A TCDS that
   cites "through 25-118" would need a human decision (probably use 25-117).
4. **27-41 and 29-48** have no DRS document and are undeclared. Same open
   question as item 1.
5. **Part 36 gap list is mostly noise.** The manifest assumes contiguous
   numbering. Part 36 isn't: 36-32 is 2022, 36-54 is 2002 (report kind
   `ordinal_out_of_date_order`). 36-33 to 36-53 (21 designators) have no DRS
   document and probably never existed; unconfirmed. Separately, 36-1, 36-2,
   36-3, 36-5, 36-11 and 36-32 have real sections in DRS that the eCFR-derived
   manifest never listed (CITAs restart). They need the section pipeline, not
   this one.
6. **Authority-only declarations for Parts 25, 27, 29 and 36 are not promoted.**
   `data/` only holds Part 23. 25-85, 27-31, 27-39, 29-37, 29-46, 36-21 and
   36-23 are in the regenerated `tools/out/work/manifest_faa_{p}_part_amendments.json`
   and will flow in with those parts' bulk emits. Check they are there when
   each part is first promoted.

## Code and process risks

7. **DRS lookup cache never expires.** `tools/out/cache/drs/far_amendment/`
   caches hits and misses for good (`--force` refreshes). A designator that is
   a gap today and gets a DRS document later stays "none" until forced. Gaps
   are by definition below an existing ordinal, so this is unlikely, but a
   time limit like the TCDS listing's 24 h would be cheap.
8. **The verdict trusts DRS listing fields, not the document text.** `judge()`
   uses `Section == "Sec. 0.0"` plus the title. I read the text of all ten
   documents by hand once (each only revises or "continues to read" the
   authority citation, 23-55 also removes SFAR 41) but the code does not. A
   `Sec. 0.0` document with an unexpected title is `unrecognised`, not declared.
9. **FR cite lookup is a window heuristic.** It scans weekdays from 30 days
   before to 7 days after the DRS effective date for a rule whose docket line
   names the designator. Zero or several matches means no cite and an
   `authority_only_no_fr_cite` report row (the revision is still declared).
   27-39 and 29-46 have an empty FR `effective_on`, so the date cross-check
   does not apply to them. DRS prints their docket as `FAA-19998-4390`; the FR
   has `FAA-98-4390`.
10. **`emit --part` assumes designator prefix = part** (`23-47` belongs to `23`).
    True for FAA; wrong for CAR or EASA designators. Fine while emit is
    FAA-only.
11. **Shared staging.** `tools/out/extracted/faa/` held 1,280 files from another
    session and `promote` scans all of `tools/out/staged/`. I scoped `emit`
    with a missing `--in-dir`. A plain `emit` then `promote` would sweep in
    everything. Consider a `--only` filter on `promote`.
12. **Any test that calls `manifest.main` must pass `--skip-drs` or patch
    `far_amendment_documents`**, or it will try the real DRS. I fixed
    `test_main_end_to_end`; nothing enforces it for new tests. A conftest guard
    that fails on a real DRS request would.
13. **Part 23 must be run with `--as-of 2017-08-29`.** The default is now the
    newest eCFR date, which is the post-rewrite Part 23. The README says so;
    nothing enforces it.
14. **Network-call counter.** A DRS lookup adds 1 to `http.network_calls`
    however many pages it took, so the stderr "network calls: N" undercounts.
15. **Regenerated work files.** `manifest_faa_{25,27,29,36}*` in
    `tools/out/work/` were overwritten with this run's output. The previous
    copies were only in a session scratchpad and are gone. Differences are the
    new declarations plus whatever the other session's manifest changes did.

## Not done

- No aircraft were added. SR20 (A00009CH Rev 25, through 23-47) and DA 42
  (A57CE Rev 34, through 23-55) can now be, but any TCDS citing 23-56 or
  23-60 cannot (item 1).
- `ruff`, `mypy`, `pytest` and `build.py` all passed after the change. The
  build report (`cert_basis_report.json`) was not reviewed beyond the summary
  line.
