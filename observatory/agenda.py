"""An agenda: a repository holding a record (`.evidence/`) and a file `agenda.json` that says what it is for.

    python3 observatory/agenda.py check agenda.json    exit 1, with the reasons, if the file is malformed
    python3 observatory/agenda.py seed agenda.json     the root question, as a line for `ev apply`
    python3 observatory/agenda.py owner agenda.json    the name under which the root question is asked
    python3 observatory/agenda.py page agenda.json SITE OWNER/REPO
                                                       a page sending readers of the agenda's own
                                                       site to the Observatory at SITE

The file holds

    title        a name, a few words
    kind         `open-agenda` (anyone may add subquestions), `closed-agenda` (the maintainers set the
                 questions; anyone may answer them) or `problem` (one question)
    question     the root question, the one every other question on the record helps to settle
    created      when the agenda was posed, as an ISO 8601 time with a zone
    summary      a paragraph for the index: why the question matters and what would count as progress
    maintainers  GitHub logins of those who merge contributions; the first asks the root question
    tags         optional, a list of words

The root question is asked as the first maintainer at the time `created`, so that asking it again,
from any workflow run, yields the same id. The kind is a matter of the repository's governance, not
of the record: the record accepts any question, and a closed agenda is closed because its
maintainers merge only answers.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

KINDS = ("open-agenda", "closed-agenda", "problem")
REQUIRED = {"title": str, "kind": str, "question": str, "created": str, "summary": str, "maintainers": list}
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")


def problems(agenda) -> list[str]:
    if not isinstance(agenda, dict):
        return ["agenda.json must hold a JSON object"]
    out = [f"{k} is missing" for k in REQUIRED if k not in agenda]
    out += [f"{k} must be a {t.__name__}" for k, t in REQUIRED.items() if k in agenda and not isinstance(agenda[k], t)]
    if out:
        return out
    if agenda["kind"] not in KINDS:
        out.append(f"kind must be one of {', '.join(KINDS)}")
    if not all(isinstance(m, str) and LOGIN.fullmatch(m) for m in agenda["maintainers"]) or not agenda["maintainers"]:
        out.append("maintainers must be a non-empty list of GitHub logins")
    try:
        if datetime.fromisoformat(agenda["created"].replace("Z", "+00:00")).tzinfo is None:
            out.append("created needs a time zone, e.g. 2026-10-07T00:00:00Z")
    except ValueError:
        out.append("created must be an ISO 8601 time")
    if not all(isinstance(t, str) for t in agenda.get("tags", [])):
        out.append("tags must be a list of words")
    for k in ("title", "question", "summary"):
        if not agenda[k].strip():
            out.append(f"{k} is empty")
    return out


def load(path: str | Path) -> dict:
    agenda = json.loads(Path(path).read_text())
    if bad := problems(agenda):
        raise ValueError("; ".join(bad))
    return agenda


def seed(agenda: dict) -> dict:
    return {"ask": agenda["question"], "ref": "root", "created": agenda["created"]}


def page(agenda: dict, site: str, repo: str) -> str:
    """The agenda's own GitHub Pages site serves the record's files; people read it on the Observatory."""
    target = html.escape(f"{site.rstrip('/')}/agenda.html?repo={repo}", quote=True)
    title = html.escape(agenda["title"])
    return (f'<!doctype html><meta charset="utf-8"><title>{title}</title>'
            f'<meta http-equiv="refresh" content="0; url={target}">'
            f'<p><a href="{target}">{title}</a> on the Observatory. The record itself is in '
            f'<a href="snapshot.json">snapshot.json</a> and <a href="store/index.json">store/</a>, '
            f'from which <code>ev pull</code> reads.</p>\n')


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("check", "seed", "owner", "page"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        agenda = load(argv[1])
    except (OSError, ValueError) as e:
        print(f"agenda: {argv[1]}: {e}", file=sys.stderr)
        return 1
    if argv[0] == "seed":
        print(json.dumps(seed(agenda), ensure_ascii=False))
    elif argv[0] == "owner":
        print(agenda["maintainers"][0])
    elif argv[0] == "page":
        if len(argv) != 4:
            print("usage: agenda.py page agenda.json SITE OWNER/REPO", file=sys.stderr)
            return 2
        print(page(agenda, argv[2], argv[3]), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
