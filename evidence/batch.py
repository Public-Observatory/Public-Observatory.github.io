"""`ev apply`: a harness hands over a whole run as lines of JSON, recorded all at once or not at all.

Each line is one JSON object naming exactly one of `ask`, `claim` or `review`:

    {"ask": "How many primes are below 1000?", "ref": "q1", "parents": ["q0"]}
    {"claim": "There are 168 primes below 1000.", "ref": "c1", "answers": ["q1"], "value": 168,
     "files": ["primes.py"], "cmd": "python3 primes.py 1000 168", "depends_on": ["c0", "3baae1d9"]}
    {"claim": "Trial division is too slow beyond 10^7.", "kind": "negative", "notes": ["timed out"]}
    {"review": "c1", "verdict": "reproduced", "method": "re-ran on a second machine"}

Fields, with the type they hold (a list may be given as a single string):

    every line   ref (text), created (ISO 8601 time with a zone)
    ask          parents (questions)
    claim        kind, answers (questions), depends_on (claims), refutes (claims), files, cmd, setup,
                 notes, value
    review       verdict, method (required), note, superseded_by (a claim), counter (a claim)

A reference is a `ref` given on an earlier line, which takes precedence, or else the id of an object
on record, or a unique prefix of it of at least six hexadecimal digits; the short prefixes the
command line accepts would let a mistyped ref name some unrelated object. Files are read relative
to the directory of the batch file (to the working directory for standard input). A value is an
integer, true or false, a decimal number (kept with the digits written), a string as `ev claim
--value` reads it, or a value object as stored. Unknown fields are refused, so that a misspelt
field is not silently dropped.

The batch is atomic: every line is checked and recorded with all writes held back, and nothing is
written unless every line succeeds; the error names the line. An object's id is a function of its
content, its author and its time of creation. A line that gives `created` therefore yields the
same id whenever and wherever the same author applies it. A line without `created` is stamped with
one time shared by the whole batch, and if the same author already recorded an object differing
from it only in that time, the line resolves to the earlier object instead of recording a twin. So
re-applying a batch records nothing new in any store that holds the first application, but two
labs applying a batch without times independently obtain different ids; a harness that wants ids
to agree everywhere gives `created`.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from .errors import EvidenceError
from .store import SAFE_INT, Store, now, parse_value

TYPES = ("ask", "claim", "review")
FIELDS = {"ask": {"parents"},
          "claim": {"kind", "answers", "depends_on", "refutes", "files", "cmd", "setup", "notes", "value"},
          "review": {"verdict", "method", "note", "superseded_by", "counter"}}
LISTS = ("parents", "answers", "depends_on", "refutes", "files", "setup", "notes")
ID_PREFIX = re.compile(r"[0-9a-f]{6,64}")


def _constant(name: str):
    raise ValueError(f"{name} is not a number")


def _loads(text: str):
    # Decimals keep the digits written, so that 0.930 is recorded as 0.930.
    return json.loads(text, parse_float=Decimal, parse_constant=_constant)


def read(text: str) -> list[tuple[int, object]]:
    """The lines of a JSON Lines batch with their line numbers; blank lines are skipped."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                out.append((n, _loads(line)))
            except (ValueError, RecursionError) as e:
                raise EvidenceError(f"line {n}: not JSON ({e})") from None
    return out


def read_array(text: str) -> list[tuple[int, object]]:
    """A batch given as one JSON array, numbered from 1."""
    try:
        items = _loads(text)
    except (ValueError, RecursionError) as e:
        raise EvidenceError(f"not JSON ({e})") from None
    if not isinstance(items, list):
        raise EvidenceError("the lines must be a JSON array")
    return list(enumerate(items, 1))


def value(v) -> dict | str:
    if isinstance(v, bool):
        return {"exact": v}
    if isinstance(v, int):
        return {"exact": v} if abs(v) < SAFE_INT else {"quantity": str(v)}
    if isinstance(v, Decimal):
        return parse_value(str(v))
    if isinstance(v, (str, dict)):
        return v  # read or checked by Store.claim
    raise EvidenceError("value must be a number, true, false, text or a value object")


