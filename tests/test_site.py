"""The website's builder: agenda files, issues read as questions and claims, and the index."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))

import agenda  # noqa: E402
import build  # noqa: E402

GOOD = {"title": "Counting primes fast", "kind": "open-agenda",
        "question": "How fast can one count the primes below x?", "created": "2026-10-01T09:00:00Z",
        "summary": "Which methods work at which scale.", "maintainers": ["isabeldahlgren"]}


def issue(number, label, body, state="open", **extra):
    return {"number": number, "title": f"Issue {number}", "labels": [{"name": l} for l in label.split()], "body": body,
            "state": state, "html_url": f"https://github.com/Lab/primes/issues/{number}", "user": {"login": "alice"},
            "created_at": "2026-10-02T00:00:00Z", "comments": 0, **extra}


ISSUES = [
    issue(1, "question", "### Question\n\nWhat is pi(10^12)?\n\n### Part of\n\n_No response_", state="closed"),
    issue(2, "question", "### Question\n\nIs LMO faster than a sieve at 10^12?\n\n### Part of\n\n#1"),
    issue(3, "claim reproduced", "### Claim\n\npi(10^12) = 37607912018.\n\n### Kind\n\nresult\n\n### Answers\n\n#1\n\n"
                                 "### Builds on\n\n_No response_\n\n### Evidence\n\nSee #9; run `make check`."),
    issue(4, "claim", "### Claim\n\nTrial division is too slow beyond 10^7.\n\n### Kind\n\nnegative", user={"login": "bob"}),
    issue(5, "claim refuted", "### Claim\n\npi(1000) = 169.\n\n### Kind\n\nwish\n\n### Answers\n\n"
                              "https://github.com/Lab/primes/issues/1, 2"),
    issue(6, "bug", "Something else entirely."),
    issue(7, "claim", "no form at all", pull_request={}),
]


class AgendaTest(unittest.TestCase):
    def test_template_is_a_valid_agenda(self):
        self.assertEqual(agenda.problems(json.loads((ROOT / "agenda-template" / "agenda.json").read_text())), [])

    def test_problems(self):
        self.assertEqual(agenda.problems(GOOD), [])
        self.assertEqual(agenda.problems([]), ["agenda.json must hold a JSON object"])
        self.assertIn("summary is missing", agenda.problems({k: v for k, v in GOOD.items() if k != "summary"}))
        for change, why in (({"kind": "wish"}, "kind must be one of"), ({"maintainers": []}, "maintainers"),
                            ({"maintainers": ["no spaces allowed"]}, "maintainers"),
                            ({"created": "2026-10-01T09:00:00"}, "time zone"), ({"created": "soon"}, "ISO 8601"),
                            ({"question": "  "}, "question is empty"), ({"tags": [1]}, "tags"),
                            ({"title": 3}, "title must be a str")):
            self.assertTrue(any(why in p for p in agenda.problems({**GOOD, **change})), change)

    def test_check_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agenda.json"
            path.write_text(json.dumps({**GOOD, "kind": "wish"}))
            run = subprocess.run([sys.executable, str(ROOT / "site" / "agenda.py"), "check", str(path)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn("kind must be one of", run.stderr)


class IssuesTest(unittest.TestCase):
    def test_forms_become_questions_and_claims(self):
        e = build.entry("Lab/primes", GOOD, ISSUES)
        self.assertEqual([(q["number"], q["text"], q["parents"], q["status"]) for q in e["questions"]],
                         [(1, "What is pi(10^12)?", [], "answered"), (2, "Is LMO faster than a sieve at 10^12?", [1], "open")])
        claims = {c["number"]: c for c in e["claims"]}
        self.assertEqual(sorted(claims), [3, 4, 5])  # not the bug report, not the pull request
        self.assertEqual((claims[3]["status"], claims[3]["answers"], claims[3]["builds_on"]), ("reproduced", [1], []))
        self.assertIn("make check", claims[3]["evidence"])
        self.assertEqual((claims[4]["kind"], claims[4]["status"]), ("negative", "proposed"))
        self.assertEqual((claims[5]["kind"], claims[5]["status"], claims[5]["answers"]), ("result", "refuted", [1, 2]))
        self.assertEqual(e["summary"], {"questions": 2, "answered": 1, "claims": 3, "reproduced": 1, "refuted": 1,
                                        "dead_ends": 1, "contributors": 2})

    def test_an_issue_without_a_form_keeps_its_title(self):
        q = build.item(issue(8, "question", "Free text, no headings."))
        self.assertEqual((q["text"], q["parents"]), ("Issue 8", []))


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def agenda_dir(self, name: str, meta: dict, issues=None) -> Path:
        d = self.dir / name
        d.mkdir()
        (d / "agenda.json").write_text(json.dumps(meta))
        if issues is not None:
            (d / "issues.json").write_text(json.dumps(issues))
        return d

    def test_local_index(self):
        good = self.agenda_dir("primes", GOOD, ISSUES)
        bare = self.agenda_dir("bare", {**GOOD, "title": "Bare"})
        bad = self.agenda_dir("broken", {**GOOD, "kind": "wish"})
        entries, skipped = build.from_local([good, bare, bad])
        self.assertEqual([(e["repo"], e["summary"]["claims"]) for e in entries], [("local/primes", 3), ("local/bare", 0)])
        self.assertEqual(len(skipped), 1)
        self.assertIn("kind must be one of", skipped[0])
        out = self.dir / "site"
        build.write(out, entries)
        index = json.loads((out / "agendas.json").read_text())
        self.assertEqual([e["repo"] for e in index["agendas"]], ["local/bare", "local/primes"])

    def test_github_index_skips_what_it_cannot_read(self):
        repo = {"full_name": "Lab/primes", "default_branch": "main", "html_url": "https://github.com/Lab/primes",
                "stargazers_count": 3, "pushed_at": "2026-10-06T00:00:00Z"}
        page1 = [issue(100 + i, "question", "") for i in range(100)]
        files = {
            "https://api.github.com/search/repositories?q=topic%3Aobservatory-agenda&per_page=100":
                {"items": [repo, {**repo, "full_name": "Lab/gone"}, {**repo, "full_name": "Lab/bad"}]},
            "https://raw.githubusercontent.com/Lab/primes/main/agenda.json": GOOD,
            "https://api.github.com/repos/Lab/primes/issues?state=all&per_page=100&page=1": page1,
            "https://api.github.com/repos/Lab/primes/issues?state=all&per_page=100&page=2": ISSUES,
            "https://raw.githubusercontent.com/Lab/bad/main/agenda.json": {**GOOD, "maintainers": []},
        }

        def get(url, token=None):
            if url not in files:
                raise OSError(f"404 {url}")
            return json.dumps(files[url]).encode()

        entries, skipped = build.from_github(get=get)
        self.assertEqual([(e["repo"], e["stars"], e["summary"]["questions"]) for e in entries], [("Lab/primes", 3, 102)])
        self.assertEqual(sorted(s.split(":")[0] for s in skipped), ["Lab/bad", "Lab/gone"])


if __name__ == "__main__":
    unittest.main()
