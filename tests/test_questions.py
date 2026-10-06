import contextlib
import io
import os
import time
import tempfile
import unittest
from pathlib import Path

from evidence import EvidenceError, Store, report
from evidence.cli import main


class QuestionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(Path(self.tmp.name) / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(Path(self.tmp.name) / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_question_is_answered_only_by_a_standing_reproduced_claim(self):
        q = self.a.ask("How many primes are there below 1000?")
        self.assertEqual(self.a.question_statuses()[q].state, "open")
        c = self.a.claim("168", answers=[q[:8]])
        self.assertEqual(self.a.question_statuses()[q].state, "proposed")
        self.a.review(c, "reproduced", "counted")
        self.assertEqual(self.a.question_statuses()[q].state, "answered")
        self.a.review(c, "refuted", "miscounted")
        self.assertEqual(self.a.question_statuses()[q].state, "open")

    def test_answers_and_parents_must_be_questions(self):
        c = self.a.claim("x")
        with self.assertRaises(EvidenceError):
            self.a.claim("y", answers=[c])
        with self.assertRaises(EvidenceError):
            self.a.ask("z", parents=[c])
        q = self.a.ask("q")
        with self.assertRaises(EvidenceError):
            self.a.claim("w", depends_on=[q])

    def test_todo_offers_the_deepest_open_questions(self):
        big = self.a.ask("Why is the sky blue?")
        mid = self.a.ask("How does scattering depend on wavelength?", parents=[big])
        leaf = self.a.ask("Measure scattering at 450nm and 650nm.", parents=[mid])
        todo = [(t["action"], t["id"], t["impact"]) for t in self.a.todo()]
        self.assertEqual(todo, [("answer", leaf, 3)])

    def test_search_finds_questions(self):
        q = self.a.ask("Is the Collatz map eventually periodic for every start?")
        self.assertEqual(self.a.search("collatz")[0][1], q)


class WithdrawalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(Path(self.tmp.name) / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(Path(self.tmp.name) / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_withdrawn_refutation_no_longer_counts(self):
        base = self.a.claim("lemma")
        top = self.a.claim("theorem", depends_on=[base])
        r = self.a.review(base, "refuted", "timed out, mistakenly")
        self.assertEqual(self.a.statuses()[top].label, "at-risk")
        self.a.withdraw(r, note="the timeout was ours")
        s = self.a.statuses()
        self.assertEqual(s[base].state, "proposed")
        self.assertEqual(s[top].label, "proposed")

    def test_only_the_reviewer_may_withdraw(self):
        base = self.a.claim("lemma")
        r = self.a.review(base, "refuted", "counterexample")
        self.b.pull(self.a)
        with self.assertRaises(EvidenceError):
            self.b.withdraw(r)
        # A withdrawal forged by hand into the store is ignored.
        self.b.put_object({"type": "withdrawal", "review": r, "by": self.b.author(), "note": "", "created": "x"})
        self.assertEqual(self.b.statuses()[base].state, "refuted")


    def test_question_dags_are_read_in_linear_time(self):
        # Layers of two questions, each part of both questions above it: 2^n paths, 2n questions.
        layer = [self.a.ask("root")]
        for i in range(20):
            layer = [self.a.put_object({"type": "question", "text": f"q{i}.{j}", "author": {"agent": "m"},
                                        "parents": sorted(layer), "created": "x"}) for j in range(2)]
        chain = layer[0]
        for i in range(1500):
            chain = self.a.put_object({"type": "question", "text": f"c{i}", "author": {"agent": "m"},
                                       "parents": [chain], "created": "x"})
        store = Store(self.a.root)
        start = time.time()
        self.assertLess(len(report.markdown(store).splitlines()), 2000)
        os.environ["EV_DIR"] = str(self.a.root)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["questions"]), 0)
        finally:
            os.environ.pop("EV_DIR")
        self.assertLess(len(out.getvalue().splitlines()), 2000)
        self.assertLess(time.time() - start, 10)

if __name__ == "__main__":
    unittest.main()