def apply(store: Store, lines: list[tuple[int, object]], base: Path = Path("."),
          dry_run: bool = False) -> list[dict]:
    """Record a batch through `Store.ask`, `claim` and `review`, atomically. Returns, per line,
    its number, type, id, ref (if any) and whether the object is new to the store."""
    at = now()
    known = set(store.ids())
    defined = {o["ref"]: n for n, o in lines if isinstance(o, dict) and isinstance(o.get("ref"), str)}
    refs: dict[str, tuple[str, str, int]] = {}  # ref: (id, type, line)
    out = []

    def resolve(r, type_: str) -> str:
        if not isinstance(r, str) or not r:
            raise EvidenceError(f"a reference must be non-empty text, not {r!r}")
        if r in refs:
            h, t, m = refs[r]
            if t != type_:
                raise EvidenceError(f"{r!r} is the {t} on line {m}, not a {type_}")
            return h
        if r in defined:
            raise EvidenceError(f"{r!r} is defined only on line {defined[r]}; refer to earlier lines only")
        if not ID_PREFIX.fullmatch(r):
            raise EvidenceError(f"unknown reference {r!r}: neither a ref on an earlier line nor an id "
                                "(at least six hexadecimal digits)")
        return store.resolve(r, type_)

    def record(n: int, obj) -> None:
        if not isinstance(obj, dict):
            raise EvidenceError("not a JSON object")
        types = [t for t in TYPES if t in obj]
        if len(types) != 1:
            raise EvidenceError(f"needs exactly one of {', '.join(TYPES)}")
        t = types[0]
        if extra := set(obj) - FIELDS[t] - {t, "ref", "created"}:
            raise EvidenceError(f"unknown field(s) for {t}: {', '.join(sorted(extra))}")
        a = dict(obj)
        for f in LISTS:
            if isinstance(a.get(f), str):
                a[f] = [a[f]]
            if not (isinstance(a.get(f, []), list) and all(isinstance(x, str) for x in a.get(f, []))):
                raise EvidenceError(f"{f} must be text or a list of texts")
        for f in (t, "ref", "created", "kind", "cmd", "verdict", "method", "note", "superseded_by", "counter"):
            if f in a and not isinstance(a[f], str):
                raise EvidenceError(f"{f} must be text")
        if t != "review" and not a[t].strip():
            raise EvidenceError(f"{t} must not be empty")
        if (r := a.get("ref")) is not None and (not r or r in refs):
            raise EvidenceError(f"ref {r!r} is " + ("empty" if not r else f"already used on line {refs[r][2]}"))
        # Without a time of its own, a line takes the batch's and resolves to its twin if one exists.
        when, reuse = a.get("created", at), "created" not in a
        if t == "ask":
            kind = "question"
            h = store.ask(a["ask"], parents=[resolve(p, "question") for p in a.get("parents", [])],
                          created=when, reuse=reuse)
        elif t == "claim":
            kind = "claim"
            files = [base / f for f in a.get("files", [])]
            for f in files:
                if not f.is_file():
                    raise EvidenceError(f"no such file: {f}")
            h = store.claim(a["claim"], kind=a.get("kind", "result"), files=files, cmd=a.get("cmd"),
                            notes=a.get("notes", []), setup=a.get("setup", []),
                            depends_on=[resolve(d, "claim") for d in a.get("depends_on", [])],
                            answers=[resolve(q, "question") for q in a.get("answers", [])],
                            refutes=[resolve(x, "claim") for x in a.get("refutes", [])],
                            value=value(a["value"]) if "value" in a else None, created=when, reuse=reuse)
        else:
            kind = "review"
            for f in ("verdict", "method"):
                if not a.get(f, "").strip():
                    raise EvidenceError(f"a review needs {f}")
            if ("superseded_by" in a) != (a["verdict"] == "superseded"):
                raise EvidenceError("superseded_by goes with the verdict superseded, and only with it")
            by = a.get("superseded_by")
            h = store.review(resolve(a["review"], "claim"), a["verdict"], a["method"], note=a.get("note", ""),
                             superseded_by=resolve(by, "claim") if by is not None else None,
                             counter=resolve(a["counter"], "claim") if "counter" in a else None,
                             created=when, reuse=reuse)
        if r is not None:
            refs[r] = (h, kind, n)
        out.append({"line": n, "type": kind, "id": h, **({"ref": r} if r is not None else {}),
                    "new": h not in known})
        known.add(h)

    with store.staged(commit=not dry_run):
        for n, obj in lines:
            try:
                record(n, obj)
            except (EvidenceError, OSError) as e:
                raise EvidenceError(f"line {n}: {e}") from None
    return out
