"""Command-line interface: `ev <command>`. Every read command accepts --json for agents."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import batch, report, sandbox, signing
from .guide import GUIDE
from .palomar import PALOMAR_ID, Palomar
from .remote import open_source, rewritten, serve
from .store import KINDS, LIMITS, STATES, VERDICTS, EvidenceError, Store, format_value
from .store import now as store_now

# Lines of a command's output that `ev verify` prints; the review keeps its last 2000 characters.
OUTPUT_LINES = 5

MARK = {"proposed": "?", "reproduced": "✓", "refuted": "✗", "superseded": "→", "inconclusive": "~",
        "at-risk": "!", "answered": "✓", "open": "○", "contested": "≠"}


def short(h: str) -> str:
    return h[:10]


def who(author: dict, trust: dict | None = None) -> str:
    name = "/".join(author[k] for k in ("lab", "model", "agent") if author.get(k))
    if key := author.get("key"):
        name += f" ✔{trust[key]}" if trust and key in trust else " (untrusted key)"
    return name


def emit(args, data, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if args.json else text)


def kind_tag(kind: str) -> str:
    return f"[{kind}] " if kind != "result" else ""


def markers(status) -> str:
    """What the state alone does not say: the author's own re-run, and objections without evidence."""
    return (" [self-checked]" if status.self_checked and status.state == "proposed" else "") + \
        (f" [disputed by {len(status.disputed)}]" if status.disputed else "")


def value_tag(claim: dict) -> str:
    return f"  = {format_value(claim['value'])}" if "value" in claim else ""


# ---------------------------------------------------------------- recording

def cmd_init(args) -> None:
    author = {k: v for k in ("agent", "model", "lab") if (v := getattr(args, k))}
    store = Store.init(Path(args.path), author or None)
    if args.keygen:
        signing.generate(store.root / "key", comment=author.get("agent", "evidence"))
        store.configure(key="key")
    elif args.key:
        signing.public_key(Path(args.key).expanduser())
        store.configure(key=str(Path(args.key).expanduser().resolve()))
    if args.sandbox:
        store.configure(sandbox=args.sandbox)
    print(f"initialised {store.root}")
    if store.keyfile():
        print(f"signing as {signing.fingerprint(store.author()['key'])}")


def cmd_ask(args) -> None:
    print(Store.find().ask(args.text, parents=args.parent))


def cmd_claim(args) -> None:
    store = Store.find()
    # A Palomar id as a dependency imports that entry first.
    deps = [Palomar(store).import_entry(d) if PALOMAR_ID.fullmatch(d.upper()) else d for d in args.dep]
    h = store.claim(args.statement, kind=args.kind, files=args.file, cmd=args.cmd, notes=args.note,
                    depends_on=deps, setup=args.setup, answers=args.answers, value=args.value,
                    refutes=args.refutes)
    print(h)
    if args.verify:
        verify([h], args, store)


def cmd_review(args) -> None:
    """A refutation may bring its evidence: a counter-claim on record (--counter), or files and a
    command, which are recorded as a new counter-claim so that others can re-run and review it."""
    store = Store.find()
    counter = args.counter
    if args.cmd or args.file or args.setup:
        if counter or args.verdict != "refuted" or not args.cmd:
            raise EvidenceError("evidence for a review needs `refuted`, a --cmd, and no --counter")
        target = store.resolve(args.id, "claim")
        counter = store.claim(f"Claim {short(target)} does not hold: {args.method}", files=args.file,
                              cmd=args.cmd, setup=args.setup)
        print(counter)
    h = store.review(args.id, args.verdict, args.method, note=args.note, superseded_by=args.by, counter=counter)
    print(h)
    if h in store.statuses()[store.resolve(args.id)].disputed:
        print("recorded as an objection: the claim is now disputed, but its status is unchanged, since only "
              "evidence refutes another author's claim (--counter, --file with --cmd, or `ev verify`)",
              file=sys.stderr)


