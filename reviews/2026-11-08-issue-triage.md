# Issue triage and phased plan (2026-11-08)

A ranking of every open item in [ISSUES.md](../ISSUES.md), plus a recommended
order of work. Counts come from the 2026-11-07 `cert_basis.sqlite` and the
`data/` tree, which are unchanged since that build. `(new)` marks an item added
by this triage.

## Status (checked 2026-11-14)

Checked against `issues/` (an item with no heading there is closed) and `git
log`. The tables below are the 2026-11-08 ranking with closed items removed.
Where they disagree with `issues/`, `issues/` wins. Item counts, effort and
phase labels are from 2026-11-08 and were not re-ranked.

**Closed since the ranking (removed from the tables, 12):**
DOD-8, EASA-10, EASA-19, ETCDS-12, ETCDS-14, FAA-19, FAA-24, NATO-6, PROC-13, PROC-14, TCDS-11, TCDS-2. (PROC-13, PROC-14, TCDS-11, ETCDS-14, FAA-19,
EASA-19, EASA-10 closed by 2026-11-10; TCDS-2 at step 4 of the multi-model work;
ETCDS-12, FAA-24, DOD-8 and NATO-6 since.)

**Partly done, still open (6).** Do not treat these as finished:

| ID | Done | Still open |
|---|---|---|
| BUILD-12 | Report has a `coverage` section (0bc1bfd) | Maintainer picks a Phase 2 target, with a way to sample reference accuracy |
| ROADMAP-8 | CI workflows and `data-*` tag releases written (4e4a53d) | Never run on GitHub. Push `main`, push a `data-*-test` tag, fetch it with the app's `fetch_db.py` |
| PROC-15 | Reuse terms recorded in docs/RIGHTS.md and `data/NOTICE` (b26cd45, 9553aa7) | NATO and EASA terms unresolved; decide whether NATO text stays |
| PROC-17 | Sampler and 62-version pilot (2cd7c4b); `audit-data` skill ran a first 80-version audit on 2026-11-12 | Sample too small for per-issuer rates; findings in `DATA_FINDINGS.md` |
| TCDS-12 | Re-parse promoted: 69 models gained Part 36 references (b3ca90c) | 16 entries still cite Part 36 with none (6aff1d9) |
| ETCDS-15 | 18 aircraft promoted with Part 36 references (861a8c0) | The lines listed in the issue; composite lines need splitting |

**Open items that this ranking never covered (32):** BUILD-13, BUILD-14, BUILD-15, BUILD-16, BUILD-17, CAR-10, CAR-11, CAR-12, CAR-13, CAR-7, CAR-8, CAR-9, EASA-22, EASA-24, EASA-25, ETCDS-16, ETCDS-17, ETCDS-18, ETCDS-19, FAA-30, FAA-31, FAA-32, PROC-18, ROADMAP-11, ROADMAP-12, TCDS-14, TCDS-15, TCDS-16, TCDS-17, TCDS-18, TCDS-19, TCDS-20.
Rank them at the next triage. Of these, CAR-7 to CAR-13 and FAA-30 to FAA-32
come from the damage scan and reader reports; TCDS-14 to TCDS-20 and ETCDS-16
to ETCDS-19 come from the multi-model and manufacturer work; ROADMAP-11 and
ROADMAP-12 are decisions and the app release. BUILD-13 to BUILD-17 (from the
2026-11-11 database review) and ROADMAP-12 were filed on 2026-11-14.

**Phases: none is done.** Phase 0 and Phase 1 are in progress. Phases 2, 3 and 4
are not started in any way that meets their "Done when" test (TCDS-2 is closed,
and the multi-model TCDS work in `2026-11-10-multi-model-tcds-proposal.md`
advances Phase 2, but no coverage target is agreed). Phase 5 is a backlog, so it
never completes. Each phase heading below has its own status line from
2026-11-10, **not refreshed**. Delete this file once every phase is done and
nothing in it is still open.

**Not re-checked:** the "Stale items found" list and the "Where things stand"
figures (counts date from the 2026-11-07 build; the build is now schema 15).

## How items were ranked

In order of weight:

1. **Can a reader get a wrong answer without noticing?** Silently wrong beats
   visibly missing, which beats cosmetic.
