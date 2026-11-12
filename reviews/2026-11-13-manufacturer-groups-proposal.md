# Manufacturer groups for display (proposal, 2026-11-13)

Status: **approved 2026-11-13, implemented (uncommitted).** The maintainer
took the recommendations and asked for less complexity. The design was cut
to what has value:

- no `manufacturer_groups` table: `manufacturers.group_name` is a column;
- no candidate report (first-word families are mostly noise);
- no group-name clash check;
- v13 is this change only (D5).

Kept: one group per manufacturer (build), and in assemble: stale rows, two
rows for one manufacturer, a missing column, and a lookalike group with a
name that has no row. Decisions as taken: D1 option C; D2 no row = legal
name; D3 yes; D4 marques not now (TCDS-20); D5 own v13; D6 Gulfstream,
Diamond, Daher and Airbus (Defence and Space GmbH, S.A, Poland) grouped,
ZLIN and Airvan left apart.

Evidence (read against `input/` by a subagent): Diamond's TCDS state the
GmbH-to-Inc. transfers (DA 40, DA 62). For Gulfstream, Daher and Airbus no
TCDS links the holders legally; the rows cite the shared name the TCDS
print (model names, headings, EADS predecessor names) and say "Display
group, not a legal relation". §8 lists what is left open.

## 1. How a manufacturer name flows today

| Stage | What holds the name | Kept | Lost |
|---|---|---|---|
| TCDS PDF (`input/`) | cover / holder field | everything | — |
| Parser → `tools/out/derived/tcb/{issuer}/{tcds}/` | `_tcds.json` `holder` and each fragment's `manufacturer`, `clean_name`d. Identical in all 363 fragments; present on all 619 `_tcds.json` | printed holder per TCDS | — |
| `assemble` → `tools/out/staged/aircraft/` | `manufacturer` = primary fragment's holder, then `manufacturers.respell` (spelling / renamed / distinct rows). Path slug from the result | the canonical legal company | **the printed holder of every TCB**. For a linked model, the other regulator's holder is dropped entirely |
| `promote` → `data/aircraft/` | same as staged | | |
| `build.py` → SQLite | `manufacturers(id, name UNIQUE)`, `aircraft_models.manufacturer_id`, `search_aircraft.manufacturer` | one name per company | — |

DATA_FORMAT says so explicitly: "The name printed on each TCDS is not kept in
`data/`; the rows record it." Today **23 TCBs** print a holder different
from their file's `manufacturer`. Examples: A16NM prints "Gulfstream
Aerospace LP" under "Gulfstream Aerospace LP (GALP)"; EASA.A.005 prints
"DIAMOND AIRCRAFT INDUSTRIES GMBH"; the FAA validation of the GA8 prints "GA8
Airvan (Pty) Ltd". `tools/out/` is regenerable, but none of this reaches the
contract. So requirement 2 (nothing lost) is **not met today** for the
printed name, and this proposal fixes that too.

The app (FARFETCHed) reads `mf.name` everywhere: the nav menu, the
`?manufacturer=` filter, the index sort and the export. It also hard-codes
`MANUFACTURER_ALIASES = {"cessna": "textron"}` in `services/search.py`. That
is curation living in the wrong repo.

## 2. What the corpus looks like

- Catalogues: 738 distinct aircraft holder strings (FAA current + EASA; 1,057
  including historical FAA), 677 `company_key`s.
- Grouping by first word gives 67 families with more than one key,
  175 keys in all. **Most are false**: "American …" (6 unrelated companies),
  "Air …", "General …", "Aero …", "FS 2000/2001/2002/2003 Corp.", "Wright
  Jr. Elzie / Wright Kevin". Some real groups don't share a first word:
  "Hamilton Metalplane Division Boeing Airplane Co.", "Pilatus Britten-Norman".
  No name rule works. Every group is a judgement.