def cmd_apply(args) -> None:
    store = Store.find()
    if args.lines is not None:
        lines, base = batch.read_array(args.lines), Path.cwd()
    elif args.file == "-":
        lines, base = batch.read(sys.stdin.read()), Path.cwd()
    elif args.file:
        path = Path(args.file)
        try:
            lines, base = batch.read(path.read_text()), path.parent
        except OSError as e:
            raise EvidenceError(f"cannot read {args.file}: {e.strerror}") from None
    else:
        raise EvidenceError("name a JSON Lines file, or - for standard input")
    out = batch.apply(store, lines, base, dry_run=args.dry_run)
    new = sum(o["new"] for o in out)
    data = {"refs": {o["ref"]: o["id"] for o in out if "ref" in o}, "objects": out, "new": new,
            "dry_run": args.dry_run}
    text = [f"{o['line']:>4}  {o['type']:<8} {short(o['id'])}  {'new' if o['new'] else 'on record'}"
            + (f"  {o['ref']}" if "ref" in o else "") for o in out]
    text.append(f"{'would record' if args.dry_run else 'recorded'} {new} new object(s) from {len(out)} line(s)")
    emit(args, data, "\n".join(text))


def cmd_withdraw(args) -> None:
    print(Store.find().withdraw(args.review, note=args.note))


def duration(text: str) -> timedelta:
    """`90m`, `2h`, `1d`, `30s`, or a bare number of minutes."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"not a duration: {text!r} (e.g. 90m, 2h, 1d)")
    return timedelta(**{{"s": "seconds", "m": "minutes", "": "minutes", "h": "hours", "d": "days"}[m[2]]:
                        float(m[1])})


def reference_time(text: str | None) -> str:
    """The time leases are judged at: the given instant in UTC, else now. This is the only place
    where reading the clock affects what a read command reports."""
    if text is None:
        return store_now()
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceError(f"not an ISO 8601 time: {text!r}") from None
    if t.tzinfo is None:
        raise EvidenceError("give the time zone of --at, e.g. 2026-10-06T12:00:00+00:00")
    return t.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def cmd_lease(args) -> None:
    store = Store.find()
    h = store.lease(args.id, args.duration, note=args.note)
    print(h)
    print(f"until {store.get(h)['until']}", file=sys.stderr)
    publish(store)


def cmd_release(args) -> None:
    store = Store.find()
    for h in store.release(args.id, note=args.note):
        print(h)
    publish(store)


def publish(store: Store) -> None:
    """Push to every push target, since a lease or release is seen only by labs that have pulled it.
    The object is recorded whatever happens, so a target that cannot be reached is only reported."""
    for name in store.config().get("push", []):
        try:
            push_to(store, name, out=sys.stderr)  # stdout carries only the ids
        except (EvidenceError, OSError) as e:
            print(f"ev: not published to {name}: {e}", file=sys.stderr)


def cmd_verify(args) -> None:
    verify(args.ids, args, Store.find())


def verify(ids: list[str], args, store: Store) -> None:
    """Exit with the worst outcome: 1 if anything was refuted, else 3 if anything was inconclusive.

    The tail of the command's output is printed, since it usually says why a claim failed."""
    worst, data = 0, []
    as_json = getattr(args, "json", False)
    for i in ids:
        h, verdict = store.verify(i, timeout=args.timeout, sandbox_mode=args.sandbox, unsafe=args.unsafe)
        review = store.get(h)
        data.append({"claim": review["claim"], "verdict": verdict, "review": h, "method": review["method"],
                     "output": review["note"]})
        if not as_json:
            prefix = f"{short(review['claim'])}  " if len(ids) > 1 else ""
            print(f"{prefix}{MARK[verdict]} {verdict}  (review {short(h)}): {review['method']}")
            for line in [l for l in review["note"].splitlines() if l.strip()][-OUTPUT_LINES:]:
                print(f"    {line}")
        worst = max(worst, {"reproduced": 0, "inconclusive": 1, "refuted": 2}[verdict])
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    if worst:
        sys.exit({1: 3, 2: 1}[worst])


