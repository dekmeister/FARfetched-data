# 04 — Open questions for the maintainer

Each question lists what it blocks and a recommendation.

### Q-01 — Rename `data/regulations/` to `data/documents/`? (blocks Phase 2)

The CLAUDE.md path rule is about *flatness*. The proposal keeps it flat
(`{issuer}/{document}/{provision}.json`) but renames the root and the part
file. The alternative is keeping `data/regulations/` and adding sibling
roots (`data/advisory_circulars/`, `data/handbooks/`). That splits one
concept across several loaders and schemas.
**Recommend:** a single `data/documents/` root with `doc_kind` inside the
file. Update the CLAUDE.md rule text to match.

### Q-02 — Sign off the P-06 resolution rules (blocks Phase 1)

In particular:
- (a) Does a range's `from` mean "first revision included", so that "Part
  23 effective 1965 as amended by 23-1 thru …" is authored as
  `from: "23-0"`? Or should the base revision always be implicit?
- (b) Is the conflict group "TCB + applicability" right, or should
  overrides apply only within a single TCDS line?
- (c) When a paragraph-scoped ref resolves to the same version as the
  whole provision, is dropping it correct?
**Recommend:** (a) explicit `from`, with the base included only when
named, since that is the most literal reading of the TCDS. (b) TCB +
applicability. (c) yes.

### Q-03 — How to represent repeal / `[Reserved]` (blocks ingesting 23-64)

Options:
1. A version row whose `text` is the source's literal "[Reserved]" or
   "[Removed]" plus a CHECK-constrained `version_kind`
   (`text | reserved | removed`).
2. Store only the literal text and let consumers detect it.

Option 1 is a *kind* column, not the untranscribed-placeholder `status`
column the repo rule forbids. Every row still has real source text.
**Recommend:** option 1. Confirm that it doesn't conflict with the intent
of the no-status rule.

### Q-04 — Structured serial applicability? (affects Phase 1 scope)

The proposal stores `applicability` verbatim
("525-0600 thru 525-0684, 525-0686 thru 525-0701") and uses it only as a
conflict-group key. Structured serial ranges (`from_sn`, `to_sn`) would
allow "which basis applies to S/N 525-0650?", but serial formats vary by
manufacturer.
**Recommend:** verbatim now. Add a structured child table later if the app
needs serial lookup.

### Q-05 — WAL vs DELETE journal mode on the shipped file

CLAUDE.md requires WAL. See F-21 for why DELETE plus read-only/immutable
readers suits a static artifact better.
**Recommend:** DELETE. Check what the NFSN daemon's file permissions allow
before deciding.

### Q-06 — Aircraft files: one per model or one per TCDS?

One TCDS (3A12) defines the basis for many models. Per-model files copy
shared basis lines and the TCDS metadata (F-12, F-24). A per-TCDS file
with a `models[]` list and per-model applicability would remove the
duplication, but it changes the authoring unit and `faa_tcds.py`'s output.
**Recommend:** decide before transcribing a second model on an existing
TCDS. Lean towards per-TCDS, because it mirrors the source document.

### Q-07 — Where do `provision_relations` live in JSON?

Options:
- (a) A `related` array on the provision file. This is one-sided:
  whichever side is authored.
- (b) Separate files `data/relations/*.json`.

Derived relations (same-number FAA parts) are computed, not authored.
**Recommend:** (a) for `guidance_for` / `modifies`, authored on the
AC/SC side, and (b) for `equivalent_to`, which belongs to neither side.

### Q-08 — `user_version` policy

Is the app expected to require an exact match, or to accept "same major"?
SQLite's `user_version` is one integer. One option is to encode
`major * 1000 + minor`.
**Recommend:** exact match until the app has a reason to be lenient.

### Q-09 — Fold `title_number` into `documents.code`?

`title_number` is only meaningful for CFR. It's currently unenforced (F-09)
and unread by the build. Folding it into `code` ('14 CFR 23') loses
nothing.
**Recommend:** yes.