- How ambiguous the real families are:
  - **Clear:** Gulfstream Aerospace Corporation / GALP; Diamond GmbH / Inc.;
    Daher Aircraft SAS / Daher Aircraft Design LLC; Textron Aviation Inc. /
    Textron Aviation Defense LLC; Bombardier Inc. / Bombardier Aerospace
    Inc; Saab AB and its divisions.
  - **Judgement calls:** Airbus (S.A.S.) / Airbus Helicopters / Airbus
    Canada LP / Airbus Defence and Space GmbH and S.A. (CASA) / Airbus
    Poland. Lockheed Aircraft Corporation / Lockheed Martin. Bell Textron vs
    Textron Aviation: same parent, but users say "Bell". ZLIN AERO /
    ZLIN AIRCRAFT. GA8 Airvan / Airvan10.
  - **Same name, unrelated companies:** Dornier Luftfahrt / Dornier
    Seawings; Helio Aircraft Corporation / Helio Aircraft LLC / Helio Alaska;
    Viking Air / Viking Flying Boat. These must not be grouped by default.
- **Marque ≠ holder.** "Textron Aviation Inc." holds the Cessna, Beechcraft
  and Hawker TCs. Users think "Cessna 172", but a holder-level group can only
  say "Textron Aviation". Splitting by marque needs a per-TCDS row (see D4).

In `data/` today (64 manufacturers), the multi-company candidates are
Gulfstream (2), Diamond (2), Daher (2), Airbus (4: S.A.S., Defence and Space
GmbH, Defence and Space S.A, Poland), ZLIN (2) and Airvan (2, one untracked
dir from other work).

## 3. Options considered

| | Option | Verdict |
|---|---|---|
| A | App-side lookup table (extend `MANUFACTURER_ALIASES`) | Rejected. The curation has no evidence trail and no review step, every consumer repeats it, and it doesn't fix the lost printed name. |
| B | Make `manufacturer` itself the group name ("Gulfstream") | Rejected. It overwrites the legal holder (requirement 2), merges `distinct` companies, and moves paths. |
| C | **Three separate names: printed holder per TCDS, legal holder per model, display group per company, each from its own source** | **Recommended.** Additive and traceable, and the existing `distinct` decisions stay intact. |
| C′ | As C, but the groups live in a new `data/manufacturers.json` registry file | Cleaner normalisation, but it adds a new file kind, schema and path rule for one string per company. The existing "repeat it, build checks it's identical" pattern (`tcb[].tcds` metadata) does the same job. Not recommended now. |

## 4. Recommendation (option C)

### Three names, three sources

| Name | Means | Where it comes from | JSON | SQLite |
|---|---|---|---|---|
| printed holder | exactly what this TCDS prints (cleaned only by `clean_name`: hyphens, NFKC, spaces) | parser, `_tcds.json` `holder` | **new** `tcb[].tcds.holder` | **new** `tcds.holder TEXT NOT NULL` |
| manufacturer | the legal TC holder, one spelling per company | `manufacturers.tsv` (unchanged) | `manufacturer` (unchanged) | `manufacturers.name` (unchanged) |
| manufacturer group | display name a user recognises | **new** `tools/overrides/manufacturer_groups.tsv` | **new** top-level `manufacturer_group` | **new** `manufacturer_groups(id, name UNIQUE)`, `manufacturers.group_id NOT NULL` FK |

`holder` sits on `tcds` because it is a fact of the TCDS cover. Every model
file sharing a TCDS must then agree on it, and the build's existing
"TCDS metadata identical" check covers that for free.

### Override file: `tools/overrides/manufacturer_groups.tsv`

```
manufacturer	group	evidence
Gulfstream Aerospace Corporation	Gulfstream	EASA.IM.A.169 cover …; models marketed as Gulfstream GIV, G500 …
Gulfstream Aerospace LP (GALP)	Gulfstream	FAA A16NM: TC transferred from IAI to Gulfstream Aerospace LP 2002-03-26; model "Gulfstream G150" …
```