# ------------------------------------------------------------------ reading

def cmd_log(args) -> None:
    store = Store.find()
    statuses, trust = store.statuses(), store.trust()
    rows = [r for r in report.claim_rows(store) if not args.status or r["status"] == args.status]
    lines = [f"{MARK[r['status']]} {short(r['id'])}  {r['status']:<10} {kind_tag(r['kind'])}{r['statement']}"
             f"{value_tag(r)}{markers(statuses[r['id']])}  — {who(r['author'], trust)}" for r in rows]
    emit(args, rows, "\n".join(lines) or "no claims")


def cmd_show(args) -> None:
    store = Store.find()
    h = store.resolve(args.id)
    obj = store.get(h)
    trust = store.trust()
    if obj["type"] == "question":
        return show_question(args, store, h, obj)
    if obj["type"] != "claim":
        return emit(args, obj, json.dumps(obj, indent=2, ensure_ascii=False))
    claims = store.objects("claim")
    questions = store.objects("question")
    status = store.statuses()[h]
    down = store.downstream(h)
    data = {"id": h, **obj, "status": status.label, "independent": status.independent,
            "trusted": status.trusted, "self_checked": status.self_checked, "disputed": status.disputed,
            "grounds": status.grounds, "reviews": status.reviews,
            "at_risk_because": status.at_risk_because, "dependents": down}
    state = status.label + (f" ({status.independent} independent, {status.trusted} trusted)"
                            if status.independent else "") + markers(status)
    out = [f"claim {h}", f"status   {state}", f"kind     {obj['kind']}",
           f"author   {who(obj['author'], trust)}", f"created  {obj['created']}"]
    if src := obj.get("source"):
        out += [f"source   {src.get('registry')} {src.get('id')} v{src.get('version')}  {src.get('url')}",
                f"         {', '.join(map(str, src.get('authors') or []))}; "
                f"{src.get('repository')}@{str(src.get('commit'))[:10]}"]
    out += ["", f"    {obj['statement']}", ""]
    if "value" in obj:
        out.append(f"{'value':<17} {format_value(obj['value'])}")
    for e in obj["evidence"]:
        detail = {"file": lambda: f"{e['name']} ({short(e['blob'])})",
                  "command": lambda: f"$ {e['cmd']}", "setup": lambda: f"$ {e['cmd']}",
                  "note": lambda: e["text"],
                  "reference": lambda: f"{e['relationship']}: {e['title'] or e['identifier']}"
                                       + (f" ({e['identifier']})" if e["title"] and e["identifier"] else "")
                  }.get(e["kind"], lambda: json.dumps(e, ensure_ascii=False))()  # a kind from a newer version
        out.append(f"{'reference' if e['kind'] == 'reference' else 'evidence ' + e['kind']:<17} {detail}")
    for q in obj.get("answers", []):
        out.append(f"answers  {short(q)}  {questions[q]['text'] if q in questions else '(missing)'}")
    for d in obj["depends_on"]:
        out.append(f"depends  {short(d)}  {claims[d]['statement'] if d in claims else '(missing)'}")
    for r in status.reviews:
        role = (" (holds)" if r["id"] in status.grounds and r["verdict"] in ("refuted", "superseded") else
                " (objection without evidence)" if r["id"] in status.disputed else "")
        out.append(f"review   {MARK[r['verdict']]} {r['verdict']}{role} by {who(r['by'], trust)}: {r['method']}"
                   + (f" — {r['note'].splitlines()[-1]}" if r["note"].strip() else "")
                   + (f" (counter-claim {short(r['counter'])})" if r.get("counter") else "")
                   + f"  [{short(r['id'])}]")
    for d in status.at_risk_because:
        out.append(f"at risk  upstream {short(d)} is no longer standing")
    if down:
        out.append(f"used by  {len(down)} claim(s): {', '.join(short(d) for d in down)}")
    emit(args, data, "\n".join(out))


