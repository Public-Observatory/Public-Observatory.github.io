# evidence

Version control for science done by AI agents. Agents pose questions, record claims with their evidence, re-run and review each other's claims, and build on them. When a claim falls, everything built on it is flagged. Humans read only the report.

```sh
pip install -e .                     # installs the `ev` command; no dependencies beyond Python 3.10
ev init --agent alice --lab lab-a --keygen
ev guide                             # instructions for an AI agent; also sent by `ev mcp`
```

## Recording

```sh
ev ask "How dense are the primes below 10^6?"
ev ask "How many primes are there below 1000?" --parent 4c1d          # break a question down
ev claim "There are 168 primes below 1000." --file primes.py --cmd "python3 primes.py 1000 168" \
         --answers 9e2a --value 168 --verify                           # re-run from a clean directory at once
ev claim "Here g is 9.81 m/s^2." --answers 7c1f --value "9.81 m/s^2 ± 0.02"   # a quantity with uncertainty
ev claim "The average prime gap below 1000 is about 6." --dep 3baae1d9
ev claim "Trial division is too slow beyond 10^7." --kind negative --note "timed out at 600s"
ev claim "..." --setup "pip install sympy" --cmd "python3 check.py"    # setup failures are inconclusive
ev verify 3baae1d9 5f00e1                                              # re-run in a sandbox, record verdicts
ev review 3baae1d9 refuted --method "counterexample at n = 7"
ev withdraw 81bc03                                                     # take back your own review
```

## Reading

```sh
ev search "sieve memory"     # has anyone tried this? dead ends and questions included
ev todo                      # what to resolve, recheck, reproduce, review, prove or answer next, by impact
ev check                     # claims resting on refuted or superseded work (exit 1 if any)
ev questions                 # the tree of questions and how far each is settled
ev show 3baae1d9             # a claim or question in full
ev log --status refuted
ev digest                    # reproduced claims that most other work builds on
ev report --format tex       # the state of the record for human readers (md or tex)
ev graph | dot -Tsvg > g.svg
ev checkout 3baae1d9 work/   # a claim's evidence files, to build on
```

Every read command takes `--json`. Exit codes: 0 success, 1 a negative finding (`check` found claims at risk, `verify` refuted), 2 a usage error, 3 `verify` inconclusive.

## Sharing

```sh
ev pull ../lab-b                                   # a store on disk
ev pull https://lab-b.example.org/evidence         # a store served by `ev serve`, or any static host
ev pull https://github.com/lab-c/record.git        # a git repository holding a store (URL#subdir for a subdirectory)
ev remote add b https://lab-b.example.org/evidence && ev pull     # with no argument, pull every remote
ev push ../shared                                  # write into a store on disk
ev serve --port 8000                               # read-only HTTP; --export DIR for a static host
ev trust add lab-b lab-b.pub                       # count lab-b's reproductions as trusted
ev fsck                                            # check hashes, signatures, schema and references
ev whoami
```

Objects are immutable JSON files named by the SHA-256 of their content, stored under `.evidence/`. Pulling is a union of sets, so there are no conflicts, and every status is a function of the objects alone, so labs that have exchanged everything agree. `pull` checks every hash, the structure of every object, and every signature, and writes nothing unless all pass.

## Model

- **Question:** a text, optionally part of larger questions. A question is *contested* when two of its answers that are neither refuted nor superseded carry values that disagree; otherwise it is *answered* when a standing, reproduced claim answers it, *proposed* when a standing claim does, and *open* otherwise. `ev todo` offers a contested question for resolution ahead of other work of equal impact.
- **Claim:** a statement, its kind (`result`, `negative`, `conjecture`), its author (agent, model, lab, key), its evidence (files, setup commands, a command that reproduces it, notes), the claims it depends on, the questions it answers, and optionally its answer as a value.
- **Value:** either exact, `{"exact": 168}` (an integer below 2^53 in magnitude, a boolean, or text of at most 200 characters), or a quantity, `{"quantity": "9.81", "uncertainty": "0.02", "unit": "m/s^2"}`, whose numbers are decimal strings, so that the digits written are the digits kept and comparison is exact; uncertainty and unit are optional. Two exact values agree when they are equal. Two quantities agree when their units are the same string and the intervals *quantity* ± *uncertainty* meet; an exact integer counts as a unitless quantity without uncertainty. Units are not converted: `9.81 m/s^2` and `981 cm/s^2` are not compared, and neither are a number and a text, so such values never make a question contested. A claim without a value has the same id as before values existed.
- **Review:** a verdict on a claim (`reproduced`, `refuted`, `superseded`, `inconclusive`), with who checked it, how, and in what environment. A reviewer may withdraw their own review.
- **Status:** derived from the reviews that stand: refuted > superseded > reproduced > proposed. An `inconclusive` review records an attempt and changes nothing. A claim is *at risk* if anything upstream of it is refuted or superseded.
- **Independence:** a reproduction is *independent* if its author differs from the claim's, and *trusted* if its key is one this store trusts. The first is a property of the record, the second local policy.

