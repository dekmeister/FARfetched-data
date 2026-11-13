"""Choose what readers read for a promotion, estimate the cost, write batches.

Inputs: delta.jsonl (delta.py), fields.jsonl (fields.py) and the new-hit
files from checks.py / scan_data.py. Items are built by items.py (modes diff,
full, field; see there and READER.md).

What is read:
  always    words, versions-added, basis-lines / references diffs, new or
            added TCBs, field flags and unverifiable fields, and any item
            with a new check hit;
  sampled   --field-sample passes per verbatim/date field (stratified by
            directory), and as many over all `listed` deviation fields
            together and per judgement field (SAMPLED_FIELDS), --class-sample
            each of layout-only and markup-only, new-file document versions
            (all when ≤ --new-docs, else that many stratified, hits always),
            --dev-sample new deviation records (stratified by issuer, kind
            and stage);
  never     fields-only files whose fields all passed (beyond the sample),
            new deviation records beyond the sample (every field is checked by
            script against the listing),
            markup-lost (held back by rule), TCBs identical to data/.

Cost: each item gets an estimate (BASE[mode] + payload chars / 4 tokens), each
batch READER_OVERHEAD on top. Calibrated on the 2026-11-13 run: 23 readers,
~2.23M tokens, ~97k per batch of 8 whole-TCDS items (~9k payload tokens).
Batches are packed per mode, by source, up to --batch-tokens. If the total
is over --budget, the optional samples shrink step by step (DOWNSCALE). If
the must-read alone is over --hard-stop, nothing is written and the exit
code is 3: the change is pipeline-sized, so ask the user to split it.

    PYTHONPATH=.:.claude/skills/audit-data/scripts uv run python \\
        .claude/skills/promote-staged/scripts/batches.py \\
        --delta $S/delta.jsonl --fields $S/fields.jsonl \\
        --hits $S/new_checks.tsv --hits $S/new_scan.tsv --out-dir $S/batches

Writes OUT_DIR/batch_NN_<mode>.jsonl, OUT_DIR/plan.json (counts, estimate,
downscale steps, batches, dispatch waves) and OUT_DIR/not_read.tsv (every
changed file no item covers, and why). Summary on stderr. Read-only outside
OUT_DIR.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from items import (  # noqa: E402
    aircraft_items,
    dedup,
    deviation_item,
    document_items,
    field_excerpt,
    tcb_index,
)
from sample import round_robin  # noqa: E402

READER_OVERHEAD = 20_000
# full-tcds: a whole basis against the PDF; full-doc: one new provision
# full-dev: one deviation record against its listing entry
BASE = {
    "field": 600,
    "diff": 2_500,
    "full-tcds": 8_000,
    "full-doc": 3_000,
    "full-dev": 1_500,
}
MAX_ITEMS = {"field": 30, "diff": 12, "full": 6}
WAVE = 16  # readers dispatched at once (the harness allows 20)
ALWAYS = {
    "words",
    "versions-added",
    "basis-lines",
    "references",
    "tcb-added",
    "field-flag",
}
SAMPLED_FIELD_KINDS = {"verbatim", "date"}
# all `listed` deviation fields share one sample: they are one exact rule
LISTED_POOL = "deviation listed fields"
# derived fields whose script check is partial: their passes are sampled too
SAMPLED_FIELDS = {"deviation.stage", "deviation.final", "deviation.citations"}
# (setting, value) applied in order while the estimate is over --budget
DOWNSCALE = [
    ("class_sample", 4),
    ("field_sample", 10),
    ("new_docs", 8),
    ("dev_sample", 8),
    ("class_sample", 0),
    ("field_sample", 5),
    ("new_docs", 0),
    ("dev_sample", 0),
]


def est(item: dict[str, Any]) -> int:
    mode = item["mode"]
    if mode == "full":
        mode = (
            "full-tcds"
            if "tcds" in item
            else "full-dev"
            if "deviation" in item
            else "full-doc"
        )
    return BASE[mode] + len(json.dumps(item, ensure_ascii=False)) // 4


def load_hits(paths: list[Path]) -> dict[tuple[str, str], list[str]]:
    """(relpath, locator) → hit summaries, from checks.py or scan_data.py rows.
    The locator is the designator for a version; aircraft hits match by file."""
    hits: dict[tuple[str, str], list[str]] = defaultdict(list)
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if cells[0] == "check" or len(cells) < 4:
                continue
            if "/" in cells[1]:  # checks.py: check, relpath, locator, detail
                rel, loc = cells[1], cells[2]
                note = f"{cells[0]} {cells[2]}: {cells[3][:150]}"
            else:  # scan_data.py: check, issuer, document, key, designator, ...
                rel = f"documents/{cells[1].lower()}/{cells[2]}/{cells[3]}.json"
                loc = cells[4]
                note = f"{cells[0]} {cells[4]}: {' '.join(cells[5:])[:150]}"
            key = (rel, loc if rel.startswith("documents/") else "")
            if note not in hits[key]:
                hits[key].append(note)
    return hits


def field_items(path: Path | None) -> tuple[list[dict], dict[str, list[dict]]]:
    """(must-read flags, passes by field) from fields.jsonl."""
    flags: list[dict[str, Any]] = []
    passes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if path is None:
        return flags, passes
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        item = {
            "mode": "field",
            "relpath": r["relpaths"][0],
            "relpaths": r["relpaths"],
            "field": r["field"],
            "where": r["where"],
            "old": r["old"],
            "new": r["new"],
            "check": f"{r['status']}: {r['note']}".rstrip(": "),
            "source": r["source"],
            "group": r["relpaths"][0].split("/")[1],
            "source_key": r["source"] or r["relpaths"][0],
        }
        if r["status"] != "ok":
            item["reason"] = "field-flag"
            item["excerpt"] = (
                field_excerpt(r["source"], str(r["new"] or "")) or r["excerpt"]
            )
            flags.append(item)
        elif r["kind"] == "listed":
            item["reason"] = "field-sample"
            item["excerpt"] = r["excerpt"]
            passes[LISTED_POOL].append(item)
        elif r["kind"] in SAMPLED_FIELD_KINDS or r["field"] in SAMPLED_FIELDS:
            item["reason"] = "field-sample"
            item["excerpt"] = r["excerpt"]
            passes[r["field"]].append(item)
    return flags, passes


def stratified(items: list[dict], n: int, rng: random.Random) -> list[dict]:
    pools: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        pools[it["group"]].append(it)
    return round_robin(pools, n, rng)


def select(pools: dict[str, Any], s: dict[str, int], seed: int) -> list[dict]:
    rng = random.Random(seed)
    picked = list(pools["must"])
    for items in pools["fields"].values():
        picked += stratified(items, s["field_sample"], rng)
    for cls in ("layout-only", "markup-only"):
        picked += stratified(pools["optional"][cls], s["class_sample"], rng)
    docs = pools["optional"]["new-file"]
    picked += (
        docs if len(docs) <= s["new_docs"] else stratified(docs, s["new_docs"], rng)
    )
    devs = pools["optional"].get("deviation-new", [])
    picked += stratified(devs, s["dev_sample"], rng)
    return picked


def pack(items: list[dict], target: int) -> list[list[dict]]:
    batches: list[list[dict]] = []
    for mode in ("field", "diff", "full"):
        cur: list[dict] = []
        size = READER_OVERHEAD
        for it in sorted(
            (i for i in items if i["mode"] == mode), key=lambda i: i["source_key"]
        ):
            cost = est(it)
            if cur and (size + cost > target or len(cur) >= MAX_ITEMS[mode]):
                batches.append(cur)
                cur, size = [], READER_OVERHEAD
            cur.append(it)
            size += cost
        if cur:
            batches.append(cur)
    return batches


def total(batches: list[list[dict]]) -> int:
    return sum(READER_OVERHEAD + sum(est(i) for i in b) for b in batches)


def build_pools(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict], dict]:
    rows = [
        json.loads(ln) for ln in args.delta.read_text(encoding="utf-8").splitlines()
    ]
    known = tcb_index(args.data)
    hits = load_hits(args.hits)
    items: list[dict[str, Any]] = []
    notes: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["kind"] == "document":
            items += document_items(row, args.staged, args.data)
        elif row["kind"] == "deviation":
            if (dev := deviation_item(row, args.staged)) is not None:
                items.append(dev)
        else:
            its, nts = aircraft_items(row, args.staged, known)
            items += its
            notes[row["relpath"]] += nts
    flags, passes = field_items(args.fields)
    pools: dict[str, Any] = {
        "must": [],
        "fields": passes,
        "optional": defaultdict(list),
    }
    for it in dedup(items) + flags:
        loc = it.get("designator", "") if it["relpath"].startswith("documents/") else ""
        if found := [h for rel in it["relpaths"] for h in hits.get((rel, loc), [])]:
            it["hits"] = found
        if (
            it.get("hits")
            or it["reason"] in ALWAYS
            or it["mode"] == "full"
            and it["relpath"].startswith("aircraft/")
        ):
            pools["must"].append(it)
        else:
            pools["optional"][it["reason"]].append(it)
    return pools, rows, notes


def _why(rel: str, cls: set[str], failed: set[str], notes: dict) -> str:
    """Why a changed file is covered by no reading item."""
    if rel.endswith("/_document.json") and "fields-only" not in cls:
        return "index file (revision list): checked by the build"
    if "markup-lost" in cls:
        return "hold: markup-lost"
    if "fields-only" in cls:
        if rel in failed:
            return "fields: script flagged (see fields.jsonl)"
        return "fields: verified by script"
    if notes.get(rel):
        return "; ".join(notes[rel])
    if "versions-removed" in cls:
        return "versions removed: needs a reason"
    if rel.startswith("deviations/"):
        if rel in failed:
            return "deviation: script flagged a field (see fields.jsonl)"
        return "deviation: every field checked by script, not sampled"
    return "not sampled: " + ",".join(sorted(cls))


def not_read(
    rows: list[dict], picked: list[dict], fields: Path | None, notes: dict
) -> list[str]:
    covered = {rel for it in picked for rel in it["relpaths"]}
    failed: set[str] = set()
    if fields:
        for ln in fields.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r["status"] != "ok":
                failed.update(r["relpaths"])
    return [
        f"{row['relpath']}\t{_why(row['relpath'], set(row['class']), failed, notes)}"
        for row in rows
        if row["relpath"] not in covered
    ]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--delta", type=Path, required=True)
    p.add_argument("--fields", type=Path, help="fields.jsonl from fields.py")
    p.add_argument("--hits", type=Path, action="append", default=[])
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--staged", type=Path, default=Path("tools/out/staged"))
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--batch-tokens", type=int, default=60_000)
    p.add_argument("--budget", type=int, default=400_000)
    p.add_argument("--hard-stop", type=int, default=800_000)
    p.add_argument("--field-sample", type=int, default=20)
    p.add_argument("--class-sample", type=int, default=8)
    p.add_argument("--new-docs", type=int, default=24)
    p.add_argument("--dev-sample", type=int, default=16)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args(argv)


def plan_batches(
    args: argparse.Namespace, pools: dict
) -> tuple[list[list[dict]], dict, list[str]]:
    s = {
        "field_sample": args.field_sample,
        "class_sample": args.class_sample,
        "new_docs": args.new_docs,
        "dev_sample": args.dev_sample,
    }
    steps: list[str] = []
    batches = pack(select(pools, s, args.seed), args.batch_tokens)
    for name, value in DOWNSCALE:
        if total(batches) <= args.budget:
            break
        if s[name] > value:
            s[name] = value
            steps.append(f"{name}={value}")
            batches = pack(select(pools, s, args.seed), args.batch_tokens)
    return batches, s, steps


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pools, rows, notes = build_pools(args)
    batches, settings, steps = plan_batches(args, pools)
    must_cost = total(pack(pools["must"], args.batch_tokens))
    picked = [i for b in batches for i in b]
    estimate = total(batches)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    reasons = Counter(i["reason"] for i in picked)
    available = Counter(i["reason"] for i in pools["must"])
    for cls, its in [
        *pools["optional"].items(),
        *(("field-sample", v) for v in pools["fields"].values()),
    ]:
        available[cls] += len(its)
    plan = {
        "estimate_tokens": estimate,
        "must_read_tokens": must_cost,
        "budget": args.budget,
        "hard_stop": args.hard_stop,
        "settings": settings,
        "downscale_steps": steps,
        "items_by_reason": {
            k: [reasons.get(k, 0), n] for k, n in sorted(available.items())
        },
        "batches": [
            {
                "n": n,
                "mode": b[0]["mode"],
                "items": len(b),
                "est": READER_OVERHEAD + sum(est(i) for i in b),
            }
            for n, b in enumerate(batches, 1)
        ],
        "waves": -(-len(batches) // WAVE),
    }
    (args.out_dir / "plan.json").write_text(
        json.dumps(plan, indent=1) + "\n", encoding="utf-8"
    )
    if must_cost > args.hard_stop:
        print(
            f"STOP: must-read alone is ~{must_cost:,} tokens, over the hard stop {args.hard_stop:,}. No batches written; ask the user to split the promotion.",
            file=sys.stderr,
        )
        return 3
    for n, b in enumerate(batches, 1):
        with (args.out_dir / f"batch_{n:02}_{b[0]['mode']}.jsonl").open(
            "w", encoding="utf-8"
        ) as fh:
            for i, item in enumerate(b, 1):
                item = {
                    "id": f"{n:02}.{i:02}",
                    **{
                        k: v
                        for k, v in item.items()
                        if k not in ("group", "source_key")
                    },
                }
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    skipped = not_read(rows, picked, args.fields, notes)
    (args.out_dir / "not_read.tsv").write_text(
        "".join(f"{ln}\n" for ln in skipped), encoding="utf-8"
    )
    for k, (got, n) in plan["items_by_reason"].items():
        print(f"{got:5} / {n:<5} {k}", file=sys.stderr)
    over = " OVER BUDGET" if estimate > args.budget else ""
    print(
        f"{len(picked)} items in {len(batches)} batches ({plan['waves']} waves of ≤{WAVE}); "
        f"estimate ~{estimate:,} tokens (budget {args.budget:,}){over}; "
        f"downscale: {', '.join(steps) or 'none'}; {len(skipped)} changed files not read",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
