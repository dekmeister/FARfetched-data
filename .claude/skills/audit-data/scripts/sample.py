"""Draw a random, spread-out sample of provision versions and TCDS for an audit.

Provision versions are drawn round-robin across documents (faa/23, easa/cs-25,
caa/car-3, ...), each draw a random version of a random provision, so every
document and every era is represented whatever its size. TCDS are drawn
round-robin across issuers (FAA, EASA), one distinct TCDS per draw (a TCDS
covering several models is one entry; one of its models is picked). Each item carries the local source copies a reader needs: the
extracted text (tools/out/extracted) and the source file under input/.

    uv run python .claude/skills/audit-data/scripts/sample.py \
        --regs 80 --tcds 20 --out-dir <scratch>/audit
    # focus: only CS-25 and CAR, versions mentioning a formula, EASA TCDS
    ... --document easa/cs-25 --issuer caa --issuer cab --grep '='
    ... --tcds-issuer EASA

Writes OUT_DIR/regs.jsonl, OUT_DIR/tcds.jsonl and OUT_DIR/paths.txt (the
sampled files, relative to data/, for checks.py --paths). stderr: the seed
and what was drawn. Read-only outside OUT_DIR.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

DATA = Path("data")
EXTRACTED = Path("tools/out/extracted")
INPUT = Path("input")


def _first(paths: list[Path]) -> list[str]:
    return [p.as_posix() for p in paths if p.exists()][:4]


def source_copies(issuer: str, doc: str, key: str, v: dict[str, Any]) -> dict[str, Any]:
    """Best-effort pointers to the local source copies of one version."""
    des = str(v.get("designator"))
    url = v.get("source_url") or ""
    if issuer == "faa":
        doc_id = url.rsplit("/", 1)[-1].split(".")[0]
        extracted = [EXTRACTED / "faa" / f"{doc}_{key}_{des}.json"]
        sources = [INPUT / "cache/drs/far_doc" / f"{doc_id}.json"]
    elif issuer == "easa":
        extracted = [EXTRACTED / "easa" / doc / des / f"{key}.txt"]
        sources = [INPUT / "Regs/EASA" / doc.upper() / f"{des}.pdf"]
    elif issuer in ("caa", "cab"):
        extracted = [EXTRACTED / "car" / des / f"{key}.txt"]
        sources = sorted((INPUT / "Regs/CAR/3").glob(f"{des}*"))
    elif issuer == "nato":
        extracted = [EXTRACTED / "nato/usar" / des.lower() / f"{key}.json"]
        ed = des.replace("-", " ")
        sources = sorted((INPUT / "Regs/NATO").glob(f"*{ed}*"))
    else:
        extracted = sorted(EXTRACTED.glob(f"{issuer}/**/{key}.*"))
        sources = sorted((INPUT / "Regs/US DoD").glob("*.pdf"))
    found = _first(extracted)
    if not found:  # unknown layout: list candidates for the reader to choose
        found = _first(sorted(EXTRACTED.glob(f"{issuer}/**/{key}.*")))
    return {"extracted": found, "source": _first(sources), "source_url": url}


def provision_pool(
    issuers: set[str], documents: set[str], grep: re.Pattern[str] | None
) -> dict[str, list[tuple[Path, int]]]:
    pool: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for path in sorted((DATA / "documents").glob("*/*/*.json")):
        issuer, doc = path.parts[-3], path.parts[-2]
        if path.name.startswith("_") or (issuers and issuer not in issuers):
            continue
        if documents and f"{issuer}/{doc}" not in documents:
            continue
        versions = json.loads(path.read_text(encoding="utf-8"))["versions"]
        for i, v in enumerate(versions):
            text = v.get("text")
            if text and (grep is None or grep.search(text)):
                pool[f"{issuer}/{doc}"].append((path, i))
    return pool


def round_robin(pools: dict[str, list[Any]], n: int, rng: random.Random) -> list[Any]:
    """n draws without replacement, cycling over the pools in random order."""
    remaining = {k: rng.sample(v, len(v)) for k, v in pools.items() if v}
    order = sorted(remaining)
    rng.shuffle(order)
    picked: list[Any] = []
    while len(picked) < n and remaining:
        for key in list(order):
            if key not in remaining:
                continue
            picked.append(remaining[key].pop())
            if not remaining[key]:
                del remaining[key]
            if len(picked) == n:
                break
    return picked


def provision_item(path: Path, i: int) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    v = doc["versions"][i]
    prev = doc["versions"][i - 1] if i else None
    issuer, document = path.parts[-3], path.parts[-2]
    return {
        "relpath": path.relative_to(DATA).as_posix(),
        "designator": v["designator"],
        "previous_designator": prev and prev.get("designator"),
        "title": v.get("title_at_revision"),
        "grouping": v.get("grouping_at_time"),
        "text": v["text"],
        "publication_cite": v.get("publication_cite"),
        **source_copies(issuer, document, path.stem, v),
    }


def tcds_pool(issuers: set[str]) -> dict[str, list[list[tuple[Path, int]]]]:
    """Per issuer, one entry per TCDS: the (aircraft file, tcb index) of every
    model it covers, so a TCDS with many models is drawn no more often."""
    by_tcds: dict[tuple[str, str], list[tuple[Path, int]]] = defaultdict(list)
    for path in sorted((DATA / "aircraft").glob("*/*.json")):
        for i, tcb in enumerate(json.loads(path.read_text(encoding="utf-8"))["tcb"]):
            t = tcb["tcds"]
            if not issuers or t["issuer"] in issuers:
                by_tcds[(t["issuer"], t["tcds_number"])].append((path, i))
    pool: dict[str, list[list[tuple[Path, int]]]] = defaultdict(list)
    for (issuer, _num), models in sorted(by_tcds.items()):
        pool[issuer].append(models)
    return pool


def tcds_item(path: Path, i: int) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    tcb = doc["tcb"][i]
    t = tcb["tcds"]
    num, rev = t["tcds_number"], t["revision"]
    if t["issuer"] == "FAA":
        pdf = INPUT / "TCDS/FAA" / f"{num}_Rev{rev}.pdf"
        text = Path("tools/out/derived/tcds_text") / f"{num}_Rev{rev}.txt"
    else:
        pdf = INPUT / "TCDS/EASA" / f"{num}_Issue{rev}.pdf"
        text = Path("tools/out/derived/tcds_text/EASA") / f"{num}_Issue{rev}.txt"
    return {
        "relpath": path.relative_to(DATA).as_posix(),
        "model": f"{doc['manufacturer']} {doc['model_designation']}",
        "tcds": t,
        "categories": tcb.get("categories"),
        "certification_basis": tcb["certification_basis"],
        "source": _first([pdf]),
        "source_text": _first([text]),
        "fragment_dir": _first([Path("tools/out/derived/tcb") / t["issuer"] / num]),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--regs", type=int, default=80)
    p.add_argument("--tcds", type=int, default=20)
    p.add_argument("--seed", type=int, help="default: random (printed)")
    p.add_argument("--issuer", action="append", default=[], help="faa, easa, caa, …")
    p.add_argument("--document", action="append", default=[], help="e.g. faa/25")
    p.add_argument("--grep", help="only versions whose text matches this regex")
    p.add_argument("--tcds-issuer", action="append", default=[], help="FAA or EASA")
    p.add_argument("--out-dir", type=Path, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed = (
        args.seed if args.seed is not None else random.SystemRandom().randrange(10**6)
    )
    rng = random.Random(seed)
    grep = re.compile(args.grep) if args.grep else None
    regs = round_robin(
        provision_pool(set(args.issuer), set(args.document), grep), args.regs, rng
    )
    tcds = round_robin(tcds_pool(set(args.tcds_issuer)), args.tcds, rng)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    reg_items = [provision_item(p, i) for p, i in regs]
    tcds_items = [tcds_item(*rng.choice(models)) for models in tcds]
    for name, items in (("regs", reg_items), ("tcds", tcds_items)):
        with (args.out_dir / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for item in items:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    paths = sorted({it["relpath"] for it in reg_items + tcds_items})
    (args.out_dir / "paths.txt").write_text("\n".join(paths) + "\n", encoding="utf-8")
    no_src = sum(1 for it in reg_items if not it["extracted"] and not it["source"])
    print(
        f"seed {seed}: {len(reg_items)} versions from "
        f"{len({it['relpath'].rsplit('/', 1)[0] for it in reg_items})} documents, "
        f"{len(tcds_items)} TCDS; {no_src} versions with no local source found",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
