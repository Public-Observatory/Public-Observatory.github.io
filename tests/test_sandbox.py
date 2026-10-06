import os
import tempfile
import unittest
from pathlib import Path

from evidence import EvidenceError, Store
from evidence import sandbox

MODE = sandbox.resolve("auto")


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("EV_AGENT", None)
        os.environ.pop("EV_SANDBOX", None)
        self.a = Store.init(Path(self.tmp.name) / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(Path(self.tmp.name) / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_refuses_other_labs_code_without_sandbox(self):
        h = self.a.claim("x", cmd="true")
        self.b.pull(self.a)
        with self.assertRaises(EvidenceError):
            self.b.verify(h, sandbox_mode="none")
        self.assertEqual(self.b.verify(h, sandbox_mode="none", unsafe=True)[1], "reproduced")
        self.assertEqual(self.a.verify(h, sandbox_mode="none")[1], "reproduced")  # our own code

    def test_review_records_sandbox(self):
        h = self.a.claim("x", cmd="true")
        review = self.a.get(self.a.verify(h, sandbox_mode="none")[0])
        self.assertEqual(review["environment"]["sandbox"], "none")


@unittest.skipIf(MODE == "none", "no sandbox on this machine")
class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(os.path.realpath(self.tmp.name))
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_cannot_write_outside_work_directory(self):
        target = self.dir / "escaped"
        h = self.a.claim("harmless", cmd=f"touch {target}")
        verdict = self.a.verify(h, sandbox_mode=MODE)[1]
        self.assertFalse(target.exists())
        self.assertEqual(verdict, "inconclusive")

    def test_cannot_read_ssh_keys(self):
        secret = Path.home() / ".ssh"
        if not secret.is_dir():
            self.skipTest("no ~/.ssh")
        h = self.a.claim("reads keys", cmd=f"ls {secret}")
        self.assertNotEqual(self.a.verify(h, sandbox_mode=MODE)[1], "reproduced")

    def test_no_network_in_command(self):
        h = self.a.claim("online", cmd="python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\"")
        self.assertNotEqual(self.a.verify(h, sandbox_mode=MODE, timeout=20)[1], "reproduced")

    def test_ordinary_work_runs(self):
        script = self.dir / "s.py"
        script.write_text("import tempfile\nopen('out.txt', 'w').write('x')\ntempfile.mkstemp()\n")
        h = self.a.claim("writes locally", files=[script], cmd="python3 s.py")
        self.assertEqual(self.a.verify(h, sandbox_mode=MODE)[1], "reproduced")


if __name__ == "__main__":
    unittest.main()
