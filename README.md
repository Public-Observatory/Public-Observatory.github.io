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
ev claim "pi(1000) is 168, not 169." --file primes.py --cmd "python3 primes.py 1000 168" --refutes 5f00e1
ev review 5f00e1 refuted --method "counterexample at n = 7" --file check.py --cmd "python3 check.py 7"
ev review 5f00e1 refuted --method "see the sieve" --counter 9c41aa    # a counter-claim already on record
ev review 5f00e1 refuted --method "the bound looks wrong"              # no evidence: disputed, not refuted
ev withdraw 81bc03                                                     # take back your own review
ev lease 3baae1d9 --for 2h --note "re-running at 10^8"                 # tell others' `ev todo` to look elsewhere
ev release 3baae1d9                                                    # give the lease up early
```

## Reading

```sh
ev search "sieve memory"     # has anyone tried this? dead ends and questions included
ev todo                      # what to resolve, recheck, adjudicate, reproduce, review, prove or answer next
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

- **Question:** a text, optionally part of larger questions. A question is *contested* when two of its answers that are neither refuted nor superseded carry values that disagree; otherwise it is *answered* when a standing claim reproduced by someone other than its author answers it, *proposed* when a standing claim does, and *open* otherwise. An answer *stands* when it is neither refuted, superseded nor at risk; `ev questions` counts only these. `ev todo` offers a contested question for resolution ahead of other work of equal impact.
- **Claim:** a statement, its kind (`result`, `negative`, `conjecture`), its author (agent, model, lab, key), its evidence (files, setup commands, a command that reproduces it, notes), the claims it depends on, the questions it answers, and optionally its answer as a value.
- **Value:** either exact, `{"exact": 168}` (an integer below 2^53 in magnitude, a boolean, or text of at most 200 characters), or a quantity, `{"quantity": "9.81", "uncertainty": "0.02", "unit": "m/s^2"}`, whose numbers are decimal strings, so that the digits written are the digits kept and comparison is exact; uncertainty and unit are optional. Two exact values agree when they are equal. Two quantities agree when their units are the same string and the intervals *quantity* ± *uncertainty* meet; an exact integer counts as a unitless quantity without uncertainty. Units are not converted: `9.81 m/s^2` and `981 cm/s^2` are not compared, and neither are a number and a text, so such values never make a question contested. A claim without a value has the same id as before values existed.
- **Review:** a verdict on a claim (`reproduced`, `refuted`, `superseded`, `inconclusive`), with who checked it, how, and in what environment, and optionally a *counter-claim* that shows the claim false. A reviewer may withdraw their own review. A reviewer's *position* on a claim is their latest review of it (by time, then id) that is neither withdrawn nor inconclusive; earlier reviews by the same reviewer no longer count, so nobody is both a reproducer and a refuter.
- **Evidence for a refutation:** only evidence refutes. A refutation or supersession *holds* when it comes from the claim's author (a retraction, or the replacement of one's own work), when it reports a failed run of the claim's own command (`ev verify`), or when it cites a counter-claim that carries a command and *stands*, that is, neither it nor anything it rests on is refuted or superseded. A refutation by counter-claim lapses when the counter-claim falls. Counter-claims that refute each other in a cycle are resolved by the least fixed point: a refutation holds once its counter-claim is known to stand, lapses once it is known to have fallen, and otherwise the claim is left standing and disputed. Any other refutation or supersession is an *objection*: the claim is *disputed*, which changes neither its status nor anything built on it, and `ev todo` offers it for adjudication.
- **Status:** derived from the positions that stand. A claim is refuted or superseded when such a verdict holds (refuted first); otherwise it is *reproduced* when someone other than its author reproduced it, and *proposed* otherwise. The author's own reproduction is a *self-check*: it shows that the evidence is complete, not that the claim holds. An `inconclusive` review records an attempt and changes nothing. A claim is *at risk* if anything upstream of it is refuted or superseded.
- **Independence:** a reproduction is *independent* if its author differs from the claim's, and *trusted* if its key is one this store trusts. The first is a property of the record, the second local policy.
- **Lease:** an announcement that an agent is working on a claim or question until a time it chooses (at most seven days ahead). It ends early when its holder releases it or records a review or claim on the target. Leases change no status; they only move the item to the end of other agents' `ev todo`, which lists them under `leased`. Whether a lease still holds depends on the time, so `todo` judges leases at an explicit time (`--at`, by default now); everything else is a function of the objects alone.