- Keyed on the **canonical** manufacturer, after `manufacturers.tsv`. It is
  a separate file because it makes a different claim: display grouping, not
  legal identity. Mixing it into `manufacturers.tsv` would blur `distinct`.
- A manufacturer with no row is its own group, named exactly as its
  `manufacturer` (D2).
- Fatal in `assemble`, same style as the registry: a missing column; empty
  evidence; a row whose manufacturer no staged file has (stale); a group
  name equal to a *different* company's legal name that isn't itself in
  that group.
- Fatal: **a `distinct` lookalike set from `manufacturers.tsv` whose members
  have no group rows** (D3). Distinct companies with a shared name are the
  cases where grouping matters, so they get an explicit decision either
  way. Groups can still differ ("Helio" / "Helio Alaska").
- New candidate report `tools/out/reports/manufacturer_group_candidates.tsv`:
  first-word and lookalike families among staged manufacturers that have no
  group row. Evidence for a human, never applied.
- Evidence is read by Sonnet subagents against `input/` (TCDS holder records,
  marketing names in the model sections), as a separate step.

### Build (`certbuild/`)

- `sources.py` / schema: `manufacturer_group` required string, non-empty;
  `tcds.holder` required string, non-empty.
- New load check: every file with the same `manufacturer` has the same
  `manufacturer_group` (fail loud, listing the files).
- `ddl.py`: `manufacturer_groups`, `manufacturers.group_id`, `tcds.holder`;
  `SCHEMA_VERSION` bump.
- `aircraft.py` / `lookups.py`: upsert group, then manufacturer with its
  group; insert holder.
- `search.py`: `search_aircraft.manufacturer` holds the group, legal name
  and distinct printed holders, newline-joined. No new FTS column. "GALP",
  "Gulfstream" and every printed spelling find the model.
- Report: row counts for the new table, plus `manufacturer_groups` with more
  than one manufacturer.

### Tools

- `assemble.py`: copy `facts.holder` into each fragment's `tcb[].tcds.holder`
  (primary and others). Apply group rows after `respell`. Write
  `manufacturer_group`.
- `s00_common/manufacturers.py` gets a sibling `manufacturer_groups.py`
  (loader + checks), in the same shape and under ~200 lines.
- Paths are unchanged: still `{slug(manufacturer)}/{slug(designation)}`.

### Scope notes

- **Former names and search aliases** (TCDS-20 second half; the app's
  `cessna → textron`) are **not** in this change. The group fixes the
  display. Searching "Israel Aircraft Industries" or "Cessna" needs names
  that are neither printed holders nor groups. That stays in TCDS-20, and
  D4 decides whether marques join it.

## 5. Contract impact and what the app needs

**JSON (aircraft model file):** two new required fields, `manufacturer_group`
(top level) and `tcb[].tcds.holder`. Schema, DATA_FORMAT §Aircraft model
file, the factories and tests change in one commit. Every aircraft file in
`data/` changes on promote, by those two fields only.

**SQLite: v12 → v13** (or v14, see D5). New table `manufacturer_groups`, new
NOT NULL columns `manufacturers.group_id` and `tcds.holder`, and a changed
meaning of `search_aircraft.manufacturer`. SCHEMA_HISTORY gets a row.

**App (FARFETCHed) changes, one release with the DB:**
1. `SUPPORTED_SCHEMA` → 13.
2. Nav menu and index dropdown: list `manufacturer_groups.name`, with models
   under the group. Sort by group, then designation.
3. `?manufacturer=` filter: match on the group name (or rename the
   parameter to `?maker=` and redirect the old one). A legal name that is no
   longer a group 404s today, so the old links need a decision in the app.
4. Model / TCB page: group as the heading, "TC holder: <manufacturer>"
   beneath it, and per TCB "Printed on <TCDS>: <holder>" when it differs.
5. Export (`services/export.py`): add `manufacturer_group` and per-TCB
   `holder`.
