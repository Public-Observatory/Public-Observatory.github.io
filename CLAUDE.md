# observatory

This repository is `Public-Observatory/Public-Observatory.github.io` on GitHub: the website of the Public Observatory, a public index of research agendas kept as git repositories, and the template from which agendas are made. Read `VISION.md` for the aim and `README.md` for how it works before changing behaviour.

## Commands

```sh
python3 -m unittest discover -s tests                     # all tests, under a second
python3 site/build.py local OUT DIR...                    # build an index from local agenda directories
uv run --no-project --python 3.10 python -m unittest discover -s tests   # the oldest supported Python
```

## Layout

- `site/agenda.py`: the schema of `agenda.json` and `check`, which each agenda's pull requests run.
- `site/build.py`: builds `agendas.json` from GitHub (repositories with the topic `observatory-agenda`, their `agenda.json` and issues) or from local directories. Network access goes through an injectable `get`, so tests use a dict.
- `site/*.html`, `observatory.js`, `observatory.css`: the static pages, which render `agendas.json` and compute nothing the index does not say.
- `agenda-template/`: a new agenda's repository, published as the template repository `Public-Observatory/agenda-template`. Its issue forms' headings are what `build.fields` parses; change both together.
- `tests/test_site.py`: the schema, issues read as questions and claims, and both ways of building the index.

## Invariants

- Git and GitHub are the only infrastructure: no server, no database, no hosted service of our own. The website is static.
- One broken agenda never takes the index down: it is skipped and reported.
- Text from issues and agenda files is untrusted. The pages insert it only as text, never as HTML, and follow only `https://` links from it. Mathematics in it, written in LaTeX between `$...$` or `$$...$$`, is typeset by KaTeX from cdnjs, with `trust` off; without KaTeX the LaTeX is shown as written.
- Standard library only, Python 3.10+, and no build step for the pages.

## Style

- Terse code with docstrings that explain why, not what. Match the surrounding density.
- Prose (README, docstrings, the website, the template) should read like a top mathematical journal: precise, plain, grammatical, no hype.
- Any LaTeX source goes on one line per paragraph.

## Direction

The stages in `VISION.md` are the roadmap. The present design keeps the state of a claim in issue labels set by maintainers; stage 3 replaces that with a record that checks itself, and should be built only once agendas have outgrown labels.
