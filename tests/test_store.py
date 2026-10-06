import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def smuggle(self, data: bytes) -> Store:
        """A store holding the given bytes as an object under their hash."""
        c = Store.init(self.dir / f"c{digest(data)[:8]}", {"agent": "carol"})
        c._write("objects", digest(data), data)
        return c

    def test_pull_refuses_non_canonical_or_unencodable_bytes(self):
        # Re-encoding would store the object under a name that is not its hash.
        for data in (b'{"type": "dataset"}', b'{"type":"dataset","x":"\\ud800"}', b"[" * 100000 + b"]" * 100000):
            with self.subTest(data=data[:40]):
                with self.assertRaises(EvidenceError):
                    self.b.pull(self.smuggle(data))
                self.assertEqual(Store(self.b.root).fsck(), [])

    def test_pull_refuses_objects_that_would_break_reading_commands(self):
        claim = {"type": "claim", "kind": "result", "statement": "s", "author": {"agent": "m"}, "depends_on": [],
                 "created": "x", "evidence": []}
        bad_objects = (
            {**claim, "author": {"agent": "m", "key": ["not", "a", "string"]}},
            {**claim, "author": {"agent": "m", "lab": 5}},
            {**claim, "evidence": [{"kind": "note", "text": 5}]},
            {**claim, "evidence": [{"kind": "reference", "relationship": "x"}]},
            {**claim, "source": "palomar"},
            *({**claim, "evidence": [{"kind": "file", "name": n, "blob": "0" * 64}]} for n in ("..", "", "a/b", "x\0")),
        )
        for bad in bad_objects:
            with self.subTest(bad=bad):
                with self.assertRaises(EvidenceError):
                    self.b.pull(self.smuggle(json.dumps(bad, sort_keys=True, separators=(",", ":")).encode()))
        self.b.search("s")

