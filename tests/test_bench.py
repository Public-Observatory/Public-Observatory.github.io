"""The agent benchmark is sound: its constants are right, and the scripted baseline scores as expected."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

import planted  # noqa: E402


class BenchTest(unittest.TestCase):
    def test_planted_constants(self):
        for n, k in {**planted.TRUE, **planted.QUESTIONS}.items():
            self.assertEqual(planted.pi(n), k)
        for n, k in planted.FALSE.items():
            self.assertNotEqual(planted.pi(n), k)

    def test_baseline_catches_errors_but_answers_nothing(self):
        os.environ.pop("EV_AGENT", None)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                planted.setup(d)
            planted.baseline(d)
            s = planted.score(d)
        self.assertEqual(s["errors_refuted"], 1.0)
        self.assertEqual(s["true_left_standing"], 1.0)
        self.assertEqual(s["true_reproduced"], 1.0)
        self.assertEqual(s["downstream_flagged"], 1.0)
        self.assertEqual(s["questions_answered"], 0.0)  # what a real agent must add


if __name__ == "__main__":
    unittest.main()