2. **Reach.** How many models and provisions it touches, and whether a
   certification basis reaches it.
3. **Does it block other work?** Prerequisites rank above their size.
4. **Effort** breaks ties. S is hours, M is days, L is weeks or more.

The site is live and readers are filing reports, so publishing and accuracy
problems count as current, not future.

## Where things stand

- **Healthy:** full test suite, ruff and mypy pass. The build has 0 unresolved
  references, 325 models and schema 10, and the app supports schema 10.
- **Main finding:** the build's clean result overstates coverage. 1,330 of 1,850
  regulation lines have no references, and 97 of 325 models resolve to no
  provision (BUILD-12, TCDS-13).
- **Publishing:** the app fetches the latest GitHub release asset, but the repo
  has no releases and no CI (ROADMAP-8).
- **Reproducibility:** the staged tree is older than `data/`, so nothing shows
  today that the pipeline reproduces what is published (PROC-13).

## Not verified

- Which database build the live site is serving now.
- Whether the pipeline reproduces `data/`. Re-running it would have replaced the
  staged tree during the uncommitted EASA extract split in `tools/`.
- Whether newer amendments exist upstream. No web check was made.
- The rights position in PROC-15. It records an unassessed question only.
- The causes in TCDS-13 come from a sample, not a full count.
- App behaviour for TEXT-7 and TEXT-10 was not reviewed.

## Ranking

### Critical

| # | ID | Problem | Why here | Effort | Phase |
|---|---|---|---|---|---|
| 1 | BUILD-12 (new) ◐ | Build report does not measure basis coverage | The success metric hides the largest gap | S | 0 |
| 2 | TCDS-13 (new) | 1,330 of 1,850 regulation lines unresolved | Core product function; 97 models have nothing | L | 2 |
| 3 | ROADMAP-8 ◐ | No CI or releases | The app's data feed depends on it | M | 0 |
| 6 | PROC-15 ◐ (new) | Redistribution rights not assessed | Public now; the answer could remove content | S–M | 0 |
| 7 | FAA-29 (new) | Part 23 stops before the 2017 rewrite | 21 models cite amendments that are absent | L | 2 |
| 8 | PROC-17 ◐ (new) | No measured text accuracy | Without it, quality can't be claimed or tracked | M | 1 |

### High

| # | ID | Problem | Why here | Effort | Phase |
|---|---|---|---|---|---|
| 11 | EASA-17 | Tables flattened, often column by column | ~120 versions; numbers can be misread | L | 3 |
| 12 | TEXT-11 | Display formulas scrambled | ~150 files; misleading engineering content | L | 3 |
| 13 | TCDS-12 ◐ | FAA TCDS not re-parsed for Part 36 | 69 models gain references; trial already done | S | 1 |
| 14 | ETCDS-15 ◐ | EASA Part 36 citations unresolved | 35 models; same run as TCDS-12 | S–M | 1 |
| 16 | TEXT-1 | Trailing paragraphs attached to the last item | 1,024 rows; wrong paragraph scope | M–L | 3 |
| 17 | TEXT-8 | Real paragraph breaks dropped | Same fix as TEXT-1 | with TEXT-1 | 3 |
| 18 | TEXT-10 | Paragraph refs can verify under a wrong reading | False assurance on 402 verified refs | S–M | 1 |
| 20 | ETCDS-7 | Series sections not split (A330 and others) | 42 TCDS, including major airliners | M–L | 2 |
| 21 | ETCDS-6 | Shared basis sections not attached | Models get a partial or empty basis | M | 2 |
| 23 | FAA-3 | E23@23-2 missing, date unconfirmed | Reached by 96 models | M | 3 |
| 24 | CAR-6 (new) | 73 CAR `TEXT MISSING` untracked | Largest gap group; 57 versions on bases | M | 3 |
| 25 | CAR-5 | V-speed subscripts misread | Wrong symbols in OCR'd rules | M | 3 |
| 26 | CAR-1 | OCR-damaged labels leave text flat | 40 cases; affects paragraph refs | M | 3 |
| 27 | FAA-25 | Image-only DRS tables missing | Cells absent, including HIRF | M | 3 |
| 28 | FAA-28 | A25/B25@25-0 image-only | Foundational appendices missing | M | 3 |
| 29 | TEXT-14 (new) | Figures not represented | Reader-reported; needs a format decision | M | 3 |
| 32 | CAR-4 | CAB 3.304 table OCR-damaged | Wrong words, one provision | S | 3 |
| 33 | TEXT-6 | 171 flat-failed texts | Paragraph refs unverifiable | M | 3 |
| 35 | PROC-10 | `input/` backup (see Stale items) | No current offsite copy | S | 0 |
| 36 | ETCDS-1 | EASA TCDS replaced in place upstream | Irreplaceable; history not accumulating | S | 0 |
| 37 | NATO-7 (new) | USAR.865 title spilled into text | Open reader report; quick | S | 1 |
| 38 | EASA-8 | CS 25.773@16 missing but recoverable | Text is in the PDF | S | 1 |
| 39 | TCDS-1 | Cirrus additions model | Decide before Cirrus scope grows | S–M | 2 |
| 40 | TCDS-4 | CS citations on FAA TCDS | 12 lines; parser form known | S | 2 |
| 41 | ETCDS-10 | PC-12 paragraph letters unread | Common aircraft; small parser change | S | 2 |
| 42 | ETCDS-8 | 12 in-scope models refused | Includes ERJ 170 and BAe 146 layouts | M | 2 |

