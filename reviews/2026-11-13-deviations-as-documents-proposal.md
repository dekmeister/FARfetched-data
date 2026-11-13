# Deviations as documents in their own right (ROADMAP-2): proposal

2026-11-13. Status: **Phase 1 built for EASA (schema v14) and FAA (v15), not
promoted.** TCDS links, CRI links and text are outstanding: ISSUES ROADMAP-2. D1
(separate entity), D2 (all), D3/D4 (use EASA's published proposals; CRI links
only as reviewed rows) and D5 (link only) are answered below; CMs and ETSO
deviations are left out.

## What we have

- **TCDS lines.** 1,988 deviation lines (ELOS, special condition, exemption):
  EASA 1,527, FAA 461. Schema v11 links the *sections they cite*
  (`cert_basis_citations`), not the deviation itself.
- **FAA sources (DRS).** The listing caches hold ELOS 1,813, SC final 1,443,
  SC proposed 382 and exemptions 37,342 distinct numbers. Every row carries
  metadata: number, subject, date, applicant, make, model, CFR part and
  sections, docket, and the DRS `source_url`. SC finals are mostly HTML
  (Federal Register text, 1,404 of 1,477). ELOS memos and exemptions are PDF
  letters, some of them scans.
- **EASA sources.** 1,477 catalogue rows and 1,473 files downloaded. Only what
  went out to consultation is public: generic SCs/ESFs (`SC-F23.1309-02`) and
  their CRDs. Project CRIs (`CRI F-01`, `D-04`) are not published, and their
  labels are numbered per project.

**How many TCDS lines name a document we can get** (a rough token match of the
line against catalogue numbers, 2026-11-13):

| | Lines | Name a catalogue number |
|---|---|---|
| FAA ELOS | 318 | 132 |
| FAA SC | 107 | 75 |
| FAA exemption | 36 | 35 |
| EASA (all) | 1,527 | ~1 |

