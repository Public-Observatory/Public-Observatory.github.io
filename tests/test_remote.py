import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from evidence import EvidenceError, Store
from evidence.remote import open_source, serve


class RemoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(self.dir / "b", {"agent": "bob", "lab": "lab-b"})
        script = self.dir / "s.py"
        script.write_text("print(1)\n")
        self.h = self.a.claim("served", files=[script], cmd="python3 s.py")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pull_over_http(self):
        server = serve(self.a, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with open_source(f"http://127.0.0.1:{server.server_address[1]}") as src:
                self.assertEqual(self.b.pull(src), 2)  # the claim and its file
            self.assertEqual(self.b.checkout(self.h, self.dir / "w")[0].read_text(), "print(1)\n")
            with open_source(f"http://127.0.0.1:{server.server_address[1]}/nothing-here") as src:
                with self.assertRaises(EvidenceError):
                    self.b.pull(src)
        finally:
            server.shutdown()

    def test_pull_from_git_repository(self):
        repo = self.dir / "repo.git"
        work = self.dir / "a"
        git = lambda *a, cwd=work: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
        git("init", "-q")
        (work / ".evidence" / "key").write_text("secret")  # stands in for a signing key
        git("add", ".evidence")
        tracked = git("ls-files").stdout.decode().split()
        self.assertNotIn(".evidence/key", tracked)
        self.assertNotIn(".evidence/config.json", tracked)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "record")
        git("clone", "-q", "--bare", str(work), str(repo), cwd=self.dir)
        with open_source(f"file://{repo}") as src:
            self.assertEqual(self.b.pull(src), 2)

    def test_push_to_local_store(self):
        self.assertEqual(self.a.push(self.b), 2)
        self.assertIn(self.h, self.b.objects("claim"))


    def test_git_url_cannot_be_read_as_an_option(self):
        seen = []

        def run(argv, **kw):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 1, "", "no")

        real, subprocess.run = subprocess.run, run
        try:
            with self.assertRaises(EvidenceError):
                with open_source("--upload-pack=x.git"):
                    pass
        finally:
            subprocess.run = real
        self.assertLess(seen[0].index("--"), seen[0].index("--upload-pack=x.git"))

if __name__ == "__main__":
    unittest.main()
