#!/usr/bin/env python3
"""12+ unittests for ReproDossier (stdlib, determinism, ledger, verdicts)."""

import copy
import json
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from reprodossier import (
    canonical_json, sha256_text, is_sha256,
    evaluate, markdown_report, append_ledger, verify_ledger,
    EXAMPLES, main,
)


class TestCore(unittest.TestCase):
    def test_canonical_and_sha(self):
        a = {"b": 1, "a": 2}
        cj = canonical_json(a)
        self.assertEqual(cj, '{"a":2,"b":1}')
        self.assertTrue(is_sha256(sha256_text(cj)))

    def test_is_sha256(self):
        self.assertTrue(is_sha256("a" * 64))
        self.assertFalse(is_sha256("a" * 63))
        self.assertFalse(is_sha256("g" * 64))

    def test_reduce_reproducible(self):
        claims = [{"output_hash": "a" * 64}] * 3
        r = evaluate({"evidence": claims})
        self.assertEqual(r["verdict"], "reproducible")
        self.assertEqual(r["quorum"], 3)
        self.assertEqual(len(r["reasons"]), 0)

    def test_reduce_mismatch(self):
        claims = [{"output_hash": "a" * 64}, {"output_hash": "b" * 64}]
        r = evaluate({"evidence": claims})
        self.assertEqual(r["verdict"], "mismatch")
        self.assertTrue(any("hash_diff" in rr for rr in r["reasons"]))

    def test_reduce_unattested(self):
        r = evaluate({"evidence": [{"output_hash": "a" * 64}]})
        self.assertEqual(r["verdict"], "unattested")

    def test_determinism_same_input(self):
        st = EXAMPLES["reproducible"]
        r1 = evaluate(st)
        r2 = evaluate(st)
        self.assertEqual(r1["verdict"], r2["verdict"])
        self.assertEqual(r1["ledger"][-1]["entry_hash"], r2["ledger"][-1]["entry_hash"])

    def test_ledger_append_and_verify(self):
        led = []
        e1 = {"input_id": "t1", "verdict": "reproducible"}
        led = append_ledger(led, e1)
        self.assertTrue(verify_ledger(led)["ok"])
        e2 = {"input_id": "t2", "verdict": "mismatch"}
        led = append_ledger(led, e2)
        self.assertTrue(verify_ledger(led)["ok"])

    def test_ledger_tamper_detect(self):
        led = []
        led = append_ledger(led, {"input_id": "t", "verdict": "reproducible"})
        tampered = copy.deepcopy(led)
        tampered[0]["verdict"] = "hacked"
        self.assertFalse(verify_ledger(tampered)["ok"])

    def test_reasons_accum(self):
        st = EXAMPLES["mismatch"]
        r = evaluate(st)
        self.assertGreater(len(r["reasons"]), 0)

    def test_markdown_report(self):
        res = evaluate(EXAMPLES["reproducible"])
        md = markdown_report(res, EXAMPLES["reproducible"])
        self.assertIn("reproducible", md)
        self.assertIn("ledger_tail", md)

    def test_cli_sample(self):
        rc = main(["sample"])
        self.assertEqual(rc, 0)

    def test_cli_run_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "st.json"
            p.write_text(json.dumps(EXAMPLES["reproducible"]))
            rc = main(["run", str(p)])
            self.assertEqual(rc, 0)
            rc2 = main(["report", str(p)])
            self.assertEqual(rc2, 0)


if __name__ == "__main__":
    unittest.main()
