# Rights to the source text

What each issuer says about reuse of the text in `data/`, recorded on 2026-11-08.
These are one maintainer's working notes and **not legal advice**. They were made
from each issuer's own pages and the local source PDFs. Only NATO and part of EASA
remain open, and those are flagged below.

Code in this repo is MIT licensed ([LICENSE](../LICENSE)). That licence doesn't
cover the source text. See [data/NOTICE](../data/NOTICE).

| Issuer | Documents | What was found | Open |
|---|---|---|---|
| FAA | 14 CFR 23, 25, 26, 27, 29, 36; FAA TCDS | US Government works. [17 U.S.C. § 105(a)](https://www.law.cornell.edu/uscode/text/17/105): "Copyright protection under this title is not available for any work of the United States Government." | None seen |
| CAA, CAB | CAR 3 | Predecessor US agencies, so taken to fall under the same section. Not separately researched. | Low |
| DoD | MIL-HDBK-516 to 516D | All six PDFs state: "DISTRIBUTION STATEMENT A: Approved for public release; distribution is unlimited." | None seen |
| EASA | CS-23, 25, 27, 29; EASA TCDS | [Site notice](https://www.easa.europa.eu/en/copyright-disclaimer): "Reproduction is authorised, provided the source is acknowledged, save where otherwise stated." | **Yes** |
| NATO | STANAG 4671 Ed. 1, AEP-4671 Ed. B | 2019 PDFs are marked `© NATO/OTAN`. No reuse terms found. | **Yes** |

## Open questions

**NATO.** This is the main risk, because the text is published here and no
permission to reproduce it has been found.

- `AEP-4671 EdB V1` and `STANAG-4671 Ed3` carry `© NATO/OTAN`. A search of their
  first six pages found no statement on reproduction.
- The Ed. 1 PDF has no copyright mark in the text of those pages. It came from an
  archive copy (NATO-1), and its `source_url` points at the NSO catalogue entry,
  not at the file actually used.
- NSO's own terms page could not be read for this note.

Needed: read the NSO terms, or ask NSO or a national standardization authority. If
permission can't be established, decide whether the NATO text stays in `data/`.

**EASA.** The site-wide notice permits reproduction with acknowledgement "save where
otherwise stated". A sample of the ED Decision PDFs in `input/Regs/EASA/` carries
this footer on the Decision's form page: "© European Union Aviation Safety Agency.
All rights reserved. ... Proprietary document." The sampled TCDS PDF (EASA.A.004)
has a similar footer: "© EASA, 2024. All rights reserved." These may be template
wording on quality forms, but that is a guess. Needed: confirm that the general permission
covers Certification Specifications and TCDS, or ask EASA.

**Attribution.** EASA's condition is that the source is acknowledged.
`data/NOTICE` does this for the dataset, and each version has a `source_url`. Whether
that is enough on the app's pages has not been reviewed.
