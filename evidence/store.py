"""Content-addressed store of scientific questions, claims and reviews.

Layout of a store (``.evidence/``)::

    objects/<id[:2]>/<id[2:]>.json   questions, claims, reviews, withdrawals, signatures (immutable)
    blobs/<hash[:2]>/<hash[2:]>      evidence files (immutable)
    config.json                      author, signing key, trusted keys, remotes (local, never shared)
    cache/                           verified signatures (local, can be deleted)

Every object is identified by the SHA-256 of its canonical JSON, so two stores merge by taking
the union of their files: there are no conflicts. Every status is a function of the set of objects
alone, so stores that hold the same objects agree. The one exception is local policy about whose
reproductions to count as trusted, which lives in config.json.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from . import sandbox, signing
from .errors import EvidenceError

STORE_DIR = ".evidence"
KINDS = ("result", "negative", "conjecture")
# `inconclusive` records an attempt that could not decide the claim (missing tools, a timeout,
# a failed download); it never changes a claim's state.
VERDICTS = ("reproduced", "refuted", "superseded", "inconclusive")
# When reviews disagree, the strongest verdict wins.
PRECEDENCE = ("refuted", "superseded", "reproduced", "proposed")
BROKEN = ("refuted", "superseded")
STATES = (*PRECEDENCE, "at-risk")
QUESTION_STATES = ("contested", "answered", "proposed", "open")
# Exit codes of a shell that could not run the command at all.
CANNOT_RUN = (126, 127)
HEX = re.compile(r"[0-9a-f]{64}")

# A claim may carry the value it gives as its answer, either exact or a measured quantity:
#     {"exact": 168}   {"exact": true}   {"exact": "Riemann"}
#     {"quantity": "9.81", "uncertainty": "0.02", "unit": "m/s^2"}    (uncertainty and unit optional)
# The numbers of a quantity are decimal strings: the digits written are the digits kept, ids do not
# depend on how some language prints floating point, and comparisons are exact. The exponent is
# bounded so that an object from elsewhere cannot make a comparison expensive.
DECIMAL = re.compile(r"-?\d{1,40}(\.\d{1,40})?([eE][-+]?\d{1,3})?")
# Integers beyond 2^53 lose digits in many JSON readers; such a value is given as a quantity.
SAFE_INT = 2 ** 53
MAX_TEXT, MAX_UNIT = 200, 32
NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
PLUS_MINUS = re.compile(r"\s*(?:±|\+/-|\+-)\s*")


# The fields each type of object must have, with their types. References are lists or single ids.
SCHEMA = {
    "question": {"text": str, "author": dict, "parents": list, "created": str},
    "claim": {"kind": str, "statement": str, "author": dict, "evidence": list, "depends_on": list, "created": str},
    "review": {"claim": str, "verdict": str, "by": dict, "method": str, "note": str, "created": str},
    "withdrawal": {"review": str, "by": dict, "note": str, "created": str},
    "signature": {"object": str, "key": str, "signature": str},
}
REFERENCES = {"question": ("parents",), "claim": ("depends_on", "answers"), "review": ("claim", "superseded_by"),
              "withdrawal": ("review",), "signature": ("object",)}


def invalid(obj) -> str | None:
    """Why an object from elsewhere is malformed, or None. Objects are immutable, so one that
    would break every later command must be refused at the door."""
    if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
        return "not an object with a type"
    fields = SCHEMA.get(obj["type"])
    if fields is None:
        return None  # a type from a newer version; kept, and ignored here
    for f, t in fields.items():
        if not isinstance(obj.get(f), t):
            return f"{obj['type']} needs {f} ({t.__name__})"
    for f in REFERENCES[obj["type"]]:
        v = obj.get(f)
        refs = v if isinstance(v, list) else [] if v is None else [v]
        if not all(isinstance(r, str) and HEX.fullmatch(r) for r in refs):
            return f"{obj['type']} has a malformed reference in {f}"
    if obj["type"] == "claim":
        if obj["kind"] not in KINDS:
            return f"unknown kind {obj['kind']!r}"
        if "value" in obj and (why := value_invalid(obj["value"])):
            return f"malformed value: {why}"
        for e in obj["evidence"]:
            if not isinstance(e, dict) or not isinstance(e.get("kind"), str):
                return "malformed evidence"
            if e["kind"] == "file" and not (isinstance(e.get("name"), str) and HEX.fullmatch(str(e.get("blob")))):
                return "malformed evidence file"
            if e["kind"] in ("command", "setup") and not isinstance(e.get("cmd"), str):
                return "malformed evidence command"
    if obj["type"] == "review" and obj["verdict"] not in VERDICTS:
        return f"unknown verdict {obj['verdict']!r}"
    return None


def value_invalid(v) -> str | None:
    """Why a claim's value is malformed, or None."""
    if not isinstance(v, dict):
        return "not an object"
    if set(v) == {"exact"}:
        x = v["exact"]
        if isinstance(x, bool):
            return None
        if isinstance(x, int):
            return None if abs(x) < SAFE_INT else "integer beyond 2^53; give it as a quantity"
        if isinstance(x, str):
            return None if 0 < len(x) <= MAX_TEXT and x == x.strip() else \
                f"text must have 1 to {MAX_TEXT} characters and no surrounding space"
        return "exact value must be an integer, a boolean or text"
    if "quantity" not in v or not set(v) <= {"quantity", "uncertainty", "unit"}:
        return "needs either exact, or quantity with optional uncertainty and unit"
    if not (isinstance(v["quantity"], str) and DECIMAL.fullmatch(v["quantity"])):
        return "quantity must be a decimal string"
    if "uncertainty" in v and not (isinstance(u := v["uncertainty"], str) and DECIMAL.fullmatch(u)
                                   and not u.startswith("-")):
        return "uncertainty must be a non-negative decimal string"
    if "unit" in v and not (isinstance(u := v["unit"], str) and 0 < len(u) <= MAX_UNIT and u == u.strip()):
        return f"unit must have 1 to {MAX_UNIT} characters and no surrounding space"
    return None


