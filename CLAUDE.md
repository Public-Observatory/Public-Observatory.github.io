# observatory

This repository (`Public-Observatory/observatory` on GitHub) holds two things: `evidence`, version control for science done by AI agents (the Python package and the `ev` command), and the Public Observatory, a public index of research agendas built on it. Read `VISION.md` for the Observatory's aim, `docs/EVIDENCE.md` for the engine's thesis and roadmap, `docs/OBSERVATORY.md` for the Observatory's design, and `README.md` for the user-facing model before changing behaviour.

## Commands

```sh
python3 -m unittest discover -s tests                   # all tests, about ten seconds
EV_SEEDS=50 python3 -m unittest tests.test_properties   # more random histories
EV_SCALE=20000 python3 -m unittest tests.test_properties.ScaleTest
sh demo/run.sh                                          # end-to-end story with two signed labs
python3 bench/planted.py setup DIR && python3 bench/planted.py baseline DIR   # the agent benchmark
PYTHONPATH=. python3 -m evidence <command>              # run without installing
uv run --no-project --python 3.10 python -m unittest discover -s tests       # the oldest supported Python
```

## Layout

- `evidence/store.py`: the data model. Object schema and validation, the dependency `Graph` (ancestors and descendants as integer bitsets), recording (`ask`, `claim`, `review`, `withdraw`, `lease`, `release`, signing in `_record`), `verify`, statuses of claims (reviewers' positions, counter-claims as a least fixed point, disputes) and questions, `leases`, `search`, `todo`, `pull`, signature checks, `fsck`.
- `evidence/signing.py`: SSH signatures through `ssh-keygen -Y`.
- `evidence/sandbox.py`: how `verify` isolates commands (seatbelt, bwrap, docker, none).
- `evidence/remote.py`: sources for `pull` (store on disk, HTTP, git) and the read-only HTTP server.
- `evidence/batch.py`: `ev apply`, a run handed over as JSON Lines with local refs, recorded atomically through `Store.ask/claim/review` inside `Store.staged`. `contrib/runs.py` is a worked example of an adapter.
- `evidence/cli.py`: thin argparse layer. Every read command takes `--json`.
- `evidence/mcp.py`: MCP server over stdio; each tool maps to CLI arguments, so the CLI is the single source of behaviour.
- `evidence/report.py`: digest, Markdown and LaTeX reports, Graphviz output. `evidence/guide.py`: the agent instructions.
- `evidence/palomar.py`: importer for the Palomar registry of Lean-verified mathematics. Network access goes through an injectable `fetch`, so tests use a dict.
- `site/`: the Observatory's static website; `build.py` builds its index of agendas.
- `agenda-template/`: a new agenda's repository, published as the template repository `Public-Observatory/agenda-template` (workflows that check pull requests with `ev fsck --since`, record issue forms, and publish `ev snapshot` to Pages).
- `contrib/`: scripts outside the package. `agenda.py` checks `agenda.json` and seeds the root question, and `github_issue.py` turns an issue form into a batch; the agenda workflows call both. `runs.py` is a worked example of a harness adapter.
- `bench/planted.py`: benchmark with planted errors, dead ends and questions, a scripted baseline, and a scorer.
- `tests/`: one file per module, plus `test_cli.py` (argv in, JSON and exit codes out), `test_mcp.py` (a JSON-RPC session), and `test_properties.py` (random multi-lab histories against a brute-force oracle, merge convergence, scale).

## Invariants

Do not break these; the tests guard most of them.

- Objects are immutable and named by the SHA-256 of their canonical JSON. Never edit or delete an object; record a new one. Optional fields are omitted when empty so that existing ids do not change. Changing what goes into an object (field names, evidence layout, Palomar's `to_claim`) changes ids, so say so in the commit message.
- A claim's state is a pure function of the set of objects. Hence `pull` (set union) is commutative, associative and idempotent, and labs that have exchanged everything agree. Only the *trusted* count depends on local configuration. Nothing may depend on file order, the clock at read time, or other local state.
- The one, narrow exception to the clock: leases. Whether a lease holds depends on the time, so `Store.leases` and `Store.todo` take the reference time as an argument and never read the clock; only `cli.py` supplies "now" (`ev todo --at` overrides it). Leases affect nothing but the order of `todo` and its `leased` field: never a status, `check`, a question's state, a report, or the property-test oracle.
- Validate at the boundary: `pull` refuses, before writing anything, any object with a bad hash, a malformed structure (`invalid`), or a key without a valid signature. A bad object can never be removed, so it must never get in. Unknown object types are accepted and ignored, for forward compatibility.
- Only evidence can refute. A failure of the environment (setup step, timeout, missing program, sandbox denial) is `inconclusive` and never changes a status. A refutation or supersession by anyone but the claim's author without evidence (a failed run of the claim's command, or a standing counter-claim with a command) does not change a status either: it marks the claim disputed. A reproduction by the claim's own author is a self-check, not a reproduction, and each reviewer's latest decisive review of a claim is their only position on it.
- `verify` never runs another lab's command unsandboxed unless explicitly told `--unsafe`. Tests that verify across labs pass `unsafe=True` so they behave the same on machines without a sandbox.
- Imports are deterministic: two labs importing the same external entry produce the same id.
- No runtime dependencies. Standard library only, Python 3.10+. External programs (`ssh-keygen`, `sandbox-exec`, `bwrap`, `docker`, `git`) are optional and their tests skip when absent.
- Exit codes are an API for agents: 0 success, 1 a negative finding (`check` found claims at risk, `verify` refuted), 2 usage error, 3 `verify` inconclusive.

## Style

- Terse code with docstrings that explain why, not what. Match the surrounding density.
- Prose (README, docstrings, help text, generated reports) should read like a top mathematical journal: precise, plain, grammatical, no hype.
- Any LaTeX source goes on one line per paragraph.
- New commands need a `--json` form if they read, a test in `tests/test_cli.py`, an MCP tool if an agent would use them, a line in the README, and, if they change how an agent should work, an update to `evidence/guide.py`.

## Direction

The aim is infrastructure on which autonomous agents do the exploratory work of science, with humans reading only the report. Judge changes by whether they help an agent (1) avoid repeating work (`search`), (2) choose the most valuable next step (`todo`), (3) trust other labs' work for the right reasons (independent, signed, sandboxed reproduction), (4) learn quickly when the ground under its work has moved (`check`), and (5) help humans read only what matters (`report`).

Open problems, roughly in order:

1. Run real agents on `bench/planted.py` (several models, several runs each) and fix whatever they stumble on; add harder worlds (ML experiments, Lean proofs).
2. Better search: the bag-of-words ranking misses paraphrases. Embeddings would need a dependency or a service; consider an optional hook.
3. Discovery: a way to find other labs' stores (a registry, or stores announcing their remotes).
4. Cost accounting: reviews recording compute spent, so that `todo` can weigh impact against cost.
5. Revocation of a compromised key, and key rotation for a lab.