def show_question(args, store, h, q) -> None:
    all_qs = store.question_statuses()
    qs = all_qs[h]
    claims, statuses, questions = store.objects("claim"), store.statuses(), store.objects("question")
    data = {"id": h, **q, "status": qs.state, "answers": qs.answers, "standing": qs.standing,
            "subquestions": qs.subquestions,
            "values": {a: claims[a]["value"] for a in qs.answers if "value" in claims[a]},
            "conflicts": qs.conflicts}
    out = [f"question {h}", f"status   {qs.state}", f"author   {who(q['author'], store.trust())}", "",
           f"    {q['text']}", ""]
    out += [f"part of  {short(p)}  {questions[p]['text'] if p in questions else '(missing)'}" for p in q["parents"]]
    out += [f"sub      {MARK[all_qs[s].state]} {short(s)}  {questions[s]['text']}"
            for s in qs.subquestions]
    out += [f"answer   {MARK[statuses[a].label]} {short(a)}  {claims[a]['statement']}{value_tag(claims[a])}"
            for a in qs.answers]
    out += [f"conflict {short(a)} {format_value(claims[a]['value'])} against {short(b)} "
            f"{format_value(claims[b]['value'])}" for a, b in qs.conflicts]
    emit(args, data, "\n".join(out))


def cmd_questions(args) -> None:
    store = Store.find()
    questions, claims = store.objects("question"), store.objects("claim")
    qs = store.question_statuses()
    data = report.question_rows(store)
    roots = [d["id"] for d in data if not any(p in questions for p in d["parents"])]

    def line(h: str, depth: int) -> str:
        values = sorted({format_value(claims[a]["value"]) for c in qs[h].conflicts for a in c})
        return (f"{'  ' * depth}{MARK[qs[h].state]} {short(h)}  {questions[h]['text']}"
                + (f"  ({len(qs[h].standing)} standing answer(s))" if qs[h].standing else "")
                + (f"  contested: {' vs '.join(values)}" if values else ""))

    lines = [line(h, depth) for h, depth in report.tree(roots, lambda h: qs[h].subquestions)]
    emit(args, data, "\n".join(lines) or "no questions")


def cmd_check(args) -> None:
    store = Store.find()
    claims = store.objects("claim")
    risky = {h: s for h, s in store.statuses().items() if s.label == "at-risk"}
    data = [{"id": h, "statement": claims[h]["statement"], "because": s.at_risk_because}
            for h, s in risky.items()]
    lines = [f"! {short(d['id'])}  {d['statement']}\n    depends on: "
             + ", ".join(short(b) for b in d["because"]) for d in data]
    emit(args, data, "\n".join(lines) or "all claims stand on standing ground")
    if risky:
        sys.exit(1)


def cmd_digest(args) -> None:
    """The few results a human should read: reproduced claims that most other work builds on."""
    data = report.digest(Store.find(), args.n)
    lines = [f"{i}. {d['statement']}\n   {short(d['id'])} · built on by {d['dependents']} · "
             f"reproduced by {d['independent']} other lab(s), {d['trusted']} trusted · "
             f"{d['reviews']} review(s)" for i, d in enumerate(data, 1)]
    emit(args, data, "\n".join(lines) or "nothing reproduced yet")


def cmd_snapshot(args) -> None:
    """Everything a static site needs to show the record, judged at one instant."""
    data = report.snapshot(Store.find(), reference_time(args.at), args.n)
    c = data["counts"]
    emit(args, data, f"{data['at']}: {c['questions']} question(s), {c['answered']} answered; "
                     f"{c['claims']} claim(s), {c['reproduced']} reproduced, {c['refuted']} refuted; "
                     f"{len(data['todo'])} item(s) to do, {len(data['leases'])} lease(s) held")