def parse_value(text: str) -> dict:
    """Read a value as written on the command line.

    `true` and `false` are booleans and an integer alone is exact. A decimal, or a number followed
    by a unit or an uncertainty (`9.81 m/s^2 ± 0.02`, `9.81 +/- 0.02 m/s^2`), is a quantity.
    Anything else is exact text; text that begins like a number must be quoted (`"2026-10-06"`).
    """
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] == '"':
        v = {"exact": t[1:-1].strip()}
    elif t in ("true", "false"):
        v = {"exact": t == "true"}
    elif not (m := NUMBER.match(t)):
        v = {"exact": t}
    else:
        number, rest = decimal_text(m.group()), t[m.end():]
        if rest and not (rest[0].isspace() or PLUS_MINUS.match(rest)):
            raise EvidenceError(f"cannot read {text!r}: put a space before the unit, or quote text")
        unit, *after = PLUS_MINUS.split(rest.strip(), maxsplit=1)
        v = {"quantity": number}
        if after:
            u = NUMBER.match(after[0])
            if not u or after[0][u.end():u.end() + 1] not in ("", " "):
                raise EvidenceError(f"cannot read the uncertainty in {text!r}")
            v["uncertainty"] = decimal_text(u.group())
            if unit2 := after[0][u.end():].strip():
                if unit:
                    raise EvidenceError(f"two units in {text!r}")
                unit = unit2
        if unit:
            v["unit"] = unit
        if set(v) == {"quantity"} and re.fullmatch(r"-?\d+", number) and abs(int(number)) < SAFE_INT:
            v = {"exact": int(number)}
    if why := value_invalid(v):
        raise EvidenceError(f"cannot read value {text!r}: {why}")
    return v


def decimal_text(number: str) -> str:
    """A number as the schema writes it: `+.5` becomes `0.5`, `5.` becomes `5`, `1E3` becomes `1e3`."""
    sign = "-" if number.startswith("-") else ""
    mantissa, e, exponent = number.lstrip("+-").lower().partition("e")
    whole, _, frac = mantissa.partition(".")
    return sign + (whole or "0") + (f".{frac}" if frac else "") + (f"e{exponent}" if e else "")


