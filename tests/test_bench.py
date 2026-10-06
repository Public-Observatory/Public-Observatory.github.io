"""The agent benchmark is sound: its constants are right, its scores measure the agent, and the scripted
baseline, alone and in a swarm, scores as expected."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

import planted  # noqa: E402
from evidence import Store  # noqa: E402


class BenchTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EV_AGENT", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def world(self) -> Store:
        with contextlib.redirect_stdout(io.StringIO()):
            planted.setup(self.dir)
        return Store(self.dir / "agent" / ".evidence")

    def by_text(self, s: Store, text: str) -> str:
        return next(h for kind in ("claim", "question") for h, o in s.objects(kind).items()
                    if text in (o.get("statement"), o.get("text")))

    def test_planted_constants(self):
        for n, k in {**planted.TRUE, **planted.QUESTIONS}.items():
            self.assertEqual(planted.pi(n), k)
        for n, k in planted.FALSE.items():
            self.assertNotEqual(planted.pi(n), k)
        n, right, wrong = planted.CONTESTED
        self.assertEqual((planted.pi(n), wrong != right), (right, True))
        for lo, hi in planted.DOWNSTREAM:
            self.assertNotEqual(planted.stated(lo, hi), planted.pi(hi) - planted.pi(lo))

    def test_no_answer_key_on_disk(self):
        self.world()
        names = {p.name for p in self.dir.rglob("*")}
        self.assertNotIn("key.json", names)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["agent", "world"])
        # The world's own record contains the contested question, but nothing that says which answer is wrong.
        q = planted.question_text(planted.CONTESTED[0])
        world = Store(self.dir / "world" / ".evidence")
        self.assertEqual(world.question_statuses()[self.by_text(world, q)].state, "contested")

    def test_baseline_catches_errors_but_adds_nothing(self):
        self.world()
        planted.baseline(self.dir)
        self.assertEqual(planted.score(self.dir), {
            "errors_refuted": 1.0, "true_left_standing": 1.0, "true_reproduced": 1.0,
            "dependants_reclaimed": 0.0,  # what a real agent must add
            "questions_answered": 0.0,    # likewise
            "answers_wrong": 0, "contested_resolved": 1.0, "dead_end_repeated": 0, "claims_recorded": 0})

    def test_answers_scored_on_value_not_on_self_verification(self):
        agent = self.world()
        agent.pull(Store(self.dir / "world" / ".evidence"))
        q50, q200 = (self.by_text(agent, planted.question_text(n)) for n in planted.QUESTIONS)
        agent.claim("There are 5133 primes below 50000.", answers=[q50], value={"exact": 5133})
        agent.claim("The count below 200000 is 18000.", answers=[q200], value={"exact": 18000})
        s = planted.score(self.dir)
        self.assertEqual((s["questions_answered"], s["answers_wrong"]), (0.5, 1))
        # A value outweighs whatever numbers the statement happens to mention.
        agent.claim("Below 200000 (not 17984) there are 17985 primes.", answers=[q200], value={"exact": 17985})
        self.assertEqual(planted.score(self.dir)["questions_answered"], 0.5)
        agent.claim("Below 200000 there are 17984 primes.", answers=[q200])
        self.assertEqual(planted.score(self.dir)["questions_answered"], 1.0)

    def test_dependants_must_be_reclaimed(self):
        agent = self.world()
        planted.baseline(self.dir)
        agent = Store(agent.root)
        agent.claim("Between 1000 and 2000 there are 135 primes.", value={"exact": 135})
        self.assertEqual(planted.score(self.dir)["dependants_reclaimed"], 0.5)
        wrong = self.by_text(agent, planted.range_statement(10000, 20000, 1034))
        better = agent.claim("The interval [10^4, 2*10^4) holds 1033 primes.", value={"exact": 1033})
        self.assertEqual(planted.score(self.dir)["dependants_reclaimed"], 0.5)  # nothing ties it to the range
        agent.review(wrong, "superseded", "recomputed from corrected counts", superseded_by=better)
        self.assertEqual(planted.score(self.dir)["dependants_reclaimed"], 1.0)

    def test_dead_end_repeated_only_when_ignored(self):
        agent = self.world()
        agent.pull(Store(self.dir / "world" / ".evidence"))
        agent.claim("Trial division finds 9592 primes below 100000.", cmd="python3 trial.py")
        agent.claim("Trial division is slow here too.", kind="negative")
        self.assertEqual(planted.score(self.dir)["dead_end_repeated"], 1)
        # Testing the recorded dead end engages it, whatever the outcome.
        agent.verify(self.by_text(agent, planted.DEAD_END_STATEMENT), unsafe=True)
        self.assertEqual(planted.score(self.dir)["dead_end_repeated"], 0)

    def test_leases_halve_duplicated_attempts(self):
        without = planted.swarm(self.dir / "without", agents=4, leases=False)
        with_leases = planted.swarm(self.dir / "with", agents=4, leases=True)
        self.assertEqual(without["claims_verified"], with_leases["claims_verified"])
        self.assertGreater(without["duplicated"], 0)
        self.assertLessEqual(2 * with_leases["duplicated"], without["duplicated"])

    def test_run_records_a_scored_run(self):
        out = self.dir / "results"
        # A stand-in agent that saves the prompt and asserts it was pointed at its store.
        cmd = 'test -d "$EV_DIR/objects" && test -d .evidence && cat > prompt.txt && echo done'
        with contextlib.redirect_stdout(io.StringIO()):
            record = planted.run(self.dir / "b", cmd, "stand-in", "sh", out)
        self.assertEqual(record["exit"], 0)
        self.assertEqual(record["scores"]["claims_recorded"], 0)
        self.assertIn("EV_DIR=", (self.dir / "b" / "agent" / "prompt.txt").read_text())
        [saved] = out.glob("*.json")
        self.assertEqual(json.loads(saved.read_text()), record)
        self.assertEqual({"model", "harness", "date", "scores", "transcript"} - set(record), set())
        self.assertEqual((out / record["transcript"]).read_text().strip(), "done")


if __name__ == "__main__":
    unittest.main()
