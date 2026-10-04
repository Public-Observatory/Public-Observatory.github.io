"""Content-addressed store of scientific claims and reviews.

Layout of a store (``.evidence/``)::

    objects/<id[:2]>/<id[2:]>.json   claims and reviews (immutable)
    blobs/<hash[:2]>/<hash[2:]>      evidence files (immutable)
    config.json                      default author for this store

Every object is identified by the SHA-256 of its canonical JSON, so two
stores merge by taking the union of their files: there are no conflicts.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = ".evidence"
KINDS = ("result", "negative", "conjecture")
VERDICTS = ("reproduced", "refuted", "superseded")
# When reviews disagree, the strongest verdict wins.
PRECEDENCE = ("refuted", "superseded", "reproduced", "proposed")


class EvidenceError(Exception):
    pass


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Status:
    state: str
    reviews: list[dict]
    at_risk_because: list[str]


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "objects").is_dir():
            raise EvidenceError(f"not an evidence store: {self.root}")

    # ------------------------------------------------------------------ setup

    @classmethod
    def init(cls, path: Path, author: dict | None = None) -> "Store":
        root = Path(path) / STORE_DIR
        (root / "objects").mkdir(parents=True, exist_ok=True)
        (root / "blobs").mkdir(exist_ok=True)
        config = root / "config.json"
        if author or not config.exists():
            config.write_text(json.dumps({"author": author or {}}, indent=2) + "\n")
        return cls(root)

    @classmethod
    def find(cls, start: Path | None = None) -> "Store":
        if env := os.environ.get("EV_DIR"):
            return cls(Path(env))
        here = Path(start or Path.cwd()).resolve()
        for d in (here, *here.parents):
            if (d / STORE_DIR / "objects").is_dir():
                return cls(d / STORE_DIR)
        raise EvidenceError("no .evidence store found (run `ev init`)")

    def author(self) -> dict:
        config = json.loads((self.root / "config.json").read_text())
        author = dict(config.get("author", {}))
        for key in ("agent", "model", "lab"):
            if value := os.environ.get(f"EV_{key.upper()}"):
                author[key] = value
        if "agent" not in author:
            raise EvidenceError("no author: set EV_AGENT or run `ev init --agent NAME`")
        return author

    # ---------------------------------------------------------------- objects

    def _path(self, kind: str, h: str) -> Path:
        return self.root / kind / h[:2] / (h[2:] + (".json" if kind == "objects" else ""))

    def put_object(self, obj: dict) -> str:
        data = canonical(obj)
        h = digest(data)
        path = self._path("objects", h)
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        return h

    def put_blob(self, data: bytes) -> str:
        h = digest(data)
        path = self._path("blobs", h)
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        return h

    def get(self, h: str) -> dict:
        return json.loads(self._path("objects", self.resolve(h)).read_bytes())

    def blob(self, h: str) -> bytes:
        return self._path("blobs", h).read_bytes()

    def ids(self) -> list[str]:
        return [p.parent.name + p.stem for p in (self.root / "objects").glob("*/*.json")]

    def resolve(self, prefix: str) -> str:
        matches = [h for h in self.ids() if h.startswith(prefix)]
        if not matches:
            raise EvidenceError(f"unknown id: {prefix}")
        if len(matches) > 1:
            raise EvidenceError(f"ambiguous id: {prefix}")
        return matches[0]

    def objects(self, type_: str) -> dict[str, dict]:
        out = {}
        for h in self.ids():
            obj = json.loads(self._path("objects", h).read_bytes())
            if obj["type"] == type_:
                out[h] = obj
        return out

    # ----------------------------------------------------------------- claims

    def claim(self, statement: str, kind: str = "result", files: list[Path] = (),
              cmd: str | None = None, notes: list[str] = (), depends_on: list[str] = ()) -> str:
        if kind not in KINDS:
            raise EvidenceError(f"kind must be one of {KINDS}")
        deps = sorted({self.resolve(d) for d in depends_on})
        for d in deps:
            if self.get(d)["type"] != "claim":
                raise EvidenceError(f"{d[:10]} is not a claim")
        evidence = [{"kind": "file", "name": Path(f).name, "blob": self.put_blob(Path(f).read_bytes())}
                    for f in files]
        if cmd:
            evidence.append({"kind": "command", "cmd": cmd})
        evidence += [{"kind": "note", "text": n} for n in notes]
        return self.put_object({
            "type": "claim", "kind": kind, "statement": statement, "author": self.author(),
            "evidence": evidence, "depends_on": deps, "created": now(),
        })

    def review(self, claim: str, verdict: str, method: str, note: str = "",
               superseded_by: str | None = None) -> str:
        if verdict not in VERDICTS:
            raise EvidenceError(f"verdict must be one of {VERDICTS}")
        claim = self.resolve(claim)
        if verdict == "superseded":
            if not superseded_by:
                raise EvidenceError("superseded needs --by CLAIM")
            superseded_by = self.resolve(superseded_by)
        return self.put_object({
            "type": "review", "claim": claim, "verdict": verdict, "by": self.author(),
            "method": method, "note": note, "superseded_by": superseded_by, "created": now(),
        })

    def verify(self, claim: str, timeout: int = 600) -> tuple[str, str]:
        """Re-run a claim's command on its evidence files in a clean directory."""
        claim = self.resolve(claim)
        obj = self.get(claim)
        cmds = [e["cmd"] for e in obj["evidence"] if e["kind"] == "command"]
        if not cmds:
            raise EvidenceError("claim has no command to re-run")
        with tempfile.TemporaryDirectory() as work:
            for e in obj["evidence"]:
                if e["kind"] == "file":
                    (Path(work) / e["name"]).write_bytes(self.blob(e["blob"]))
            try:
                run = subprocess.run(cmds[0], shell=True, cwd=work, capture_output=True,
                                     text=True, timeout=timeout)
                code, output = run.returncode, (run.stdout + run.stderr).strip()
            except subprocess.TimeoutExpired:
                code, output = None, f"timed out after {timeout}s"
        verdict = "reproduced" if code == 0 else "refuted"
        method = f"re-ran `{cmds[0]}` (exit {code})"
        return self.review(claim, verdict, method, note=output[-2000:]), verdict

    # ----------------------------------------------------------------- status

    def statuses(self) -> dict[str, Status]:
        claims = self.objects("claim")
        reviews = self.objects("review")
        by_claim: dict[str, list[dict]] = {h: [] for h in claims}
        for r in sorted(reviews.values(), key=lambda r: r["created"]):
            by_claim.setdefault(r["claim"], []).append(r)

        own = {}
        for h, rs in by_claim.items():
            verdicts = {r["verdict"] for r in rs} | {"proposed"}
            own[h] = next(v for v in PRECEDENCE if v in verdicts)

        out = {}
        for h in claims:
            broken = [d for d in self.upstream(h, claims) if own.get(d) in ("refuted", "superseded")]
            out[h] = Status(own[h], by_claim[h], broken)
        return out

    def upstream(self, h: str, claims: dict | None = None) -> list[str]:
        claims = claims if claims is not None else self.objects("claim")
        seen, stack = [], list(claims[h]["depends_on"])
        while stack:
            d = stack.pop()
            if d not in seen and d in claims:
                seen.append(d)
                stack.extend(claims[d]["depends_on"])
        return seen

    def downstream(self, h: str, claims: dict | None = None) -> list[str]:
        claims = claims if claims is not None else self.objects("claim")
        return [c for c in claims if h in self.upstream(c, claims)]

    # ---------------------------------------------------------------- sharing

    def pull(self, other: "Store") -> int:
        """Copy every object and blob we lack from another store, checking hashes."""
        copied = 0
        for kind in ("objects", "blobs"):
            for src in (other.root / kind).glob("*/*"):
                h = src.parent.name + src.name.removesuffix(".json")
                dst = self._path(kind, h)
                if dst.exists():
                    continue
                data = src.read_bytes()
                if digest(data) != h:
                    raise EvidenceError(f"corrupt {kind[:-1]} in {other.root}: {h}")
                dst.parent.mkdir(exist_ok=True)
                shutil.copyfile(src, dst)
                copied += 1
        return copied