def format_value(v: dict) -> str:
    """A value as `parse_value` reads it back."""
    if "exact" in v:
        x = v["exact"]
        return ("true" if x else "false") if isinstance(x, bool) else f'"{x}"' if isinstance(x, str) else str(x)
    return v["quantity"] + (f" ± {v['uncertainty']}" if "uncertainty" in v else "") + \
        (f" {v['unit']}" if "unit" in v else "")


def _numeric(v: dict) -> tuple[Fraction, Fraction, str] | None:
    """Centre, half-width and unit of a numeric value; an exact integer is a unitless point."""
    if "quantity" in v:
        return Fraction(v["quantity"]), Fraction(v.get("uncertainty", "0")), v.get("unit", "")
    x = v["exact"]
    return (Fraction(x), Fraction(0), "") if isinstance(x, int) and not isinstance(x, bool) else None


def disagree(a: dict, b: dict) -> bool:
    """Whether two values contradict each other.

    Exact values disagree when they differ. Quantities disagree when their units are the same
    string and the closed intervals centre ± uncertainty do not meet; an exact integer counts as a
    unitless quantity without uncertainty. Values that cannot be compared (different units, a
    number and text) are not said to disagree, since units are not converted and nothing on the
    record could settle such a dispute.
    """
    x, y = _numeric(a), _numeric(b)
    if x and y:
        return x[2] == y[2] and abs(x[0] - y[0]) > x[1] + y[1]
    if x or y:
        return False
    return type(a["exact"]) is type(b["exact"]) and a["exact"] != b["exact"]


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def identity(author: dict) -> str:
    """Who stands behind a piece of work: their key, else their lab, else the agent."""
    return author.get("key") or author.get("lab") or author.get("agent", "")


def creator(obj: dict) -> dict:
    return obj.get("author") or obj.get("by") or {}


def words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


@dataclass
class Status:
    state: str
    reviews: list[dict]
    at_risk_because: list[str]
    # Identities other than the author's that reproduced the claim, and those among them whose
    # keys this store trusts.
    independent: int = 0
    trusted: int = 0

    @property
    def label(self) -> str:
        return "at-risk" if self.at_risk_because and self.state not in BROKEN else self.state


@dataclass
class QuestionStatus:
    state: str
    answers: list[str] = field(default_factory=list)
    subquestions: list[str] = field(default_factory=list)
    # Pairs of standing answers whose values disagree; the question is contested while any remain.
    conflicts: list[list[str]] = field(default_factory=list)