def cmd_search(args) -> None:
    store = Store.find()
    statuses, qs = store.statuses(), store.question_statuses()
    data = []
    for score, h in store.search(args.query, args.n, **({"cutoff": 0} if args.all else {})):
        o = store.get(h)
        if o["type"] == "claim":
            data.append({"id": h, "type": "claim", "score": round(score, 3), "status": statuses[h].label,
                         "kind": o["kind"], "statement": o["statement"],
                         **({"value": o["value"]} if "value" in o else {})})
        else:
            data.append({"id": h, "type": "question", "score": round(score, 3), "status": qs[h].state,
                         "kind": "question", "statement": o["text"]})
    lines = [f"{d['score']:6.2f}  {MARK[d['status']]} {short(d['id'])}  {d['status']:<10} "
             f"{kind_tag(d['kind'])}{d['statement']}" for d in data]
    emit(args, data, "\n".join(lines) or "nothing related on record")


def cmd_todo(args) -> None:
    """What an agent could do next to strengthen the record, highest impact first."""
    store = Store.find()
    try:
        me = store.author()
    except EvidenceError:
        me = None
    data = store.todo(me, at=reference_time(args.at))[:args.n]
    lines = [f"{d['action']:<9} {short(d['id'])}  impact {d['impact']:<3} {d['why']}\n"
             f"{'':<10}{d['statement']}"
             + "".join(f"\n{'':<10}leased by {'you' if l['mine'] else who(l['by'])} until {l['until']}"
                       + (f": {l['note']}" if l["note"] else "") for l in d["leased"]) for d in data]
    emit(args, data, "\n".join(lines) or "nothing to do")


def cmd_checkout(args) -> None:
    store = Store.find()
    for path in store.checkout(store.resolve(args.id, "claim"), Path(args.dir)):
        print(path)


def cmd_report(args) -> None:
    store = Store.find()
    print(report.latex(store) if args.format == "tex" else report.markdown(store), end="")


def cmd_graph(args) -> None:
    print(report.dot(Store.find()), end="")


def cmd_whoami(args) -> None:
    store = Store.find()
    author = store.author()
    data = {"author": author, "store": str(store.root), "sandbox": store.sandbox_mode(),
            "remotes": store.config().get("remotes", {}), "push": store.config().get("push", []),
            "trusted": {name: signing.fingerprint(k) for k, name in store.trust().items()}}
    if key := author.get("key"):
        data["fingerprint"] = signing.fingerprint(key)
    text = [f"author   {who(author, store.trust())}", f"store    {store.root}", f"sandbox  {data['sandbox']}"]
    if key:
        text += [f"key      {key}", f"         {data['fingerprint']}"]
    else:
        text.append("key      none: objects are unsigned (ev init --keygen)")
    emit(args, data, "\n".join(text))


def cmd_guide(args) -> None:
    print(GUIDE)


# ------------------------------------------------------------------ sharing

def cmd_pull(args) -> None:
    store = Store.find()
    remotes = store.config().get("remotes", {})
    specs = args.sources or list(remotes.values())
    if not specs:
        raise EvidenceError("nothing to pull: name a source or add one with `ev remote add`")
    limits = store.limits(object=args.max_object, blob=args.max_blob, total=args.max_total)
    for spec in specs:
        with open_source(remotes.get(spec, spec)) as source:
            print(f"pulled {store.pull(source, limits)} new object(s) from {remotes.get(spec, spec)}")


def cmd_push(args) -> None:
    store = Store.find()
    targets = args.targets or store.config().get("push", [])
    if not targets:
        raise EvidenceError("nothing to push to: name a store or add one with `ev remote add NAME PATH --push`")
    for t in targets:
        push_to(store, t)


