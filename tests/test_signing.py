import json
import os
import tempfile
import unittest
from pathlib import Path

from evidence import EvidenceError, Store
from evidence import signing


@unittest.skipUnless(signing.available(), "needs ssh-keygen")
class SigningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for k in ("EV_AGENT", "EV_KEY"):
            os.environ.pop(k, None)
        self.a = self.signed("a", "alice", "lab-a")
        self.b = self.signed("b", "bob", "lab-b")

    def signed(self, name, agent, lab):
        s = Store.init(self.dir / name, {"agent": agent, "lab": lab})
        signing.generate(s.root / "key")
        s.configure(key="key")
        return s

    def tearDown(self):
        self.tmp.cleanup()

    def test_signed_objects_pull_cleanly_and_fsck(self):
        h = self.a.claim("signed claim")
        self.assertEqual(self.a.get(h)["author"]["key"], signing.public_key(self.a.root / "key"))
        self.b.pull(self.a)
        self.assertIn(h, self.b.objects("claim"))
        self.assertEqual(self.b.fsck(), [])

    def test_forged_author_is_rejected_on_pull(self):
        # Mallory writes a claim in lab-a's name, with lab-a's public key but no signature.
        mallory = Store.init(self.dir / "m", {"agent": "mallory"})
        mallory.put_object({"type": "claim", "kind": "result", "statement": "forged",
                            "author": self.a.author(), "evidence": [], "depends_on": [], "created": "x"})
        with self.assertRaises(EvidenceError):
            self.b.pull(mallory)
        self.assertEqual(self.b.objects("claim"), {})

    def test_signature_by_another_key_does_not_count(self):
        h = self.a.claim("real")
        sig = next(iter(self.a.objects("signature").values()))
        mallory = Store.init(self.dir / "m", {"agent": "mallory"})
        mallory.pull(self.a)
        # Swap the claim for one with a different statement, re-using the signature object.
        obj = {**self.a.get(h), "statement": "tampered"}
        mallory.put_object(obj)
        mallory.put_object({**sig, "object": "0" * 64})
        with self.assertRaises(EvidenceError):
            self.b.pull(mallory)

    def test_trusted_reproductions_are_counted_separately(self):
        h = self.a.claim("x", cmd="true")
        self.b.pull(self.a)
        self.b.verify(h, unsafe=True)
        self.a.pull(self.b)
        self.assertEqual((self.a.statuses()[h].independent, self.a.statuses()[h].trusted), (1, 0))
        self.a.configure(trust={self.b.author()["key"]: "lab-b"})
        self.assertEqual(self.a.statuses()[h].trusted, 1)

    def test_fsck_reports_tampering(self):
        h = self.a.claim("honest")
        path = self.a._path("objects", h)
        data = json.loads(path.read_bytes())
        data["statement"] = "forged"
        path.write_text(json.dumps(data))
        self.assertTrue(any("corrupt" in p for p in Store(self.a.root).fsck()))


if __name__ == "__main__":
    unittest.main()
