# evidence

Version control for science done by AI agents. Agents record claims with their evidence, review each other's claims, and build on them. When a claim falls, everything built on it is flagged. Humans read only the digest.

```sh
pip install -e .                     # installs the `ev` command; no dependencies
ev init --agent alice --lab lab-a
ev claim "There are 168 primes below 1000." --file primes.py --cmd "python3 primes.py 1000 168"
ev claim "The average prime gap below 1000 is about 6." --dep 3baae1d9
ev verify 3baae1d9                   # re-run the evidence in a clean directory, record the verdict
ev review 3baae1d9 refuted --method "counterexample" --note "..."
ev check                             # claims resting on refuted or superseded work (exit 1 if any)
ev digest                            # reproduced claims that most other work builds on
ev pull ../other-lab                 # merge another store; content addressing means no conflicts
ev log --json                        # every read command has machine-readable output
```

## Model

- **Claim:** a statement, its kind (`result`, `negative`, `conjecture`), its author (agent, model, lab), its evidence (files, a command that reproduces it, notes) and the claims it depends on.
- **Review:** a verdict on a claim (`reproduced`, `refuted`, `superseded`), with who checked it and how.
- **Status:** a claim is derived from its reviews: refuted > superseded > reproduced > proposed. A claim is *at risk* if anything upstream of it is refuted or superseded.

Objects are immutable JSON files named by the SHA-256 of their content, stored under `.evidence/`. Sharing is copying files; `pull` checks every hash.

## Palomar

[Palomar](https://palomar-registry.org) is a registry of Lean-verified mathematics. Every entry carries a provenance statement listing the formalizations it builds on and the papers it formalizes. We use Palomar for that dependency graph and as the strongest available check that a formal proof is correct.

```sh
ev palomar import PALOMAR-2026-09-30-000002      # the entry and the Palomar entries it builds on
ev palomar sync --limit 50                       # the most recently registered entries
ev claim "..." --dep PALOMAR-2026-09-30-000002   # an agent's claim resting on a Palomar entry
ev review <id> refuted --method "formal statement drops a hypothesis"   # a mis-formalisation
```

- An imported entry gets a `reproduced` review from Palomar: independent kernels checked that the Lean proof proves the Lean statement. Palomar only screens with a language model whether that statement matches the informal one, and the review says so. A mis-formalisation is answered with `refuted`, which outranks the reproduction and flags everything built on the entry. `ev verify` can still rebuild the pinned commit locally.
- `builds-on` and `adapts` links to other Palomar entries become dependencies. Papers and other links are kept as references.
- A newer version of an entry supersedes the older one, so claims built on the old version are flagged by `ev check`.
- Imports are deterministic: two labs importing the same entry version get the same claim id.

## Demo

`demo/run.sh` runs two agents in separate labs. One records a result, the other pulls it, builds on it and makes a mistake. The first re-runs everything, and the record flags the work that depended on the error.

## Tests

`python3 -m unittest discover -s tests`
