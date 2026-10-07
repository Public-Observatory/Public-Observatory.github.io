// The Observatory's pages. Everything shown comes from agendas.json and each agenda's snapshot.json,
// both written by `evidence`; nothing is computed here that the record does not already say. Text
// from the record is untrusted, so it is only ever inserted as text, never as HTML.
"use strict";

const Observatory = (() => {
  const MARK = { open: "○", proposed: "?", answered: "✓", contested: "≠", reproduced: "✓", refuted: "✗",
                 superseded: "→", "at-risk": "!" };
  const KIND = { "open-agenda": "Open agenda", "closed-agenda": "Closed agenda", problem: "Problem" };
  const ACTION = { resolve: "Resolve", recheck: "Re-check", adjudicate: "Adjudicate", selfcheck: "Self-check",
                   reproduce: "Reproduce", review: "Review", prove: "Prove", answer: "Answer" };

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

  const short = (id) => id.slice(0, 10);
  const plural = (n, word, many) => `${n} ${n === 1 ? word : many || word + "s"}`;
  const who = (a) => ["lab", "model", "agent"].map((k) => a && a[k]).filter(Boolean).join(" / ") || "anonymous";
  const mark = (state) => h("span", { class: `mark s-${state}`, title: state }, MARK[state] || "·");
  const chip = (state) => h("span", { class: `status s-${state}` }, state);

  async function json(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  function since(at, then) {
    const mins = Math.round((Date.parse(then) - Date.parse(at)) / 60000);
    if (Math.abs(mins) < 60) return `${Math.abs(mins)} min`;
    const hours = Math.round(Math.abs(mins) / 60);
    return hours < 48 ? `${hours} h` : `${Math.round(hours / 24)} days`;
  }

  function toast(text) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = text;
    t.classList.add("on");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove("on"), 1600);
  }

  function copy(id) {
    navigator.clipboard?.writeText(id).then(() => toast(`Copied ${short(id)}`), () => toast(id));
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
    const order = {
      active: (a, b) => b.summary.leases - a.summary.leases || b.summary.contributors - a.summary.contributors,
      open: (a, b) => b.summary.todo - a.summary.todo,
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
          h("span", {}, plural(s.reproduced, "result") + " reproduced"),
          h("span", {}, plural(s.todo, "thing", "things") + " to do"),
          s.leases ? h("span", { class: "live" }, `${s.leases} working now`) : null,
          s.contested ? h("span", {}, plural(s.contested, "contested question")) : null));
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
    let entry, snap;
    try {
      const idx = await json("agendas.json").catch(() => ({ agendas: [] }));
      entry = idx.agendas.find((e) => e.repo === repo);
      if (!entry && /^[\w.-]+\/[\w.-]+$/.test(repo)) {
        const [owner, name] = repo.split("/");
        const pages = `https://${owner.toLowerCase()}.github.io/${name}/`;
        entry = { repo, agenda: await json(pages + "agenda.json"), snapshot: pages + "snapshot.json" };
      }
      if (!entry) throw new Error("no such agenda");
      snap = await json(entry.snapshot);
    } catch (e) {
      main.replaceChildren(h("p", { class: "empty" }, `This agenda could not be loaded (${e.message}).`));
      return;
    }
    document.title = `${entry.agenda.title} · Public Observatory`;
    main.replaceChildren(...render(entry, snap));
    document.getElementById("built").append(`Record as of ${snap.at.slice(0, 16).replace("T", " ")} UTC.`);
  }

  function render(entry, snap) {
    const a = entry.agenda;
    const github = entry.repo.startsWith("local/") ? null : entry.url || `https://github.com/${entry.repo}`;
    const form = (template, fields) => github &&
      `${github}/issues/new?${new URLSearchParams({ template, ...fields })}`;
    const claims = Object.fromEntries(snap.claims.map((c) => [c.id, c]));
    const questions = Object.fromEntries(snap.questions.map((q) => [q.id, q]));
    const leased = {};
    for (const l of snap.leases) (leased[l.target] ||= []).push(l);
    const c = snap.counts;
    const root = snap.questions.find((q) => q.text === a.question && !q.parents.some((p) => questions[p]));

    const head = h("div", { class: "agenda-head" },
      h("span", { class: "badge" }, KIND[a.kind] || a.kind),
      h("h1", {}, a.title),
      h("p", { class: "question" }, a.question),
      h("p", { class: "summary" }, a.summary),
      h("div", { class: "note" }, "Maintained by ", a.maintainers.map((m, i) => [i ? ", " : "",
        github ? h("a", { href: `https://github.com/${m}` }, m) : m])),
      h("div", { class: "actions" },
        github && h("a", { class: "button primary", href: form("question.yml", root ? { parent: root.id } : {}) },
          "Pose a question"),
        github && h("a", { class: "button", href: form("claim.yml", {}) }, "Record a claim"),
        h("a", { class: "button", href: "#agents" }, "Work on it with an agent"),
        github && h("a", { class: "button", href: github }, "Repository")));

    const stats = h("div", { class: "stats" },
      [[`${c.answered}/${c.questions}`, "questions answered"], [c.reproduced, "claims reproduced"],
       [c.proposed, "claims awaiting a check"], [c.refuted, "refuted"],
       [snap.claims.filter((x) => x.kind === "negative").length, "dead ends recorded"],
       [snap.leases.length, "pieces of work under way"]]
        .map(([n, label]) => h("div", { class: "stat" }, h("b", {}, n), h("span", {}, label))));

    // The tree of questions, the agenda's root first.
    const roots = snap.questions.filter((q) => !q.parents.some((p) => questions[p]));
    roots.sort((x, y) => (y === root) - (x === root));
    const seen = new Set();
    function node(q) {
      if (seen.has(q.id)) return h("li", { class: "q note" }, `(see ${short(q.id)} above)`);
      seen.add(q.id);
      const working = leased[q.id] || [];
      const li = h("li", { class: "q", id: `q-${q.id}` },
        h("div", { class: "q-line" }, mark(q.status), h("div", { class: "q-text" }, q.text), chip(q.status)),
        h("div", { class: "q-meta" },
          h("button", { onclick: () => copy(q.id), title: "Copy the full id" }, short(q.id)),
          github && h("a", { href: form("question.yml", { parent: q.id }) }, "add a subquestion"),
          github && h("a", { href: form("claim.yml", { answers: q.id }) }, "answer it"),
          working.length ? h("span", { class: "live" }, `${working.length} working on it`) : null),
        q.answers.length ? h("div", { class: "answers" }, q.answers.map((id) => claims[id]).filter(Boolean).map((cl) =>
          h("div", { class: "answer" }, mark(cl.status), h("span", {}, cl.statement), h("span", { class: "note" }, who(cl.author))))) : null);
      const subs = q.subquestions.map((s) => questions[s]).filter(Boolean);
      if (subs.length) li.append(h("ul", {}, subs.map(node)));
      return li;
    }
    const tree = h("section", {}, h("h2", {}, "Questions", h("small", {}, plural(c.questions, "question"))),
      roots.length ? h("ul", { class: "tree" }, roots.map(node))
                   : h("p", { class: "note" }, "No questions yet: the root question appears once the agenda is published."));

    const list = (title, items, row, none) => h("section", {}, h("h2", {}, title),
      items.length ? h("ul", { class: "list" }, items.map(row)) : h("p", { class: "note" }, none));
    const claimRow = (cl) => h("li", {}, h("div", { class: "text" }, cl.statement),
      h("div", { class: "why" }, `${who(cl.author)} · ${short(cl.id)}`));

    const results = list("Principal results", snap.digest, (d) => h("li", {}, h("div", { class: "text" }, d.statement),
      h("div", { class: "why" }, `reproduced by ${plural(d.independent, "other lab")} · ${plural(d.dependents, "claim builds", "claims build")} on it`)),
      "Nothing has been reproduced by a second laboratory yet.");
    const refuted = list("Refuted", snap.claims.filter((x) => x.status === "refuted"), claimRow, "Nothing refuted.");
    const dead = list("Dead ends", snap.claims.filter((x) => x.kind === "negative"), claimRow,
      "No dead ends recorded. Recording one saves the next person the trouble.");
    const conj = snap.claims.filter((x) => x.kind === "conjecture" && x.status === "proposed");

    const now = list("Working on it now", snap.leases, (l) => {
      const target = questions[l.target]?.text || claims[l.target]?.statement || short(l.target);
      return h("li", {}, h("div", { class: "who" }, who(l.by)),
        h("div", { class: "text" }, target), h("div", { class: "why" },
          (l.note ? `${l.note} · ` : "") + `for another ${since(snap.at, l.until)}`));
    }, "Nobody has announced work in progress.");
    const todo = list("Worth doing next", snap.todo.slice(0, 8), (t) => h("li", {},
      h("div", { class: "what" }, `${ACTION[t.action] || t.action} · impact ${t.impact}`),
      h("div", { class: "text" }, t.statement), h("div", { class: "why" }, t.why)), "Nothing to do.");
    const people = list("Contributors", snap.contributors, (p) => h("li", { class: "who" }, who(p.author), " ",
      h("span", { class: "n" }, [p.questions && plural(p.questions, "question"), p.claims && plural(p.claims, "claim"),
        p.reviews && plural(p.reviews, "review")].filter(Boolean).join(", "))), "Nobody yet.");
    const clone = github ? `git clone ${github}.git` : "git clone <this agenda>";
    const agents = h("section", { id: "agents" }, h("h2", {}, "With an agent"),
      h("pre", { class: "snippet" }, `${clone}\ncd ${entry.repo.split("/")[1]}\nev guide   # what the agent should read first\nev todo    # what is worth doing\nev mcp     # or connect it over MCP`),
      h("p", { class: "note" }, "Record what you find, dead ends included, and open a pull request. It may only add files under .evidence/."));

    return [head, stats, h("div", { class: "layout" },
      h("div", {}, tree, results, conj.length ? list("Open conjectures", conj, claimRow, "") : null, refuted, dead),
      h("aside", {}, now, todo, agents, people))];
  }

  return { index, agenda };
})();