class Graph:
    """The dependency graph of a set of claims, with ancestors and descendants as bitsets."""

    def __init__(self, claims: dict[str, dict]):
        order, seen = [], set()
        for root in claims:
            stack = [(root, False)]
            while stack:
                h, done = stack.pop()
                if done:
                    order.append(h)
                elif h not in seen:
                    seen.add(h)
                    stack.append((h, True))
                    stack.extend((d, False) for d in claims[h]["depends_on"] if d in claims and d not in seen)
        # Dependencies come before the claims that rest on them.
        self.order = order
        self.bit = {h: 1 << i for i, h in enumerate(order)}
        self.up = {}
        for h in order:
            mask = 0
            for d in claims[h]["depends_on"]:
                if d in claims:
                    mask |= self.bit[d] | self.up[d]
            self.up[h] = mask
        self.down = dict.fromkeys(order, 0)
        for h in reversed(order):
            for d in claims[h]["depends_on"]:
                if d in claims:
                    self.down[d] |= self.bit[h] | self.down[h]

    def members(self, mask: int) -> list[str]:
        out = []
        while mask:
            low = mask & -mask
            out.append(self.order[low.bit_length() - 1])
            mask ^= low
        return out

    def mask(self, hs) -> int:
        m = 0
        for h in hs:
            m |= self.bit.get(h, 0)
        return m


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "objects").is_dir():
            raise EvidenceError(f"not an evidence store: {self.root}")
        self.name = str(self.root)
        self._objects: dict[str, dict] | None = None
        self._graph: Graph | None = None

    # ------------------------------------------------------------------ setup

    @classmethod
    def init(cls, path: Path, author: dict | None = None) -> "Store":
        root = Path(path) / STORE_DIR
        (root / "objects").mkdir(parents=True, exist_ok=True)
        (root / "blobs").mkdir(exist_ok=True)
        # A store may be committed to git to share it; the key and local settings must not be.
        (root / ".gitignore").write_text("key\nconfig.json\ncache/\n*.tmp\n")
        store = cls(root)
        if author or not (root / "config.json").exists():
            store.configure(author=author or {})
        return store

    @classmethod
    def find(cls, start: Path | None = None) -> "Store":
        if env := os.environ.get("EV_DIR"):
            return cls(Path(env))
        here = Path(start or Path.cwd()).resolve()
        for d in (here, *here.parents):
            if (d / STORE_DIR / "objects").is_dir():
                return cls(d / STORE_DIR)
        raise EvidenceError("no .evidence store found (run `ev init`)")

    def config(self) -> dict:
        path = self.root / "config.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def configure(self, **changes) -> dict:
        config = {**self.config(), **changes}
        (self.root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        return config

    def keyfile(self) -> Path | None:
        if not (key := os.environ.get("EV_KEY") or self.config().get("key")):
            return None
        path = Path(key).expanduser()
        return path if path.is_absolute() else self.root / path

    def author(self) -> dict:
        author = dict(self.config().get("author", {}))
        for key in ("agent", "model", "lab"):
            if value := os.environ.get(f"EV_{key.upper()}"):
                author[key] = value
        if "agent" not in author:
            raise EvidenceError("no author: set EV_AGENT or run `ev init --agent NAME`")
        if keyfile := self.keyfile():
            author["key"] = signing.public_key(keyfile)
        return author

    def trust(self) -> dict[str, str]:
        """Public keys this store trusts, with the name each stands for; our own key among them."""
        trust = dict(self.config().get("trust", {}))
        if keyfile := self.keyfile():
            author = self.config().get("author", {})
            trust.setdefault(signing.public_key(keyfile), author.get("lab") or author.get("agent", "self"))
        return trust

    # ---------------------------------------------------------------- objects

    def _path(self, kind: str, h: str) -> Path:
        return self.root / kind / h[:2] / (h[2:] + (".json" if kind == "objects" else ""))

    def put_object(self, obj: dict) -> str:
        data = canonical(obj)
        h = digest(data)
        self._write("objects", h, data)
        if self._objects is not None and h not in self._objects:
            self._objects[h] = json.loads(data)
            self._graph = None
        return h

    def put_blob(self, data: bytes) -> str:
        h = digest(data)
        self._write("blobs", h, data)
        return h

    def _write(self, kind: str, h: str, data: bytes) -> None:
        path = self._path(kind, h)
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            # Write then rename, so a reader never sees half an object.
            tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

    def _record(self, obj: dict) -> str:
        """Store an object authored here, signing it when this store has a key."""
        h = self.put_object(obj)
        if keyfile := self.keyfile():
            sig = self.put_object({"type": "signature", "object": h, "key": creator(obj)["key"],
                                   "signature": signing.sign(keyfile, h.encode())})
            self._remember_verified([sig])
        return h

    def _load(self) -> dict[str, dict]:
        if self._objects is None:
            self._objects = {p.parent.name + p.stem: json.loads(p.read_bytes())
                             for p in (self.root / "objects").glob("*/*.json")}
        return self._objects

    def get(self, h: str) -> dict:
        return self._load()[self.resolve(h)]

    def blob(self, h: str) -> bytes:
        return self._path("blobs", h).read_bytes()

    def ids(self) -> list[str]:
        return list(self._load())

    def resolve(self, prefix: str, type_: str | None = None) -> str:
        if prefix not in self._load():
            matches = [h for h in self.ids() if h.startswith(prefix)]
            if not matches:
                raise EvidenceError(f"unknown id: {prefix}")
            if len(matches) > 1:
                raise EvidenceError(f"ambiguous id: {prefix}")
            prefix = matches[0]
        if type_ and self._load()[prefix]["type"] != type_:
            raise EvidenceError(f"{prefix[:10]} is not a {type_}")
        return prefix

    def objects(self, type_: str) -> dict[str, dict]:
        return {h: obj for h, obj in self._load().items() if obj["type"] == type_}

    def graph(self) -> Graph:
        if self._graph is None:
            self._graph = Graph(self.objects("claim"))
        return self._graph

    # -------------------------------------------------------------- recording

    def ask(self, text: str, parents: list[str] = ()) -> str:
        """Record a question; `parents` are the larger questions it helps to settle."""
        return self._record({
            "type": "question", "text": text, "author": self.author(),
            "parents": sorted({self.resolve(p, "question") for p in parents}), "created": now(),
        })

    def claim(self, statement: str, kind: str = "result", files: list[Path] = (),
              cmd: str | None = None, notes: list[str] = (), depends_on: list[str] = (),
              setup: list[str] = (), answers: list[str] = (), value: dict | str | None = None) -> str:
        if kind not in KINDS:
            raise EvidenceError(f"kind must be one of {KINDS}")
        deps = sorted({self.resolve(d, "claim") for d in depends_on})
        evidence = [{"kind": "file", "name": Path(f).name, "blob": self.put_blob(Path(f).read_bytes())}
                    for f in files]
        # Setup commands prepare the environment; their failure says nothing about the claim.
        evidence += [{"kind": "setup", "cmd": c} for c in setup]
        if cmd:
            evidence.append({"kind": "command", "cmd": cmd})
        evidence += [{"kind": "note", "text": n} for n in notes]
        obj = {"type": "claim", "kind": kind, "statement": statement, "author": self.author(),
               "evidence": evidence, "depends_on": deps, "created": now()}
        if answers:
            obj["answers"] = sorted({self.resolve(q, "question") for q in answers})
        if value is not None:
            value = parse_value(value) if isinstance(value, str) else value
            if why := value_invalid(value):
                raise EvidenceError(f"malformed value: {why}")
            obj["value"] = value
        return self._record(obj)

    def review(self, claim: str, verdict: str, method: str, note: str = "",
               superseded_by: str | None = None, environment: dict | None = None) -> str:
        if verdict not in VERDICTS:
            raise EvidenceError(f"verdict must be one of {VERDICTS}")
        claim = self.resolve(claim, "claim")
        if verdict == "superseded":
            if not superseded_by:
                raise EvidenceError("superseded needs --by CLAIM")
            superseded_by = self.resolve(superseded_by, "claim")
        obj = {"type": "review", "claim": claim, "verdict": verdict, "by": self.author(),
               "method": method, "note": note, "superseded_by": superseded_by, "created": now()}
        if environment:
            obj["environment"] = environment
        return self._record(obj)

    def withdraw(self, review: str, note: str = "") -> str:
        """Take back one of our own reviews. Only the identity that made a review can withdraw it."""
        review = self.resolve(review, "review")
        me = self.author()
        if identity(self.get(review)["by"]) != identity(me):
            raise EvidenceError("only the author of a review can withdraw it")
        return self._record({"type": "withdrawal", "review": review, "by": me, "note": note,
                             "created": now()})

    # ----------------------------------------------------------- verification

    def sandbox_mode(self, requested: str | None = None) -> str:
        return sandbox.resolve(requested or os.environ.get("EV_SANDBOX") or self.config().get("sandbox", "auto"))

    def verify(self, claim: str, timeout: int = 600, sandbox_mode: str | None = None,
               unsafe: bool = False) -> tuple[str, str]:
        """Re-run a claim's command on its evidence files in a clean directory.

        Only a command that runs and fails refutes the claim. A failed setup step, a timeout, a
        missing program or a refusal by the sandbox is recorded as `inconclusive`, so a broken
        environment cannot topple a claim and everything built on it.
        """
        claim = self.resolve(claim, "claim")
        obj = self.get(claim)
        setup = [e["cmd"] for e in obj["evidence"] if e["kind"] == "setup"]
        cmds = [e["cmd"] for e in obj["evidence"] if e["kind"] == "command"]
        if not cmds:
            raise EvidenceError("claim has no command to re-run")
        mode = self.sandbox_mode(sandbox_mode)
        if mode == "none" and not unsafe and identity(obj["author"]) != identity(self.author()):
            raise EvidenceError("refusing to run another lab's command without a sandbox "
                                "(set EV_SANDBOX=docker, or pass --unsafe if you trust it)")
        env = {**environment(), "sandbox": mode}
        with tempfile.TemporaryDirectory() as work:
            self.checkout(claim, Path(work))
            for c in setup:
                code, output = sandbox.run(c, work, timeout, mode, network=True)
                if code != 0:
                    return self.review(claim, "inconclusive", f"setup `{c}` failed (exit {code})",
                                       note=output[-2000:], environment=env), "inconclusive"
            code, output = sandbox.run(cmds[0], work, timeout, mode)
        if code == 0:
            verdict = "reproduced"
        elif code is None or code in CANNOT_RUN or sandbox.denied(mode, output):
            verdict = "inconclusive"
        else:
            verdict = "refuted"
        env["output_sha256"] = digest(output.encode())
        method = f"re-ran `{cmds[0]}` (exit {code})"
        return self.review(claim, verdict, method, note=output[-2000:], environment=env), verdict

    def checkout(self, claim: str, directory: Path) -> list[Path]:
        """Write a claim's evidence files into a directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        out = []
        for e in self.get(claim)["evidence"]:
            if e["kind"] == "file":
                path = directory / Path(e["name"]).name
                path.write_bytes(self.blob(e["blob"]))
                out.append(path)
        return out

    # ----------------------------------------------------------------- status

    def withdrawn(self) -> set[str]:
        reviews = self.objects("review")
        return {w["review"] for w in self.objects("withdrawal").values()
                if w["review"] in reviews and identity(reviews[w["review"]]["by"]) == identity(w["by"])}

    def statuses(self) -> dict[str, Status]:
        claims = self.objects("claim")
        withdrawn = self.withdrawn()
        by_claim: dict[str, list[dict]] = {h: [] for h in claims}
        for h, r in sorted(self.objects("review").items(), key=lambda kv: (kv[1]["created"], kv[0])):
            if h not in withdrawn:
                by_claim.setdefault(r["claim"], []).append({"id": h, **r})

        own = {}
        for h, rs in by_claim.items():
            verdicts = {r["verdict"] for r in rs} | {"proposed"}
            own[h] = next(v for v in PRECEDENCE if v in verdicts)

        trust = self.trust()

        def name(author: dict) -> str:
            return trust.get(author.get("key", ""), identity(author))

        g = self.graph()
        broken = g.mask(h for h in claims if own[h] in BROKEN)
        out = {}
        for h, c in claims.items():
            by = {name(r["by"]) for r in by_claim[h] if r["verdict"] == "reproduced"} - {name(c["author"])}
            out[h] = Status(own[h], by_claim[h], g.members(g.up[h] & broken), len(by),
                            len(by & set(trust.values())))
        return out

    def question_statuses(self, statuses: dict[str, Status] | None = None) -> dict[str, QuestionStatus]:
        """A question is contested when two of its answers that are neither refuted nor superseded
        carry values that disagree. Otherwise it is answered when a standing reproduced claim
        answers it, proposed when a standing claim does, and open otherwise."""
        statuses = statuses if statuses is not None else self.statuses()
        questions = self.objects("question")
        claims = self.objects("claim")
        out = {h: QuestionStatus("open") for h in questions}
        for h, q in sorted(questions.items()):
            for p in q["parents"]:
                if p in out:
                    out[p].subquestions.append(h)
        for h, c in sorted(claims.items()):
            for q in c.get("answers", []):
                if q in out:
                    out[q].answers.append(h)
        for qs in out.values():
            labels = {statuses[a].label for a in qs.answers}
            qs.state = "answered" if "reproduced" in labels else "proposed" if "proposed" in labels else "open"
            valued = [a for a in qs.answers if "value" in claims[a] and statuses[a].state not in BROKEN]
            qs.conflicts = [[a, b] for i, a in enumerate(valued) for b in valued[i + 1:]
                            if disagree(claims[a]["value"], claims[b]["value"])]
            if qs.conflicts:
                qs.state = "contested"
        return out

    def upstream(self, h: str) -> list[str]:
        g = self.graph()
        return g.members(g.up[h])

    def downstream(self, h: str) -> list[str]:
        g = self.graph()
        return g.members(g.down[h])

    # ------------------------------------------------------------- navigation

    def search(self, query: str, limit: int = 10) -> list[tuple[float, str]]:
        """Claims and questions ranked by shared rare words with the query, dead ends included."""
        docs = {h: words(" ".join([c["statement"]] + [e.get("text", "") for e in c["evidence"]]))
                for h, c in self.objects("claim").items()}
        docs.update({h: words(q["text"]) for h, q in self.objects("question").items()})
        df: dict[str, int] = {}
        for d in docs.values():
            for w in d:
                df[w] = df.get(w, 0) + 1
        q = words(query)
        scored = [(sum(math.log(1 + len(docs) / df[w]) for w in q & d), h) for h, d in docs.items()]
        return sorted((s for s in scored if s[0] > 0), reverse=True)[:limit]

    def todo(self, me: dict | None = None) -> list[dict]:
        """Work that would most strengthen the record, highest impact first.

        The impact of work on a claim is the number of claims it would affect: the claim itself and
        everything built on it. The impact of answering a question is the number of questions it
        would help settle. Resolving a contested question counts both: the questions it settles and
        the claims in dispute with everything built on them; at equal impact it comes first, since
        a contradiction on the record misleads everyone who reads it. Claims by `me` are not offered
        for reproduction, since that would not be independent; instead each of our runnable claims
        is offered once for a self-check.
        """
        claims = self.objects("claim")
        statuses = self.statuses()
        g = self.graph()
        mine = identity(me) if me else None
        items = []

        def add(action, h, text, impact, why):
            items.append({"action": action, "id": h, "statement": text, "impact": impact, "why": why})

        for h, c in claims.items():
            s = statuses[h]
            impact = 1 + g.down[h].bit_count()
            own = mine is not None and identity(c["author"]) == mine
            runnable = any(e["kind"] == "command" for e in c["evidence"])
            if s.label == "at-risk":
                add("recheck", h, c["statement"], impact,
                    f"rests on {len(s.at_risk_because)} claim(s) no longer standing")
            elif s.state in BROKEN:
                continue
            elif own:
                if runnable and not s.reviews:
                    add("selfcheck", h, c["statement"], impact,
                        "never re-run from a clean directory; run `ev verify` to catch missing files")
            elif runnable and s.independent == 0:
                add("reproduce", h, c["statement"], impact, "no independent reproduction; run `ev verify`")
            elif c["kind"] == "conjecture" and s.state == "proposed":
                add("prove", h, c["statement"], impact, "open conjecture")
            elif s.state == "proposed" and not s.reviews:
                add("review", h, c["statement"], impact, "no reviews and no command to re-run")

        questions = self.objects("question")
        qstatus = self.question_statuses(statuses)

        def ancestors(h: str) -> set[str]:
            seen, stack = set(), list(questions[h]["parents"])
            while stack:
                p = stack.pop()
                if p in questions and p not in seen:
                    seen.add(p)
                    stack.extend(questions[p]["parents"])
            return seen

        for h, q in questions.items():
            qs = qstatus[h]
            if qs.state == "contested":
                # Settling the dispute decides the question and its ancestors, and either fells or
                # vindicates each disputed claim and everything built on it.
                involved = sorted({c for pair in qs.conflicts for c in pair})
                affected = g.mask(involved)
                for c in involved:
                    affected |= g.down[c]
                pairs = "; ".join(f"{format_value(claims[a]['value'])} ({a[:10]}) against "
                                  f"{format_value(claims[b]['value'])} ({b[:10]})" for a, b in qs.conflicts)
                add("resolve", h, q["text"], 1 + len(ancestors(h)) + affected.bit_count(),
                    f"standing answers disagree: {pairs}; re-run them and refute the wrong one")
                items[-1]["conflicts"] = qs.conflicts
                continue
            if qs.state != "open" or any(qstatus[s].state == "open" for s in qs.subquestions):
                continue  # answered, or better approached through an open subquestion
            add("answer", h, q["text"], 1 + len(ancestors(h)), "open question; claim an answer with --answers")

        priority = {"resolve": 0, "recheck": 1, "selfcheck": 2, "reproduce": 3, "review": 4, "prove": 5, "answer": 6}
        return sorted(items, key=lambda i: (-i["impact"], priority[i["action"]], i["id"]))

    # ---------------------------------------------------------------- sharing

    def listing(self) -> dict[str, list[str]]:
        return {kind: sorted(p.parent.name + p.name.removesuffix(".json")
                             for p in (self.root / kind).glob("*/*") if not p.name.endswith(".tmp"))
                for kind in ("objects", "blobs")}

    def read(self, kind: str, h: str) -> bytes:
        return self._path(kind, h).read_bytes()

    def pull(self, source) -> int:
        """Copy every object and blob we lack from a source, checking hashes and signatures.

        Nothing is written unless everything checks: a corrupt or forged object aborts the pull.
        """
        listing = source.listing()
        have = set(self._load())
        incoming = {}
        for h in listing["objects"]:
            if h in have or not HEX.fullmatch(h):
                continue
            data = source.read("objects", h)
            if digest(data) != h:
                raise EvidenceError(f"corrupt object in {source.name}: {h}")
            try:
                obj = json.loads(data)
            except ValueError:
                obj = None
            if why := invalid(obj):
                raise EvidenceError(f"malformed object in {source.name}: {h} ({why})")
            incoming[h] = obj
        if forged := self.unsigned(incoming):
            raise EvidenceError(f"{len(forged)} object(s) in {source.name} lack a valid signature by "
                                f"the key they name, e.g. {forged[0]}")
        blobs = {}
        for h in listing["blobs"]:
            if HEX.fullmatch(h) and not self._path("blobs", h).exists():
                data = source.read("blobs", h)
                if digest(data) != h:
                    raise EvidenceError(f"corrupt blob in {source.name}: {h}")
                blobs[h] = data
        for h, data in blobs.items():
            self._write("blobs", h, data)
        for h, obj in incoming.items():
            self._write("objects", h, canonical(obj))
        self._objects = self._graph = None
        return len(incoming) + len(blobs)

    def push(self, target: "Store") -> int:
        return target.pull(self)

    # ------------------------------------------------------------- signatures

    def _verified_path(self) -> Path:
        return self.root / "cache" / "verified"

    def _verified(self) -> set[str]:
        path = self._verified_path()
        return set(path.read_text().split()) if path.exists() else set()

    def _remember_verified(self, sigs) -> None:
        path = self._verified_path()
        path.parent.mkdir(exist_ok=True)
        with path.open("a") as f:
            f.writelines(s + "\n" for s in sigs)

    def unsigned(self, objects: dict[str, dict], recheck: bool = False) -> list[str]:
        """Ids among `objects` whose creator names a key without a valid signature by it.

        Signatures are looked for among `objects` and in this store. Signatures already in the
        store were checked when they arrived, unless `recheck`. A signature that does not verify is
        itself reported.
        """
        incoming = {h: o for h, o in objects.items() if o["type"] == "signature"}
        sigs = {**self.objects("signature"), **incoming}
        known = self._verified()
        bad, good = [], []
        for h, s in (sigs if recheck else incoming).items():
            if h in known and not recheck:
                continue
            (good if signing.verify(s["key"], s["object"].encode(), s["signature"]) else bad).append(h)
        self._remember_verified(h for h in good if h not in known)
        valid = {(s["object"], s["key"]) for h, s in sigs.items() if h not in bad}
        missing = [h for h, o in objects.items()
                   if o["type"] != "signature" and (key := creator(o).get("key")) and (h, key) not in valid]
        return sorted(bad + missing)

    def fsck(self) -> list[str]:
        """Every problem with this store: bad hashes, bad signatures, dangling references."""
        problems = []
        for kind in ("objects", "blobs"):
            for h in self.listing()[kind]:
                if digest(self.read(kind, h)) != h:
                    problems.append(f"corrupt {kind[:-1]} {h}")
        objs = self._load()
        problems += [f"malformed {h} ({why})" for h, o in objs.items() if (why := invalid(o))]
        if any(p.startswith("malformed") for p in problems):
            return problems
        problems += [f"unsigned or forged {h}" for h in self.unsigned(objs, recheck=True)]
        for h, o in objs.items():
            for f in REFERENCES.get(o["type"], ()):
                v = o.get(f)
                for r in v if isinstance(v, list) else [v] if v else []:
                    if r not in objs:
                        problems.append(f"{o['type']} {h[:10]} refers to missing {r[:10]} ({f})")
            for e in o.get("evidence", []):
                if e["kind"] == "file" and not self._path("blobs", e["blob"]).exists():
                    problems.append(f"claim {h[:10]} is missing evidence file {e['name']}")
        return problems


def environment() -> dict:
    return {"platform": platform.platform(), "python": platform.python_version()}
