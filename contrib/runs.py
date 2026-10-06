"""Turn a directory of experiment runs into a batch for `ev apply`: a worked example of an adapter.

    python3 contrib/runs.py RUNS | ev apply -

Each subdirectory of RUNS holding a `result.json` is one run:

    {"hypothesis": "A cosine schedule lowers validation loss below 2.4.", "metric": "val_loss",
     "value": 2.51, "success": false, "command": "python3 train.py --schedule cosine",
     "created": "2026-10-01T09:00:00Z"}

A successful run becomes a claim of its hypothesis; a failed one becomes a negative claim, so that
`ev search` finds the dead end before anyone repeats it. The metric and its value are stated, and
the value is kept as the claim's value. The run's files are attached and the command is kept as a
note, not as the claim's `cmd`: it ran the experiment, and nothing says that it exits 0 exactly when
the hypothesis holds. The run directory's name is the line's ref. With `created`, two labs applying
the same runs as the same author obtain the same ids; without it, re-applying in one store still
records nothing new. Only `hypothesis` and `success` are required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def lines(runs: Path) -> list[dict]:
    out = []
    for run in sorted(p for p in Path(runs).iterdir() if (p / "result.json").is_file()):
        r = json.loads((run / "result.json").read_text())
        measured = f" ({r['metric']} = {r['value']})" if "metric" in r and "value" in r else ""
        line = {"claim": (r["hypothesis"] if r["success"] else f"Did not work: {r['hypothesis']}") + measured,
                "ref": run.name, "kind": "result" if r["success"] else "negative",
                "files": [str(f.resolve()) for f in sorted(run.iterdir()) if f.is_file() and not f.name.startswith(".")]}
        if "command" in r:
            line["notes"] = [f"ran `{r['command']}`"]
        if isinstance(r.get("value"), (int, float)) and not isinstance(r["value"], bool):
            line["value"] = r["value"]
        if "created" in r:
            line["created"] = r["created"]
        out.append(line)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 contrib/runs.py RUNS_DIR | ev apply -")
    for line in lines(Path(sys.argv[1])):
        print(json.dumps(line, ensure_ascii=False))
