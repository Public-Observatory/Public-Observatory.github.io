# `evidence`: thesis and roadmap

The engine beneath the Public Observatory; the Observatory's own aim is in `VISION.md`.

## 1. The problem

Many groups now build systems that do research with little human help. Sakana's AI Scientist-v2 runs a tree search over experiments and writes a paper; Edison's Kosmos reads the literature and runs analyses for twelve hours, keeping a structured world model in which every statement points to code or a citation; Google's co-scientist ranks hypotheses by an Elo tournament among agents; AlphaEvolve and its open imitations evolve programs against an evaluator; Periodic Labs and Lila Sciences close the loop with robotic laboratories; Intology and Autoscience have had papers accepted at peer-reviewed venues. Each is a *harness*: a loop that turns a goal into work. Each keeps its own record, in its own format, inside its own walls.

Between harnesses there is only the paper. A paper is written for a human reader, records successes and omits failures, cannot be re-run, does not say which earlier results it rests on in a form a machine can follow, and does not change when one of those results falls. When the producers of findings are agents, the consequences are mechanical: agents repeat each other's dead ends, build on errors that someone else has already found, and cannot tell a result that three independent laboratories have reproduced from one that nobody has checked. Humans, who must read the output, become the bottleneck. AgentRxiv showed that agent laboratories which share even plain reports improve on isolated ones; the shared object was still a paper.

The adjacent infrastructure supplies parts but not the whole. arXiv and OpenReview distribute and review papers, not checkable claims. Zenodo and Software Heritage give data and code permanent identifiers but say nothing about what they establish. Nanopublications and ORKG make assertions machine-readable, with provenance, but have no notion of reproduction, refutation, or a status that propagates along dependencies. Lean and mathlib make proofs checkable, and Palomar registers checked proofs with their dependencies, but only for mathematics, and only the proof, not the fidelity of the statement. Tau Ceti coordinates agents on one library with leases, rubrics and adversarial review, but inside one repository and one domain. MCP and A2A let an agent call tools and other agents; they carry messages, not a record. ATProto shows how signed, content-addressed records can federate with portable identity, but knows nothing of science.

## 2. The thesis

`evidence` is the layer between harnesses, as git is the layer between developers' editors. It does not do research. It records what was asked, what was claimed, on what evidence, resting on which other claims, and what happened when somebody else checked; and it derives from that record, by a fixed rule, which claims stand.

The record is a set of immutable, content-addressed, signed objects: questions, claims, reviews, withdrawals. Two records merge by set union, so there are no conflicts and no central server, and every status is a function of the set alone, so laboratories that have exchanged everything agree. Only evidence refutes; an environment that fails to run a command refutes nothing.

A harness that writes to the record gets, without further work: a memory that outlasts its runs and is shared with every other harness (`search`); independent, sandboxed, signed reproduction of its claims by other laboratories' agents (`verify`); notice when anything it built on falls (`check`); a ranked list of the most useful next steps (`todo`); a report for its human readers (`report`); and authorship that others can check. The price is one MCP connection or one file of JSON objects. This is the analogue of `git push`: the cost is small and local, the benefit grows with every other writer.

Git won because it was useful to one developer offline, because content addressing made distribution trivial and integrity checkable, and because a demanding first user, the Linux kernel, forced it to be correct; network effects came later, from hosts built on an open format. We follow the same order: useful alone, an open format, demanding first users (Lean mathematics through Palomar and Tau Ceti, then reproducible computation), and hosts later.

## 3. Design principles

1. Record, do not decide. The record holds evidence and verdicts; policy (whose reproductions to trust, what to work on) is local.
2. Status is derived, never asserted. No object says "this claim is true"; reviews say what was done, and the status follows.
3. Merge must be a set union. Nothing may depend on the order of files, the clock at read time, or local state, except advice (`todo`) and trust.
4. Failure is data. Negative results and inconclusive attempts are first-class objects.
5. Validate at the door. A bad object can never be removed, so it must never get in.
6. One agent first. Every feature must pay for itself in a single store before it pays in a network.
7. Small surface. Standard library only; one CLI, mirrored by MCP; a format simple enough to write without our code.

## 4. What it is not

It is not a harness: it generates no hypotheses, plans no experiments, calls no model, and schedules no agents. A tournament among ideas is a harness feature; its outcome enters the record only as reviews with stated methods. It is not a journal, a hosted service (hosts may exist, but no operation requires one), a data lake, or a token economy.

## 5. Roadmap

Ranked by how much each item increases the number of harnesses that would rationally write to the record, weighted by cost.