### Medium

| # | ID | Problem | Why here | Effort | Phase |
|---|---|---|---|---|---|
| 43 | ROADMAP-3 | More sources, JAR | JAR should rise: 34 TCBs cite it. Others stay later | L | 2 (JAR), 4 |
| 44 | FAA-27 | 25.725/727 Reserved vs deleted | Stub rule changes the published state | S | 1 |
| 45 | FAA-15 | Part 23 gaps; §401/403/413 stubs | Provisions look live after removal | S | 1 |
| 46 | FAA-18 | Missing text in Parts 25/27/29 | Mostly needs another source | M | 3 |
| 47 | FAA-23 | Part 36 gaps | FR research per gap | M | 3 |
| 48 | FAA-20 | 25-148/151 cite corrections | Wrong citation, known fix | S | 1 |
| 49 | FAA-12 | Amendment-level cites | Weaker traceability, not wrong | M | 5 |
| 50 | FAA-11 | Part 23 `--as-of` not enforced | Rerun could bring in the wrong edition | S | 1 |
| 51 | FAA-16 | FR lookup misses; §23.573@23-48 wording | Second part is a text-accuracy question | M | 3 |
| 53 | FAA-26 | Old DRS tables lack header rows | Decision; creates compare noise | S | 3 |
| 54 | EASA-20 | Collapsed versions keep worse text | Needs a policy decision | S | 1 |
| 55 | EASA-21 | CS-29 App B heading absent | Decision on one override | S | 1 |
| 56 | EASA-9 | `manifest_change_not_in_text` unreviewed | 24 possible missed changes | M | 3 |
| 58 | EASA-1 | CS-29 Amdt 10 corrigendum and date | Borrowed date in published data | S–M | 3 |
| 59 | EASA-7 | CS-23 Amdt 5/6 from republished files | Source check | M | 3 |
| 60 | EASA-18 | Chart labels read into text | Noise inside provisions | M | 3 |
| 61 | EASA-6 | Titles have no canonical source | Spot check | M | 3 |
| 62 | EASA-14 | Layout-specific heuristics | Ongoing watch on new PDFs | Ongoing | 5 |
| 63 | CAR-2 | Editorial notes read as rule text | Quick decision, then applied | S–M | 1 |
| 64 | CAR-3 | OCR junk at end of texts | Listed cases, override rows | S–M | 3 |
| 65 | DOD-7 | Continuity review limits | 516D new keys need a second pass | M | 3 |
| 66 | DOD-3 | Section intros dropped | Contract change | M | 4 |
| 67 | DOD-4 | Restarted numbering stays flat | Follows TEXT-13 | S | 3 |
| 68 | DOD-6 | Superscripts lost (10⁻⁷) | 23 places; values read wrongly | S | 3 |
| 69 | NATO-2 | `source_url` values return 404 | Provenance rule broken; cheap | S | 1 |
| 70 | NATO-4 | Tables and figures in the text layer | Handle with NATO-6 | M | 3 |
| 71 | NATO-5 | Continuity limits | 8 pairs to confirm | S | 1 |
| 72 | PROC-16 (new) | Versions without `source_url` | 936 CAR, 45 FAA | M | 3 |
| 73 | PROC-7 | Dry run misreports and can block | Promotion is a core step | S | 0 |
| 74 | PROC-12 | Very complex tools functions | Continue only when an area needs a fix | L | 5 |
| 75 | BUILD-8 | Model key is a name | Do before the corpus widens | M | 4 |
| 76 | TCDS-3 | Duplicate designations | 49 TCDS | M | 4 |
| 77 | TCDS-5 | Cover models unmatched | 1,151 designations | L | 4 |
| 78 | TCDS-10 | Whole-corpus path collisions | Only appears when widening | S–M | 4 |
| 79 | TCDS-7 | Citation 525 parse gaps | Published family | M | 2 |
| 80 | ETCDS-9 | Table-shaped basis fields | Wrong entry boundaries | M | 2 |
| 81 | ETCDS-13 | Indirect bases counted out of scope | Misleading coverage number | S–M | 2 |
| 82 | ETCDS-3 | OCR'd TCDS unreliable | Guard when parsing the 4 files | S | 2 |
| 83 | TEXT-2 | Paragraphs kept inline | 184 rows to review | M | 3 |
| 84 | TEXT-3 | Weak and fit splits | 584 rows; a sample read right | M | 3 |
| 85 | TEXT-4 | Ambiguous labels | 100 rows | S–M | 3 |
| 86 | TEXT-5 | Label gaps | 117 gaps in the report | M | 3 |
| 87 | TEXT-7 | FAA brackets span paragraphs | App rendering rule | S–M | 3 |
| 88 | TEXT-13 | Restarted lists nest wrongly | Contract change | M | 3 |
| 89 | ROADMAP-4 | Related provisions | Valuable; schema decision first | L | 4 |
| 90 | ROADMAP-9 | Widen EASA TCDS | After Phase 2 coverage | L | 4 |
| 91 | ROADMAP-10 (new) | Rotorcraft on the aircraft side | 1,267 versions unused | L | 4 |
| 92 | ROADMAP-2 | Special conditions, ELOS, exemptions | 1,866 basis entries could link to them | L | 4 |

