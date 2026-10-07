// The Observatory's pages. Everything shown comes from agendas.json, written by build.py from each
// agenda's agenda.json and its issues. Text from issues is untrusted, so it is only ever inserted as
// text, never as HTML.
"use strict";

const Observatory = (() => {
  const MARK = { open: "○", proposed: "?", answered: "✓", reproduced: "✓", refuted: "✗" };
  const KIND = { "open-agenda": "Open agenda", "closed-agenda": "Closed agenda", problem: "Problem" };

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat(Infinity)) {
      if (c === undefined || c === null || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  const plural = (n, word, many) => `${n} ${n === 1 ? word : many || word + "s"}`;
  const mark = (state) => h("span", { class: `mark s-${state}`, title: state }, MARK[state] || "·");
  const chip = (state) => h("span", { class: `status s-${state}` }, state);
  const safe = (url) => (/^https:\/\//.test(url || "") ? url : null);

  async function json(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------------ the index

  async function index() {
    const cards = document.getElementById("cards");
    const empty = document.getElementById("empty");
    let data;
    try {
      data = await json("agendas.json");
    } catch (e) {
      empty.hidden = false;
      empty.textContent = "The index could not be loaded.";
      return;
    }
    const state = { q: "", kind: "", sort: "active" };
    const progress = (s) => (s.questions ? s.answered / s.questions : 0);
    const open = (s) => s.questions - s.answered;
    const order = {
      active: (a, b) => (b.pushed || "").localeCompare(a.pushed || "") || b.summary.contributors - a.summary.contributors,
      open: (a, b) => open(b.summary) - open(a.summary),
      new: (a, b) => b.agenda.created.localeCompare(a.agenda.created),
      progress: (a, b) => progress(b.summary) - progress(a.summary),
    };

    function card(e) {
      const a = e.agenda, s = e.summary;
      const pct = Math.round(100 * progress(s));
      return h("a", { class: "card", href: `agenda.html?repo=${encodeURIComponent(e.repo)}` },
        h("div", {}, h("span", { class: "badge" }, KIND[a.kind] || a.kind)),
        h("h2", {}, a.title),
        h("p", { class: "question" }, a.question),
        h("p", { class: "summary" }, a.summary),
        h("div", { class: "bar", title: `${s.answered} of ${s.questions} questions answered` },
          h("span", { style: `width:${pct}%` })),
        h("div", { class: "foot" },
          h("span", {}, `${s.answered}/${s.questions} questions answered`),
          h("span", {}, plural(s.reproduced, "claim") + " reproduced"),
          h("span", {}, plural(s.dead_ends, "dead end")),
          h("span", {}, plural(s.contributors, "contributor"))));
    }

    function render() {
      const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      const shown = data.agendas
        .filter((e) => !state.kind || e.agenda.kind === state.kind)
        .filter((e) => {
          const text = [e.agenda.title, e.agenda.question, e.agenda.summary, ...(e.agenda.tags || [])].join(" ").toLowerCase();
          return words.every((w) => text.includes(w));
        })
        .sort(order[state.sort]);
      cards.replaceChildren(...shown.map(card));
      empty.hidden = shown.length > 0;
      empty.textContent = data.agendas.length ? "No agenda matches." : "No agendas yet. Pose the first one.";
    }

    document.getElementById("q").addEventListener("input", (ev) => { state.q = ev.target.value; render(); });
    document.getElementById("sort").addEventListener("change", (ev) => { state.sort = ev.target.value; render(); });
    for (const b of document.querySelectorAll(".chip")) {
      b.addEventListener("click", () => {
        state.kind = b.dataset.kind;
        for (const o of document.querySelectorAll(".chip")) o.setAttribute("aria-pressed", String(o === b));
        render();
      });
    }
    render();
    if (data.built) document.getElementById("built").append(` Index built ${data.built.slice(0, 16).replace("T", " ")} UTC.`);
  }

  // ------------------------------------------------------------------ one agenda

  async function agenda() {
    const main = document.getElementById("main");
    const repo = new URLSearchParams(location.search).get("repo") || "";
    let data, entry;
    try {
      data = await json("agendas.json");
      entry = data.agendas.find((e) => e.repo === repo);
      if (!entry) throw new Error("no such agenda in the index");
    } catch (e) {
      main.replaceChildren(h("p", { class: "empty" }, `This agenda could not be loaded (${e.message}).`));
      return;
    }
    document.title = `${entry.agenda.title} · Public Observatory`;
    main.replaceChildren(...render(entry));
    if (data.built) document.getElementById("built").append(`As of ${data.built.slice(0, 16).replace("T", " ")} UTC.`);
  }

  function render(entry) {
    const a = entry.agenda, s = entry.summary;
    const github = entry.repo.startsWith("local/") ? null : safe(entry.url) || `https://github.com/${entry.repo}`;
    const form = (template, fields) => github && `${github}/issues/new?${new URLSearchParams({ template, ...fields })}`;
    const questions = Object.fromEntries(entry.questions.map((q) => [q.number, q]));
    const answers = {};
    for (const c of entry.claims) for (const n of c.answers) (answers[n] ||= []).push(c);
    const link = (i) => safe(i.url) ? h("a", { href: i.url }, `#${i.number}`) : `#${i.number}`;

    const head = h("div", { class: "agenda-head" },
      h("span", { class: "badge" }, KIND[a.kind] || a.kind),
      h("h1", {}, a.title),
      h("p", { class: "question" }, a.question),
      h("p", { class: "summary" }, a.summary),
      h("div", { class: "note" }, "Maintained by ", a.maintainers.map((m, i) => [i ? ", " : "",
        github ? h("a", { href: `https://github.com/${m}` }, m) : m])),
      h("div", { class: "actions" },
        github && h("a", { class: "button primary", href: form("question.yml", {}) }, "Pose a question"),
        github && h("a", { class: "button", href: form("claim.yml", {}) }, "Record a claim"),
        github && h("a", { class: "button", href: github }, "Repository")));

    const stats = h("div", { class: "stats" },
      [[`${s.answered}/${s.questions}`, "questions answered"], [s.claims, "claims"], [s.reproduced, "reproduced"],
       [s.refuted, "refuted"], [s.dead_ends, "dead ends recorded"], [s.contributors, "contributors"]]
        .map(([n, label]) => h("div", { class: "stat" }, h("b", {}, n), h("span", {}, label))));

    // The tree of questions: a question whose parents are not in the agenda is a root.
    const roots = entry.questions.filter((q) => !q.parents.some((p) => questions[p]));
    const seen = new Set();
    function node(q) {
      if (seen.has(q.number)) return h("li", { class: "q note" }, `(see #${q.number} above)`);
      seen.add(q.number);
      const li = h("li", { class: "q" },
        h("div", { class: "q-line" }, mark(q.status), h("div", { class: "q-text" }, q.text), chip(q.status)),
        h("div", { class: "q-meta" }, link(q),
          github && h("a", { href: form("question.yml", { "part-of": `#${q.number}` }) }, "add a subquestion"),
          github && h("a", { href: form("claim.yml", { answers: `#${q.number}` }) }, "answer it")),
        (answers[q.number] || []).length ? h("div", { class: "answers" }, answers[q.number].map((c) =>
          h("div", { class: "answer" }, mark(c.status), h("span", {}, c.text), h("span", { class: "note" }, c.author)))) : null);
      const subs = entry.questions.filter((x) => x.parents.includes(q.number));
      if (subs.length) li.append(h("ul", {}, subs.map(node)));
      return li;
    }
    const tree = h("section", {}, h("h2", {}, "Questions", h("small", {}, plural(s.questions, "question"))),
      roots.length ? h("ul", { class: "tree" }, roots.map(node))
                   : h("p", { class: "note" }, "No questions yet. Pose the first subquestion."));

    const list = (title, items, row, none) => h("section", {}, h("h2", {}, title),
      items.length ? h("ul", { class: "list" }, items.map(row)) : h("p", { class: "note" }, none));
    const claimRow = (c) => h("li", {}, h("div", { class: "text" }, c.text),
      h("div", { class: "why" }, c.author, " · ", link(c), c.comments ? ` · ${plural(c.comments, "comment")}` : ""));

    const reproduced = list("Reproduced", entry.claims.filter((c) => c.status === "reproduced"), claimRow,
      "Nothing has been reproduced yet.");
    const pending = list("Awaiting a check", entry.claims.filter((c) => c.status === "proposed" && c.kind !== "negative"),
      claimRow, "Nothing awaits a check.");
    const refuted = list("Refuted", entry.claims.filter((c) => c.status === "refuted"), claimRow, "Nothing refuted.");
    const dead = list("Dead ends", entry.claims.filter((c) => c.kind === "negative"), claimRow,
      "No dead ends recorded. Recording one saves the next person the trouble.");
    const contribute = h("section", {}, h("h2", {}, "How to contribute"),
      h("p", { class: "note" }, "Pose a question or record a claim through the forms above. Code, data and proofs go in a pull request that the claim links to. A maintainer labels a claim reproduced once someone other than its author has checked it, and refuted only when the refutation itself can be checked."));

    return [head, stats, h("div", { class: "layout" },
      h("div", {}, tree, reproduced, pending, refuted, dead),
      h("aside", {}, contribute))];
  }

  return { index, agenda };
})();
