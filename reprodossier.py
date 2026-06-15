#!/usr/bin/env python3
"""ReproDossier — build artifact reproducibility attestation (stdlib only).

CLI: sample | run <state.json> | report <state.json>
Deterministic engine. Hash-chain ledger. 3-way verdict.
"""

import argparse
import copy
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

GENESIS = "0" * 64


def canonical_json(obj: Any) -> str:
    """Deterministic serialization."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_sha256(s: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", s or ""))


def normalize_state(state: dict) -> dict:
    s = copy.deepcopy(state or {})
    if "evidence" not in s:
        s["evidence"] = []
    if "ledger" not in s:
        s["ledger"] = []
    if "input_id" not in s:
        s["input_id"] = "unknown"
    return s


def load_evidence(state: dict) -> list[dict]:
    return list(state.get("evidence", []))


def reduce_verdict(claims: list[dict]) -> dict:
    if not claims or len(claims) < 2:
        return {"verdict": "unattested", "reasons": ["insufficient_sources"]}
    hashes = [c.get("output_hash") for c in claims if c.get("output_hash")]
    if not hashes:
        return {"verdict": "unattested", "reasons": ["no_hashes"]}
    first = hashes[0]
    if not all(is_sha256(h) or (len(str(h or '')) == 64 and all(c in '0123456789abcdef' for c in str(h or ''))) for h in hashes):
        return {"verdict": "unattested", "reasons": ["invalid_hash_format"]}
    all_match = all(h == first for h in hashes)
    if all_match:
        return {"verdict": "reproducible", "reasons": [], "quorum": len(claims)}
    mismatches = [i for i, h in enumerate(hashes) if h != first]
    return {"verdict": "mismatch", "reasons": [f"hash_diff_at_{i}" for i in mismatches], "quorum": len(claims)}


def append_ledger(ledger: list[dict], entry: dict) -> list[dict]:
    if not ledger:
        prev = GENESIS
    else:
        prev = ledger[-1].get("entry_hash", GENESIS)
    payload = {"prev": prev, "entry": entry}
    eh = sha256_text(canonical_json(payload))
    new_e = copy.deepcopy(entry)
    new_e["prev_hash"] = prev
    new_e["entry_hash"] = eh
    out = copy.deepcopy(ledger)
    out.append(new_e)
    return out


def verify_ledger(ledger: list[dict]) -> dict:
    if not ledger:
        return {"ok": True, "reasons": []}
    prev = GENESIS
    for i, e in enumerate(ledger):
        if e.get("prev_hash") != prev:
            return {"ok": False, "reasons": [f"chain_break_at_{i}"]}
        core = {k: e[k] for k in e if k not in ("prev_hash", "entry_hash")}
        expected = sha256_text(canonical_json({"prev": prev, "entry": core}))
        if e.get("entry_hash") != expected:
            return {"ok": False, "reasons": [f"hash_mismatch_at_{i}"]}
        prev = e.get("entry_hash", GENESIS)
    return {"ok": True, "reasons": []}


def evaluate(state: dict) -> dict:
    s = normalize_state(state)
    claims = load_evidence(s)
    red = reduce_verdict(claims)
    entry = {
        "input_id": s["input_id"],
        "verdict": red["verdict"],
        "sources": len(claims),
    }
    new_ledger = append_ledger(s.get("ledger", []), entry)
    v = verify_ledger(new_ledger)
    reasons = list(red.get("reasons", []))
    if not v["ok"]:
        reasons.extend(v["reasons"])
    return {
        "verdict": red["verdict"],
        "reasons": reasons,
        "ledger": new_ledger,
        "quorum": red.get("quorum", 0),
    }


def markdown_report(result: dict, state: dict) -> str:
    lines = [
        "# ReproDossier Report",
        f"verdict: {result['verdict']}",
        "reasons:",
    ]
    for r in result.get("reasons", []):
        lines.append(f"- {r}")
    lines.append(f"quorum: {result.get('quorum', 0)}")
    tail = ""
    if result.get("ledger"):
        tail = result["ledger"][-1].get("entry_hash", "")[:16] + "..."
    lines.append(f"ledger_tail: {tail or 'genesis'}")
    return "\n".join(lines)


EXAMPLES = {
    "reproducible": {
        "input_id": "example-repro",
        "evidence": [
            {"output_hash": "a" * 64, "source_id": "matrix"},
            {"output_hash": "a" * 64, "source_id": "trustix"},
            {"output_hash": "a" * 64, "source_id": "enclave"},
        ],
        "ledger": [],
    },
    "mismatch": {
        "input_id": "example-mismatch",
        "evidence": [
            {"output_hash": "b" * 64, "source_id": "matrix"},
            {"output_hash": "c" * 64, "source_id": "trustix"},
        ],
        "ledger": [],
    },
    "unattested": {
        "input_id": "example-unattested",
        "evidence": [{"output_hash": "d" * 64, "source_id": "onlyone"}],
        "ledger": [],
    },
}


def cmd_sample() -> int:
    for name, st in EXAMPLES.items():
        res = evaluate(st)
        print(f"[{name}] {res['verdict']} reasons={res['reasons']}")
    return 0


def cmd_run(state_path: str) -> int:
    p = pathlib.Path(state_path)
    state = json.loads(p.read_text(encoding="utf-8"))
    res = evaluate(state)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def cmd_report(state_path: str) -> int:
    p = pathlib.Path(state_path)
    state = json.loads(p.read_text(encoding="utf-8"))
    res = evaluate(state)
    md = markdown_report(res, state)
    print(md)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reprodossier", description="ReproDossier reproducibility attestation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="Emit 3 example verdicts")
    p_run = sub.add_parser("run", help="Evaluate state.json -> JSON")
    p_run.add_argument("state", help="path to state.json")
    p_rep = sub.add_parser("report", help="Evaluate state.json -> Markdown")
    p_rep.add_argument("state", help="path to state.json")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd == "sample":
        return cmd_sample()
    if args.cmd == "run":
        return cmd_run(args.state)
    if args.cmd == "report":
        return cmd_report(args.state)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