The FAA lines with no match mostly carry no identifier ("25.1415(d) Emergency
Locator Transmitter (ELT)", "Special Conditions dated January 14, 1969"). EASA
lines name CRIs, which have no public copy.

## Why not provisions

A deviation does not fit the `documents` → `provisions` → `versions` model:

- It is one-off: one issue, sometimes an amendment, never a series of
  revisions.
- `text` is required on every version (no `status` column, by design), and
  most ELOS and exemption PDFs are letters or scans that we can't reliably turn
  into label-line text. Requiring text would block the link-only case, which
  is the valuable one.
- There would be ~3,600 FAA ELOS/SC "documents" with one or two "provisions"
  each. That would bloat the documents list, search and similarity.

The `doc_kind` values `special_condition`, `elos` and `exemption` were reserved
for this and have never been used.

## Proposal: a separate deviation record, link first, text later

### Phase 1: deviation records (metadata + source link)

New tree: `data/deviations/{issuer}/{kind}/{number-slug}.json`. Its schema is
`schemas/deviation.schema.json`, emitted by tools from the catalogues, with no
download needed beyond what is already done.

```json
{
  "issuer": "FAA",
  "kind": "special_condition",
  "number": "23-117-SC",
  "title": "S-TEC Corporation Mirage PA-46-350P With Single Sided EFIS; Protection of Systems for HIRF",
  "stage": "final",
  "issued_on": "2002-05-06",
  "applicant": "S-TEC Corporation",
  "make_model": "Piper PA-46-350P",
  "cites": [{ "issuer": "FAA", "document": "23", "number": "1309" }],
  "regulation_ref": "23.1309",
  "source_url": "https://drs.faa.gov/browse/excelExternalWindow/A01DDE005B87160086256BC3004B067F.0001",
  "publication_cite": "",
  "text": null
}
```

- `regulation_ref` stays verbatim, like `raw_reference`. `cites` is parsed
  from it with the existing citation reader and resolved by the build (fail
  loud on an unknown section), so a provision page can list "deviations
  against this section".
- `text` is null in Phase 1. The app shows the metadata and links to the source.
- SQLite: tables `deviations` and `deviation_cites`, plus a contract version
  bump.

### Phase 2: link TCDS lines to deviation records

The tools match a deviation line's identifier against the records and write
`deviation: {issuer, kind, number}` on the entry, next to `citations`. It is
computed, not reviewed, the same stance as v11: the verbatim line is always
shown. A `tools/overrides/` row can force or block a link. The build fails on a
link to an unknown record. Expect about 240 FAA lines, essentially no EASA
lines.

### Phase 3: text where the source is structured

FAA SC finals are FR HTML with a "The Special Conditions" section whose
numbered conditions fit label-line text. That is about 1,400 documents with
real text. ELOS memos, exemptions and EASA PDFs stay link-only unless a later
OCR or extraction pass is worth it, judged from a sample.

## Decisions

- **D1. Separate `deviations` entity rather than provisions.** Recommended: yes.
  Then drop or keep the three unused `doc_kind` values (recommend drop, since
  they never shipped).
- **D2. Scope of Phase 1 records.**
  - Recommended: all FAA ELOS and SC (final + proposed, ~3,600), exemptions
    citing a certification part or cited by a TCDS (~2,400), and EASA final
    SC/ESF/DEV publications (~200, `role=final`).
  - The alternative is only what a TCDS cites (~240). That is smaller, but it
    loses the "deviations against this section" view.
- **D3. Proposed SCs.** Records of their own (`stage: proposed`), or only
  finals with the proposal as a second link? Recommended: a record of its own,
  linked to its final when the final's `special_condition_ref` names it.
- **D4. EASA CRIs.** No public copy and per-project numbering, so no records.
  The verbatim TCDS line stays the only representation. Recommended: confirm,
  and answer ETCDS-18 in the same breath.
- **D5. Publishing local copies.** Link to the regulator only (`source_url`).
  Never serve our downloaded files: EASA replaces files in place, and the
  rights position is unclear (docs/RIGHTS.md). Recommended: link only.

## Before Phase 1

- Re-run the FAA catalogue so that it holds ELOS and SC rows. Today it holds
  only exemptions: an earlier full run likely stopped on the exemption count
  mismatch before writing anything. That is fixed in tools: the short stretch
  is re-read live, and a failing type no longer discards the others.
- Sample ~20 SC final HTML files to confirm the Phase 3 structure claim.

## Answers so far (2026-11-13)

- **D1:** separate entity, pending the user's view on the database argument
  below.
- **D2:** scope is all.
- **D3/D4:** use EASA's published proposed SCs, ESFs and DEVs. They are the
  public part of some project CRIs. ~90 of the 699 EASA publications name a
  product ("Proposed Equivalent Safety Finding on Door indication. Applicable
  to Boeing 787"). A publication never carries the CRI label, so a TCDS CRI line
  can only be linked by product + subject + cited section. Those links are
  reviewed override rows with evidence, never automatic matches.
- **D5:** link to the regulator only.

### Database shape (for D1)

```
deviations            (id, issuer_id, kind, key, number, stage, title, issued_on,
                       applicant, make_model, regulation_ref, source_url,
                       publication_cite, text NULL, final_id NULL → deviations)
                       UNIQUE (issuer_id, kind, key)
deviation_cites       (deviation_id, seq, document_id, provision_id, paragraph)
                       FK (document_id, provision_id) → provisions
cert_basis_entry_deviations (entry_id, seq, deviation_id, link_basis)
                       link_basis IN ('identifier', 'reviewed')
```

- `key` is not `number`: DRS numbers repeat (exemption amendments, and
  duplicates under different document ids), so the key adds a suffix the way
  MIL-HDBK-516 provision keys do.
- `final_id` links a proposed SC/ESF/DEV to its final. It is a self-FK, and a
  CHECK makes it valid only from `stage = 'proposed'`.
- An entry → deviation link table, not a column on `cert_basis_entries`,
  because one line can name several memos.
- `text` is nullable here and only here. The `provision_versions` rule (text
  always present) stays untouched.
- Search: a separate FTS table, or rows in `search_text` with a source column.
  Decide in Phase 1.
- Drop the unused `doc_kind` values `special_condition`, `elos` and
  `exemption`.

### Scope detail for "all"

The EASA listing also holds Certification Memoranda (108) and ETSO deviations
(147). CMs are guidance, not deviations, and ETSO deviations apply to
appliances, not aircraft. Proposed: leave both out of `deviations`. CMs can
become an `amc_gm`-like document later if wanted.
