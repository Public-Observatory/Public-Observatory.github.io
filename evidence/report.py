"""The record written up for people: a digest, a report in Markdown or LaTeX, and a graph.

Humans are meant to read only what matters. The report therefore leads with the questions and
how far they are settled, with contradictions between standing answers spelled out, then gives
the principal results (claims reproduced by someone other than their author that most other work
rests on), what was refuted and on what evidence, the claims disputed without evidence, the dead
ends, the open conjectures, and the work at risk. A refutation is reported by the evidence that
holds, never by an objection that changed nothing.
"""

from __future__ import annotations

from datetime import date

from .store import BROKEN, Store, format_value
from .store import identity as store_identity

ITEMS = 10


def digest(store: Store, n: int = 5) -> list[dict]:
    """Reproduced claims, ranked by how much rests on them and then by trusted and independent checks."""
    claims = store.objects("claim")
    statuses = store.statuses()
    g = store.graph()
    ranked = sorted(((g.down[h].bit_count(), statuses[h].trusted, statuses[h].independent,
                      len(statuses[h].reviews), h)
                     for h in claims if statuses[h].label == "reproduced"), reverse=True)
    return [{"id": h, "statement": claims[h]["statement"], "dependents": d, "trusted": t,
             "independent": i, "reviews": r} for d, t, i, r, h in ranked[:n]]


def sections(store: Store) -> tuple[dict, list[tuple[str, list[str]]]]:
    """Counts, and (title, items) pairs whose items are plain sentences."""
    claims = store.objects("claim")
    questions = store.objects("question")
    statuses = store.statuses()
    qs = store.question_statuses(statuses)
    labels = [s.label for s in statuses.values()]
    counts = {"claims": len(claims), "questions": len(questions),
              **{k: labels.count(k) for k in ("reproduced", "proposed", "refuted", "superseded", "at-risk")},
              "answered": sum(q.state == "answered" for q in qs.values()),
              "contested": sum(q.state == "contested" for q in qs.values()),
              "disputed": sum(bool(s.disputed) for s in statuses.values())}

    def given(a: str) -> str:
        return f"{format_value(claims[a]['value'])} (claim {a[:10]}, {statuses[a].label})"

    def q_line(h: str, depth: int) -> str:
        q = qs[h]
        best = next((a for a in q.answers if statuses[a].label == "reproduced"), None) or next(
            (a for a in q.answers if statuses[a].label == "proposed"), None)
        answer = f" Answer: {claims[best]['statement']}" if best else ""
        if q.conflicts:
            answer = " Standing answers disagree: " + "; ".join(
                f"{given(a)} against {given(b)}" for a, b in q.conflicts) + "."
        return ("  " * depth) + f"{questions[h]['text']} ({q.state}).{answer}"

    roots = [h for h, q in questions.items() if not any(p in questions for p in q["parents"])]
    out = [("Questions", [q_line(h, d) for h, d in tree(sorted(roots, key=lambda h: (questions[h]["created"], h)),
                                                         lambda h: qs[h].subquestions)])]
    out.append(("Principal results", [
        f"{d['statement']} Reproduced by {plural(d['independent'], 'independent lab')}; "
        f"{plural(d['dependents'], 'claim rests', 'claims rest')} on it." for d in digest(store, ITEMS)]))
    refuted = [f"{claims[h]['statement']} {grounds(store, claims, h, s)}"
               for h, s in statuses.items() if s.state in BROKEN]
    out.append(("Refuted and superseded", refuted[:ITEMS]))
    out.append(("Disputed", [
        f"{claims[h]['statement']} ({s.label}) Objected to without evidence that holds: "
        + "; ".join(sentence(r["method"]) for r in s.reviews if r["id"] in s.disputed)
        for h, s in statuses.items() if s.disputed][:ITEMS]))
    out.append(("Dead ends", [c["statement"] for h, c in claims.items()
                              if c["kind"] == "negative" and statuses[h].label not in BROKEN][:ITEMS]))
    out.append(("Open conjectures", [c["statement"] for h, c in claims.items()
                                     if c["kind"] == "conjecture" and statuses[h].label == "proposed"][:ITEMS]))
    out.append(("At risk", [f"{claims[h]['statement']} Rests on {plural(len(s.at_risk_because), 'claim')} no "
                            f"longer standing." for h, s in statuses.items() if s.label == "at-risk"][:ITEMS]))
    return counts, [(t, items) for t, items in out if items]


def sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def grounds(store: Store, claims: dict, h: str, s) -> str:
    """Why a claim fell, as one or two sentences: the evidence that holds, not every opinion."""
    reviews = {r["id"]: r for r in s.reviews}
    r = next((reviews[g] for g in s.grounds if reviews[g]["verdict"] == s.state), reviews[s.grounds[0]])
    last = r["note"].strip().splitlines()[-1] if r["note"].strip() else ""
    if r["verdict"] == "superseded":
        text = f"Superseded by claim {r['superseded_by'][:10]}"
        return text + (f" ({r['method'].strip()})." if r["method"].strip() else ".")
    if store_identity(r["by"]) == store_identity(claims[h]["author"]):
        text = f"Retracted by its author: {sentence(r['method'])}"
    elif c := r.get("counter"):
        text = f"Refuted by claim {c[:10]}: {sentence(claims[c]['statement'])}"
    else:
        text = f"Refuted by a failed run: {sentence(r['method'])}"
        return text + (f" The output ended with “{last}”." if last else "")
    return text + (f" Note: {sentence(last)}" if last else "")


