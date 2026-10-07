// The Observatory's pages. Everything shown comes from agendas.json, written by build.py from each
// agenda's agenda.json and its issues. Text from issues is untrusted, so it is only ever inserted as
// text, never as HTML. Mathematics in it, written as LaTeX between $...$ or $$...$$, is then typeset by
// KaTeX, which builds its own markup from the text and, with `trust` off, follows no links.
"use strict";

const Observatory = (() => {
  const MARK = { open: "○", answered: "✓" };
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

  // Markdown links [text](https://...) in untrusted text become anchors, and only https links do; any other
  // bracketed text stays as written. With `links` off (inside a card, itself a link) only the label is kept.
  const LINK = /\[([^\]\n]+)\]\((\S+?)\)/g;
  function rich(text, links = true) {
    const out = [];
    let last = 0;
    for (const m of String(text).matchAll(LINK)) {
      if (!links || safe(m[2])) {
        out.push(text.slice(last, m.index), links ? h("a", { href: m[2], rel: "noopener" }, m[1]) : m[1]);
        last = m.index + m[0].length;
      }
    }
    out.push(text.slice(last));
    return out;
  }

  // Without KaTeX, if its CDN cannot be reached, the LaTeX is left as it was written.
  function typeset(el) {
    if (!window.renderMathInElement) return;
    renderMathInElement(el, { throwOnError: false, trust: false,
      delimiters: [{ left: "$$", right: "$$", display: true }, { left: "$", right: "$", display: false },
                   { left: "\\[", right: "\\]", display: true }, { left: "\\(", right: "\\)", display: false }] });
    // As in TeX, punctuation after a formula stays on the formula's line.
    for (const k of el.querySelectorAll(".katex")) {
      if (k.closest(".katex-display")) continue;
      let node = k;
      while (!node.nextSibling && node.parentNode !== el && node.parentNode.childNodes.length === 1) node = node.parentNode;
      const t = node.nextSibling, m = t && t.nodeType === Node.TEXT_NODE && /^[.,;:!?)\]]+/.exec(t.data);
      if (!m) continue;
      t.data = t.data.slice(m[0].length);
      const span = h("span", { class: "nowrap" });
      node.replaceWith(span);
      span.append(node, m[0]);
    }
  }

  async function json(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  // A native <select> opens the operating system's menu, which no stylesheet reaches. This draws the
  // menu in the page's own style and keeps the <select>, hidden, as the source of truth: choosing an
  // option sets its value and fires its "change", so listeners and the page without JavaScript work.
  function menu(select) {
    const options = [...select.options];
    const label = h("span", {}, select.selectedOptions[0].text);
    const button = h("button", { type: "button", class: "menu-button", "aria-haspopup": "listbox", "aria-expanded": "false", "aria-label": select.getAttribute("aria-label") }, label);
    const list = h("ul", { class: "menu-list", role: "listbox", tabindex: "-1", hidden: true });
    const items = options.map((o, i) => h("li", { role: "option", id: `${select.id}-${i}`, "aria-selected": String(o.selected), onclick: () => choose(i), onmousemove: () => focus(i) }, o.text));
    list.append(...items);
    let active = select.selectedIndex;

    function focus(i) {
      active = (i + items.length) % items.length;
      items.forEach((it, j) => it.classList.toggle("active", j === active));
      list.setAttribute("aria-activedescendant", items[active].id);
      items[active].scrollIntoView({ block: "nearest" });
    }
    function toggle(open) {
      list.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      if (open) { focus(select.selectedIndex); list.focus(); }
    }
    function choose(i) {
      toggle(false);
      button.focus();
      if (i === select.selectedIndex) return;
      select.selectedIndex = i;
      label.textContent = options[i].text;
      items.forEach((it, j) => it.setAttribute("aria-selected", String(j === i)));
      select.dispatchEvent(new Event("change"));
    }

    button.addEventListener("click", () => toggle(list.hidden));
    button.addEventListener("keydown", (ev) => {
      if (["ArrowDown", "ArrowUp"].includes(ev.key)) { ev.preventDefault(); toggle(true); }
    });
    list.addEventListener("keydown", (ev) => {
      const keys = { ArrowDown: () => focus(active + 1), ArrowUp: () => focus(active - 1), Home: () => focus(0), End: () => focus(items.length - 1),
        Enter: () => choose(active), " ": () => choose(active), Escape: () => { toggle(false); button.focus(); }, Tab: () => toggle(false) };
      if (!keys[ev.key]) return;
      if (ev.key !== "Tab") ev.preventDefault();
      keys[ev.key]();
    });
    const wrap = h("div", { class: "menu" }, button, list);
    document.addEventListener("click", (ev) => { if (!wrap.contains(ev.target)) toggle(false); });
    select.hidden = true;
    select.after(wrap);
  }

  // ------------------------------------------------------------------ the index

  async function index() {
    menu(document.getElementById("sort"));
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
        h("p", { class: "question" }, rich(a.question, false)),
        h("p", { class: "summary" }, rich(a.summary, false)),
        h("div", { class: "bar", title: `${s.answered} of ${s.questions} questions answered` },
          h("span", { style: `width:${pct}%` })),
        h("div", { class: "foot" },
          h("span", {}, `${s.answered}/${s.questions} questions answered`),
          h("span", {}, plural(s.claims, "claim")),
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
      typeset(cards);
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
    document.title = `${entry.agenda.title} · The Public Observatory`;
    main.replaceChildren(...render(entry));
    typeset(main);
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
      h("p", { class: "question" }, rich(a.question)),
      h("p", { class: "summary" }, rich(a.summary)),
      h("div", { class: "note" }, "Maintained by ", a.maintainers.map((m, i) => [i ? ", " : "",
        github ? h("a", { href: `https://github.com/${m}` }, m) : m])),
      h("div", { class: "actions" },
        github && h("a", { class: "button primary", href: form("question.yml", {}) }, "Pose a question"),
        github && h("a", { class: "button", href: form("claim.yml", {}) }, "Record a claim"),
        github && h("a", { class: "button", href: github }, "Repository")));

    const stats = h("div", { class: "stats" },
      [[`${s.answered}/${s.questions}`, "questions answered"], [s.claims, "claims"], [s.contributors, "contributors"]]
        .map(([n, label]) => h("div", { class: "stat" }, h("b", {}, n), h("span", {}, label))));

    // The tree of questions: a question whose parents are not in the agenda is a root.
    const roots = entry.questions.filter((q) => !q.parents.some((p) => questions[p]));
    const seen = new Set();
    function node(q) {
      if (seen.has(q.number)) return h("li", { class: "q note" }, `(see #${q.number} above)`);
      seen.add(q.number);
      const li = h("li", { class: "q" },
        h("div", { class: "q-line" }, mark(q.status), h("div", { class: "q-text" }, rich(q.text)), chip(q.status)),
        h("div", { class: "q-meta" }, link(q),
          github && h("a", { href: form("claim.yml", { answers: `#${q.number}` }) }, "answer it")),
        (answers[q.number] || []).length ? h("div", { class: "answers" }, answers[q.number].map((c) =>
          h("div", { class: "answer" }, h("span", { class: "text" }, rich(c.text)), h("span", { class: "note" }, c.author, " · ", link(c))))) : null);
      const subs = entry.questions.filter((x) => x.parents.includes(q.number));
      if (subs.length) li.append(h("ul", {}, subs.map(node)));
      return li;
    }
    const tree = h("section", {}, h("h2", {}, "Questions", h("small", {}, plural(s.questions, "question"))),
      roots.length ? h("ul", { class: "tree" }, roots.map(node))
                   : h("p", { class: "note" }, "No questions yet. Pose the first subquestion."));

    const list = (title, items, row, none) => h("section", {}, h("h2", {}, title),
      items.length ? h("ul", { class: "list" }, items.map(row)) : h("p", { class: "note" }, none));
    const claimRow = (c) => h("li", {}, h("div", { class: "text" }, rich(c.text)),
      h("div", { class: "why" }, c.author, " · ", link(c), c.comments ? ` · ${plural(c.comments, "comment")}` : ""));

    // A claim that answers an answered question is shown under that question, and only there.
    const settled = (c) => c.answers.some((n) => questions[n] && questions[n].status === "answered");
    const claims = list("Claims", entry.claims.filter((c) => !settled(c)), claimRow, entry.claims.length
      ? "Every claim answers an answered question and is shown under it."
      : "No claims yet. A failed approach is worth recording too: it saves the next person the trouble.");
    const contribute = h("section", {}, h("h2", {}, "How to contribute"),
      h("p", { class: "note" }, "Pose a question or record a claim with the buttons above: state the question or the claim, and everything else is optional. A failed approach is a claim too, so that nobody repeats it. Anyone may check a claim and say in its issue what they did and what happened."));

    return [head, stats, h("div", { class: "layout" },
      h("div", {}, tree, claims),
      h("aside", {}, contribute))];
  }

  return { index, agenda };
})();
