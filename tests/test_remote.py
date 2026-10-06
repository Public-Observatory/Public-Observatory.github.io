import contextlib
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from evidence import EvidenceError, Store
from evidence import remote
from evidence.remote import open_source, serve
from evidence.store import digest


class Spy:
    """A source that records which files `pull` opens."""

    def __init__(self, store):
        self.store, self.name, self.opened = store, store.name, []

    def listing(self):
        return self.store.listing()

    def open(self, kind, h):
        self.opened.append((kind, h))
        return self.store.open(kind, h)


@contextlib.contextmanager
def hostile(index: bytes, body: bytes):
    """A server that answers the index with `index` and every file with `body`."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = index if self.path == "/index.json" else body
            self.send_response(200)
            self.end_headers()  # no Content-Length: the client must bound what it reads itself
            with contextlib.suppress(OSError):
                self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with open_source(f"http://127.0.0.1:{server.server_address[1]}") as src:
            yield src
    finally:
        server.shutdown()
        server.server_close()


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
            server.server_close()

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


class LimitTest(unittest.TestCase):
    """A source need not be trusted, so what one pull takes from it is bounded."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ.pop("EV_AGENT", None)
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(self.dir / "b", {"agent": "bob", "lab": "lab-b"})
        data = self.dir / "data.bin"
        data.write_bytes(os.urandom(5000))
        self.h = self.a.claim("big data", files=[data], cmd="true")

    def tearDown(self):
        self.tmp.cleanup()

    def assertRefused(self, source, limits=None, match=""):
        with self.assertRaisesRegex(EvidenceError, match):
            self.b.pull(source, limits)
        self.assertEqual(self.b.listing(), {"objects": [], "blobs": []})
        self.assertEqual([p.name for p in self.b.root.iterdir() if p.name.endswith(".tmp")], [])

    def test_unreferenced_blobs_are_not_fetched(self):
        stray = self.a.put_blob(b"nothing refers to this")
        spy = Spy(self.a)
        self.assertEqual(self.b.pull(spy), 2)
        self.assertNotIn(("blobs", stray), spy.opened)
        self.assertEqual(self.b.listing()["blobs"], [self.a.get(self.h)["evidence"][0]["blob"]])
        self.assertEqual(self.b.fsck(), [])

    def test_object_limit(self):
        self.assertRefused(self.a, {"object": 100}, "limit of 100 bytes for one object")

    def test_blob_limit(self):
        self.assertRefused(self.a, {"blob": 4999}, "limit of 4999 bytes for one blob")
        self.assertEqual(self.b.pull(self.a, {"blob": 5000}), 2)

    def test_total_limit(self):
        size = sum(len(self.a.read("objects", h)) for h in self.a.listing()["objects"])
        self.assertRefused(self.a, {"total": size + 4999}, "for one pull")
        self.assertEqual(self.b.pull(self.a, {"total": size + 5000}), 2)

    def test_limits_from_config(self):
        self.b.configure(limits={"blob": "4K"})
        self.assertEqual(self.b.limits(), {"object": 2 ** 20, "blob": 4096, "total": 2 ** 32})
        self.assertRefused(self.a, match="4096 bytes for one blob")
        self.assertEqual(self.b.limits(blob="1M")["blob"], 2 ** 20)
        self.b.configure(limits={"blobs": 1})
        with self.assertRaises(EvidenceError):
            self.b.limits()

    def test_corrupt_blob(self):
        blob = self.a.get(self.h)["evidence"][0]["blob"]
        self.a._path("blobs", blob).write_bytes(b"tampered")
        self.assertRefused(self.a, match="corrupt blob")

    def test_http_response_is_read_only_up_to_the_limit(self):
        obj = json.dumps({"type": "question"}).encode()
        index = json.dumps({"objects": [digest(obj)], "blobs": []}).encode()
        with hostile(index, b"x" * (3 * 2 ** 20)) as src:
            self.assertRefused(src, match="limit of 1048576 bytes for one object")

    def test_http_index_is_bounded(self):
        with mock.patch.object(remote, "INDEX_LIMIT", 1000), hostile(b" " * 5000, b"") as src:
            self.assertRefused(src, match="index")


if __name__ == "__main__":
    unittest.main()
