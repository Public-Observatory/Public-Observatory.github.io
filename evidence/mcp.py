"""A Model Context Protocol server over stdio, so that any MCP-capable agent can use the record.

Each tool is a thin wrapper around the command line: the tool's arguments become `ev` arguments,
read commands are run with --json, and the output is returned as text. The command line stays the
single source of behaviour. Register it with an agent as the command `ev mcp`, run in the
directory of the store (or with EV_DIR set).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys

from . import __version__
from .guide import GUIDE
from .store import KINDS, VERDICTS

PROTOCOL = "2025-06-18"

S = {"type": "string"}
A = {"type": "array", "items": {"type": "string"}}
I = {"type": "integer"}


def flag(name: str, values) -> list[str]:
    if values is None or values is False:
        return []
    if values is True:
        return [name]
    if isinstance(values, list):
        return [x for v in values for x in (name, str(v))]
    return [name, str(values)]


# name: (description, properties, required, argv builder)
TOOLS = {
    "search": ("Find claims and questions related to a query, dead ends included. Use before starting any work.",
               {"query": S, "n": I}, ["query"], lambda a: ["search", a["query"], *flag("-n", a.get("n")), "--json"]),
    "todo": ("The work that would most strengthen the record, highest impact first: resolve (a contested "
             "question), recheck, reproduce, review, prove, answer. Items others have leased come last and list the lease under `leased`.",
             {"n": I}, [], lambda a: ["todo", *flag("-n", a.get("n")), "--json"]),
    "lease": ("Announce that you are working on a claim or question, so that other agents' todo steers elsewhere. "
              "duration is e.g. 90m, 2h or 1d (default 2h). Recording a review or claim on the target ends it.",
              {"id": S, "duration": S, "note": S}, ["id"],
              lambda a: ["lease", a["id"], *flag("--for", a.get("duration")), *flag("--note", a.get("note"))]),
    "release": ("End your lease on a claim or question without recording work on it, e.g. when you give up.",
                {"id": S, "note": S}, ["id"], lambda a: ["release", a["id"], *flag("--note", a.get("note"))]),
    "show": ("A claim or question in full: evidence, dependencies, reviews, status, dependents.",
             {"id": S}, ["id"], lambda a: ["show", a["id"], "--json"]),
    "log": ("All claims, optionally only those with a given status.", {"status": S}, [],
            lambda a: ["log", *flag("--status", a.get("status")), "--json"]),
    "questions": ("The tree of questions with their status (contested, answered, proposed, open), answers, "
                  "values and conflicts.", {}, [], lambda a: ["questions", "--json"]),
    "check": ("Claims that rest on refuted or superseded work.", {}, [], lambda a: ["check", "--json"]),
    "digest": ("The reproduced results most other work builds on.", {"n": I}, [],
               lambda a: ["digest", *flag("-n", a.get("n")), "--json"]),
    "ask": ("Record an open question, optionally as part of larger ones.", {"text": S, "parents": A}, ["text"],
            lambda a: ["ask", a["text"], *flag("--parent", a.get("parents"))]),
    "claim": (f"Record a claim with its evidence. kind is one of {', '.join(KINDS)}; record dead ends as negative. "
              "files are paths on this machine; cmd must exit 0 exactly when the claim holds; verify re-runs it at once. "
              "When the claim answers a question, give the answer as value: an integer (168), true or false, "
              "quoted text, or a quantity with optional uncertainty and unit (9.81 ± 0.02 m/s^2), so that "
              "disagreeing answers are detected.",
              {"statement": S, "kind": S, "files": A, "cmd": S, "setup": A, "notes": A, "depends_on": A,
               "answers": A, "value": S, "verify": {"type": "boolean"}}, ["statement"],
              lambda a: ["claim", a["statement"], *flag("--kind", a.get("kind")), *flag("--file", a.get("files")),
                         *flag("--cmd", a.get("cmd")), *flag("--setup", a.get("setup")),
                         *flag("--note", a.get("notes")), *flag("--dep", a.get("depends_on")),
                         *flag("--answers", a.get("answers")), *flag("--value", a.get("value")),
                         *flag("--verify", a.get("verify"))]),
    "verify": ("Re-run claims' commands in a sandbox and record the verdicts.", {"ids": A, "timeout": I}, ["ids"],
               lambda a: ["verify", *a["ids"], *flag("--timeout", a.get("timeout"))]),
    "review": (f"Record a verdict ({', '.join(VERDICTS)}) on a claim and how it was reached.",
               {"id": S, "verdict": S, "method": S, "note": S, "superseded_by": S}, ["id", "verdict", "method"],
               lambda a: ["review", a["id"], a["verdict"], "--method", a["method"], *flag("--note", a.get("note")),
                          *flag("--by", a.get("superseded_by"))]),
    "withdraw": ("Take back one of your own reviews.", {"review": S, "note": S}, ["review"],
                 lambda a: ["withdraw", a["review"], *flag("--note", a.get("note"))]),
    "checkout": ("Write a claim's evidence files into a directory.", {"id": S, "dir": S}, ["id", "dir"],
                 lambda a: ["checkout", a["id"], a["dir"]]),
    "pull": ("Fetch other labs' work: paths, URLs, git repositories or remote names (default: all remotes). "
             "Sizes such as `512M` raise the bounds on one object, one evidence file and one pull.",
             {"sources": A, "max_object": S, "max_blob": S, "max_total": S}, [],
             lambda a: ["pull", *a.get("sources", []), *flag("--max-object", a.get("max_object")),
                        *flag("--max-blob", a.get("max_blob")), *flag("--max-total", a.get("max_total"))]),
    "guide": ("How to work on this record.", {}, [], lambda a: ["guide"]),
}


def call(name: str, arguments: dict) -> tuple[str, bool]:
    from .cli import main
    argv = TOOLS[name][3](arguments)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    text = out.getvalue().strip()
    if err.getvalue().strip():
        text = (text + "\n" + err.getvalue().strip()).strip()
    # Exit 1 reports a finding (claims at risk, a refutation), not a failure of the tool.
    return text or f"exit {code}", code not in (0, 1, 3)


def tool_list() -> list[dict]:
    return [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r}}
            for n, (d, p, r, _) in TOOLS.items()]


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # a notification
    params = msg.get("params") or {}
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", PROTOCOL),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "evidence", "version": __version__},
                  "instructions": GUIDE}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tool_list()}
    elif method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            text, error = call(name, params.get("arguments") or {})
        except Exception as e:  # report, never crash the server
            text, error = f"{type(e).__name__}: {e}", True
        result = {"content": [{"type": "text", "text": text}], "isError": error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve_stdio(stdin=None, stdout=None) -> None:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()
