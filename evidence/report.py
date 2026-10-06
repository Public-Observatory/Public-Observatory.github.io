"""The record written up for people: a digest, a report in Markdown or LaTeX, and a graph.

Humans are meant to read only what matters. The report therefore leads with the questions and
how far they are settled, then gives the principal results (reproduced claims that most other work
rests on), what was refuted and how, the dead ends, the open conjectures, and the work at risk.
"""

from __future__ import annotations

from datetime import date

from .store import BROKEN, Store

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
              "answered": sum(q.state == "answered" for q in qs.values())}

    def q_line(h: str, depth: int) -> list[str]:
        q = qs[h]
        best = next((a for a in q.answers if statuses[a].label == "reproduced"), None) or next(
            (a for a in q.answers if statuses[a].label == "proposed"), None)
        answer = f" Answer: {claims[best]['statement']}" if best else ""
        out = [("  " * depth) + f"{questions[h]['text']} ({q.state}).{answer}"]
        for s in q.subquestions:
            out += q_line(s, depth + 1)
        return out

    roots = [h for h, q in questions.items() if not any(p in questions for p in q["parents"])]
    out = [("Questions", [line for h in sorted(roots, key=lambda h: questions[h]["created"])
                          for line in q_line(h, 0)])]
    out.append(("Principal results", [
        f"{d['statement']} Reproduced by {plural(d['independent'], 'independent lab')}; "
        f"{plural(d['dependents'], 'claim rests', 'claims rest')} on it." for d in digest(store, ITEMS)]))
    refuted = []
    for h, s in statuses.items():
        if s.state in BROKEN:
            r = next(r for r in s.reviews if r["verdict"] == s.state)
            found = r["note"].strip().splitlines()[-1] if r["note"].strip() else ""
            refuted.append(f"{claims[h]['statement']} {s.state.capitalize()}: {r['method']}"
                           + (f", which gave: {found}." if found else "."))
    out.append(("Refuted and superseded", refuted[:ITEMS]))
    out.append(("Dead ends", [c["statement"] for h, c in claims.items()
                              if c["kind"] == "negative" and statuses[h].label not in BROKEN][:ITEMS]))
    out.append(("Open conjectures", [c["statement"] for h, c in claims.items()
                                     if c["kind"] == "conjecture" and statuses[h].label == "proposed"][:ITEMS]))
    out.append(("At risk", [f"{claims[h]['statement']} Rests on {plural(len(s.at_risk_because), 'claim')} no "
                            f"longer standing." for h, s in statuses.items() if s.label == "at-risk"][:ITEMS]))
    return counts, [(t, items) for t, items in out if items]


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
    if c["questions"]:
        if c["questions"] == 1:
            text += f" The question is {'answered' if c['answered'] else 'open'}."
        else:
            text += f" {c['answered']} of the {c['questions']} questions {'is' if c['answered'] == 1 else 'are'} answered."
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
        out.append(f'  "{h[:10]}" [shape=box, fillcolor="{"palegreen" if qs[h].state == "answered" else "lightblue"}", '
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
