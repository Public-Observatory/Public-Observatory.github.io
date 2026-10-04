"""Import entries from Palomar (https://palomar-registry.org), a registry of Lean-verified mathematics.

Palomar's mechanical check is as strong as certainty gets: independent kernels confirm that
the Lean proof proves the Lean statement, under an allowlist of axioms. So an imported entry
gets a `reproduced` review from Palomar. What Palomar does not settle is whether the formal
statement says what the title and paper say; that is only screened by a language model. The
review records this limit, and a mis-formalisation is answered with a `refuted` review, which
outranks the reproduction and flags everything built on the entry.

We also take the dependency graph: each entry's provenance statement lists
the formalizations it builds on and the papers it formalizes. Dependencies on other Palomar
entries become `depends_on` edges, imported recursively; everything else is kept as a
reference. Imports are deterministic, so two labs importing the same entry version get the
same claim id and their stores merge cleanly.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable

from .store import EvidenceError, Store

DATA = "https://data.palomar-registry.org/"
SITE = "https://palomar-registry.org/"
AUTHOR = {"agent": "palomar-import", "lab": "palomar-registry.org"}
# Relationships in `related_formalizations` that make one entry rest on another.
DEPENDS = {"builds-on", "adapts"}
PALOMAR_ID = re.compile(r"PALOMAR-\d{4}-\d{2}-\d{2}-\d{6}")


def http_fetch(path: str) -> dict | None:
    # The data host rejects Python's default user agent.
    req = urllib.request.Request(DATA + path, headers={"User-Agent": "evidence/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise EvidenceError(f"palomar: {e.code} fetching {path}") from e
    except urllib.error.URLError as e:
        raise EvidenceError(f"palomar: cannot reach {DATA} ({e.reason})") from e


class Palomar:
    def __init__(self, store: Store, fetch: Callable[[str], dict | None] = http_fetch):
        self.store = store
        self.fetch = fetch
        self._recent: dict | None = None

    # ---------------------------------------------------------------- lookup

    def local(self, pid: str) -> dict[int, str]:
        """Claims already imported for a Palomar id, by version."""
        out = {}
        for h, c in self.store.objects("claim").items():
            src = c.get("source", {})
            if src.get("registry") == "palomar" and src.get("id") == pid:
                out[src["version"]] = h
        return out

    def recent(self) -> list[dict]:
        if self._recent is None:
            self._recent = self.fetch("recent.json") or {"entries": []}
        return self._recent["entries"]

    def latest_version(self, pid: str) -> int:
        for e in self.recent():
            if e["id"] == pid:
                return e["version"]
        v = 0
        while self.fetch(f"entries/{pid}-v{v + 1}.json") is not None:
            v += 1
        if not v:
            raise EvidenceError(f"palomar: no such entry {pid}")
        return v

    def entry(self, pid: str, version: int) -> dict:
        e = self.fetch(f"entries/{pid}-v{version}.json")
        if e is None:
            raise EvidenceError(f"palomar: no such entry {pid} v{version}")
        return e

    # ---------------------------------------------------------------- import

    def import_entry(self, pid: str, version: int | None = None, depth: int = 3,
                     _seen: set | None = None) -> str:
        """Import an entry and, up to `depth` levels, the Palomar entries it depends on."""
        pid = pid.upper()
        if not PALOMAR_ID.fullmatch(pid):
            raise EvidenceError(f"not a Palomar id: {pid}")
        version = version or self.latest_version(pid)
        have = self.local(pid)
        if version in have:
            return have[version]
        _seen = _seen if _seen is not None else set()
        _seen.add(pid)
        e = self.entry(pid, version)

        deps = []
        for r in e.get("provenance", {}).get("related_formalizations", []):
            m = PALOMAR_ID.search(r.get("identifier", ""))
            if r.get("relationship") in DEPENDS and m and m.group() not in _seen and depth > 0:
                deps.append(self.import_entry(m.group(), depth=depth - 1, _seen=_seen))

        h = self.store.put_object(self.to_claim(e, deps))
        # Registration requires passing the mechanical check.
        if e.get("status") == "registered":
            self.store.put_object(self.to_review(e, h))
        self.link_versions(pid)
        return h

    def link_versions(self, pid: str) -> None:
        """Mark every held version but the newest as superseded by the newest."""
        have = self.local(pid)
        newest = max(have)
        created = self.store.get(have[newest])["created"]
        for v, old in have.items():
            if v < newest:
                self.store.put_object({
                    "type": "review", "claim": old, "verdict": "superseded", "by": AUTHOR,
                    "method": f"Palomar registered version {newest}", "note": "",
                    "superseded_by": have[newest], "created": created,
                })

    def sync(self, limit: int = 20, depth: int = 3) -> list[str]:
        return [self.import_entry(e["id"], e["version"], depth=depth) for e in self.recent()[:limit]]

    @staticmethod
    def to_review(e: dict, claim: str) -> dict:
        ver, review = e.get("verification", {}), e.get("review", {})
        # Entries before schema 5 do not name the kernels; Comparator ran them.
        kernels = ", ".join(k["name"] for k in ver.get("kernels", [])) or "Comparator"
        return {
            "type": "review", "claim": claim, "verdict": "reproduced", "by": AUTHOR,
            "method": (f"Palomar: formal statement kernel-checked by {kernels}; match with the informal "
                       f"statement checked only by a language model"),
            "note": (f"alignment review {review.get('outcome', 'unknown')} by "
                     f"{', '.join(review.get('reviewer_models', [])) or 'unknown'}; "
                     f"trust level {e.get('trust', {}).get('level', 'unknown')}; "
                     f"workflow {ver.get('workflow_url', 'unknown')}"),
            "superseded_by": None, "created": ver.get("verified_at", e["registered_at"]),
        }

    @staticmethod
    def to_claim(e: dict, deps: list[str]) -> dict:
        f = e.get("formalization", {})
        src = e.get("source", {})
        prov = e.get("provenance", {})
        ver = e.get("verification", {})

        evidence = [{"kind": "note", "text": e.get("abstract", "")}]
        if src.get("repository") and src.get("commit"):
            path = src.get("project_path") or "."
            evidence.append({"kind": "command", "cmd": (
                f"git clone -q https://github.com/{src['repository']} repo && cd repo && "
                f"git checkout -q {src['commit']} && cd {path} && "
                f"(lake exe cache get >/dev/null 2>&1 || true) && lake build")})
        for s in prov.get("mathematical_sources", []):
            evidence.append({"kind": "reference", "relationship": s.get("relationship", "other"),
                             "title": s.get("title", ""), "identifier": s.get("identifier", "")})
        for r in prov.get("related_formalizations", []):
            evidence.append({"kind": "reference", "relationship": r.get("relationship", "other"),
                             "title": "", "identifier": r.get("identifier", "")})

        return {
            "type": "claim",
            "kind": "result",
            "statement": e["title"],
            "author": AUTHOR,
            "evidence": evidence,
            "depends_on": sorted(set(deps)),
            "created": e["registered_at"],
            "source": {
                "registry": "palomar",
                "id": e["id"],
                "version": e["version"],
                "url": f"{SITE}entry.html?id={e['id']}&version={e['version']}",
                "repository": src.get("repository"),
                "commit": src.get("commit"),
                "theorems": f.get("theorem_names", []),
                "challenge_sha256": ver.get("challenge_sha256"),
                "authors": [a["name"] for a in e.get("authors", [])],
                # Either a pinned repository or a path vendored inside the project.
                "lean_dependencies": [f"{d['repository']}@{d.get('revision', '')}" if "repository" in d
                                      else f"{d.get('name', '?')} (vendored at {d.get('path', '?')})"
                                      for d in f.get("project_dependencies", [])],
            },
        }
