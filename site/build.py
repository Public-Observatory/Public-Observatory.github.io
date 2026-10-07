"""Build `agendas.json`, the index the Observatory's website reads.

    python3 site/build.py github OUT [TOPIC]     agendas on GitHub with the topic (default observatory-agenda)
    python3 site/build.py local OUT DIR...       agendas in local directories, for previews

An agenda is a repository holding `agenda.json`. Its questions and claims are its issues labelled
`question` or `claim`, opened through the forms in `agenda-template/.github/ISSUE_TEMPLATE`. A claim
is reviewed in its issue's comments; a maintainer closes a question once it is answered.
The index carries, for each agenda, the agenda file, its questions and claims, and the numbers the
front page shows. An agenda whose files cannot be read is left out and reported, so that one broken
repository does not take the index down. With `local`, a directory may hold `issues.json`, a list
of issues as the GitHub API returns them.

Set GITHUB_TOKEN to search with a higher rate limit. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agenda as agendas  # noqa: E402

TOPIC = "observatory-agenda"
LIMIT = 2 << 20  # bytes read from any one response
PAGES = 10  # pages of 100 issues read from any one agenda
EMPTY = "_No response_"


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


def fields(body: str | None) -> dict[str, str]:
    """The answers of an issue form by label. GitHub renders a form as one `### Label` heading per
    field and `_No response_` for a field left empty; an empty answer is left out."""
    out = {}
    for m in re.finditer(r"^### (.+?)\s*\n(.*?)(?=^### |\Z)", body or "", re.M | re.S):
        if (value := m[2].strip()) and value != EMPTY:
            out[m[1].strip()] = value
    return out


def numbers(text: str | None) -> list[int]:
    """Issue numbers as people write them: `#12`, `12`, or a link to the issue."""
    return sorted({int(n) for n in re.findall(r"(?:#|/issues/|\b)(\d+)\b", text or "")})


def item(issue: dict) -> dict | None:
    """A question or claim from an issue, or None for any other issue or a pull request. A question's text
    is its `Question` field and a claim's is its title; earlier forms used `Claim` and `Part of`."""
    if "pull_request" in issue:
        return None
    labels = sorted(l["name"] if isinstance(l, dict) else l for l in issue.get("labels", []))
    f = fields(issue.get("body"))
    base = {"number": issue["number"], "url": issue.get("html_url", ""),
            "author": (issue.get("user") or {}).get("login", ""), "created": issue.get("created_at", ""),
            "comments": issue.get("comments", 0), "labels": labels}
    if "question" in labels:
        return {"type": "question", "text": f.get("Question", issue["title"]), "parents": numbers(f.get("Subquestion of") or f.get("Part of")),
                "status": "answered" if issue.get("state") == "closed" else "open", **base}
    if "claim" in labels:
        return {"type": "claim", "text": f.get("Claim", issue["title"]), "answers": numbers(f.get("Answers")),
                "evidence": f.get("Evidence", ""), **base}
    return None


def entry(repo: str, agenda: dict, issues: list[dict], **extra) -> dict:
    items = [i for i in map(item, issues) if i]
    questions = sorted((i for i in items if i["type"] == "question"), key=lambda i: i["number"])
    claims = sorted((i for i in items if i["type"] == "claim"), key=lambda i: i["number"])
    summary = {"questions": len(questions), "answered": sum(q["status"] == "answered" for q in questions),
               "claims": len(claims),
               "contributors": len({i["author"] for i in items if i["author"]})}
    return {"repo": repo, "agenda": agenda, "questions": questions, "claims": claims, "summary": summary, **extra}


def issues_of(full: str, token: str | None, get) -> list[dict]:
    out = []
    for page in range(1, PAGES + 1):
        batch = json.loads(get(f"https://api.github.com/repos/{full}/issues?state=all&per_page=100&page={page}", token))
        out += batch
        if len(batch) < 100:
            break
    return out


def from_github(topic: str = TOPIC, token: str | None = None, get=fetch) -> tuple[list[dict], list[str]]:
    q = urllib.parse.quote(f"topic:{topic}")
    found = json.loads(get(f"https://api.github.com/search/repositories?q={q}&per_page=100", token))
    out, skipped = [], []
    for r in found.get("items", []):
        full, branch = r["full_name"], r["default_branch"]
        try:
            agenda = json.loads(get(f"https://raw.githubusercontent.com/{full}/{branch}/agenda.json"))
            if bad := agendas.problems(agenda):
                raise ValueError("; ".join(bad))
            out.append(entry(full, agenda, issues_of(full, token, get), url=r["html_url"],
                             stars=r["stargazers_count"], pushed=r["pushed_at"]))
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as e:
            skipped.append(f"{full}: {e}")
    return out, skipped


def from_local(dirs: list[Path]) -> tuple[list[dict], list[str]]:
    entries, skipped = [], []
    for d in dirs:
        try:
            agenda = agendas.load(d / "agenda.json")
            issues = json.loads((d / "issues.json").read_text()) if (d / "issues.json").exists() else []
            entries.append(entry(f"local/{d.name}", agenda, issues))
        except (OSError, ValueError, KeyError, TypeError) as e:
            skipped.append(f"{d}: {e}")
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
    if argv[0] == "github":
        entries, skipped = from_github(argv[2] if len(argv) > 2 else TOPIC, os.environ.get("GITHUB_TOKEN"))
    else:
        entries, skipped = from_local([Path(d) for d in argv[2:]])
    write(out, entries)
    for s in skipped:
        print(f"skipped {s}", file=sys.stderr)
    print(f"indexed {len(entries)} agenda(s) in {out / 'agendas.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
