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

    def test_search_scores_and_drops_weak_matches(self):
        dead = self.ev("claim", "Trial division is too slow beyond 10^7.", "--kind", "negative", lab="lab-a")
        q = self.ev("ask", "Is trial division fast enough for primes below 10^8?", lab="lab-a")
        for s in ("Water is wet.", "The sky is blue.", "Grass is green."):
            self.ev("claim", s, lab="lab-a")
        hits = self.js("search", "is trial division fast enough?", lab="lab-a")
        self.assertEqual({h["id"] for h in hits}, {dead, q})
        self.assertTrue(all(h["score"] > 0 for h in hits))
        self.assertEqual(len(self.js("search", "is trial division fast enough?", "--all", lab="lab-a")), 5)
        line = self.ev("search", "trial division", lab="lab-a").splitlines()[0]
        self.assertRegex(line, r"^\s*\d+\.\d\d  ")

    def test_verify_shows_the_output(self):
        h = self.ev("claim", "There are 169 primes below 1000.", "--file", str(DEMO),
                    "--cmd", "python3 primes.py 1000 169", lab="lab-a")
        out = self.ev("verify", h, lab="lab-a", ok=(1,))
        self.assertIn("refuted", out)
        self.assertIn("168", out)  # the program's own report of what it counted
        [v] = json.loads(self.ev("verify", h, "--json", lab="lab-a", ok=(1,)))
        self.assertEqual((v["claim"], v["verdict"]), (h, "refuted"))
        self.assertIn("168", v["output"])

    def test_todo_text_puts_action_id_impact_and_why_on_one_line(self):
        h = self.ev("claim", "x", "--cmd", "true", lab="lab-a")
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        [item] = self.js("todo", lab="lab-b")
        self.assertEqual(set(item), {"action", "id", "statement", "impact", "why", "leased"})
        first = self.ev("todo", lab="lab-b").splitlines()[0]
        for part in ("reproduce", h[:10], "impact 1", item["why"]):
            self.assertIn(part, first)

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

    def test_pull_limits(self):
        self.ev("claim", "with a file", "--file", str(DEMO), "--cmd", "true", lab="lab-a")
        self.ev("pull", str(self.dir / "lab-a"), "--max-blob", "100", lab="lab-b", ok=(2,))
        self.ev("pull", str(self.dir / "lab-a"), "--max-blob", "lots", lab="lab-b", ok=(2,))
        self.assertIn("pulled 2", self.ev("pull", str(self.dir / "lab-a"), "--max-blob", "1M", lab="lab-b"))

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

        self.assertIn("re-running", self.ev("todo", lab="lab-c"))
        self.assertEqual(todo[1]["leased"][0]["note"], "re-running")
        self.ev("release", first, lab="lab-c", ok=(2,))  # carol holds no lease
        self.ev("release", first, lab="lab-b")
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-c")
        self.assertEqual(self.js("todo", lab="lab-c")[0]["leased"], [])
        self.assertEqual(self.ev("fsck", lab="lab-c"), "ok")

    def test_lease_and_release_publish_to_push_targets(self):
        shared = self.dir / "shared"
        self.ev("init", str(shared), "--agent", "nobody")
        x = self.ev("claim", "x", "--cmd", "true", lab="lab-a")
        self.ev("push", lab="lab-a", ok=(2,))  # no push target yet
        self.ev("remote", "add", "shared", str(shared), "--push", lab="lab-a")
        self.assertEqual(self.js("whoami", lab="lab-a")["push"], ["shared"])
        self.ev("push", lab="lab-a")
        self.ev("remote", "add", "shared", str(shared), lab="lab-b")
        self.ev("pull", lab="lab-b")
        self.ev("lease", x, lab="lab-b")  # lab-b has no push target: the lease stays at home
        self.assertEqual(self.js("todo", lab="lab-a")[0]["leased"], [])
        self.ev("remote", "add", "shared", str(shared), "--push", lab="lab-b")
        self.ev("lease", x, "--note", "again", lab="lab-b")
        self.ev("pull", lab="lab-a")
        self.assertIn("again", [lease["note"] for lease in self.js("todo", lab="lab-a")[0]["leased"]])
        self.ev("release", x, lab="lab-b")
        self.ev("pull", lab="lab-a")
        self.assertEqual(self.js("todo", lab="lab-a")[0]["leased"], [])
        self.ev("remote", "remove", "shared", lab="lab-b")
        self.assertEqual(self.js("whoami", lab="lab-b")["push"], [])

    def test_keygen_and_trust(self):
        from evidence import signing
        if not signing.available():
            self.skipTest("needs ssh-keygen")
        self.ev("init", str(self.dir / "lab-c"), "--agent", "carol", "--lab", "lab-c", "--keygen")
        me = self.js("whoami", lab="lab-c")
        self.assertTrue(me["fingerprint"].startswith("SHA256:"))
        self.ev("trust", "add", "lab-c", str(self.dir / "lab-c" / ".evidence" / "key.pub"), lab="lab-a")
        self.ev("claim", "signed", "--cmd", "true", lab="lab-c")
        self.ev("pull", str(self.dir / "lab-c"), lab="lab-a")
        self.assertIn("✔lab-c", self.ev("log", lab="lab-a"))
        self.assertEqual(self.ev("fsck", lab="lab-a"), "ok")

    # ------------------------------------------------------------------ apply

    def batch(self, lines, name="batch.jsonl"):
        run = self.dir / "run"
        run.mkdir(exist_ok=True)
        path = run / name
        path.write_text("".join((l if isinstance(l, str) else json.dumps(l)) + "\n" for l in lines))
        return str(path)

    def fails(self, *argv, lab):
        os.environ["EV_DIR"] = str(self.dir / lab / ".evidence")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(list(argv)), 2)
        return err.getvalue()

    def count(self, lab):
        return len(list((self.dir / lab / ".evidence" / "objects").glob("*/*.json")))

    def test_apply_resolves_local_refs_and_ids_on_record(self):
        old = self.ev("claim", "The sieve of Eratosthenes is correct.", lab="lab-a")
        (self.dir / "run").mkdir()
        (self.dir / "run" / "primes.py").write_bytes(DEMO.read_bytes())
        path = self.batch([
            {"ask": "How dense are the primes?", "ref": "q0"},
            {"ask": "How many primes are below 1000?", "ref": "q1", "parents": "q0"},
            "",
            {"claim": "There are 168 primes below 1000.", "ref": "c1", "answers": ["q1"], "value": 168,
             "files": ["primes.py"], "cmd": "python3 primes.py 1000 168", "depends_on": [old[:8]]},
            '{"claim": "The density near 1000 is 0.168.", "ref": "c2", "depends_on": "c1", "value": 0.1680}',
            {"claim": "Trial division is too slow beyond 10^7.", "kind": "negative", "notes": "timed out"},
            {"review": "c1", "verdict": "reproduced", "method": "counted by hand", "ref": "r1"},
        ])
        out = self.js("apply", path, lab="lab-a")
        self.assertEqual(sorted(out["refs"]), ["c1", "c2", "q0", "q1", "r1"])
        self.assertEqual([o["line"] for o in out["objects"]], [1, 2, 4, 5, 6, 7])
        self.assertEqual(out["new"], 6)
        ids = out["refs"]
        c1 = self.js("show", ids["c1"], lab="lab-a")
        self.assertEqual((c1["answers"], c1["depends_on"], c1["value"]), ([ids["q1"]], [old], {"exact": 168}))
        self.assertEqual(c1["status"], "proposed")  # reproduced by its own author: a self-check only
        self.assertEqual(self.js("show", ids["c2"], lab="lab-a")["value"], {"quantity": "0.1680"})
        self.assertEqual(self.js("show", ids["q1"], lab="lab-a")["parents"], [ids["q0"]])
        self.ev("verify", ids["c1"], lab="lab-a")  # the file was found next to the batch
        self.assertEqual(self.ev("fsck", lab="lab-a"), "ok")
        self.assertIn("recorded 0 new object(s) from 6 line(s)", self.ev("apply", path, lab="lab-a"))

    def test_apply_records_counter_claims(self):
        wrong = self.ev("claim", "There are 26 primes below 100.", "--cmd", "false", lab="lab-b")
        self.ev("pull", str(self.dir / "lab-b"), lab="lab-a")
        out = self.js("apply", self.batch([
            {"claim": "A sieve finds 25 primes below 100.", "cmd": "true", "refutes": wrong[:8], "ref": "c"},
            {"claim": "There are 26 primes below 100.", "cmd": "false", "ref": "w"},
            {"claim": "Counting again gives 25.", "cmd": "true", "ref": "k"},
            {"review": "w", "verdict": "refuted", "method": "a recount", "counter": "k"},
        ]), lab="lab-a")
        self.assertEqual(self.js("show", wrong, lab="lab-a")["status"], "refuted")
        self.assertEqual(self.js("show", out["refs"]["w"], lab="lab-a")["status"], "refuted")
        self.ev("apply", self.batch([{"claim": "x", "counter": "k"}]), lab="lab-a", ok=(2,))  # counter is a review's

    def test_apply_is_all_or_nothing(self):
        good = [{"ask": "Q?", "ref": "q"}, {"claim": "A.", "ref": "c", "answers": "q"}]
        bad = [{"claim": "B.", "depends_on": "nowhere"},
               {"claim": "B.", "depends_on": "q"},                          # a question, not a claim
               {"claim": "B.", "depends_on": "later"},
               {"claim": "B.", "files": ["missing.py"]},
               {"claim": "B.", "value": "9.81 ± x"},
               {"claim": "B.", "kind": "rumour"},
               {"claim": "B.", "dep": ["c"]},                               # a misspelt field
               {"claim": "B.", "created": "yesterday"},
               {"ask": "B?", "claim": "B."},
               {"review": "c", "verdict": "refuted"},                       # no method
               {"review": "c", "verdict": "superseded", "method": "m"},     # by what?
               {"ask": "Q again?", "ref": "q"},                             # a ref used twice
               ["not", "an", "object"],
               '{"ask": "unterminated',
               ]
        before = self.count("lab-a")
        for line in bad:
            err = self.fails("apply", self.batch(good + [line, {"claim": "C.", "ref": "later"}]), lab="lab-a")
            self.assertIn("line 3:", err, line)
            self.assertEqual(self.count("lab-a"), before, line)
        self.fails("apply", str(self.dir / "nowhere.jsonl"), lab="lab-a")
        dry = self.js("apply", self.batch(good), "--dry-run", lab="lab-a")
        self.assertEqual((dry["dry_run"], dry["new"], self.count("lab-a")), (True, 2, before))
        self.assertEqual(self.js("apply", self.batch(good), lab="lab-a")["new"], 2)

    def test_apply_is_deterministic_and_idempotent(self):
        lines = [{"ask": "How many primes are below 100?", "ref": "q", "created": "2026-10-01T12:00:00Z"},
                 {"claim": "There are 25.", "ref": "c", "answers": "q", "value": 25,
                  "created": "2026-10-01T13:00:00.5+01:00"}]
        first = self.js("apply", self.batch(lines), lab="lab-a")
        self.assertEqual(self.js("show", first["refs"]["c"], lab="lab-a")["created"], "2026-10-01T12:00:00+00:00")
        again = self.js("apply", self.batch(lines), lab="lab-a")
        self.assertEqual((again["refs"], again["new"]), (first["refs"], 0))
        # Another lab applying the same run as the same author obtains the same ids.
        os.environ.update(EV_AGENT="alice", EV_LAB="lab-a")
        self.assertEqual(self.js("apply", self.batch(lines), lab="lab-b")["refs"], first["refs"])
        del os.environ["EV_AGENT"], os.environ["EV_LAB"]

        # A line without a time resolves to an object on record that differs from it only in time.
        untimed = [{k: v for k, v in l.items() if k != "created"} for l in lines]
        self.assertEqual(self.js("apply", self.batch(untimed), lab="lab-a")["new"], 0)
        # So re-applying an untimed batch in one store records nothing new.
        untimed[0]["ask"] = "How many primes are below 200?"
        one = self.js("apply", self.batch(untimed), lab="lab-a")
        self.assertEqual(one["new"], 2)
        before = self.count("lab-a")
        two = self.js("apply", self.batch(untimed), lab="lab-a")
        self.assertEqual((two["refs"], two["new"], self.count("lab-a")), (one["refs"], 0, before))

    def test_apply_reads_standard_input(self):
        import sys
        stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"ask": "From a pipe?", "ref": "q"}) + "\n")
        try:
            out = self.js("apply", "-", lab="lab-a")
        finally:
            sys.stdin = stdin
        self.assertEqual(self.js("show", out["refs"]["q"], lab="lab-a")["text"], "From a pipe?")

    def test_failed_runs_become_negative_claims_that_search_finds(self):
        import subprocess
        import sys
        runs = self.dir / "runs"
        for name, hyp, value, ok in (("r1", "Dropout 0.1 lowers validation loss below 2.4.", 2.31, True),
                                     ("r2", "A cosine schedule lowers validation loss below 2.4.", 2.51, False)):
            (runs / name).mkdir(parents=True)
            (runs / name / "result.json").write_text(json.dumps(
                {"hypothesis": hyp, "metric": "val_loss", "value": value, "success": ok,
                 "command": f"python3 train.py --run {name}", "created": "2026-10-01T09:00:00Z"}))
        adapter = Path(__file__).resolve().parent.parent / "contrib" / "runs.py"
        lines = subprocess.run([sys.executable, str(adapter), str(runs)], capture_output=True, text=True,
                               check=True).stdout
        out = self.js("apply", self.batch(lines.splitlines(), "runs.jsonl"), lab="lab-a")
        hits = self.js("search", "cosine schedule", lab="lab-a")
        self.assertEqual((hits[0]["id"], hits[0]["kind"]), (out["refs"]["r2"], "negative"))
        self.assertEqual(hits[0]["value"], {"quantity": "2.51"})
        shown = self.js("show", out["refs"]["r1"], lab="lab-a")
        self.assertEqual((shown["kind"], [e["name"] for e in shown["evidence"] if e["kind"] == "file"]),
                         ("result", ["result.json"]))

    def test_snapshot_is_the_record_at_one_instant(self):
        q = self.ev("ask", "How many primes are there below 1000?", lab="lab-a")
        c = self.ev("claim", "There are 168 primes below 1000.", "--cmd", "true", "--answers", q, "--value", "168",
                    lab="lab-a")
        self.ev("pull", str(self.dir / "lab-a"), lab="lab-b")
        self.ev("verify", c, "--unsafe", lab="lab-b")
        open_q = self.ev("ask", "How many twin primes are there below 1000?", lab="lab-b")
        self.ev("lease", open_q, "--for", "1h", "--note", "trying a sieve", lab="lab-b")
        lease = self.js("todo", lab="lab-b")[0]["leased"][0]
        start = self.js("show", lease["id"], lab="lab-b")["created"]
        snap = self.js("snapshot", "--at", start, lab="lab-b")
        self.assertEqual(snap, self.js("snapshot", "--at", start, lab="lab-b"))  # no clock, no file order
        self.assertEqual((snap["format"], snap["at"]), (1, start))
        self.assertEqual(snap["questions"], self.js("questions", lab="lab-b"))
        self.assertEqual(snap["claims"], self.js("log", lab="lab-b"))
        self.assertEqual([d["id"] for d in snap["digest"]], [c])
        self.assertEqual([t["id"] for t in snap["todo"]], [open_q])
        self.assertEqual((snap["counts"]["reproduced"], snap["counts"]["answered"]), (1, 1))
        self.assertEqual({r["author"]["agent"]: (r["questions"], r["claims"], r["reviews"])
                          for r in snap["contributors"]}, {"alice": (1, 1, 0), "bob": (1, 0, 1)})
        self.assertEqual([(l["target"], l["note"]) for l in snap["leases"]], [(open_q, "trying a sieve")])
        self.assertEqual(self.js("snapshot", "--at", lease["until"], lab="lab-b")["leases"], [])  # expired
        self.assertIn("1 answered", self.ev("snapshot", "--at", start, lab="lab-b"))
        self.ev("snapshot", "--at", "soon", lab="lab-b", ok=(2,))

    def test_fsck_since_refuses_a_rewritten_record(self):
        import shutil
        import subprocess
        if not shutil.which("git"):
            self.skipTest("needs git")
        repo = self.dir / "lab-a"

        def git(*argv):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *argv],
                           check=True, capture_output=True)

        git("init", "-q")
        first = self.ev("claim", "x", lab="lab-a")
        git("add", "-A")
        git("commit", "-qm", "x")
        self.ev("claim", "y", lab="lab-a")
        self.assertEqual(self.ev("fsck", "--since", "HEAD", lab="lab-a"), "ok")  # added files are welcome
        path = repo / ".evidence" / "objects" / first[:2] / f"{first[2:]}.json"
        path.unlink()
        out = json.loads(self.ev("fsck", "--since", "HEAD", "--json", lab="lab-a", ok=(1,)))
        self.assertTrue(any(p.startswith("deleted since HEAD:") and first[2:] in p for p in out), out)
        self.ev("fsck", "--since", "no-such-rev", lab="lab-a", ok=(2,))

    def test_issue_forms_become_objects_once(self):
        import subprocess
        import sys
        adapter = Path(__file__).resolve().parent.parent / "contrib" / "github_issue.py"
        url = "https://github.com/o/agenda/issues/"

        def post(n, label, body):
            event = self.dir / f"issue-{n}.json"
            event.write_text(json.dumps({"action": "opened", "issue": {
                "number": n, "labels": [{"name": label}], "body": body, "html_url": url + str(n),
                "created_at": "2026-10-07T12:00:00Z"}}))
            r = subprocess.run([sys.executable, str(adapter), str(event)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return self.js("apply", self.batch(r.stdout.splitlines(), f"issue-{n}.jsonl"), lab="lab-a")

        root = self.ev("ask", "Which sieve is fastest below 10^9?", lab="lab-a")
        q = post(1, "question", f"### Question\n\nIs a segmented sieve faster below 10^9?\n\n### Part of\n\n{root[:10]}\n")
        qid = q["refs"]["issue-1"]
        self.assertEqual(self.js("show", qid, lab="lab-a")["parents"], [root])
        c = post(2, "claim", f"### Claim\n\nIt is, by a factor of three.\n\n### Kind\n\nresult\n\n"
                             f"### Answers\n\n{qid[:8]}\n\n### Builds on\n\n_No response_\n\n### Value\n\n3\n\n"
                             f"### Evidence\n\nTimed on one laptop.\n")
        shown = self.js("show", c["refs"]["issue-2"], lab="lab-a")
        self.assertEqual((shown["answers"], shown["value"], shown["depends_on"]), ([qid], {"exact": 3}, []))
        self.assertEqual([e["text"] for e in shown["evidence"]], ["Timed on one laptop.", f"posted as {url}2"])
        self.assertEqual(post(2, "claim", f"### Claim\n\nIt is, by a factor of three.\n\n### Kind\n\nresult\n\n"
                                          f"### Answers\n\n{qid[:8]}\n\n### Builds on\n\n_No response_\n\n"
                                          f"### Value\n\n3\n\n### Evidence\n\nTimed on one laptop.\n")["new"], 0)
        self.assertEqual(post(3, "discussion", "### Anything\n\nhello\n")["new"], 0)


if __name__ == "__main__":
    unittest.main()