### Low, accept, or wait

| # | ID | Problem | Disposition | Effort | Phase |
|---|---|---|---|---|---|
| 93 | FAA-1 | 23-56, 23-60 undeclared | Research when a TCDS needs it | M | 5 |
| 94 | FAA-4 | 25-118 skipped number | Wait for a TCDS | S | 5 |
| 95 | FAA-5 | 27-41, 29-48 undocumented | As FAA-1 | M | 5 |
| 96 | FAA-6 | Part 36 numbering above 36-32 | One confirmation | S | 5 |
| 97 | FAA-10 | Figure-only or absent text | Recheck if a source appears | S | 5 |
| 98 | EASA-2 | Amdt 2 ED Decision conflict | Quick source check | S | 5 |
| 99 | EASA-3 | Duplicate page in Amdt 1 PDF | Spot check | S | 5 |
| 100 | EASA-4 | 23.851 said to change but doesn't | Spot check | S | 5 |
| 101 | EASA-5 | Appendix I has no text layer | Accept unless a source appears | n/a | 5 |
| 102 | EASA-11 | Letter-spaced CS-29 text | Search and display only | M | 5 |
| 103 | EASA-12 | CS25-0 heading run-ons | Cosmetic | S | 5 |
| 104 | EASA-13 | 25.807(k) only in Amdt 27 | Ask or check Decisions | S | 5 |
| 105 | EASA-15 | Small extract improvements | Opportunistic | S | 5 |
| 106 | EASA-16 | Subpart label style | Display decision | S | 5 |
| 107 | DOD-2 | 516/516A cross-reference table | Follows ROADMAP-4 | M | 4 |
| 108 | DOD-5 | Titles are first sentences | Accept as documented | n/a | 5 |
| 109 | NATO-1 | Edition gap | Blocked on documents | n/a | 5 |
| 110 | NATO-3 | Annexes and Book 2 | Annex C follows ROADMAP-4 | M | 4 |
| 111 | TCDS-6 | 3A12 serial scope | Check the PDF with the 172 | S | 5 |
| 112 | TCDS-8 | FAA TCDS `source_url` | Appears done (see Stale items) | S | 0 |
| 113 | TCDS-9 | Restricted without a basis | Accept | n/a | 5 |
| 114 | ETCDS-2 | 29 TCDS not downloadable | Only if needed | n/a | 5 |
| 115 | ETCDS-4 | BA.025 is not a TCDS | Quick skip rule | S | 5 |
| 116 | ETCDS-11 | Noise sub-labels in the value | Cosmetic, but `raw_reference` scope | S | 5 |
| 117 | TEXT-12 | Opening words on the heading line | Accept or fix later | M | 5 |
| 118 | BUILD-3 | Two-step replace | Accept | S | 5 |
| 119 | BUILD-10 | Untyped JSON in the build | Refactor only | L | 5 |
| 120 | BUILD-11 | Build time | Not painful yet | M | 5 |
| 121 | PROC-1 | Cache misses never expire | Do with PROC-14 | S | 5 |
| 122 | PROC-2 | Authority-only verdict | Accept and review | S | 5 |
| 123 | PROC-3 | FR cite lookup heuristic | Override rows when needed | S | 5 |
| 124 | PROC-4 | FAA designator prefix | Only if reused | S | 5 |
| 125 | PROC-5 | Real DRS calls in tests | Appears done (see Stale items) | S | 0 |
| 126 | PROC-6 | Network counter | Cosmetic | S | 5 |
| 127 | PROC-8 | FAA extract serial | Only if batch time hurts | M | 5 |
| 128 | PROC-9 | Stale inputs | Owner decides | S | 5 |
| 129 | ROADMAP-5 | Structured serial applicability | Bears on TCDS-1; defer | L | 5 |
| 130 | ROADMAP-6 | Deferred schema items | Bundle with another contract change | M | 5 |
| 131 | ROADMAP-7 | Official DRS API documentation | Nice to have | S | 5 |

