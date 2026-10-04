"""Command-line interface: `ev <command>`. Every read command accepts --json for agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .palomar import PALOMAR_ID, Palomar
from .store import KINDS, STORE_DIR, VERDICTS, EvidenceError, Store

MARK = {"proposed": "?", "reproduced": "✓", "refuted": "✗", "superseded": "→"}


def short(h: str) -> str:
    return h[:10]


def who(author: dict) -> str:
    return "/".join(author[k] for k in ("lab", "model", "agent") if author.get(k))


def label(status) -> str:
    return "at-risk" if status.at_risk_because and status.state not in ("refuted", "superseded") else status.state


def emit(args, data, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if args.json else text)


# ---------------------------------------------------------------- commands

def cmd_init(args) -> None:
    author = {k: v for k in ("agent", "model", "lab") if (v := getattr(args, k))}
    store = Store.init(Path(args.path), author or None)
    print(f"initialised {store.root}")


def cmd_claim(args) -> None:
    store = Store.find()
    # A Palomar id as a dependency imports that entry first.
    deps = [Palomar(store).import_entry(d) if PALOMAR_ID.fullmatch(d.upper()) else d for d in args.dep]
    h = store.claim(args.statement, kind=args.kind, files=args.file, cmd=args.cmd,
                    notes=args.note, depends_on=deps)
    print(h)


def cmd_review(args) -> None:
    store = Store.find()
    print(store.review(args.id, args.verdict, args.method, note=args.note, superseded_by=args.by))


def cmd_verify(args) -> None:
    store = Store.find()
    h, verdict = store.verify(args.id, timeout=args.timeout)
    print(f"{MARK[verdict]} {verdict}  (review {short(h)})")
    if verdict != "reproduced":
        sys.exit(1)


def cmd_log(args) -> None:
    store = Store.find()
    claims = store.objects("claim")
    statuses = store.statuses()
    rows = []
    for h, c in sorted(claims.items(), key=lambda kv: kv[1]["created"]):
        state = label(statuses[h])
        if args.status and state != args.status:
            continue
        rows.append({"id": h, "status": state, "kind": c["kind"], "statement": c["statement"],
                     "author": c["author"], "created": c["created"]})
    lines = [f"{MARK.get(r['status'], '!')} {short(r['id'])}  {r['status']:<10} "
             f"{'[' + r['kind'] + '] ' if r['kind'] != 'result' else ''}{r['statement']}  "
             f"— {who(r['author'])}" for r in rows]
    emit(args, rows, "\n".join(lines) or "no claims")


def cmd_show(args) -> None:
    store = Store.find()
    h = store.resolve(args.id)
    obj = store.get(h)
    if obj["type"] != "claim":
        emit(args, obj, json.dumps(obj, indent=2, ensure_ascii=False))
        return
    claims = store.objects("claim")
    status = store.statuses()[h]
    down = store.downstream(h, claims)
    data = {"id": h, **obj, "status": label(status), "reviews": status.reviews,
            "at_risk_because": status.at_risk_because, "dependents": down}
    out = [f"claim {h}", f"status   {label(status)}", f"kind     {obj['kind']}",
           f"author   {who(obj['author'])}", f"created  {obj['created']}"]
    if src := obj.get("source"):
        out += [f"source   {src['registry']} {src['id']} v{src['version']}  {src['url']}",
                f"         {', '.join(src['authors'])}; {src['repository']}@{src['commit'][:10]}"]
    out += ["", f"    {obj['statement']}", ""]
    for e in obj["evidence"]:
        detail = {"file": lambda: f"{e['name']} ({short(e['blob'])})",
                  "command": lambda: f"$ {e['cmd']}", "note": lambda: e["text"],
                  "reference": lambda: f"{e['relationship']}: {e['title'] or e['identifier']}"
                                       + (f" ({e['identifier']})" if e["title"] and e["identifier"] else "")
                  }[e["kind"]]()
        out.append(f"{'reference' if e['kind'] == 'reference' else 'evidence ' + e['kind']:<17} {detail}")
    for d in obj["depends_on"]:
        out.append(f"depends  {short(d)}  {claims[d]['statement'] if d in claims else '(missing)'}")
    for r in status.reviews:
        out.append(f"review   {MARK[r['verdict']]} {r['verdict']} by {who(r['by'])}: {r['method']}"
                   + (f" — {r['note'].splitlines()[-1]}" if r["note"] else ""))
    for d in status.at_risk_because:
        out.append(f"at risk  upstream {short(d)} is no longer standing")
    if down:
        out.append(f"used by  {len(down)} claim(s): {', '.join(short(d) for d in down)}")
    emit(args, data, "\n".join(out))


def cmd_check(args) -> None:
    store = Store.find()
    claims = store.objects("claim")
    risky = {h: s for h, s in store.statuses().items() if label(s) == "at-risk"}
    data = [{"id": h, "statement": claims[h]["statement"], "because": s.at_risk_because}
            for h, s in risky.items()]
    lines = [f"! {short(d['id'])}  {d['statement']}\n    depends on: "
             + ", ".join(short(b) for b in d["because"]) for d in data]
    emit(args, data, "\n".join(lines) or "all claims stand on standing ground")
    if risky:
        sys.exit(1)


def cmd_digest(args) -> None:
    """The few results a human should read: reproduced claims that most other work builds on."""
    store = Store.find()
    claims = store.objects("claim")
    statuses = store.statuses()
    ranked = sorted(((len(store.downstream(h, claims)), len(statuses[h].reviews), h)
                     for h in claims if label(statuses[h]) == "reproduced"), reverse=True)
    data = [{"id": h, "statement": claims[h]["statement"], "dependents": n, "reviews": r}
            for n, r, h in ranked[:args.n]]
    lines = [f"{i}. {d['statement']}\n   {short(d['id'])} · built on by {d['dependents']} · "
             f"{d['reviews']} review(s)" for i, d in enumerate(data, 1)]
    emit(args, data, "\n".join(lines) or "nothing reproduced yet")


def cmd_palomar(args) -> None:
    store = Store.find()
    pal = Palomar(store)
    before = set(store.ids())
    if args.action == "import":
        hs = [pal.import_entry(i, version=args.version, depth=args.depth) for i in args.ids]
    else:
        hs = pal.sync(limit=args.limit, depth=args.depth)
    new = len(set(store.ids()) - before)
    claims = store.objects("claim")
    for h in hs:
        src = claims[h]["source"]
        print(f"{short(h)}  {src['id']} v{src['version']}  {claims[h]['statement']}")
    print(f"{new} new object(s); kernel-checked by Palomar, refute any mis-formalisation with `ev review`")


def cmd_pull(args) -> None:
    store = Store.find()
    path = Path(args.path)
    other = Store(path / STORE_DIR if (path / STORE_DIR).is_dir() else path)
    print(f"pulled {store.pull(other)} new object(s) from {other.root}")


# ------------------------------------------------------------------ parser

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ev", description="Version control for science.")
    sub = p.add_subparsers(dest="command", required=True)
    js = argparse.ArgumentParser(add_help=False)
    js.add_argument("--json", action="store_true", help="machine-readable output")

    s = sub.add_parser("init", help="create a store in PATH")
    s.add_argument("path", nargs="?", default=".")
    for k in ("agent", "model", "lab"):
        s.add_argument(f"--{k}")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("claim", help="record a claim with its evidence")
    s.add_argument("statement")
    s.add_argument("--kind", choices=KINDS, default="result")
    s.add_argument("--file", action="append", default=[], type=Path, help="evidence file (repeatable)")
    s.add_argument("--cmd", help="command that reproduces the claim from its files")
    s.add_argument("--note", action="append", default=[])
    s.add_argument("--dep", action="append", default=[], help="claim id or Palomar id this builds on (repeatable)")
    s.set_defaults(func=cmd_claim)

    s = sub.add_parser("review", help="record a verdict on a claim")
    s.add_argument("id")
    s.add_argument("verdict", choices=VERDICTS)
    s.add_argument("--method", required=True, help="how it was checked")
    s.add_argument("--note", default="")
    s.add_argument("--by", help="the superseding claim")
    s.set_defaults(func=cmd_review)

    s = sub.add_parser("verify", help="re-run a claim's command and record the verdict")
    s.add_argument("id")
    s.add_argument("--timeout", type=int, default=600)
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("log", parents=[js], help="list claims")
    s.add_argument("--status", choices=("proposed", "at-risk", *VERDICTS))
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("show", parents=[js], help="show a claim in full")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("check", parents=[js], help="flag claims built on refuted work (exit 1 if any)")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("digest", parents=[js], help="what a human should read")
    s.add_argument("-n", type=int, default=5)
    s.set_defaults(func=cmd_digest)

    s = sub.add_parser("palomar", help="import Lean-verified entries and their dependencies from Palomar")
    pal = s.add_subparsers(dest="action", required=True)
    t = pal.add_parser("import", help="import entries by Palomar id")
    t.add_argument("ids", nargs="+", metavar="PALOMAR-ID")
    t.add_argument("--version", type=int, help="specific version (default: latest)")
    t.add_argument("--depth", type=int, default=3, help="levels of Palomar dependencies to follow")
    t.set_defaults(func=cmd_palomar)
    t = pal.add_parser("sync", help="import the most recently registered entries")
    t.add_argument("--limit", type=int, default=20)
    t.add_argument("--depth", type=int, default=3)
    t.set_defaults(func=cmd_palomar)

    s = sub.add_parser("pull", help="merge in another store")
    s.add_argument("path")
    s.set_defaults(func=cmd_pull)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except EvidenceError as e:
        print(f"ev: {e}", file=sys.stderr)
        return 2
    return 0