class RefutationTest(unittest.TestCase):
    """Only evidence refutes another author's claim; prose disputes it; each reviewer holds one position."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(self.dir / "b", {"agent": "bob", "lab": "lab-b"})
        self.c = Store.init(self.dir / "c", {"agent": "carol", "lab": "lab-c"})

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self):
        for x in (self.a, self.b, self.c):
            for y in (self.a, self.b, self.c):
                x.pull(y)

    def test_ids_of_existing_kinds_of_object_are_unchanged(self):
        # Computed with the code before counter-claims and disputes existed.
        with mock.patch("evidence.store.now", return_value="2026-01-01T00:00:00+00:00"):
            c = self.a.claim("There are 168 primes below 1000.", cmd="python3 primes.py 1000 168", notes=["sieve"])
            c2 = self.a.claim("x", cmd="true")
            self.b.pull(self.a)
            r = self.b.review(c, "refuted", "counterexample", note="n = 7")
            s = self.b.review(c2, "superseded", "newer bound", superseded_by=c)
            e = self.a.review(c, "reproduced", "re-ran", environment={"platform": "p", "output_sha256": "0" * 64})
        self.assertEqual([h[:16] for h in (c, c2, r, s, e)],
                         ["4d19aea2a0b455de", "c8d8da191a7067d2", "54bb84696d6d5f15", "a5073c6537d19fcc",
                          "23b0fb4858d01ad9"])

    def test_prose_refutation_by_another_lab_only_disputes(self):
        x = self.a.claim("x", cmd="true")
        top = self.a.claim("built on x", depends_on=[x])
        self.sync()
        self.b.verify(x, unsafe=True)
        r = self.c.review(x, "refuted", "I disagree")
        s = self.c.review(top, "superseded", "mine is better", superseded_by=x)
        self.sync()
        st = self.a.statuses()
        self.assertEqual((st[x].state, st[x].independent, st[x].disputed), ("reproduced", 1, [r]))
        self.assertEqual((st[top].label, st[top].disputed), ("proposed", [s]))
        self.assertEqual({t["id"]: t["action"] for t in self.a.todo(self.a.author())}[x], "adjudicate")
        # Whoever has already taken a position on the claim is not asked again.
        self.assertNotIn(("adjudicate", x), [(t["action"], t["id"]) for t in self.b.todo(self.b.author())])
        self.c.withdraw(r)
        self.assertEqual(self.c.statuses()[x].disputed, [])

    def test_self_check_is_not_a_reproduction(self):
        x = self.a.claim("x", cmd="true")
        self.a.verify(x)
        st = self.a.statuses()[x]
        self.assertEqual((st.state, st.self_checked, st.independent), ("proposed", True, 0))

    def test_a_reviewer_holds_one_position(self):
        x = self.a.claim("x", cmd="true")
        self.sync()
        first, _ = self.b.verify(x, unsafe=True)
        later = self.b.review(x, "refuted", "on reflection")
        self.b.review(x, "inconclusive", "could not rerun")  # an attempt is not a position
        st = self.b.statuses()[x]
        self.assertEqual((st.state, st.independent, st.disputed), ("proposed", 0, [later]))
        self.b.withdraw(later)
        st = self.b.statuses()[x]
        self.assertEqual((st.state, st.grounds, st.disputed), ("reproduced", [first], []))

    def test_counter_claims_hold_while_they_stand(self):
        x = self.a.claim("x", cmd="true")
        top = self.a.claim("built on x", depends_on=[x])
        self.sync()
        y = self.b.claim("not x", cmd="false", refutes=[x])
        self.sync()
        self.assertEqual(self.a.statuses()[x].state, "refuted")
        self.assertEqual(self.a.statuses()[top].at_risk_because, [x])
        self.assertEqual(self.a.statuses()[y].label, "proposed")
        self.c.verify(y, unsafe=True)  # the counter-claim's own command fails
        self.sync()
        st = self.a.statuses()
        self.assertEqual((st[y].state, st[x].state, st[x].disputed, st[top].at_risk_because),
                         ("refuted", "proposed", [], []))

    def test_counter_claims_in_a_cycle_leave_both_disputed(self):
        x = self.a.claim("x", cmd="true")
        y = self.b.claim("y", cmd="true")
        self.sync()
        rx = self.b.review(x, "refuted", "y shows x false", counter=y)
        ry = self.a.review(y, "refuted", "x shows y false", counter=x)
        self.sync()
        st = self.c.statuses()
        self.assertEqual((st[x].state, st[x].disputed, st[y].state, st[y].disputed),
                         ("proposed", [rx], "proposed", [ry]))
        # Evidence from outside the cycle decides it.
        self.c.review(y, "refuted", "re-ran", environment={"output_sha256": "0" * 64})
        st = self.c.statuses()
        self.assertEqual((st[x].state, st[x].disputed, st[y].state), ("proposed", [], "refuted"))

    def test_counter_claim_must_carry_a_command_and_not_rest_on_its_target(self):
        x = self.a.claim("x")
        prose = self.b.claim("x is wrong")
        with self.assertRaises(EvidenceError):
            self.b.claim("x is wrong", refutes=[x])
        with self.assertRaises(EvidenceError):
            self.b.claim("x is wrong", cmd="true", refutes=[x], depends_on=[x])
        self.b.pull(self.a)
        with self.assertRaises(EvidenceError):
            self.b.review(x, "refuted", "see claim", counter=prose)
        # Written by hand, such reviews are objections, or wait on a cycle through the target.
        hand = self.b._record({"type": "review", "claim": x, "verdict": "refuted", "by": self.b.author(),
                               "method": "m", "note": "", "superseded_by": None, "counter": prose, "created": "x"})
        self.assertEqual(self.b.statuses()[x].disputed, [hand])
        self.c.pull(self.a)
        leaning = self.c.claim("x fails", cmd="true", depends_on=[x])
        circular = self.c.review(x, "refuted", "m", counter=leaning)
        st = self.c.statuses()
        self.assertEqual((st[x].state, st[x].disputed, st[leaning].label), ("proposed", [circular], "proposed"))


if __name__ == "__main__":
    unittest.main()
