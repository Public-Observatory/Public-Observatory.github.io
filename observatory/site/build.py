"""Build `agendas.json`, the index the Observatory's website reads.

    python3 observatory/site/build.py github OUT [TOPIC]     agendas on GitHub with the topic (default
                                                              observatory-agenda), read from their Pages
    python3 observatory/site/build.py local OUT DIR...       agendas in local directories, for previews

Each agenda is a repository holding `agenda.json` and a record, whose publish workflow puts
`snapshot.json` on its GitHub Pages site. The index carries, for each agenda, the agenda file, where
its snapshot is, and the few numbers the front page shows; the page of one agenda fetches the
snapshot itself. An agenda whose files cannot be read is left out and reported, so that one broken
repository does not take the index down. With `local`, the snapshots are computed here and written
beside the index under `data/`.

Set GITHUB_TOKEN to search with a higher rate limit. Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "observatory"))

import agenda as agendas  # noqa: E402

TOPIC = "observatory-agenda"
LIMIT = 2 << 20  # bytes read from any one file


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str, token: str | None = None) -> bytes:
    headers = {"User-Agent": "observatory-index", "Accept": "application/vnd.github+json"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        data = r.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError(f"{url} is larger than {LIMIT} bytes")
    return data


def summary(snap: dict) -> dict:
    """The numbers on an agenda's card."""
    c = snap["counts"]
    return {"questions": c["questions"], "answered": c["answered"], "contested": c["contested"],
            "claims": c["claims"], "reproduced": c["reproduced"], "refuted": c["refuted"],
            "todo": len(snap["todo"]), "leases": len(snap["leases"]),
            "contributors": len(snap["contributors"]), "at": snap["at"]}


def entry(repo: str, agenda: dict, snapshot_url: str, snap: dict, **extra) -> dict:
    return {"repo": repo, "agenda": agenda, "snapshot": snapshot_url, "summary": summary(snap), **extra}


def from_github(topic: str = TOPIC, token: str | None = None, get=fetch) -> tuple[list[dict], list[str]]:
    q = urllib.parse.quote(f"topic:{topic}")
    found = json.loads(get(f"https://api.github.com/search/repositories?q={q}&per_page=100", token))
    out, skipped = [], []
    for r in found.get("items", []):
        full, branch = r["full_name"], r["default_branch"]
        owner, name = full.split("/")
        pages = f"https://{owner.lower()}.github.io/{name}/"
        try:
            agenda = json.loads(get(f"https://raw.githubusercontent.com/{full}/{branch}/agenda.json"))
            if bad := agendas.problems(agenda):
                raise ValueError("; ".join(bad))
            snap = json.loads(get(pages + "snapshot.json"))
            out.append(entry(full, agenda, pages + "snapshot.json", snap, url=r["html_url"], stars=r["stargazers_count"],
                             pushed=r["pushed_at"]))
        except (OSError, ValueError, KeyError, urllib.error.URLError) as e:
            skipped.append(f"{full}: {e}")
    return out, skipped


def from_local(dirs: list[Path], out: Path) -> tuple[list[dict], list[str]]:
    from evidence.report import snapshot
    from evidence.store import STORE_DIR, Store
    at = now()
    entries, skipped = [], []
    for d in dirs:
        try:
            agenda = agendas.load(d / "agenda.json")
            snap = snapshot(Store(d / STORE_DIR), at)
        except Exception as e:  # a preview reports every broken directory and carries on
            skipped.append(f"{d}: {e}")
            continue
        path = Path("data") / d.name / "snapshot.json"
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_text(json.dumps(snap, ensure_ascii=False))
        entries.append(entry(f"local/{d.name}", agenda, path.as_posix(), snap))
    return entries, skipped


def write(out: Path, entries: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    entries = sorted(entries, key=lambda e: e["repo"].lower())
    (out / "agendas.json").write_text(json.dumps({"built": now(), "agendas": entries}, ensure_ascii=False, indent=1))


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("github", "local") or (argv[0] == "local" and len(argv) < 3):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if argv[0] == "github":
        entries, skipped = from_github(argv[2] if len(argv) > 2 else TOPIC, os.environ.get("GITHUB_TOKEN"))
    else:
        entries, skipped = from_local([Path(d) for d in argv[2:]], out)
    write(out, entries)
    for s in skipped:
        print(f"skipped {s}", file=sys.stderr)
    print(f"indexed {len(entries)} agenda(s) in {out / 'agendas.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
