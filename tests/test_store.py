import json
import os
import tempfile
import unittest
from pathlib import Path

from evidence import EvidenceError, Store
from evidence.store import digest


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(self.dir / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_content_addressing_is_stable(self):
        h = self.a.put_object({"x": 1, "y": [2, 3]})
        self.assertEqual(h, self.a.put_object({"y": [2, 3], "x": 1}))

    def test_new_claim_is_proposed(self):
        h = self.a.claim("water boils at 100C")
        self.assertEqual(self.a.statuses()[h].state, "proposed")
        self.assertEqual(self.a.get(h)["author"]["agent"], "alice")

    def test_refutation_puts_dependents_at_risk_transitively(self):
        base = self.a.claim("lemma")
        mid = self.a.claim("theorem", depends_on=[base[:8]])
        top = self.a.claim("corollary", depends_on=[mid])
        self.a.review(base, "refuted", "counterexample")
        s = self.a.statuses()
        self.assertEqual(s[base].state, "refuted")
        self.assertEqual(s[mid].at_risk_because, [base])
        self.assertEqual(s[top].at_risk_because, [base])
        self.assertEqual(s[top].state, "proposed")

    def test_refuted_beats_reproduced(self):
        h = self.a.claim("x")
        self.a.review(h, "reproduced", "ran it")
        self.a.review(h, "refuted", "ran it on more data")
        self.assertEqual(self.a.statuses()[h].state, "refuted")

    def test_superseded_requires_replacement(self):
        h = self.a.claim("old")
        with self.assertRaises(EvidenceError):
            self.a.review(h, "superseded", "newer bound")
        new = self.a.claim("new")
        self.a.review(h, "superseded", "newer bound", superseded_by=new)
        self.assertEqual(self.a.statuses()[h].state, "superseded")

    def test_verify_reruns_command_on_evidence_files(self):
        script = self.dir / "check.py"
        script.write_text("assert sum(range(5)) == 10\n")
        ok = self.a.claim("sum works", files=[script], cmd="python3 check.py")
        script.write_text("assert 1 == 2\n")
        bad = self.a.claim("arithmetic is broken", files=[script], cmd="python3 check.py")
        self.assertEqual(self.a.verify(ok)[1], "reproduced")
        self.assertEqual(self.a.verify(bad)[1], "refuted")

    def test_pull_merges_without_conflict(self):
        ha = self.a.claim("from a")
        hb = self.b.claim("from b", depends_on=[])
        self.b.pull(self.a)
        self.a.pull(self.b)
        self.assertEqual(set(self.a.ids()), set(self.b.ids()))
        self.assertIn(ha, self.b.objects("claim"))
        self.assertIn(hb, self.a.objects("claim"))
        self.assertEqual(self.a.pull(self.b), 0)

    def test_pull_rejects_tampered_objects(self):
        h = self.a.claim("honest")
        path = self.a._path("objects", h)
        path.write_bytes(path.read_bytes().replace(b"honest", b"forged"))
        with self.assertRaises(EvidenceError):
            self.b.pull(self.a)

    def test_ambiguous_and_unknown_ids(self):
        with self.assertRaises(EvidenceError):
            self.a.resolve("nope")


    def test_environment_failures_are_inconclusive_not_refutations(self):
        base = self.a.claim("needs a tool", cmd="no-such-program-xyz")
        top = self.a.claim("built on it", depends_on=[base])
        self.assertEqual(self.a.verify(base)[1], "inconclusive")
        slow = self.a.claim("slow", cmd="sleep 5")
        self.assertEqual(self.a.verify(slow, timeout=1)[1], "inconclusive")
        fetch = self.a.claim("fetched", setup=["exit 1"], cmd="true")
        self.assertEqual(self.a.verify(fetch)[1], "inconclusive")
        s = self.a.statuses()
        self.assertEqual(s[base].state, "proposed")
        self.assertEqual(s[top].label, "proposed")

    def test_verify_records_environment(self):
        h = self.a.claim("echo", cmd="echo hi")
        review = self.a.get(self.a.verify(h)[0])
        self.assertIn("python", review["environment"])
        self.assertIn("output_sha256", review["environment"])

    def test_only_other_labs_count_as_independent(self):
        h = self.a.claim("x", cmd="true")
        self.a.verify(h)
        self.assertEqual(self.a.statuses()[h].independent, 0)
        self.b.pull(self.a)
        self.b.verify(h, unsafe=True)
        self.assertEqual(self.b.statuses()[h].independent, 1)

    def test_search_finds_dead_ends(self):
        self.a.claim("Trial division is too slow beyond 10^7.", kind="negative")
        self.a.claim("Water is wet.")
        hits = self.a.search("is trial division fast enough?")
        self.assertEqual(len(hits), 2)
        self.assertEqual(self.a.get(hits[0][1])["kind"], "negative")

    def test_todo_ranks_by_impact_and_offers_own_claims_only_for_selfcheck(self):
        base = self.a.claim("lemma", cmd="true")
        self.a.claim("theorem", depends_on=[base])
        self.a.claim("open", kind="conjecture")
        self.assertEqual([t["action"] for t in self.a.todo(self.a.author())], ["selfcheck"])
        self.a.verify(base)
        self.assertEqual(self.a.todo(self.a.author()), [])
        self.b.pull(self.a)
        todo = self.b.todo(self.b.author())
        self.assertEqual([(t["action"], t["impact"]) for t in todo],
                         [("reproduce", 2), ("review", 1), ("prove", 1)])
        self.a.review(base, "refuted", "counterexample")
        self.assertEqual(self.a.todo(self.a.author())[0]["action"], "recheck")

    def test_checkout_writes_evidence_files(self):
        script = self.dir / "check.py"
        script.write_text("print(1)\n")
        h = self.a.claim("prints", files=[script], cmd="python3 check.py")
        out = self.a.checkout(h, self.dir / "work")
        self.assertEqual([p.read_text() for p in out], ["print(1)\n"])

    def test_upstream_and_downstream(self):
        a = self.a.claim("a")
        b = self.a.claim("b", depends_on=[a])
        c = self.a.claim("c", depends_on=[a, b])
        self.assertEqual(sorted(self.a.downstream(a)), sorted([b, c]))
        self.assertEqual(sorted(self.a.upstream(c)), sorted([a, b]))
        self.assertEqual(self.a.downstream(c), [])


    def test_pull_refuses_malformed_objects(self):
        bad_objects = (
            {"type": "claim", "statement": "no deps"},
            {"no": "type"},
            [1, 2],
            {"type": "review", "claim": "../../etc", "verdict": "reproduced", "by": {}, "method": "",
             "note": "", "created": "x"},
            {"type": "claim", "kind": "result", "statement": "s", "author": {}, "depends_on": [], "created": "x",
             "evidence": [{"kind": "file", "name": "x", "blob": "nothex"}]},
        )
        for i, bad in enumerate(bad_objects):
            with self.subTest(bad=bad):
                c = Store.init(self.dir / f"c{i}", {"agent": "carol"})
                data = json.dumps(bad).encode()
                c._write("objects", digest(data), data)
                with self.assertRaises(EvidenceError):
                    self.b.pull(c)
                self.assertTrue(any(p.startswith("malformed") for p in Store(c.root).fsck()))
        # Objects of a type from a newer version pass through and are ignored.
        c = Store.init(self.dir / "newer", {"agent": "carol"})
        c.put_object({"type": "dataset", "anything": 1})
        self.b.pull(c)
        self.assertEqual(self.b.statuses(), {})

if __name__ == "__main__":
    unittest.main()