6. Search: keep or drop `MANUFACTURER_ALIASES`. It still works, but it
   belongs in TCDS-20 / D4.
7. Model URLs (`/aircraft/{issuer}/{tcds}/{model}`) are unaffected.

## 6. Decisions needed

| # | Question | Recommendation |
|---|---|---|
| D1 | Approve option C: printed holder on `tcb[].tcds.holder`, display group as top-level `manufacturer_group`, groups in `manufacturer_groups.tsv` | Yes |
| D2 | Default for a manufacturer with no group row: its legal name ("Pilatus Aircraft Ltd."), or must every manufacturer get a simpler name ("Pilatus")? | Default to the legal name. Add a short-name row where wanted (a group of one is allowed). Rows then grow only with what's staged, as the registry does. |
| D3 | Must every `distinct` lookalike set carry explicit group rows (fatal if not)? | Yes. Those are exactly the ambiguous cases. |
| D4 | Marques (Cessna / Beechcraft / Hawker under Textron Aviation Inc.): in scope now, via a `tcds`-scoped group row? | Not now. Groups stay per company. Log marques with former names under TCDS-20. |
| D5 | Contract version: the 2026-11-11 DB review also plans v13 (steps 5–7). Share one bump and app release, or go first as v13? | Go first as v13 with its own app release; it is additive and doesn't depend on DB review decisions. |
| D6 | First group rows for today's `data/` (each with subagent-read evidence): Gulfstream (Corp + GALP), Diamond (GmbH + Inc.), Daher (SAS + Design LLC). Also Airbus (which of S.A.S. / D&S GmbH / D&S S.A / Poland?), ZLIN (AERO + AIRCRAFT?), Airvan (GA8 Airvan + Airvan10?) | Do the first three. Decide Airbus, ZLIN and Airvan yourself; I'd group all four Airbus as "Airbus" and leave ZLIN and Airvan separate until a source shows lineage. |

## 7. After approval: implementation and evidence

1. Tools: `manufacturer_groups.py` + tests, `assemble` holder and group,
   candidate report. Run `compare_stages`: only `manufacturer_group` and
   `tcds.holder` added, nothing else.
2. Build: schema, DDL v13, inserts, search, report, docs (DATA_FORMAT,
   SQLITE, SCHEMA_HISTORY), `tests/factories.py`, contract/validation/search
   tests. Run `compare_builds`: only the new table, columns and
   `search_aircraft.manufacturer` change.
3. Subagents read the evidence for each group row against `input/`.
4. `promote --dry-run`: a script asserts that every changed file differs
   only by the two new keys. Then `build.py`, `pytest`, `ruff`, `mypy`.
5. Log anything open in `issues/faa-tcds.md` (TCDS-20: marques, former
   names) and leave the app checklist (§5) for the FARFETCHed repo.

Coordination: other agents have uncommitted aircraft changes in `data/`
(GA8, Airvan10, deleted Gulfstream / Citation files). The promote evidence
will be taken on top of whatever is staged then, and none of their changes
are touched.

## 8. Open after implementation

- **Promotion (maintainer).** `data/` isn't promoted: the build needs both new
  keys in every aircraft file, so `data/` builds again only after
  `promote --aircraft` of all 327 staged files. Evidence (2026-11-13): 323
  files differ from `data/` only by `manufacturer_group` and `tcds.holder`.
  Four (Bölkow BO 209 MONSUN, C-295, BN2T-4S, HA-420) also carry EASA lines
  re-split by committed parser code (tools `b7f0931`, not re-parsed until
  now, not read against the PDFs). The two A330 files are orphans: the
  ETCDS-16 headline guard refuses them. A natural-key diff of a v12 build
  against a v13 build of that tree shows no other changes.

- The app release (§5). Until then the app must stay on a v12 DB.
- Marques and former names (TCDS-20).
- When AIRBUS S.A.S. (EASA.A.004, A330) is staged it joins the Airbus
  lookalike group and needs a row; assemble will stop until it has one.
