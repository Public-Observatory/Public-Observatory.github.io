"""An agenda: a repository whose file `agenda.json` says what it is for.

    python3 site/agenda.py check agenda.json    exit 1, with the reasons, if the file is malformed

The file holds

    title        a name, a few words
    kind         `open-agenda` (anyone may add subquestions), `closed-agenda` (the maintainers set the
                 questions; anyone may answer them) or `problem` (one question)
    question     the root question, the one every other question in the agenda helps to settle
    created      when the agenda was posed, as an ISO 8601 time with a zone
    summary      a paragraph for the index: why the question matters and what would count as progress
    maintainers  GitHub logins of those who merge contributions and label issues
    tags         optional, a list of words

The kind is a matter of the repository's governance: a closed agenda is closed because its
maintainers accept only answers.
"""

from __future__ import annotations

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


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "check":
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        load(argv[1])
    except (OSError, ValueError) as e:
        print(f"agenda: {argv[1]}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