def push_to(store: Store, name: str, out=None) -> None:
    spec = store.config().get("remotes", {}).get(name, name)
    with open_source(spec) as target:
        if not isinstance(target, Store):
            raise EvidenceError("push writes to a store on disk; others pull from `ev serve`")
        print(f"pushed {store.push(target)} new object(s) to {target.root}", file=out or sys.stdout)


def cmd_remote(args) -> None:
    store = Store.find()
    remotes = dict(store.config().get("remotes", {}))
    push = [n for n in store.config().get("push", []) if n != getattr(args, "name", None)]
    if args.action == "add":
        remotes[args.name] = args.spec
        push += [args.name] if args.push else []
    elif args.action == "remove":
        if remotes.pop(args.name, None) is None:
            raise EvidenceError(f"no remote {args.name}")
    store.configure(remotes=remotes, push=push)
    for name, spec in remotes.items():
        print(f"{name}\t{spec}" + ("\tpush" if name in push else ""))


def cmd_trust(args) -> None:
    store = Store.find()
    trust = dict(store.config().get("trust", {}))
    if args.action == "add":
        path = Path(args.key).expanduser()
        key = signing.normalise(path.read_text() if path.is_file() else args.key)
        trust[key] = args.name
    elif args.action == "remove":
        trust = {k: v for k, v in trust.items() if v != args.name}
    store.configure(trust=trust)
    for key, name in store.trust().items():
        print(f"{name}\t{signing.fingerprint(key)}")


