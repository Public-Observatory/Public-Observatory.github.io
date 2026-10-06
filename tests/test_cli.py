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

    def test_only_evidence_refutes_another_labs_claim(self):
        self.ev("init", str(self.dir / "lab-c"), "--agent", "mallory", "--lab", "lab-c")
        q = self.ev("ask", "How many primes are there below 1000?", lab="lab-a")
        good = self.ev("claim", "There are 168 primes below 1000.", "--file", str(DEMO), "--cmd",
                       "python3 primes.py 1000 168", "--answers", q, "--value", "168", "--verify",
                       lab="lab-a").splitlines()[0]
        top = self.ev("claim", "The primes below 1000 have density 0.168.", "--dep", good, lab="lab-a")
        slip = self.ev("claim", "There are 169 primes below 1000.", "--answers", q, lab="lab-a")
        self.ev("review", slip, "refuted", "--method", "counted 1 as a prime", lab="lab-a")  # a retraction holds
        # The author's own run is a self-check, not a reproduction: nothing is reported as reproduced.
        shown = self.js("show", good, lab="lab-a")
        self.assertEqual((shown["status"], shown["self_checked"]), ("proposed", True))
        self.assertNotIn("Principal results", self.ev("report", lab="lab-a"))
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        self.ev("verify", good, "--unsafe", lab="lab-b")
        for lab in ("lab-a", "lab-c"):
            self.ev("pull", str(self.dir / "lab-b"), lab=lab)

        # A refutation in prose by another lab is an objection: the claim is disputed, nothing falls.
        r = self.ev("review", good, "refuted", "--method", "I disagree", lab="lab-c")
        self.ev("pull", str(self.dir / "lab-c"), lab="lab-a")
        shown = self.js("show", good, lab="lab-a")
        self.assertEqual((shown["status"], shown["independent"], shown["disputed"]), ("reproduced", 1, [r]))
        self.assertEqual(self.js("check", lab="lab-a"), [])
        self.assertEqual(self.js("show", q, lab="lab-a")["status"], "answered")
        self.assertIn("(1 standing answer(s))", self.ev("questions", lab="lab-a"))
        self.assertEqual([t["action"] for t in self.js("todo", lab="lab-a")][:1], ["adjudicate"])
        md = self.ev("report", lab="lab-a")
        self.assertIn("Objected to without evidence that holds: I disagree.", md)
        self.assertNotIn("Refuted: I disagree", md)
        self.assertIn("Retracted by its author: counted 1 as a prime.", md)

        # One position per reviewer: lab-b's later refutation replaces its reproduction.
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        self.ev("review", good, "refuted", "--method", "changed my mind", lab="lab-b")
        shown = self.js("show", good, lab="lab-b")
        self.assertEqual((shown["status"], shown["independent"], len(shown["disputed"])), ("proposed", 0, 2))

        # Evidence refutes, while it stands: a counter-claim with a command, here a wrong one.
        self.ev("claim", "x", "--cmd", "true", "--refutes", good, "--dep", good, lab="lab-c", ok=(2,))
        counter = self.ev("review", good, "refuted", "--method", "the count is 169", "--file", str(DEMO),
                          "--cmd", "python3 primes.py 1000 169", lab="lab-c").splitlines()[0]
        self.ev("pull", str(self.dir / "lab-c"), lab="lab-a")
        self.assertEqual(self.js("show", good, lab="lab-a")["status"], "refuted")
        self.assertEqual([d["id"] for d in json.loads(self.ev("check", "--json", lab="lab-a", ok=(1,)))], [top])
        self.assertEqual(self.js("show", counter, lab="lab-a")["status"], "proposed")  # not at risk itself
        self.assertIn(f"Refuted by claim {counter[:10]}", self.ev("report", lab="lab-a"))
        # Re-running the counter-claim fells it, and the refutation it carried lapses.
        self.ev("verify", counter, "--unsafe", lab="lab-a", ok=(1,))
        self.assertEqual(self.js("show", good, lab="lab-a")["status"], "reproduced")
        self.assertEqual(self.js("check", lab="lab-a"), [])

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
        # A self-check is not a reproduction; the question is answered once another lab re-runs it.
        self.assertEqual(self.js("show", sub, lab="lab-a")["status"], "proposed")
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        self.ev("verify", c, "--unsafe", lab="lab-b")
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-a")
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

    def test_disagreeing_values_contest_a_question(self):
        q = self.ev("ask", "How many primes are there below 1000?", lab="lab-a")
        right = self.ev("claim", "There are 168 primes below 1000.", "--file", str(DEMO),
                        "--cmd", "python3 primes.py 1000 168", "--answers", q, "--value", "168", lab="lab-a")
        self.ev("claim", "x", "--value", "9.81 ± x", lab="lab-a", ok=(2,))
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        wrong = self.ev("claim", "There are 170 primes below 1000.", "--file", str(DEMO),
                        "--cmd", "python3 primes.py 1000 170", "--answers", q, "--value", "170", lab="lab-b")
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-a")

        self.assertEqual(self.js("show", wrong, lab="lab-a")["value"], {"exact": 170})
        self.assertIn("= 170", self.ev("log", lab="lab-a"))
        shown = self.js("show", q, lab="lab-a")
        self.assertEqual(shown["status"], "contested")
        self.assertEqual(shown["conflicts"], [sorted([right, wrong])])
        self.assertEqual(shown["values"], {right: {"exact": 168}, wrong: {"exact": 170}})
        tree = self.js("questions", lab="lab-a")
        self.assertEqual([(t["status"], t["conflicts"]) for t in tree], [("contested", [sorted([right, wrong])])])
        self.assertIn("contested: 168 vs 170", self.ev("questions", lab="lab-a"))
        todo = self.js("todo", lab="lab-a")
        self.assertEqual((todo[0]["action"], todo[0]["id"]), ("resolve", q))
        md = self.ev("report", lab="lab-a")
        self.assertIn("The question is contested: its standing answers disagree.", md)
        self.assertIn("Standing answers disagree: ", md)
        self.assertIn(f"168 (claim {right[:10]}, proposed)", md)
        self.assertIn(f"170 (claim {wrong[:10]}, proposed)", md)
        self.assertIn("orange", self.ev("graph", lab="lab-a"))

        self.ev("verify", wrong, "--unsafe", lab="lab-a", ok=(1,))
        self.assertEqual(self.js("show", q, lab="lab-a")["status"], "proposed")
        self.assertNotIn("resolve", [t["action"] for t in self.js("todo", lab="lab-a")])

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

    def test_leases_spread_agents_over_the_work(self):
        x = self.ev("claim", "x", "--cmd", "true", lab="lab-a")
        y = self.ev("claim", "y", "--cmd", "true", lab="lab-a")
        self.ev("init", str(self.dir / "lab-c"), "--agent", "carol", "--lab", "lab-c")
        for lab in ("lab-b", "lab-c"):
            self.ev("pull", str(self.dir / "lab-a"), lab=lab)
        first = self.js("todo", lab="lab-b")[0]["id"]
        other = y if first == x else x
        self.assertEqual(self.js("todo", lab="lab-c")[0]["id"], first)  # both would take the same item

        self.ev("lease", first[:8], "--for", "90m", "--note", "re-running", lab="lab-b")
        self.ev("lease", first, "--for", "forever", lab="lab-b", ok=(2,))
        self.ev("lease", first, "--for", "8d", lab="lab-b", ok=(2,))
        own = self.js("todo", lab="lab-b")[0]
        self.assertEqual((own["id"], own["leased"][0]["mine"]), (first, True))  # our own lease hides nothing
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-c")
        todo = self.js("todo", lab="lab-c")
        self.assertEqual([t["id"] for t in todo], [other, first])
        self.assertEqual(todo[1]["leased"][0]["by"]["agent"], "bob")
        self.assertIn("leased by lab-b/bob until", self.ev("todo", lab="lab-c"))
        # Judged at the moment the lease runs out, the item is first again.
        until = todo[1]["leased"][0]["until"]
        self.assertEqual(self.js("todo", "--at", until, lab="lab-c")[0]["id"], first)
        self.ev("todo", "--at", "yesterday", lab="lab-c", ok=(2,))

        self.ev("release", first, lab="lab-c", ok=(2,))  # carol holds no lease
        self.ev("release", first, lab="lab-b")
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-c")
        self.assertEqual(self.js("todo", lab="lab-c")[0]["leased"], [])
        self.assertEqual(self.ev("fsck", lab="lab-c"), "ok")

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