## Recommended phases

### Phase 0: Trusted baseline and publishing

Finish the uncommitted EASA split in `tools/` first. It is in progress and
PROC-13 needs a stable pipeline.

- **Prove the pipeline:** TCDS-11, then PROC-13. PROC-7 makes promotion safe.
- **Publish:** ROADMAP-8, including a dry run of the app's release fetch.
- **Measure:** BUILD-12, then PROC-14. PROC-1 can join PROC-14.
- **Protect:** PROC-15, PROC-10, ETCDS-1.
- **Close if confirmed:** PROC-5, TCDS-8.

**Done when:** an offline run reproduces `data/`, a tagged release reaches the
app, and the report shows basis coverage.

**Status 2026-11-10: in progress, not done (2 of 3 criteria met).**
- [x] Offline run reproduces `data/` (PROC-13 closed). That shows it is
  reproducible, not that it is correct.
- [ ] A tagged release reaches the app: ROADMAP-8 workflows have never run.
- [x] The report shows basis coverage (BUILD-12 report part). The target is
  still undecided.
- Done: TCDS-11, PROC-13, PROC-14. Open: PROC-7, ROADMAP-8, BUILD-12 (target),
  PROC-15, PROC-10, ETCDS-1, and the closes for PROC-5 and TCDS-8.

### Phase 1: Quick corrections and owner decisions

Small changes to published data, and decisions only the maintainer can make.
Start PROC-17 here so Phases 2 and 3 can be measured against a baseline.

- **Wrong content:** EASA-19, FAA-19, FAA-27, FAA-15 (stubs), FAA-20, FAA-24,
  NATO-7, EASA-8.
- **Decisions:** ETCDS-14, ETCDS-12, EASA-20, EASA-21, CAR-2, NATO-5.
- **References:** TCDS-12, ETCDS-15, TEXT-10, FAA-11, NATO-2.

**Done when:** GitHub #18 is answered, the links are confirmed, and an accuracy
baseline is recorded.

**Status 2026-11-10: in progress, not done (1 of 3 criteria met).**
- [ ] GitHub #18 answered: NATO-7 is open.
- [x] Links confirmed (ETCDS-14 closed).
- [ ] Accuracy baseline recorded: the PROC-17 pilot exists but is partial.
- Done: EASA-19, FAA-19, ETCDS-14. Narrowed: TCDS-12, ETCDS-15, PROC-17.
  Untouched: FAA-27, FAA-15, FAA-20, FAA-24, FAA-11, NATO-7, NATO-2, NATO-5,
  EASA-8, EASA-20, EASA-21, ETCDS-12, CAR-2, TEXT-10.

