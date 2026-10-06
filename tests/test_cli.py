"""The command line as an agent sees it: arguments in, JSON and exit codes out."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from evidence.cli import main

DEMO = Path(__file__).resolve().parent.parent / "demo" / "primes.py"


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ)
        for k in ("EV_DIR", "EV_AGENT", "EV_MODEL", "EV_LAB"):
            os.environ.pop(k, None)
        for lab, agent in (("lab-a", "alice"), ("lab-b", "bob")):
            self.ev("init", str(self.dir / lab), "--agent", agent, "--lab", lab)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def ev(self, *argv, lab=None, ok=(0,)):
        if lab:
            os.environ["EV_DIR"] = str(self.dir / lab / ".evidence")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as e:
                code = e.code
        self.assertIn(code, ok, err.getvalue())
        return out.getvalue().strip()

    def js(self, *argv, lab):
        return json.loads(self.ev(*argv, "--json", lab=lab))

    def test_two_labs_catch_an_error(self):
        good = self.ev("claim", "There are 168 primes below 1000.", "--file", str(DEMO),
                       "--cmd", "python3 primes.py 1000 168", lab="lab-a")
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        wrong = self.ev("claim", "There are 1230 primes below 10000.", "--file", str(DEMO),
                        "--cmd", "python3 primes.py 10000 1230", lab="lab-b")
        top = self.ev("claim", "Prime density falls.", "--dep", good[:8], "--dep", wrong[:8], lab="lab-b")

        todo = self.js("todo", lab="lab-a")
        self.assertEqual([t["action"] for t in todo], ["selfcheck"])  # lab-a has not seen lab-b's work yet
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-a")
        todo = self.js("todo", lab="lab-a")
        self.assertEqual([t["id"] for t in todo if t["action"] == "reproduce"], [wrong])

        self.ev("verify", wrong, "--unsafe", lab="lab-a", ok=(1,))
        self.ev("verify", good, "--unsafe", lab="lab-b")
        risky = self.ev("check", "--json", lab="lab-a", ok=(1,))
        self.assertEqual([r["id"] for r in json.loads(risky)], [top])

        self.ev("pull", str(self.dir / "lab-b"), lab="lab-a")
        digest = self.js("digest", lab="lab-a")
        self.assertEqual(digest[0]["id"], good)
        self.assertEqual(digest[0]["independent"], 1)
        shown = self.js("show", top[:10], lab="lab-a")
        self.assertEqual(shown["status"], "at-risk")
        self.assertEqual(shown["at_risk_because"], [wrong])

    def test_show_survives_evidence_of_a_newer_kind_and_a_partial_source(self):
        from evidence import Store
        store = Store(self.dir / "lab-a" / ".evidence")
        h = store.put_object({"type": "claim", "kind": "result", "statement": "from the future",
                              "author": {"agent": "carol"}, "depends_on": [], "created": "x",
                              "evidence": [{"kind": "dataset", "uri": "s3://x"}], "source": {"registry": "r"}})
        self.assertIn("s3://x", self.ev("show", h, lab="lab-a"))

    def test_log_filters_by_status(self):
        h = self.ev("claim", "x", lab="lab-a")
        self.ev("review", h, "refuted", "--method", "counterexample", lab="lab-a")
        self.ev("claim", "y", lab="lab-a")
        self.assertEqual([r["id"] for r in self.js("log", "--status", "refuted", lab="lab-a")], [h])

    def test_search_and_checkout(self):
        h = self.ev("claim", "Sieving beyond 10^9 runs out of memory.", "--kind", "negative",
                    "--file", str(DEMO), lab="lab-a")
        hits = self.js("search", "memory when sieving", lab="lab-a")
        self.assertEqual(hits[0]["id"], h)
        out = self.ev("checkout", h, str(self.dir / "work"), lab="lab-a")
        self.assertTrue(Path(out).is_file())

    def test_errors_exit_2(self):
        self.ev("show", "nope", lab="lab-a", ok=(2,))
        self.ev("review", "nope", "refuted", "--method", "m", lab="lab-a", ok=(2,))

    def test_inconclusive_verify_exits_3(self):
        h = self.ev("claim", "needs a tool", "--cmd", "no-such-program-xyz", lab="lab-a")
        self.ev("verify", h, lab="lab-a", ok=(3,))
        self.assertEqual(self.js("show", h, lab="lab-a")["status"], "proposed")


    def test_questions_withdraw_and_report(self):
        big = self.ev("ask", "How dense are the primes?", lab="lab-a")
        sub = self.ev("ask", "How many primes are below 1000?", "--parent", big[:8], lab="lab-a")
        c = self.ev("claim", "There are 168 primes below 1000.", "--file", str(DEMO),
                    "--cmd", "python3 primes.py 1000 168", "--answers", sub, lab="lab-a").splitlines()[0]
        self.ev("claim", "There are 169 primes below 1000.", "--file", str(DEMO),
                "--cmd", "python3 primes.py 1000 169", "--verify", lab="lab-a", ok=(1,))
        # The sub-question has a proposed answer; the larger question is still open.
        self.assertEqual([(t["action"], t["id"]) for t in self.js("todo", lab="lab-a")],
                         [("selfcheck", c), ("answer", big)])
        r = self.ev("review", c, "refuted", "--method", "miscounted", lab="lab-a")
        self.assertEqual(self.js("show", sub, lab="lab-a")["status"], "open")
        self.ev("withdraw", r, lab="lab-a")
        self.ev("verify", c, lab="lab-a")
        tree = self.js("questions", lab="lab-a")
        self.assertEqual({q["id"]: q["status"] for q in tree}, {big: "open", sub: "answered"})
        self.assertIn("How dense", self.ev("questions", lab="lab-a"))

        md = self.ev("report", lab="lab-a")
        self.assertIn("## Questions", md)
        self.assertIn("Answer: There are 168 primes below 1000.", md)
        tex = self.ev("report", "--format", "tex", lab="lab-a")
        self.assertTrue(tex.startswith("\\documentclass"))
        self.assertEqual(tex.count("\\begin{itemize}"), tex.count("\\end{itemize}"))
        self.assertIn("digraph", self.ev("graph", lab="lab-a"))
        self.assertEqual(self.ev("fsck", lab="lab-a"), "ok")
        self.assertIn("ev search", self.ev("guide"))

    def test_remotes(self):
        h = self.ev("claim", "from a", lab="lab-a")
        self.ev("remote", "add", "a", str(self.dir / "lab-a"), lab="lab-b")
        self.assertIn("pulled 1", self.ev("pull", lab="lab-b"))
        self.assertEqual(self.js("show", h, lab="lab-b")["statement"], "from a")
        hb = self.ev("claim", "from b", lab="lab-b")
        self.ev("push", "a", lab="lab-b")
        self.assertEqual(self.js("show", hb, lab="lab-a")["statement"], "from b")
        self.ev("remote", "remove", "a", lab="lab-b")
        self.ev("pull", lab="lab-b", ok=(2,))

        pub = self.dir / "public"
        self.ev("serve", "--export", str(pub), lab="lab-b")
        self.assertEqual(sorted(p.name for p in pub.iterdir()), ["blobs", "index.json", "objects"])
        self.ev("init", str(self.dir / "lab-c"), "--agent", "carol")
        self.assertIn("pulled 2", self.ev("pull", str(pub), lab="lab-c"))

    def test_keygen_and_trust(self):
        from evidence import signing
        if not signing.available():
            self.skipTest("needs ssh-keygen")
        self.ev("init", str(self.dir / "lab-c"), "--agent", "carol", "--lab", "lab-c", "--keygen")
        me = self.js("whoami", lab="lab-c")
        self.assertTrue(me["fingerprint"].startswith("SHA256:"))
        self.ev("trust", "add", "lab-c", str(self.dir / "lab-c" / ".evidence" / "key.pub"), lab="lab-a")
        h = self.ev("claim", "signed", "--cmd", "true", lab="lab-c")
        self.ev("pull", str(self.dir / "lab-c"), lab="lab-a")
        self.assertIn("✔lab-c", self.ev("log", lab="lab-a"))
        self.assertEqual(self.ev("fsck", lab="lab-a"), "ok")


if __name__ == "__main__":
    unittest.main()
