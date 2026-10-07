"""Turn an issue opened through an agenda's issue forms into a batch for `ev apply`.

    python3 contrib/github_issue.py "$GITHUB_EVENT_PATH" | ev apply -

This is how a person without an agent adds to an agenda: the website or GitHub shows a form, the
form opens an issue, and the agenda's workflow records what the issue says and commits it. The
issue's label says what it is: `question` or `claim`. GitHub renders a form as Markdown, one
`### Label` heading per field and `_No response_` for a field left empty; the labels below are
those of the forms in `observatory/template/.github/ISSUE_TEMPLATE`.

    question   Question (required), Part of (question ids, one per line)
    claim      Claim (required), Kind, Answers (question ids), Builds on (claim ids), Value, Evidence

The issue's time of creation becomes the object's, so that the workflow running twice on one issue
records nothing new. The claim keeps the issue's address as a note, where the discussion of it is.
Who is recorded as author is the workflow's business (EV_AGENT and EV_LAB), not this script's.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EMPTY = "_No response_"


def fields(body: str) -> dict[str, str]:
    """The answers of an issue form by label; an empty answer is left out."""
    out = {}
    for m in re.finditer(r"^### (.+?)\s*\n(.*?)(?=^### |\Z)", body or "", re.M | re.S):
        if (value := m[2].strip()) and value != EMPTY:
            out[m[1].strip()] = value
    return out


def ids(text: str | None) -> list[str]:
    """Ids written one per line or separated by commas or spaces, as people paste them."""
    return re.findall(r"[0-9a-f]{6,64}", (text or "").lower())


def lines(issue: dict) -> list[dict]:
    labels = {l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])}
    f = fields(issue.get("body", ""))
    base = {"ref": f"issue-{issue['number']}", "created": issue["created_at"]}
    if "question" in labels:
        if "Question" not in f:
            raise ValueError("the form has no Question")
        return [{"ask": f["Question"], **base, **({"parents": ids(f["Part of"])} if "Part of" in f else {})}]
    if "claim" in labels:
        if "Claim" not in f:
            raise ValueError("the form has no Claim")
        line = {"claim": f["Claim"], **base, "kind": f.get("Kind", "result"),
                "notes": ([f["Evidence"]] if "Evidence" in f else []) + [f"posted as {issue['html_url']}"]}
        for key, label in (("answers", "Answers"), ("depends_on", "Builds on")):
            if label in f:
                line[key] = ids(f[label])
        if "Value" in f:
            line["value"] = f["Value"]
        return [line]
    return []


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 contrib/github_issue.py EVENT.json | ev apply -")
    event = json.loads(Path(sys.argv[1]).read_text())
    try:
        for line in lines(event.get("issue", event)):
            print(json.dumps(line, ensure_ascii=False))
    except ValueError as e:
        sys.exit(f"github_issue: {e}")
