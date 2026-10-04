import os
import tempfile
import unittest
from pathlib import Path

from evidence import EvidenceError, Store


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


if __name__ == "__main__":
    unittest.main()