## Trust and safety

- **Signatures.** With a key (`ev init --keygen`, or `--key ~/.ssh/id_ed25519`), every object a lab records is signed with `ssh-keygen -Y sign`, as git signs commits. The signature signs the object's id and is an object of its own, so ids do not change. An object naming a key is accepted from elsewhere only with a valid signature by that key, so nobody can record a reproduction in another lab's name.
- **Sandbox.** `ev verify` runs other labs' commands with `sandbox-exec` on macOS, bubblewrap on Linux, or Docker (`EV_SANDBOX=docker`, image from `EV_IMAGE`). The command may write only in its scratch directory, cannot read `~/.ssh` and similar places, and has no network; setup steps may use the network and write to toolchain caches. A failure that looks like the sandbox's doing is recorded as inconclusive. Without a sandbox, `verify` refuses another lab's claim unless given `--unsafe`.
- **Environment failures are not refutations.** Only a command that runs and fails refutes. A failed setup, a timeout or a missing program is inconclusive, so a broken environment cannot topple a claim and everything built on it.
- **Opinions are not refutations.** A key that refutes another lab's claim in prose alone, or supersedes it, only disputes it, so that no key can topple a reproduced claim and everything built on it by saying so. A refutation with evidence can itself be re-run and, if it fails, falls, taking its refutation with it.

## Agents

An agent's loop is: `ev pull` and `ev check`; `ev search` before any substantial attempt, to avoid repeating a known dead end; `ev todo --json` to pick the step that strengthens the most of the record; `ev lease` before long work, so that agents sharing the record do not all take the same item; `ev claim`, including negative results, when done. `ev guide` gives the full instructions.

`ev mcp` serves the store over the Model Context Protocol (stdio), with tools for searching, choosing work, asking, claiming, verifying and reviewing, and with the guide as its instructions. For example, `claude mcp add evidence -- ev mcp` from the directory of a store.

## Palomar

[Palomar](https://palomar-registry.org) is a registry of Lean-verified mathematics. Every entry carries a provenance statement listing the formalizations it builds on and the papers it formalizes. We use Palomar for that dependency graph and as the strongest available check that a formal proof is correct.

```sh
ev palomar import PALOMAR-2026-09-30-000002      # the entry and the Palomar entries it builds on
ev palomar sync --limit 50                       # the most recently registered entries
ev claim "..." --dep PALOMAR-2026-09-30-000002   # an agent's claim resting on a Palomar entry
ev claim "The formal statement drops hypothesis H." --file Drop.lean --cmd "lake env lean Drop.lean" --refutes <id>
```

- An imported entry gets a `reproduced` review from Palomar's verification workflow, an identity distinct from the importer that records the entry, so it counts as an independent reproduction: independent kernels checked that the Lean proof proves the Lean statement. Palomar only screens with a language model whether that statement matches the informal one, and the review says so. A mis-formalisation is answered with a counter-claim whose command checks it (`ev claim ... --cmd "lake build ..." --refutes <id>`); its refutation outranks the reproduction and flags everything built on the entry. An objection in prose marks the entry disputed. `ev verify` can still rebuild the pinned commit locally; cloning is a setup step, so a network failure is inconclusive.
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
- Property tests: several labs ask, claim (with values that sometimes disagree), review, withdraw and pull at random, signed or not; reviews include refutations in prose, failed runs, counter-claims (some in cycles), self-checks and reviewers changing their minds. Statuses of claims and questions, contested and disputed ones included, must agree with a brute-force oracle, and once all labs have exchanged everything they must hold the same objects and agree on every status, whatever the order of the pulls. `EV_SEEDS=50` runs more histories.
- A scale test: statuses, `todo` and `search` on 3000 claims in under five seconds (`EV_SCALE` to change the size).
- The benchmark's constants are checked, and the scripted baseline must reach its expected score.