### Phase 2: Certification-basis coverage

The aircraft-to-regulation link is the product, so it comes before text polish.

1. TCDS-2 first, so corrections have a path.
2. Size TCDS-13 by cause and take the causes in order of models gained.
3. Parser gaps: ETCDS-6, 7, 8, 9, 10, 13 and 3; TCDS-1, 4 and 7.
4. New content: FAA-29, and JAR from ROADMAP-3.

**Done when:** an agreed coverage target from BUILD-12 is met, and every
remaining zero-resolution model has a recorded cause.

**Status 2026-11-10: not started.** No target is agreed, and TCDS-2 and
TCDS-13 are untouched. ETCDS-16 (new) bears on this phase.

### Phase 3: Text fidelity

Work by shared cause, not by issuer.

- **Tables and formulas:** build the EASA-17 geometry extractor once, and reuse
  it for NATO-6, DOD-8 and NATO-4. Then TEXT-11, FAA-25, FAA-26, CAR-4, DOD-6.
- **Figures:** TEXT-14 decision, which also answers GitHub #3.
- **Paragraph structure:** TEXT-1 and TEXT-8 together, then TEXT-2 to 7, 13,
  DOD-4, CAR-1.
- **Missing text:** FAA-3, CAR-6, FAA-28, FAA-18, FAA-23.
- **OCR and source checks:** CAR-3, CAR-5, EASA-1, 6, 7, 9, 10, 18, FAA-16,
  DOD-7, PROC-16.

**Done when:** PROC-17 shows the error rate has dropped, and each remaining
`TEXT MISSING` has a recorded reason.

**Status 2026-11-10: not started.** Only EASA-10 is closed, as part of
EASA-19. CAR-7 and EASA-22 (new) belong here.

### Phase 4: Widen the corpus

Only after Phase 2, so scale does not multiply parser errors. Settle BUILD-8
first, because a key change is cheapest now.

- **Aircraft:** TCDS-3, 5, 10, ROADMAP-9, ROADMAP-10.
- **Documents and links:** ROADMAP-2, rest of ROADMAP-3, ROADMAP-4, DOD-2,
  DOD-3, NATO-3.

**Status 2026-11-10: not started.** It waits on Phase 2.

### Phase 5: Backlog

Everything else stays open and gets done when an area is next touched: FAA-1,
4, 5, 6, 10, 12; EASA-2, 3, 4, 5, 11, 12, 13, 14, 15, 16; DOD-5; NATO-1; TCDS-6,
9; ETCDS-2, 4, 11; TEXT-12; BUILD-3, 10, 11; PROC-1, 2, 3, 4, 6, 8, 9, 12;
ROADMAP-5, 6, 7.

**Status 2026-11-10:** by design, nothing is scheduled. None of these is closed.

## Stale items found

These were left unchanged for the maintainer to confirm.

- **TCDS-8:** all 21 FAA TCDS now have a `source_url`, so this looks closable.
- **PROC-5:** `tools/s99_tests/conftest.py` already blocks `urlopen` in every
  test, so this looks closable.
- **PROC-10:** "has no backup" is out of date. The rsync mirror on the second
  drive holds all 8,387 files. Both drives are on one machine, and the newest
  file in the offsite folder is dated 2026-09-04, before the EASA TCDS download
  of 2026-11-02. The live risk is the lack of a current offsite copy.
- **ETCDS-15:** says only IM.A.013 resolves Part 36. A.060 and A.061 do too (7
  models across 3 TCDS, which matches TCDS-12's count).
- **PROC-12:** its line counts and paths predate the recent splits. No non-test
  file now exceeds 1,000 lines in the working tree.
- **ROADMAP-3:** "JAR (low priority)" no longer fits the basis evidence.
- **Handover:** `tools/s00_docs/reviews/2026-11-03-easa-tcds-handover.md` looks
  finished, with its open points carried by ETCDS-14 and TEXT-3. It is a
  deletion candidate once the link in `issues/easa-tcds.md` is fixed.
