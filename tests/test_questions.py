import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evidence import EvidenceError, Store
from evidence.store import disagree, format_value, invalid, parse_value, value_invalid


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


class ValueTest(unittest.TestCase):
    """Answers carrying values, and questions whose standing answers contradict each other."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("EV_AGENT", None)
        os.environ.pop("EV_KEY", None)
        self.a = Store.init(Path(self.tmp.name) / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(Path(self.tmp.name) / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_claims_without_a_value_keep_their_ids(self):
        # These ids were computed before values existed; the optional field must not move them.
        with mock.patch("evidence.store.now", return_value="2026-01-01T00:00:00+00:00"):
            q = self.a.ask("How many primes are there below 1000?")
            c = self.a.claim("There are 168 primes below 1000.", answers=[q], cmd="python3 primes.py 1000 168")
            v = self.a.claim("There are 168 primes below 1000.", answers=[q], cmd="python3 primes.py 1000 168",
                             value="168")
        self.assertEqual(q, "4721e4adc3a41b0e6efabc75303e7c99130fe868b90ff6ecbef036154d1d9a42")
        self.assertEqual(c, "58bf3f871032a7cec580f01944d26a3b04093d99c80a45058c0da11e7ed166f7")
        self.assertNotIn("value", self.a.get(c))
        self.assertNotEqual(v, c)
        self.assertEqual(self.a.get(v)["value"], {"exact": 168})

    def test_parse_and_format_round_trip(self):
        cases = {
            "168": {"exact": 168}, "-3": {"exact": -3}, "true": {"exact": True}, "false": {"exact": False},
            '"2026-10-06"': {"exact": "2026-10-06"}, "Riemann": {"exact": "Riemann"},
            "9.81": {"quantity": "9.81"}, "+.5": {"quantity": "0.5"}, "3 apples": {"quantity": "3", "unit": "apples"},
            "9.81 m/s^2 ± 0.02": {"quantity": "9.81", "uncertainty": "0.02", "unit": "m/s^2"},
            "9.81 +/- 0.02 m/s^2": {"quantity": "9.81", "uncertainty": "0.02", "unit": "m/s^2"},
            "1E3 ± 5": {"quantity": "1e3", "uncertainty": "5"},
            "12345678901234567890": {"quantity": "12345678901234567890"},
        }
        for text, value in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_value(text), value)
                self.assertEqual(parse_value(format_value(value)), value)
                self.assertIsNone(value_invalid(value))
        for text in ("3m", "2026-10-06", "9.81 ± x", "9 m ± 1 s", "5 ± -1", "1e5000", '""'):
            with self.subTest(text=text), self.assertRaises(EvidenceError):
                parse_value(text)

    def test_agreement(self):
        def d(x, y):
            return disagree(parse_value(x), parse_value(y))
        self.assertTrue(d("168", "170"))
        self.assertFalse(d("168", "168"))
        self.assertFalse(d("168", "169 ± 1"))  # closed intervals that touch agree
        self.assertTrue(d("168", "169.5 ± 1"))
        self.assertFalse(d("9.81 m/s^2 ± 0.02", "9.84 m/s^2 ± 0.01"))
        self.assertTrue(d("9.81 m/s^2 ± 0.02", "9.84 m/s^2 ± 0.005"))
        self.assertFalse(d("9.81", "9.810"))
        self.assertFalse(d("9.81 m/s^2", "981 cm/s^2"))  # units are not converted, so not compared
        self.assertFalse(d("1", "true"))  # a number and a boolean are not compared
        self.assertTrue(d("true", "false"))
        self.assertTrue(d('"Riemann"', '"Euler"'))
        self.assertFalse(d('"yes"', "true"))

    def test_malformed_values_are_refused(self):
        self.assertIsNone(value_invalid({"exact": 2 ** 53 - 1}))
        for bad in ([168], {}, {"exact": 1.5}, {"exact": None}, {"exact": 2 ** 53}, {"exact": ""},
                    {"exact": " x"}, {"exact": "x" * 201}, {"exact": 1, "unit": "m"}, {"quantity": 9.81},
                    {"quantity": "9,81"}, {"quantity": "1e1000"}, {"quantity": "1", "uncertainty": "-1"},
                    {"quantity": "1", "unit": ""}, {"quantity": "1", "confidence": "0.95"}):
            with self.subTest(bad=bad):
                self.assertIsNotNone(value_invalid(bad))
                with self.assertRaises(EvidenceError):
                    self.a.claim("x", value=bad)
                obj = {"type": "claim", "kind": "result", "statement": "s", "author": {}, "evidence": [],
                       "depends_on": [], "created": "x", "value": bad}
                self.assertIsNotNone(invalid(obj))

    def test_disagreeing_standing_answers_contest_a_question(self):
        q = self.a.ask("How many primes are there below 1000?")
        right = self.a.claim("There are 168 primes below 1000.", answers=[q], value="168")
        self.a.claim("There are about 169 primes below 1000.", answers=[q], value="169 ± 1")  # agrees with both
        self.a.claim("No answer is given as a value here.", answers=[q])
        self.assertEqual(self.a.question_statuses()[q].state, "proposed")
        self.b.pull(self.a)
        wrong = self.b.claim("There are 170 primes below 1000.", answers=[q], value="170")
        self.a.pull(self.b)
        for s in (self.a, self.b):
            qs = s.question_statuses()[q]
            self.assertEqual(qs.state, "contested")
            self.assertEqual(qs.conflicts, [sorted([right, wrong])])
        todo = self.a.todo(self.a.author())
        self.assertEqual((todo[0]["action"], todo[0]["id"], todo[0]["conflicts"]), ("resolve", q, [sorted([right, wrong])]))
        self.assertIn("168", todo[0]["why"])
        # Being reproduced does not settle a contradiction; refuting the wrong answer does.
        self.a.review(right, "reproduced", "counted")
        self.assertEqual(self.a.question_statuses()[q].state, "contested")
        self.a.review(wrong, "refuted", "the count includes 1 and 1000")
        self.assertEqual(self.a.question_statuses()[q].state, "answered")
        self.assertNotIn("resolve", [t["action"] for t in self.a.todo()])

    def test_superseded_answers_and_other_questions_do_not_contest(self):
        q1, q2 = self.a.ask("first"), self.a.ask("second")
        old = self.a.claim("old", answers=[q1], value="1")
        new = self.a.claim("new", answers=[q1], value="2")
        self.a.claim("elsewhere", answers=[q2], value="3")
        self.assertEqual(self.a.question_statuses()[q1].state, "contested")
        self.assertEqual(self.a.question_statuses()[q2].state, "proposed")
        self.a.review(old, "superseded", "corrected", superseded_by=new)
        self.assertEqual(self.a.question_statuses()[q1].state, "proposed")


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


if __name__ == "__main__":
    unittest.main()