def tree(roots: list[str], children) -> list[tuple[str, int]]:
    """Nodes in depth-first order with their depths, each once. A question may be part of several
    larger ones, so following every path could take exponential time; nor may a deep chain exhaust
    the stack."""
    out, seen, stack = [], set(), [(h, 0) for h in reversed(roots)]
    while stack:
        h, depth = stack.pop()
        if h not in seen:
            seen.add(h)
            out.append((h, depth))
            stack.extend((c, depth + 1) for c in reversed(children(h)))
    return out


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else many or word + 's'}"


def summary(counts: dict) -> str:
    c = counts
    if not c["claims"] and not c["questions"]:
        return "The record is empty."
    parts = [f"{c[k]} {k}" for k in ("reproduced", "proposed", "refuted", "superseded") if c[k]]
    text = f"The record holds {plural(c['claims'], 'claim')} and {plural(c['questions'], 'question')}."
    if parts:
        text += " By status: " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."
    if c["at-risk"]:
        text += f" {plural(c['at-risk'], 'claim rests', 'claims rest')} on work that no longer stands."
    if c["disputed"]:
        text += (f" {plural(c['disputed'], 'claim is', 'claims are')} disputed by objections without "
                 f"evidence, which change no status.")
    if c["questions"] == 1:
        state = "contested: its standing answers disagree" if c["contested"] else \
            "answered" if c["answered"] else "open"
        text += f" The question is {state}."
    elif c["questions"]:
        text += f" {c['answered']} of the {c['questions']} questions {'is' if c['answered'] == 1 else 'are'} answered."
        if c["contested"]:
            text += f" {plural(c['contested'], 'question has', 'questions have')} standing answers that disagree."
    return text


def markdown(store: Store) -> str:
    counts, secs = sections(store)
    out = [f"# State of the record, {date.today().isoformat()}", "", summary(counts), ""]
    for title, items in secs:
        out += [f"## {title}", ""]
        for item in items:
            indent = len(item) - len(item.lstrip(" "))
            out.append(" " * indent + "- " + item.lstrip(" "))
        out.append("")
    return "\n".join(out)


def tex_escape(s: str) -> str:
    table = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
             "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(table.get(c, c) for c in s)


def latex(store: Store) -> str:
    """A short amsart document. Each paragraph is on one line."""
    counts, secs = sections(store)
    out = [r"\documentclass{amsart}", r"\title{State of the record}", rf"\date{{{date.today().isoformat()}}}",
           r"\begin{document}", r"\maketitle", "", tex_escape(summary(counts)), ""]
    for title, items in secs:
        out += [rf"\section*{{{title}}}", r"\begin{itemize}"]
        depth = 0
        for item in items:
            d = (len(item) - len(item.lstrip(" "))) // 2
            while depth < d:
                out.append(r"\begin{itemize}")
                depth += 1
            while depth > d:
                out.append(r"\end{itemize}")
                depth -= 1
            out.append(r"\item " + tex_escape(item.strip()))
        out += [r"\end{itemize}"] * depth + [r"\end{itemize}", ""]
    out.append(r"\end{document}")
    return "\n".join(out) + "\n"


def dot(store: Store) -> str:
    """Claims and questions as a Graphviz digraph; edges point from a claim to what it rests on."""
    colour = {"reproduced": "palegreen", "proposed": "white", "refuted": "salmon",
              "superseded": "lightgrey", "at-risk": "gold"}
    claims, questions = store.objects("claim"), store.objects("question")
    statuses, qs = store.statuses(), store.question_statuses()

    def label(text: str) -> str:
        text = text if len(text) <= 60 else text[:57] + "..."
        return text.replace("\\", "\\\\").replace('"', '\\"')

    out = ["digraph evidence {", "  rankdir=BT;", '  node [style=filled, fontname="Helvetica"];']
    for h, q in questions.items():
        fill = {"answered": "palegreen", "contested": "orange"}.get(qs[h].state, "lightblue")
        out.append(f'  "{h[:10]}" [shape=box, fillcolor="{fill}", '
                   f'label="? {label(q["text"])}"];')
        out += [f'  "{h[:10]}" -> "{p[:10]}" [style=dotted];' for p in q["parents"] if p in questions]
    for h, c in claims.items():
        shape = {"negative": "octagon", "conjecture": "diamond"}.get(c["kind"], "ellipse")
        out.append(f'  "{h[:10]}" [shape={shape}, fillcolor="{colour[statuses[h].label]}", '
                   f'label="{label(c["statement"])}"];')
        out += [f'  "{h[:10]}" -> "{d[:10]}";' for d in c["depends_on"] if d in claims]
        out += [f'  "{h[:10]}" -> "{q[:10]}" [style=dashed];' for q in c.get("answers", []) if q in questions]
    out.append("}")
    return "\n".join(out) + "\n"
