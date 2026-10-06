"""Where objects come from: another store on disk, a store served over HTTP, or a git repository.

A source has two operations, `listing()` (the ids of its objects and blobs) and `open(kind, id)`
(a binary file). `Store` is itself a source. Every byte read is checked against its id by
`Store.pull`, so a source need not be trusted: it can withhold objects but cannot alter them. Nor
can it exhaust memory or disk: `pull` reads every file in bounded chunks up to its limits, and the
index of an HTTP source is read up to INDEX_LIMIT bytes.

Serving is read-only and stateless: `ev serve` answers `GET /index.json` with the listing and
`GET /objects/ab/cdef….json` or `GET /blobs/ab/cdef…` with the file. Any static host can serve a
store exported with `ev serve --export DIR`, which writes only the public files and the index.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .errors import EvidenceError

HEX = re.compile(r"[0-9a-f]{64}")
PATH = re.compile(r"/(objects|blobs)/([0-9a-f]{2})/([0-9a-f]{62})(\.json)?")
# Room for the ids of about a million objects and blobs.
INDEX_LIMIT = 2 ** 26


class HttpSource:
    def __init__(self, url: str):
        self.url = url.rstrip("/") + "/"
        self.name = url

    def _open(self, path: str):
        req = urllib.request.Request(self.url + path, headers={"User-Agent": "evidence"})
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            e.close()
            raise EvidenceError(f"{e.code} fetching {self.url + path}") from e
        except urllib.error.URLError as e:
            raise EvidenceError(f"cannot reach {self.url} ({e.reason})") from e

    def listing(self) -> dict[str, list[str]]:
        with self._open("index.json") as r:
            data = r.read(INDEX_LIMIT + 1)
        if len(data) > INDEX_LIMIT:
            raise EvidenceError(f"the index of {self.url} exceeds {INDEX_LIMIT} bytes")
        try:
            index = json.loads(data)
        except (ValueError, RecursionError) as e:
            raise EvidenceError(f"the index of {self.url} is not JSON") from e
        if not isinstance(index, dict):
            raise EvidenceError(f"the index of {self.url} is not a JSON object")
        return {k: [h for h in index.get(k, []) if isinstance(h, str) and HEX.fullmatch(h)]
                for k in ("objects", "blobs")}

    def open(self, kind: str, h: str):
        """The response itself, so that `pull` reads it in chunks and stops at its limits."""
        return self._open(f"{kind}/{h[:2]}/{h[2:]}" + (".json" if kind == "objects" else ""))


def is_git(spec: str) -> bool:
    url = spec.partition("#")[0]
    return url.endswith(".git") or url.startswith(("git@", "ssh://", "git://", "file://",
                                                    "https://github.com/", "https://gitlab.com/",
                                                    "https://codeberg.org/"))


@contextlib.contextmanager
def open_source(spec: str):
    """Yield a source for a path, an HTTP URL or a git URL (`URL#subdir` names a directory in it)."""
    from .store import STORE_DIR, Store

    def local(path: Path):
        return Store(path / STORE_DIR if (path / STORE_DIR).is_dir() else path)

    if is_git(spec):
        url, _, sub = spec.partition("#")
        with tempfile.TemporaryDirectory() as tmp:
            # `--` keeps a URL beginning with a dash from being read as an option such as --upload-pack.
            r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--", url, tmp], capture_output=True, text=True)
            if r.returncode:
                raise EvidenceError(f"git clone {url}: {r.stderr.strip()}")
            yield local(Path(tmp) / sub)
    elif spec.startswith(("http://", "https://")):
        yield HttpSource(spec)
    else:
        yield local(Path(spec))


def serve(store, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """A read-only HTTP server for a store; the caller runs `serve_forever()`."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/index.json":
                body, kind = json.dumps(store.listing()).encode(), "application/json"
            elif m := PATH.fullmatch(self.path):
                path = store.root / m.group(1) / m.group(2) / (m.group(3) + (m.group(4) or ""))
                if not path.is_file():
                    return self.send_error(404)
                body, kind = path.read_bytes(), "application/octet-stream"
            else:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)