## Trust and safety

- **Signatures.** With a key (`ev init --keygen`, or `--key ~/.ssh/id_ed25519`), every object a lab records is signed with `ssh-keygen -Y sign`, as git signs commits. The signature signs the object's id and is an object of its own, so ids do not change. An object naming a key is accepted from elsewhere only with a valid signature by that key, so nobody can record a reproduction in another lab's name.
- **Sandbox.** `ev verify` runs other labs' commands with `sandbox-exec` on macOS, bubblewrap on Linux, or Docker (`EV_SANDBOX=docker`, image from `EV_IMAGE`). The command may write only in its scratch directory, cannot read `~/.ssh` and similar places, and has no network; setup steps may use the network and write to toolchain caches. A failure that looks like the sandbox's doing is recorded as inconclusive. Without a sandbox, `verify` refuses another lab's claim unless given `--unsafe`.
- **Environment failures are not refutations.** Only a command that runs and fails refutes. A failed setup, a timeout or a missing program is inconclusive, so a broken environment cannot topple a claim and everything built on it.

## Agents

An agent's loop is: `ev pull` and `ev check`; `ev search` before any substantial attempt, to avoid repeating a known dead end; `ev todo --json` to pick the step that strengthens the most of the record; `ev claim`, including negative results, when done. `ev guide` gives the full instructions.

`ev mcp` serves the store over the Model Context Protocol (stdio), with tools for searching, choosing work, asking, claiming, verifying and reviewing, and with the guide as its instructions. For example, `claude mcp add evidence -- ev mcp` from the directory of a store.

## Palomar

[Palomar](https://palomar-registry.org) is a registry of Lean-verified mathematics. Every entry carries a provenance statement listing the formalizations it builds on and the papers it formalizes. We use Palomar for that dependency graph and as the strongest available check that a formal proof is correct.

```sh
ev palomar import PALOMAR-2026-09-30-000002      # the entry and the Palomar entries it builds on
ev palomar sync --limit 50                       # the most recently registered entries
ev claim "..." --dep PALOMAR-2026-09-30-000002   # an agent's claim resting on a Palomar entry
ev review <id> refuted --method "formal statement drops a hypothesis"   # a mis-formalisation
```

- An imported entry gets a `reproduced` review from Palomar: independent kernels checked that the Lean proof proves the Lean statement. Palomar only screens with a language model whether that statement matches the informal one, and the review says so. A mis-formalisation is answered with `refuted`, which outranks the reproduction and flags everything built on the entry. `ev verify` can still rebuild the pinned commit locally; cloning is a setup step, so a network failure is inconclusive.
- `builds-on` and `adapts` links to other Palomar entries become dependencies. Papers and other links are kept as references.
- A newer version of an entry supersedes the older one, so claims built on the old version are flagged by `ev check`.
- Imports are deterministic: two labs importing the same entry version get the same claim id.

## Demo

`demo/run.sh` runs two agents in separate, signed labs. One poses a question and breaks it into parts, answers one part and records a dead end. The other pulls, consults the record before starting, answers the other part wrongly and builds on the error. Each re-runs the other's work; the record flags what rested on the error, and the report says what a human needs to know.

## Benchmark

`bench/planted.py` measures how well an agent works on a shared record. It builds a world about prime counts in which some claims are false, some true claims rest on false ones, one approach is a recorded dead end, and some questions are open; the answer key is kept outside the stores.

```sh
python3 bench/planted.py setup /tmp/b      # the world, an empty agent store with the world as a remote, the key
python3 bench/planted.py task /tmp/b       # the prompt to give the agent
python3 bench/planted.py score /tmp/b      # errors refuted, true claims left standing and reproduced,
                                           # dependants flagged, questions answered, dead end repeated
python3 bench/planted.py baseline /tmp/b   # a scripted agent that only re-runs what `ev todo` offers
```

The scripted baseline refutes every planted error and flags everything resting on them, but answers no questions. A real agent should match it on the first four scores and add answers.

## Tests

`python3 -m unittest discover -s tests` (about ten seconds; CI runs it on Linux and macOS with Python 3.10 and 3.13).

- Unit tests of the store, questions and withdrawals, signatures, the sandbox, remotes, and the Palomar importer (the registry is replaced by a dictionary).
- CLI tests that drive `ev` as an agent would and check its JSON output and exit codes; an MCP test that holds a JSON-RPC session with `ev mcp`.
- Property tests: several labs ask, claim (with values that sometimes disagree), review, withdraw and pull at random, signed or not. Statuses of claims and questions, contested ones included, must agree with a brute-force oracle, and once all labs have exchanged everything they must hold the same objects and agree on every status, whatever the order of the pulls. `EV_SEEDS=50` runs more histories.
- A scale test: statuses, `todo` and `search` on 3000 claims in under five seconds (`EV_SCALE` to change the size).
- The benchmark's constants are checked, and the scripted baseline must reach its expected score.
