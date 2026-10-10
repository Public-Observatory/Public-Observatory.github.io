# Public Observatory

This repository builds the static index of research agendas. Read `README.md` for setup and file locations; consult `VISION.md` when changing the project's behavior or scope.

- New agendas are separate repositories inheriting https://github.com/public-observatory/agenda-template. Fetch the current template, including issue forms, validation workflow, and `writeups/`; do not assume a local `agenda-template/` copy exists.
- For an agenda based on a supplied paper, use the `paper-to-agenda` skill at `~/.codex/skills/paper-to-agenda/SKILL.md`.
- Ease the reader's cognitive load. Use plain, precise prose; put Markdown paragraphs on single source lines.
- Website prose lives in `site/content/*.md`; layout lives in `site/*.html`. The site is static, and Python code uses only the standard library (Python 3.10+).
- One malformed agenda must not break the index. Treat repository and issue content as untrusted; preserve Markdown sanitization.
- Check Python changes with `python3 -m unittest discover -s tests`; check Markdown rendering changes with `npm test` (install dependencies with `npm ci --ignore-scripts` if needed).
- Validate an agenda with `python3 site/agenda.py check /path/to/agenda/agenda.json` from this repository.