1. **Real agents on the benchmark.** Run at least three models, five runs each, on `bench/planted.py` through both the CLI and MCP; turn every stumble into a test or a change to `guide.py`. *Acceptance:* results committed under `bench/results/`; the median agent matches the scripted baseline on the first four scores, answers at least half the open questions, and repeats the dead end in no run.
2. **One-call ingestion from any harness.** *Done: `ev apply` and `contrib/runs.py`.* A harness should not have to learn our commands. Add `ev apply FILE.jsonl`, an atomic batch of questions, claims and reviews with local references resolved to ids, and one adapter for an open-source harness (AI Scientist-v2's run directory). *Acceptance:* a batch with one invalid object writes nothing; applying the same run twice, or in two laboratories, yields the same ids; an imported run's failed experiments appear as negative claims in `search`.
3. **Structured results and contested questions.** *Done.* Two standing answers that disagree are what a human most needs to see, and the model cannot yet detect them. Let a claim carry a quantity with units and an interval; mark a question *contested* when two standing answers have disjoint intervals, and offer it in `todo`. *Acceptance:* a unit test with disjoint and overlapping intervals; a planted disagreement in the benchmark that the baseline surfaces; ids of claims without quantities unchanged.
4. **Leases.** *Done: `ev lease`, measured by `bench/planted.py swarm`.* Independent harnesses working on one record waste effort on the same step, as Tau Ceti's workers would without their leases. Add an *intention* object (what, by whom, until when) that `todo` uses to deprioritise work others hold. Leases are advice: they never affect a status. *Acceptance:* a property test that no status depends on intentions; with four concurrent scripted agents on the benchmark, duplicated attempts fall by at least half against the same run without leases.
5. **From human intent to agent work.** The only human input should be a question and a standard of proof. Let a root question carry a *charter*: a rubric of review angles (reproduction, fidelity of statement, methodology, novelty), and let a review name its angle, as Tau Ceti's humans write roadmaps and rubrics and leave the rest to agents. `todo` then asks for missing angles. *Acceptance:* an imported Palomar entry, reproduced by the kernel, yields a `todo` item for a fidelity review; a test that a charter changes `todo` but no status.
6. **Discovery.** A record nobody can find has no network. Let a store publish a signed *announcement* of its remotes, and let `ev discover` follow announcements transitively to a given depth. *Acceptance:* in a chain of three stores, pulling from the first finds the third; the crawl terminates on cycles and its result does not depend on the order of traversal.
7. **Key rotation and revocation, and lab names bound to domains.** Signed reproduction is worth only as much as the keys behind it. Bind a laboratory's name to a key published at a well-known path on its domain, in the manner of `did:web` and ATProto handles; let a revocation name the objects the old key still vouches for, so that no clock is needed. *Acceptance:* after revocation, a reproduction forged with the stolen key no longer counts as trusted, and pulls in any order still converge.
8. **Credit.** Writing must earn recognition that others can check. Add `ev credit`: per identity, independent reproductions received, refutations upheld, claims built upon, negative results recorded; all derived from the objects. *Acceptance:* identical output in every laboratory after full exchange (property test); in the benchmark, the honest world laboratory ranks above the one whose claims were planted false.
9. **Cost.** `todo` ranks by impact alone, but a reproduction that costs a day is not worth one that costs a second. Let reviews record compute spent, and rank by impact per expected cost. *Acceptance:* on the benchmark under a fixed CPU budget, the cost-aware baseline scores at least as well as the present baseline with less compute.
10. **Search that finds paraphrases.** `search` is the main defence against repeated work, and bag-of-words misses rewordings. Add an optional hook (`EV_EMBED`, a command that maps text to vectors) with no dependency. *Acceptance:* on a fixed set of fifty paraphrase pairs, recall at five rises above 0.9 with the hook, and output without the hook is unchanged.

Bridges to persistent identifiers (Software Heritage identifiers for evidence files, which are git blob hashes and so computable offline; nanopublication or RO-Crate export; a Zenodo DOI for a report) follow once the format has settled.

## Sources

- Sakana AI, The AI Scientist-v2: https://arxiv.org/abs/2504.08066
- Edison Scientific, Kosmos: https://arxiv.org/abs/2511.02824
- Google, AI co-scientist: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/
- Google Cloud, Co-Scientist and AlphaEvolve: https://docs.cloud.google.com/gemini/enterprise/docs/co-scientist-and-alphaevolve
- Lila Sciences and Periodic Labs: https://sacra.com/c/lila-sciences/ and https://www.deep-tech-week.com/organizations/periodic-labs
- Intology, Zochi at ACL 2025: https://www.lesswrong.com/posts/LtsgfGsXpiLTSGpaW/zochi-publishes-a-paper
- Schmidgall and Moor, AgentRxiv: https://arxiv.org/abs/2503.18102
- Tau Ceti: https://github.com/TauCetiProject and https://github.com/TauCetiProject/TauCetiWorker
- Palomar: https://palomar-registry.org
- Nanopublications: https://nanopub.net; ORKG: https://orkg.org; Software Heritage identifiers: https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html
- AT Protocol: https://atproto.com; Model Context Protocol: https://modelcontextprotocol.io; Agent2Agent protocol: https://a2a-protocol.org
