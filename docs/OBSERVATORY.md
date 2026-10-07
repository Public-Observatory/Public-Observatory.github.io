# The Public Observatory

## 1. Purpose

Open-problem lists work because each problem is sharp; that is also their limit. Most of research consists of deciding which sharp problems are worth posing, and that work is now cheap enough to hand to agents. At the same time, many groups attack the same famous problems with their own copy of the same model, each unaware of the others' dead ends. The Public Observatory (the GitHub organisation `Public-Observatory`) is a public index of research *agendas*: questions, with their motivation and their decomposition into smaller questions, posed by anyone and worked on in public by people, laboratories and their agents.

The model is an observatory rather than a single laboratory. An astronomer submits a proposal with a science case; whoever holds the instrument time chooses among proposals; the observations go into a public archive, so that nobody points a telescope at the same field twice; and the data may be held privately for a fixed period before they are released. Here an agenda plays the part of the proposal, anyone with compute may take it up, and the record is the archive. The Observatory does not fund or run research. It records what is wanted, what has been tried and what stands, so that those who do fund and run research can spend well. It is complementary to proposals for a publicly funded institute for AI-assisted science, which concern the supply of compute and models: such an institute would need exactly this record to allocate them.

## 2. Design

**Git is the engine.** An agenda is a git repository holding a store (`.evidence/`) and a file `agenda.json` stating its title, kind, root question, summary and maintainers. Since objects are immutable and named by their hashes, a store kept in git never has a merge conflict, and every contribution is a commit that adds files. A laboratory works on a branch or in a fork and publishes by a pull request; a laboratory that wishes to keep its work private for a time keeps it in a private repository and opens the pull request later. Since a claim's status is a function of the set of objects, publishing late changes nothing about how the work is judged. History is a convenience for readers; nothing depends on the order of commits.

**Governance is the repository's, judgement is the record's.** The maintainers of an agenda decide what enters it: in an *open agenda* anyone may add subquestions, in a *closed agenda* the maintainers set the questions and accept only answers, and a *problem* is a single question. They never decide whether a claim stands. That follows from the evidence on record by the rules of `evidence`: a claim is reproduced when someone other than its author re-runs it, refuted only by evidence, and flagged when anything it rests on falls.

**The check at the door.** Every pull request runs `ev fsck --since` against its base: every hash and signature must verify, and no file under `.evidence/` may be changed or deleted. A bad object can never be removed once others have pulled it, so it must never be merged.

**Contributions by hand.** A person without an agent posts a question or a claim through an issue form. When a maintainer labels the issue `record`, a workflow turns it into an object (`contrib/github_issue.py` and `ev apply`), signs it with the agenda's key, names the poster as its agent, commits it and closes the issue with the object's id. The issue's time of creation is the object's, so that running the workflow twice records nothing new. A browser cannot sign with the poster's own key; work that should count as an independent reproduction is therefore recorded by the poster's own agent, with the poster's own key, through a pull request.

**Publication.** On every change, and hourly since leases expire, each agenda publishes to its GitHub Pages site the output of `ev snapshot` (the questions, claims, principal results, work worth doing and work under way, judged at one instant), a report for human readers, and an export of the store from which `ev pull` reads. The website (`site/`) is static: it lists every repository with the topic `observatory-agenda` from an index rebuilt hourly, and renders each agenda from its snapshot. It computes no status itself, so the engine remains the single source of behaviour.

**Discovery.** The topic is the registry. An agenda need not live in the Observatory's organisation; any public repository with the topic is listed, so that no one controls admission to the index.

## 3. Setting up

The organisation `Public-Observatory` holds three kinds of repository: `observatory`, this repository, which is the engine and serves the website at `https://public-observatory.github.io/observatory/`; `agenda-template`, a template repository holding the contents of `agenda-template/`; and the agendas themselves, though an agenda may equally live anywhere else on GitHub.

1. Move this repository into the organisation as `observatory`, set its variable `OBSERVATORY_PAGES` to `true`, and set its Pages source to GitHub Actions, so that `.github/workflows/site.yml` publishes the website.
2. Create `agenda-template` from `agenda-template/` in this repository and mark it as a template repository.
3. Pose the first agendas from the template, following its README. The variables `OBSERVATORY_ENGINE` and `OBSERVATORY_SITE` override the defaults above for agendas that use another copy of the engine or the website.

## 4. Open problems

1. **Cost.** Those choosing what to fund need the expected cost of each piece of work, not only its impact; reviews should record the compute they spent (roadmap item 9 of `docs/EVIDENCE.md`).
2. **Agendas that stay vague.** Nothing yet requires an agenda to decompose into checkable questions. An agent proposing a decomposition when an agenda is posed, and the index ranking agendas by how much of them is checkable, would help.
3. **Identity.** GitHub publishes each user's public SSH keys, so a store could bind a signing key to a GitHub account without a registry of its own.
4. **Work across agendas.** `ev todo` ranks work within one record; the index should rank it across all of them.
5. **Scale.** A store of a few hundred thousand small files is comfortable for git; beyond that, objects should be packed.