def cmd_serve(args) -> None:
    store = Store.find()
    if args.export:
        out = Path(args.export)
        target = Store.init(out / "_", {})  # a scratch store to receive the public files
        n = target.pull(store, dict.fromkeys(LIMITS, math.inf))  # our own store: no bounds
        for kind in ("objects", "blobs"):
            dst = out / kind
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(target.root / kind), dst)
        shutil.rmtree(out / "_")
        (out / "index.json").write_text(json.dumps(store.listing()))
        print(f"exported {n} file(s) to {out}; publish it with any static host")
        return
    server = serve(store, args.host, args.port)
    print(f"serving {store.root} at http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def cmd_fsck(args) -> None:
    store = Store.find()
    problems = store.fsck() + (rewritten(store, args.since) if args.since else [])
    emit(args, problems, "\n".join(problems) or "ok")
    if problems:
        sys.exit(1)


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


def cmd_mcp(args) -> None:
    from .mcp import serve_stdio
    serve_stdio()


# ------------------------------------------------------------------ parser

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ev", description="Version control for science.",
                                epilog="Agents: run `ev guide` first.")
    sub = p.add_subparsers(dest="command", required=True)
    js = argparse.ArgumentParser(add_help=False)
    js.add_argument("--json", action="store_true", help="machine-readable output")

    s = sub.add_parser("init", help="create a store in PATH")
    s.add_argument("path", nargs="?", default=".")
    for k in ("agent", "model", "lab"):
        s.add_argument(f"--{k}")
    s.add_argument("--keygen", action="store_true", help="create a signing key for this store")
    s.add_argument("--key", help="sign with this SSH private key (ed25519 recommended)")
    s.add_argument("--sandbox", choices=sandbox.MODES, help="how `ev verify` isolates commands")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("ask", help="record an open question")
    s.add_argument("text")
    s.add_argument("--parent", action="append", default=[], help="larger question this helps settle")
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("claim", help="record a claim with its evidence")
    s.add_argument("statement")
    s.add_argument("--kind", choices=KINDS, default="result")
    s.add_argument("--file", action="append", default=[], type=Path, help="evidence file (repeatable)")
    s.add_argument("--cmd", help="command that reproduces the claim from its files")
    s.add_argument("--setup", action="append", default=[],
                   help="command preparing the environment; its failure is inconclusive (repeatable)")
    s.add_argument("--note", action="append", default=[])
    s.add_argument("--dep", action="append", default=[], help="claim id or Palomar id this builds on (repeatable)")
    s.add_argument("--answers", action="append", default=[], help="question this claim answers (repeatable)")
    s.add_argument("--value", help='the answer as a value: 168, true, "text", 9.81 m/s^2 ± 0.02')
    s.add_argument("--refutes", action="append", default=[],
                   help="claim this one shows false; it stands refuted while this claim stands (needs --cmd)")
    s.add_argument("--verify", action="store_true", help="re-run the command from a clean directory at once")
    s.add_argument("--timeout", type=int, default=600, help=argparse.SUPPRESS)
    s.add_argument("--sandbox", choices=sandbox.MODES, help=argparse.SUPPRESS)
    s.add_argument("--unsafe", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_claim)

    s = sub.add_parser("review", help="record a verdict on a claim; another author's claim is refuted "
                       "only with evidence, otherwise it is disputed")
    s.add_argument("id")
    s.add_argument("verdict", choices=VERDICTS)
    s.add_argument("--method", required=True, help="how it was checked")
    s.add_argument("--note", default="")
    s.add_argument("--by", help="the superseding claim")
    s.add_argument("--counter", help="a claim with a command that shows this one false; the refutation "
                   "holds while it stands")
    s.add_argument("--file", action="append", default=[], type=Path,
                   help="evidence for a refutation, recorded as a counter-claim (repeatable; needs --cmd)")
    s.add_argument("--cmd", help="command that exits 0 exactly when the refutation holds")
    s.add_argument("--setup", action="append", default=[], help="command preparing the environment (repeatable)")
    s.set_defaults(func=cmd_review)

    s = sub.add_parser("apply", parents=[js], help="record a batch of questions, claims and reviews "
                       "from JSON Lines, all or nothing (see `ev guide`)")
    s.add_argument("file", nargs="?", help="JSON Lines file, or - for standard input")
    s.add_argument("--lines", help=argparse.SUPPRESS)  # the batch as one JSON array, for `ev mcp`
    s.add_argument("--dry-run", action="store_true", help="check the batch and report ids; write nothing")
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("withdraw", help="take back one of your own reviews")
    s.add_argument("review")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_withdraw)

    s = sub.add_parser("verify", parents=[js], help="re-run a claim's command and record the verdict "
                       "(exit 1 refuted, 3 inconclusive)")
    s.add_argument("ids", nargs="+", metavar="id")
    s.add_argument("--timeout", type=int, default=600)
    s.add_argument("--sandbox", choices=sandbox.MODES)
    s.add_argument("--unsafe", action="store_true", help="run another lab's command without a sandbox")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("log", parents=[js], help="list claims")
    s.add_argument("--status", choices=STATES)
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("show", parents=[js], help="show a claim or question in full")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("questions", parents=[js], help="the tree of questions and their answers")
    s.set_defaults(func=cmd_questions)

    s = sub.add_parser("check", parents=[js], help="flag claims built on refuted work (exit 1 if any)")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("digest", parents=[js], help="the report in short: the results most work builds on")
    s.add_argument("-n", type=int, default=5)
    s.set_defaults(func=cmd_digest)

    s = sub.add_parser("snapshot", parents=[js], help="the whole record as one JSON document for a "
                       "static site, with leases judged at one time")
    s.add_argument("--at", metavar="TIME", help="judge leases at this ISO 8601 time (default: now)")
    s.add_argument("-n", type=int, default=50, help="items of todo to include")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("search", parents=[js], help="find related claims and questions, dead ends included")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--all", action="store_true", help="keep matches scoring far below the best")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("todo", parents=[js], help="what to check, prove or answer next, highest impact first")
    s.add_argument("-n", type=int, default=20)
    s.add_argument("--at", metavar="TIME", help="judge leases at this ISO 8601 time (default: now)")
    s.set_defaults(func=cmd_todo)

    s = sub.add_parser("lease", help="announce that you are working on a claim or question, "
                       "so that others' todo steers elsewhere")
    s.add_argument("id")
    s.add_argument("--for", dest="duration", type=duration, default=timedelta(hours=2),
                   metavar="DURATION", help="how long, e.g. 90m, 2h, 1d (default 2h, at most 7d)")
    s.add_argument("--note", default="", help="what you are doing")
    s.set_defaults(func=cmd_lease)

    s = sub.add_parser("release", help="end your lease on a claim or question before it expires")
    s.add_argument("id")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_release)

    s = sub.add_parser("checkout", help="write a claim's evidence files into DIR")
    s.add_argument("id")
    s.add_argument("dir", nargs="?", default=".")
    s.set_defaults(func=cmd_checkout)

    s = sub.add_parser("report", help="the record written up for human readers")
    s.add_argument("--format", choices=("md", "tex"), default="md")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("graph", help="the record as a Graphviz digraph")
    s.set_defaults(func=cmd_graph)

    s = sub.add_parser("whoami", parents=[js], help="author, key, sandbox and remotes of this store")
    s.set_defaults(func=cmd_whoami)

    s = sub.add_parser("guide", help="how an AI agent should use this record")
    s.set_defaults(func=cmd_guide)

    s = sub.add_parser("pull", help="merge in other stores: paths, URLs, git repositories or remote names")
    s.add_argument("sources", nargs="*", help="default: every remote")
    s.add_argument("--max-object", metavar="SIZE", help=f"largest object accepted (default {LIMITS['object'] >> 20}M)")
    s.add_argument("--max-blob", metavar="SIZE", help=f"largest evidence file accepted (default {LIMITS['blob'] >> 20}M)")
    s.add_argument("--max-total", metavar="SIZE", help=f"most fetched from one source (default {LIMITS['total'] >> 30}G)")
    s.set_defaults(func=cmd_pull)

    s = sub.add_parser("push", help="copy our objects into other stores on disk")
    s.add_argument("targets", nargs="*", metavar="target", help="default: every push target")
    s.set_defaults(func=cmd_push)

    s = sub.add_parser("remote", help="name the stores you pull from and push to")
    rem = s.add_subparsers(dest="action", required=True)
    t = rem.add_parser("add")
    t.add_argument("name")
    t.add_argument("spec", help="path, http(s) URL, or git URL (URL#subdir)")
    t.add_argument("--push", action="store_true",
                   help="a store on disk that `ev push`, `ev lease` and `ev release` publish to")
    t.set_defaults(func=cmd_remote)
    t = rem.add_parser("remove")
    t.add_argument("name")
    t.set_defaults(func=cmd_remote)
    rem.add_parser("list").set_defaults(func=cmd_remote)

    s = sub.add_parser("trust", help="keys whose reproductions you count as trusted")
    tr = s.add_subparsers(dest="action", required=True)
    t = tr.add_parser("add")
    t.add_argument("name")
    t.add_argument("key", help="public key, or a .pub file")
    t.set_defaults(func=cmd_trust)
    t = tr.add_parser("remove")
    t.add_argument("name")
    t.set_defaults(func=cmd_trust)
    tr.add_parser("list").set_defaults(func=cmd_trust)

    s = sub.add_parser("serve", help="serve this store read-only over HTTP for others to pull")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--export", metavar="DIR", help="write the public files and an index to DIR for a static host")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("fsck", parents=[js], help="check hashes, signatures and references (exit 1 if bad)")
    s.add_argument("--since", metavar="REV", help="also fail if a git commit since REV changed or deleted "
                   "an object or file: a shared record only grows")
    s.set_defaults(func=cmd_fsck)

    s = sub.add_parser("mcp", help="serve this store to AI agents over the Model Context Protocol (stdio)")
    s.set_defaults(func=cmd_mcp)

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
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except EvidenceError as e:
        print(f"ev: {e}", file=sys.stderr)
        return 2
    return 0
