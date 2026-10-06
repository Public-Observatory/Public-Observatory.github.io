"""Leases: announcements that steer other agents' `todo` elsewhere, and touch nothing else."""

import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from evidence import EvidenceError, Store, store as store_module
from evidence.store import LEASE_LIMIT, digest, timestamp


def later(t: str, **delta) -> str:
    return (timestamp(t) + timedelta(**delta)).isoformat()


class LeaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(self.dir / "b", {"agent": "bob", "lab": "lab-b"})
        self.c = Store.init(self.dir / "c", {"agent": "carol", "lab": "lab-c"})
        # Two runnable claims by carol: x has more dependants, so it tops everyone's todo.
        self.x = self.c.claim("x", cmd="true")
        self.c.claim("on x", depends_on=[self.x])
        self.y = self.c.claim("y", cmd="true")
        for s in (self.a, self.b):
            s.pull(self.c)

    def tearDown(self):
        self.tmp.cleanup()

    def order(self, s, at):
        return [(t["id"], [l["mine"] for l in t["leased"]]) for t in s.todo(s.author(), at=at)
                if t["action"] == "reproduce"]

    def test_lease_steers_others_but_not_the_holder(self):
        lease = self.a.lease(self.x, timedelta(hours=1))
        t = self.a.get(lease)["created"]
        self.b.pull(self.a)
        self.assertEqual(self.order(self.b, t), [(self.y, []), (self.x, [False])])
        self.assertEqual(self.order(self.a, t), [(self.x, [True]), (self.y, [])])
        # Without a reference time leases are not consulted.
        self.assertEqual([i["id"] for i in self.b.todo(self.b.author()) if i["action"] == "reproduce"],
                         [self.x, self.y])

    def test_lease_expires_at_the_time_its_writer_chose(self):
        lease = self.a.lease(self.x, timedelta(minutes=30))
        until = self.a.get(lease)["until"]
        self.b.pull(self.a)
        self.assertIn(self.x, self.b.leases(later(until, seconds=-1)))
        self.assertEqual(self.b.leases(until), {})
        self.assertEqual(self.order(self.b, until), [(self.x, []), (self.y, [])])

    def test_overlong_leases_are_read_as_the_limit(self):
        start = "2026-01-01T00:00:00+00:00"
        self.b.put_object({"type": "lease", "target": self.x, "by": {"agent": "mallory"}, "note": "",
                           "created": start, "until": later(start, days=365)})
        self.assertIn(self.x, self.b.leases(later(start, days=6)))
        self.assertEqual(self.b.leases((timestamp(start) + LEASE_LIMIT).isoformat()), {})
        with self.assertRaises(EvidenceError):
            self.a.lease(self.x, LEASE_LIMIT + timedelta(seconds=1))
        with self.assertRaises(EvidenceError):
            self.a.lease(self.x, timedelta(0))

    def test_release_and_work_end_a_lease(self):
        lease = self.a.lease(self.x, timedelta(hours=1))
        t = self.a.get(lease)["created"]
        self.a.release(self.x[:8])
        self.assertEqual(self.a.leases(t), {})
        with self.assertRaises(EvidenceError):
            self.a.release(self.x)  # nothing left to release
        lease = self.a.lease(self.x, timedelta(hours=1))
        self.a.verify(self.x, unsafe=True)  # the review is the work, so the lease ends
        self.assertEqual(self.a.leases(self.a.get(lease)["created"]), {})

    def test_only_the_holder_can_release(self):
        lease = self.a.lease(self.x, timedelta(hours=1))
        t = self.a.get(lease)["created"]
        self.b.pull(self.a)
        self.b.put_object({"type": "release", "lease": lease, "by": self.b.author(), "note": "", "created": t})
        self.assertIn(self.x, self.b.leases(t))
        # Nor does another agent's work on the target end it.
        self.b.review(self.x, "inconclusive", "tried")
        self.assertIn(self.x, self.b.leases(t))

    def test_questions_can_be_leased_and_answering_ends_the_lease(self):
        q = self.a.ask("why?")
        lease = self.a.lease(q, timedelta(hours=1))
        t = self.a.get(lease)["created"]
        self.assertIn(q, self.a.leases(t))
        self.a.claim("because", answers=[q])
        self.assertEqual(self.a.leases(t), {})
        with self.assertRaises(EvidenceError):
            self.a.lease(lease, timedelta(hours=1))  # a lease is not work to lease

    def test_leases_change_no_status(self):
        before = {h: (s.state, s.at_risk_because, s.independent) for h, s in self.b.statuses().items()}
        questions = self.b.question_statuses()
        self.a.lease(self.x, timedelta(hours=1))
        self.a.lease(self.y, timedelta(hours=1))
        self.a.release(self.y)
        self.b.pull(self.a)
        self.assertEqual({h: (s.state, s.at_risk_because, s.independent) for h, s in self.b.statuses().items()},
                         before)
        self.assertEqual(self.b.question_statuses(), questions)
        self.assertEqual(self.b.fsck(), [])

    def test_pull_refuses_malformed_leases(self):
        good = {"type": "lease", "target": self.x, "by": {"agent": "m"}, "note": "",
                "created": "2026-01-01T00:00:00+00:00", "until": "2026-01-01T01:00:00+00:00"}
        for i, bad in enumerate(({**good, "until": "2026-01-01T01:00:00Z"}, {**good, "created": "tomorrow"},
                                 {**good, "until": "2026-13-01T01:00:00+00:00"}, {**good, "target": "x"},
                                 {"type": "release", "lease": "x", "by": {}, "note": "", "created": ""})):
            with self.subTest(bad=bad):
                s = Store.init(self.dir / f"bad{i}", {"agent": "m"})
                data = json.dumps(bad).encode()
                s._write("objects", digest(data), data)
                with self.assertRaises(EvidenceError):
                    self.b.pull(s)

    def test_a_version_without_leases_accepts_and_ignores_them(self):
        self.a.lease(self.x, timedelta(hours=1))
        self.a.release(self.x)
        old_schema = {k: v for k, v in store_module.SCHEMA.items() if k not in ("lease", "release")}
        with mock.patch.object(store_module, "SCHEMA", old_schema):
            old = Store.init(self.dir / "old", {"agent": "olga"})
            old.pull(self.a)
            self.assertEqual(len(old.objects("lease")), 1)
            self.assertEqual(set(old.statuses()), {self.x, self.y, *self.c.objects("claim")})
            self.assertEqual(old.fsck(), [])


if __name__ == "__main__":
    unittest.main()
