# The Public Observatory

A public index of research agendas: questions, with their motivation and their decomposition into smaller questions, posed by anyone and worked on in public by people, laboratories and their agents. The website is at <https://public-observatory.github.io/>. `VISION.md` says what the Observatory is for.

## How it works

**An agenda is a git repository.** It holds `agenda.json`, which states the agenda's title, kind, root question, summary and maintainers, and a README giving its motivation, scope and standard of evidence. A new agenda is created from the template repository `Public-Observatory/agenda-template`, whose contents are `agenda-template/` here.

**Questions and claims are issues.** Each agenda has two issue forms. A question may name the larger question it helps to settle; a claim names the questions it answers and the claims it builds on, by issue number, and is a `result`, a `negative` result (an approach that did not work) or a `conjecture`. Code, data and proofs arrive as pull requests that the claim links to.

**Maintainers govern by stated rules.** In an *open agenda* anyone may add subquestions; in a *closed agenda* the maintainers set the questions and accept only answers; a *problem* is a single question. A maintainer labels a claim `reproduced` once someone other than its author has checked it, and `refuted` only when the refutation can itself be checked, and closes a question once it is answered.

**The index is the topic.** Every public repository with the topic `observatory-agenda` is listed, wherever it lives, so that no one controls admission. Every hour, `site/build.py` searches GitHub for the topic, reads each agenda's `agenda.json` and issues, and writes `agendas.json`; the static pages in `site/` render it. An agenda whose files cannot be read is left out and reported.

## Layout

```
VISION.md          what the Observatory is for
site/              the website: index.html, agenda.html, observatory.js and .css;
                   build.py builds agendas.json; agenda.py checks an agenda.json
agenda-template/   a new agenda's repository: agenda.json, README, issue forms, and a
                   workflow that checks agenda.json on every pull request
tests/             tests of site/agenda.py and site/build.py
```

## Development

```sh
python3 -m unittest discover -s tests                          # the tests; standard library only, Python 3.10+
python3 site/agenda.py check agenda-template/agenda.json       # exit 1, with the reasons, if malformed
mkdir -p _site && cp site/*.html site/*.css site/*.js _site/
python3 site/build.py local _site DIR...                       # index agendas in local directories, for a preview
python3 -m http.server -d _site                                # and serve it
```

A local agenda directory holds `agenda.json` and, optionally, `issues.json`, a list of issues as the GitHub API returns them. An agenda's check fetches `site/agenda.py` from this repository; the agenda's variable `OBSERVATORY_REPO` points it at another copy.
