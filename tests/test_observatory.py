"""The Observatory's glue: agenda files, the root question, and the index the website reads."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "contrib"))
sys.path.insert(0, str(ROOT / "site"))

import agenda  # noqa: E402
import build  # noqa: E402

from evidence import batch  # noqa: E402
from evidence.report import snapshot  # noqa: E402
from evidence.store import Store  # noqa: E402

GOOD = {"title": "Counting primes fast", "kind": "open-agenda",
        "question": "How fast can one count the primes below x?", "created": "2026-10-01T09:00:00Z",
        "summary": "Which methods work at which scale.", "maintainers": ["isabeldahlgren"]}


class AgendaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

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

    def test_root_question_has_one_id_however_often_it_is_asked(self):
        ids = []
        for lab in ("a", "b"):
            store = Store.init(self.dir / lab, {"agent": GOOD["maintainers"][0],
                                                "lab": "github"})
            out = batch.apply(store, [(1, agenda.seed(GOOD))], self.dir)
            again = batch.apply(store, [(1, agenda.seed(GOOD))], self.dir)
            self.assertEqual((out[0]["id"], again[0]["new"]), (again[0]["id"], False))
            ids.append(out[0]["id"])
        self.assertEqual(ids[0], ids[1])

    def test_page_escapes_and_points_to_the_site(self):
        page = agenda.page({**GOOD, "title": "<b>x</b>"}, "https://obs.example/", "o/r")
        self.assertIn("https://obs.example/agenda.html?repo=o/r", page)
        self.assertNotIn("<b>x</b>", page)


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ)
        os.environ.pop("EV_DIR", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def agenda_dir(self, name: str, meta: dict) -> Path:
        d = self.dir / name
        store = Store.init(d, {"agent": "alice"})
        batch.apply(store, [(1, agenda.seed(meta))], d)
        (d / "agenda.json").write_text(json.dumps(meta))
        return d

    def test_local_index_and_snapshots(self):
        good = self.agenda_dir("primes", GOOD)
        bad = self.agenda_dir("broken", {**GOOD, "kind": "wish"})
        out = self.dir / "site"
        entries, skipped = build.from_local([good, bad], out)
        self.assertEqual([e["repo"] for e in entries], ["local/primes"])
        self.assertEqual(len(skipped), 1)
        self.assertIn("kind must be one of", skipped[0])
        snap = json.loads((out / entries[0]["snapshot"]).read_text())
        self.assertEqual(snap["questions"][0]["text"], GOOD["question"])
        self.assertEqual(entries[0]["summary"]["questions"], 1)
        build.write(out, entries)
        self.assertEqual(json.loads((out / "agendas.json").read_text())["agendas"][0]["agenda"], GOOD)

    def test_github_index_skips_what_it_cannot_read(self):
        d = self.agenda_dir("primes", GOOD)
        snap = snapshot(Store(d / ".evidence"), "2026-10-07T00:00:00+00:00")
        repo = {"full_name": "Lab/primes", "default_branch": "main", "html_url": "https://github.com/Lab/primes",
                "stargazers_count": 3, "pushed_at": "2026-10-06T00:00:00Z"}
        files = {
            "https://api.github.com/search/repositories?q=topic%3Aobservatory-agenda&per_page=100":
                {"items": [repo, {**repo, "full_name": "Lab/gone"}, {**repo, "full_name": "Lab/bad"}]},
            "https://raw.githubusercontent.com/Lab/primes/main/agenda.json": GOOD,
            "https://lab.github.io/primes/snapshot.json": snap,
            "https://raw.githubusercontent.com/Lab/bad/main/agenda.json": {**GOOD, "maintainers": []},
        }

        def get(url, token=None):
            if url not in files:
                raise OSError(f"404 {url}")
            return json.dumps(files[url]).encode()

        entries, skipped = build.from_github(get=get)
        self.assertEqual([(e["repo"], e["snapshot"], e["stars"]) for e in entries],
                         [("Lab/primes", "https://lab.github.io/primes/snapshot.json", 3)])
        self.assertEqual(entries[0]["summary"]["at"], "2026-10-07T00:00:00+00:00")
        self.assertEqual(sorted(s.split(":")[0] for s in skipped), ["Lab/bad", "Lab/gone"])


if __name__ == "__main__":
    unittest.main()
