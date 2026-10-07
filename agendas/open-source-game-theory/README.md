# Research Agenda for Safe Cooperation in Open Source Game Theory

The aim is to determine when AI agents that inspect one another’s programs can cooperate usefully while remaining safe for humans, including people outside their agreements. The motivating failure is a coalition whose members benefit from coordinated behavior that harms others. The research objective is to bound that harm while preserving authorized activity and effective human intervention.

This agenda takes its starting point from **AI-Safety for Mathematicians**, especially its [Open-Source Game Theory research direction](https://mathforaisafety.org/research/open-source-game-theory), and **Lionel Levine’s [Math for AI Safety: An Invitation for Mathematicians](https://lionellevine.github.io/MAIS.pdf)**, particularly §2 and Problem MAIS-O1. These sources motivate the logical approach and the transition from individual agents to cooperative societies. The projects below combine those starting points with program equilibrium, distributed computing, formal verification, and multi-agent security.

**Priority:** begin with a small coalition game with an explicit externality, prove the limits of protection, and establish a useful guarantee under stated enforcement assumptions. More sophisticated cooperation is valuable only if it improves this safety–usefulness tradeoff.

Literature search updated 7 October 2026. The bibliography distinguishes foundational results, surveys, and recent preprints. The project questions and proposed deliverables are research proposals, not established theorems or claims of verified novelty.

## What the existing literature establishes

**Programs can support cooperation that is unavailable in the corresponding one-shot action game.** Tennenholtz formalizes program equilibrium and proves a payoff characterization in his setting. This is an equilibrium in the game of choosing programs; it does not overturn the usual analysis of the original action game. [Tennenholtz, 2004](https://www.sciencedirect.com/science/article/pii/S0899825604000314)

**Proof-based cooperation need not depend on identical source text.** Barász and coauthors construct agents using provability logic. Their resistance to exploitation concerns the modeled Prisoner’s Dilemma and relies on the relevant logical assumptions; it is not a guarantee against general harm. Critch develops bounded-resource reasoning, while Critch, Dennis, and Russell exhibit surprising program interactions and explicit open problems. [Barász et al., 2014](https://arxiv.org/abs/1401.5577); [Critch, 2016](https://arxiv.org/abs/1602.04184); [Critch, Dennis, and Russell, 2022](https://arxiv.org/abs/2208.07006)

**Simulation offers another route, including multiplayer constructions.** Cooper, Oesterheld, and Conitzer establish results with and without shared randomness. Under their assumptions, shared randomness supports a broader equilibrium characterization. Multiplayer cooperation therefore already has substantive results; the proposed extension concerns externalities, coalitional deviations, and enforceable safety. [Cooper, Oesterheld, and Conitzer, 2025](https://arxiv.org/abs/2412.14570)

**Cooperation can itself be the failure.** Hammond and coauthors distinguish miscoordination, conflict, and collusion. Schroeder de Witt and coauthors study security risks arising from interactions and shared environments. These agendas justify considering both mutually beneficial harmful agreements and arbitrary malicious behavior. [Hammond et al., 2025](https://arxiv.org/abs/2502.14143); [Schroeder de Witt et al., 2025, revised 2026](https://arxiv.org/abs/2505.02077)

**Rational coalitions and malicious participants have an existing joint theory.** Work on robust mediator implementation studies both coalition incentives and participants with unknown utilities, with bounds that depend on communication and other assumptions. Those results are a starting point, not ready-made thresholds for AI swarms. [Abraham, Dolev, and Halpern, 2008](https://www.cs.cornell.edu/info/people/halpern/papers/tcc08.pdf)

The proposed contribution is a connection between these literatures: source-aware strategic interaction, explicit protection of outsiders, and safety guarantees that survive specified adversarial deviations.

## A common model and success criterion

Begin with a finite-horizon environment and a finite set of agents. Each agent runs a program, receives a specified view of the other programs, and acts through explicitly modeled interfaces. Include human principals, affected nonparticipants, and any trusted enforcement components.

Fix the following before stating a guarantee:

- **Harm:** a set of forbidden trajectories, supplemented by a severity measure where appropriate. Specify the protected people and interests.
- **Adversary:** which agents can coordinate, when corruption occurs, which permissions and resources they control, and whether transfers between coalition members are allowed.
- **Visibility:** whether agents see authenticated executable code, an interface, a policy description, or only behavior. State what remains hidden, including model weights, memory, randomness, and external services.
- **Enforcement:** which actions are mediated, how code inspection is tied to execution, and whether agents can bypass or modify the enforcement component.
- **Timing:** the horizon, communication assumptions, deadlines, and the consequences of nontermination.

The main safety target is: **for every allowed coalition and every permitted coordinated deviation, the probability of a forbidden trajectory by the stated horizon is at most ε.** Probability is over the specified environment and protocol randomness. This is a proposed definition for the agenda, not a standard definition of program equilibrium.

Keep three properties separate. Incentive compatibility limits profitable deviations. Adversarial safety limits harm even when deviations are not profitable. Usefulness requires completing a specified class of authorized tasks; an always-refuse protocol should fail this criterion.

Human welfare must not be inferred from the agents’ payoffs. A Pareto improvement for represented principals can still harm unrepresented people. The safe-Pareto-improvement literature supplies methods for comparing games under explicit behavioral assumptions; “safe” there should not be read as a universal external-harm guarantee. [Oesterheld and Conitzer, 2022](https://link.springer.com/article/10.1007/s10458-022-09574-6)

## Project 1 Coalition safety with externalities

**Question.** Which combinations of incentives, visibility, and enforceable restrictions prevent coalitions from harming nonparticipants?

**Starting point.** Combine program equilibrium with the distinction between strategic and malicious deviations in robust mediator implementation. The new modeling ingredient is an external harm criterion, which may concern someone with no strategic move. [Tennenholtz, 2004](https://www.sciencedirect.com/science/article/pii/S0899825604000314); [Abraham, Dolev, and Halpern, 2008](https://www.cs.cornell.edu/info/people/halpern/papers/tcc08.pdf)

**First problem.** Construct a game with two active agents and a passive affected party. Both active agents gain from exceeding a shared resource limit; the affected party bears the loss. Compare source opacity, exact-code inspection, proof-based commitments, and an enforced aggregate resource cap. Then add a third active agent to test whether pairwise safeguards compose.

**Proposed results.** Seek a characterization of safe and useful program profiles for a restricted finite class. Prove a simple impossibility result when a coalition can independently force harm through an unrestricted interface. Determine which minimal restrictions restore a guarantee. Analyze transferable and nontransferable payoffs separately, since side payments change which deviations benefit a coalition.

**Deliverable.** A paper containing precise definitions, a separating example, one impossibility theorem, and one positive theorem. Exhaustive finite examples should accompany the proofs.

**Safety value.** Identifies exactly what source transparency contributes and what requires control over actions. A guarantee obtained entirely from an action cap should be credited to that cap, rather than to program reasoning.

## Project 2 Safety certificates for joint behavior

**Question.** Can agents make mutually conditional commitments whose certificates establish a global safety property?

**Starting point.** Provability-based agents provide a model of conditional cooperation. Proof-carrying code supplies a different ingredient: code accompanied by evidence that it respects a receiving system’s safety policy. Combining them requires attention to the environment and to composition. [Barász et al., 2014](https://arxiv.org/abs/1401.5577); [Necula, 1997](https://courses.grainger.illinois.edu/cs421/fa2010/papers/necula-pcc.pdf)

**First problem.** Let independently developed agents request access to a common finite resource. Require a certificate that a proposed interaction preserves a global resource invariant. Compare independent local certificates with certificates that account for shared state and concurrent use. A pair of locally valid claims about the same remaining capacity supplies an immediate stress test.

**Proposed theorem target.** Give sufficient conditions under which certified transitions preserve the global invariant through the horizon, despite arbitrary behavior at the untrusted proposal interfaces. State initial-state validity, checker soundness, complete mediation, and concurrency assumptions explicitly. Add a separate progress theorem for a nontrivial class of authorized workloads.

Ordinary invariant preservation under a sound monitor is a baseline. The research question is whether mutually conditional certificates can permit more useful interactions without circular assumptions, additional trust, or loss of coalition robustness.

**Deliverable.** A small formal model and machine-checked composition result, plus counterexamples obtained by weakening its assumptions. Existing Lean work by Duclaux and collaborators is a candidate starting point; its repository includes game semantics, bots, and an automated matchup runner. [Duclaux et al., 2026](https://github.com/ColombanD/open-source-game-theory)

**Safety value.** Moves the certificate’s subject from another agent’s willingness to cooperate to the actual property humans need preserved. Specification errors remain distinct from proof-checking errors.

## Project 3 Finite reasoning and partial transparency

**Question.** How much reasoning and authenticated information are needed for safe, useful cooperation?

**Starting point.** Critch’s bounded Löb work and Levine’s quantitative problem motivate explicit resource bounds. Cooper, Oesterheld, and Conitzer provide simulation constructions against which proof-based methods can be compared. [Critch, 2016](https://arxiv.org/abs/1602.04184); [Levine, 2026, Problem MAIS-O1](https://lionellevine.github.io/MAIS.pdf); [Cooper, Oesterheld, and Conitzer, 2025](https://arxiv.org/abs/2412.14570)

**First problem.** Fix a proof system, encoding, agent family, and search algorithm. Measure the least proof budget supporting each desired interaction, the time needed to discover a proof, and the time needed to check it. Vary the agents’ budgets independently. A short proof need not be cheap to find.

Next, replace exact executable visibility with restricted interfaces or partial disclosure. Specify which hidden components can change behavior after inspection. Do not equate access to an LLM’s inference code with a tractable proof of its behavior.

**Proposed results.** Derive explicit bounds for selected agent families and identify conditions under which timeouts preserve safety. Test whether behavioral equivalence, small implementation changes, or mismatched proof systems preserve cooperation. Treat nontermination as a modeled outcome, rather than discarding it.

**Deliverable.** Reproducible proof-budget experiments, quantitative bounds where feasible, and a comparison with simulation and opaque-action baselines at matched computational cost.

**Safety value.** Reveals whether a cooperation guarantee remains useful under actual deadlines, and whether withholding information can force unsafe behavior or merely reduce service.

## Project 4 Populations and resource bounded coalitions

**Question.** Which guarantees survive delegation, replication, entry, and correlated failures?

**Starting point.** Multiplayer simulation results show that the passage from two agents to many changes termination and equilibrium analysis. Distributed-computing lower bounds also demonstrate the importance of timing, communication, and adversary assumptions. [Cooper, Oesterheld, and Conitzer, 2025](https://arxiv.org/abs/2412.14570); [Geffner and Halpern, 2021](https://arxiv.org/abs/2104.02759)

**First problem.** Extend Project 1 to a changing population. Compare a bound on the number of compromised identities with a bound on compromised permissions or resources. Require delegated permissions to remain within an aggregate budget. Model shared verifiers, model families, and infrastructure as common failure sources.

**Proposed results.** Determine whether splitting one agent into several identities changes the safety guarantee. Derive composition bounds for interactions over a graph, starting with a fixed graph before allowing entry and delegation. Study whether shared randomness helps useful coordination while also assisting harmful coalitions.

Do not transfer numerical Byzantine-fault thresholds directly to this setting. Derive thresholds from the chosen authentication, communication, resource, and enforcement model.

**Deliverable.** A resource-based adversary model, a delegation result for a restricted protocol, and examples where guarantees stated only in terms of agent count fail.

**Safety value.** Addresses the swarm-specific risk that individually limited actors acquire dangerous aggregate capacity or share a single correlated failure.

## Project 5 Human intervention and revisable commitments

**Question.** Can agents make credible cooperative commitments while preserving authorized human revision and shutdown?

**Starting point.** The Off-Switch Game studies incentives to preserve human intervention, under assumptions about preferences and human behavior. Subsequent work shows why uncertainty alone does not generally ensure deference. Safe Pareto improvements and ex post verifiable commitments supply tools for modifying strategic interactions. [Hadfield-Menell et al., 2017](https://arxiv.org/abs/1611.08219); [Neth, 2025](https://arxiv.org/abs/2502.08864); [Oesterheld and Conitzer, 2022](https://link.springer.com/article/10.1007/s10458-022-09574-6); [Sauerberg and Oesterheld, 2026](https://arxiv.org/abs/2505.00783)

**First problem.** Study two delegated agents with an authenticated human revocation channel. Agreements expire or can be revised under publicly specified conditions. Compare unconditional commitment, unrestricted cancellation, and conditional revision. Include the possibility that one principal abuses cancellation strategically.

**Proposed results.** Characterize when useful cooperation survives the permitted revision rule. Seek conditions ensuring that neither a unilateral agent deviation nor a coalition can disable intervention or transfer permissions to an uninterruptible delegate.

Distinguish prevention from detection: discovering a broken commitment after an irreversible harmful action does not itself protect the affected party. Also distinguish preserving intervention incentives from enforcing an intervention channel independently of those incentives.

**Deliverable.** A finite sequential model, an impossibility or tradeoff result, and a protocol for a restricted useful case. Use outcome-correspondence methods to investigate comparisons that do not require selecting a particular equilibrium. [Oesterheld and Conitzer, 2025](https://arxiv.org/abs/2511.21262)

**Safety value.** Makes retained human authority a property of the interaction protocol, including downstream delegation.

## Evaluation across the projects

Use synthetic, inspectable programs first. Introduce LLM-controlled agents only after the environment, harm event, and enforcement assumptions are explicit.

Existing work supplies complementary evaluation ideas. AI-control experiments test protocols against intentional subversion, including collusion between an untrusted worker and monitor. Research on secret collusion studies covert communication. Colosseum distinguishes collusive communication from action-based harm to a joint objective. These findings motivate separate measures for intentions, actions, and consequences. [Greenblatt et al., 2024](https://arxiv.org/abs/2312.06942); [Motwani et al., 2024, revised 2025](https://arxiv.org/abs/2402.07510); [Nakamura et al., 2026](https://arxiv.org/abs/2602.15198)

Recent preprints also examine voluntary adoption of harmful coordination tools and steganographic communication between independently deployed agents. Their experimental and cryptographic assumptions should be retained when using them to motivate tests; they do not establish that arbitrary deployed swarms already have those capabilities. [Zeng and Rudzicz, 2026](https://arxiv.org/abs/2605.27593); [Pang, Smith, and Zheng, 2026](https://arxiv.org/abs/2609.28900)

Use three task families: allocation of a shared resource, joint authorization of consequential actions, and delegated work with a monitoring agent. For each, include legitimate cooperative tasks, profitable harmful deviations, and malicious deviations with no assumed payoff motive.

Compare opaque policies, identity-based cooperation, proof-based cooperation, simulation-based cooperation, and a trusted enforcement baseline. Ablate source visibility, certificate requirements, communication, shared randomness, and enforcement separately. This identifies whether improvements come from reasoning about programs or from the surrounding controls.

Report:

- Harm probability and severity, including harm to nonparticipants.
- Authorized task completion, refusal rates, and delay.
- Verification, search, and communication costs.
- Robustness to coalition resources, identity splitting, shared-component failures, and intervention.
- Statistical uncertainty and performance against held-out adversarial strategies.

A benchmark measures the tested adversaries. A universal claim requires a proof over the specified adversary class. Conversely, a proof in a toy environment establishes only the modeled property.

## First year plan

**Months 1–3: establish the smallest useful model.** Complete Project 1’s definitions and finite examples. Reproduce selected baseline program interactions before changing the game. Seek the impossibility result first, so the positive result’s enforcement assumptions have a clear purpose.

**Months 4–6: prove one compositional guarantee.** Develop Project 2 for the shared-resource environment and formalize its main invariant. Run the first bounded-reasoning experiments from Project 3. The decision point is whether conditional program reasoning enables useful behavior beyond the trusted enforcement baseline.

**Months 7–9: stress population assumptions.** Extend to three or more active agents, resource-bounded coalitions, delegation, and shared failures. Add one explicit human revision mechanism. Prioritize a sharp restricted result over a general framework with unverifiable assumptions.

**Months 10–12: evaluate and consolidate.** Run controlled LLM experiments where they test a specific theoretical assumption. Produce a paper, a formal artifact, and a benchmark with documented threat models and baselines.

The minimum successful outcome is one nontrivial safety–usefulness theorem, one boundary or impossibility result, and evidence identifying where source-aware cooperation helps. If the benefits disappear after matching enforcement and compute, that negative result should redirect effort toward protocol design and control.

## Annotated bibliography

The first two entries are the sources supplied for this agenda. The remaining entries provide the underlying results and adjacent research. This is a focused literature search, not an exhaustive systematic review. Publication years are used where verified; preprint and revision dates are distinguished below.

1. **AI-Safety for Mathematicians.** [Research Directions](https://mathforaisafety.org/research), especially [Open-Source Game Theory](https://mathforaisafety.org/research/open-source-game-theory). Living exposition, accessed 7 October 2026. Source for the initial framing and bounded-provability examples; the page attributes its concrete matchup problem to Critch and coauthors.

2. **Lionel Levine (2026).** [Math for AI Safety: An Invitation for Mathematicians](https://lionellevine.github.io/MAIS.pdf), version dated 13 September 2026. See §2, especially §2.3 on safety implications and MAIS-O1 on quantitative bounded Löb. Source for the motivating mathematical agenda.

3. **Moshe Tennenholtz (2004).** [Program equilibrium](https://www.sciencedirect.com/science/article/pii/S0899825604000314). *Games and Economic Behavior* 49(2), 363–373. DOI: 10.1016/j.geb.2004.02.002. Foundational program-equilibrium formulation and payoff characterization.

4. **Mihály Barász, Paul Christiano, Benja Fallenstein, Marcello Herreshoff, Patrick LaVictoire, and Eliezer Yudkowsky (2014).** [Robust Cooperation in the Prisoner’s Dilemma: Program Equilibrium via Provability Logic](https://arxiv.org/abs/1401.5577). arXiv:1401.5577. Primary source for modal agents and proof-based cooperation.

5. **Andrew Critch (2016).** [Parametric Bounded Löb’s Theorem and Robust Cooperation of Bounded Agents](https://arxiv.org/abs/1602.04184). arXiv:1602.04184. Bounded-resource logical foundations; explicit proof-system assumptions matter when applying the result.

6. **Andrew Critch, Michael Dennis, and Stuart Russell (2022).** [Cooperative and uncooperative institution designs: Surprises and problems in open-source game theory](https://arxiv.org/abs/2208.07006). arXiv:2208.07006. Program-interaction examples and ten open problems.

7. **Emery Cooper, Caspar Oesterheld, and Vincent Conitzer (2025).** [Characterising Simulation-Based Program Equilibria](https://arxiv.org/abs/2412.14570). *AAAI-25*; preprint first posted in 2024. Multiplayer simulation constructions and the role of shared randomness.

8. **Caspar Oesterheld.** [Program equilibrium and open-source game theory — an annotated bibliography](https://www.andrew.cmu.edu/user/coesterh/AnnotatedProgEqBibliography.html). Accessed 7 October 2026. A literature guide, including earlier work by McAfee, Howard, Rubinstein, and Fortnow; primary papers should be used for theorem attribution.

9. **C. Duclaux, R. Formenti, P. Cobben, B. Schölkopf, and Z. Jin (2026).** *Proving your way to cooperation: formalizing proof-based open source game theory in Lean*. Workshop citation as listed in Levine, reference 20; [associated repository](https://github.com/ColombanD/open-source-game-theory). The repository documents a Lean engine and Python matchup runner. Its proof coverage and trusted assumptions should be audited before reuse.

10. **Ittai Abraham, Danny Dolev, and Joseph Y. Halpern (2008).** [Lower Bounds on Implementing Robust and Resilient Mediators](https://www.cs.cornell.edu/info/people/halpern/papers/tcc08.pdf). Author manuscript dated 11 August 2008; [arXiv preprint](https://arxiv.org/abs/0704.3646) first posted in 2007. Coalition and unknown-utility robustness, with communication-dependent implementation limits.

11. **Ivan Geffner and Joseph Y. Halpern (2021).** [Lower Bounds Implementing Mediators in Asynchronous Systems](https://arxiv.org/abs/2104.02759). arXiv:2104.02759. Model-specific lower bounds relevant to claims about removing trusted mediators.

12. **George C. Necula (1997).** [Proof-Carrying Code](https://courses.grainger.illinois.edu/cs421/fa2010/papers/necula-pcc.pdf). *POPL ’97*. Foundational mechanism for validating untrusted code against a specified safety policy.

13. **Caspar Oesterheld and Vincent Conitzer (2022).** [Safe Pareto improvements for delegated game playing](https://link.springer.com/article/10.1007/s10458-022-09574-6). *Autonomous Agents and Multi-Agent Systems* 36, article 46. DOI: 10.1007/s10458-022-09574-6. Journal treatment of safe improvements; an earlier version appeared at AAMAS 2021.

14. **Nathaniel Sauerberg and Caspar Oesterheld (2026).** [Promises Made, Promises Kept: Safe Pareto Improvements via Ex Post Verifiable Commitments](https://arxiv.org/abs/2505.00783). *AAAI-26*; preprint first posted in 2025. Studies disarmament, token games, and commitments conditional on default behavior.

15. **Caspar Oesterheld and Vincent Conitzer (2025).** [Choosing What Game to Play without Selecting Equilibria: Inferring Safe (Pareto) Improvements in Binary Constraint Structures](https://arxiv.org/abs/2511.21262). arXiv:2511.21262. Inference and complexity of safe-improvement relations.

16. **Dylan Hadfield-Menell, Anca Dragan, Pieter Abbeel, and Stuart Russell (2017).** [The Off-Switch Game](https://arxiv.org/abs/1611.08219). Preprint first posted in 2016. A model of human intervention incentives and uncertainty about utility.

17. **Sven Neth (2025).** [Off-Switching Not Guaranteed](https://arxiv.org/abs/2502.08864). arXiv:2502.08864. Examines limitations of arguments from preference uncertainty to deference.

18. **Lewis Hammond and coauthors (2025).** [Multi-Agent Risks from Advanced AI](https://arxiv.org/abs/2502.14143). Cooperative AI Foundation, Technical Report 1. Taxonomy of miscoordination, conflict, collusion, and underlying risk factors.

19. **Christian Schroeder de Witt and coauthors (2025; revised 2026).** [Open Challenges in Multi-Agent Security: Towards Secure Systems of Interacting AI Agents](https://arxiv.org/abs/2505.02077). arXiv:2505.02077, version 2 dated 29 April 2026. Broader security agenda for interacting agents and environments.

20. **Ryan Greenblatt, Buck Shlegeris, Kshitij Sachan, and Fabien Roger (2024).** [AI Control: Improving Safety Despite Intentional Subversion](https://arxiv.org/abs/2312.06942). ICML version; preprint first posted in 2023. Empirical protocol evaluation under intentional subversion, including untrusted monitoring.

21. **Sumeet Ramesh Motwani, Mikhail Baranchuk, Martin Strohmeier, Vijay Bolina, Philip H. S. Torr, Lewis Hammond, and Christian Schroeder de Witt (2024; revised 2025).** [Secret Collusion among AI Agents: Multi-Agent Deception via Steganography](https://arxiv.org/abs/2402.07510). arXiv:2402.07510, version 5. Earlier title: *Secret Collusion among Generative AI Agents*. Framework and experiments for covert coordination.

22. **Mason Nakamura, Abhinav Kumar, Saswat Das, Sahar Abdelnabi, Saaduddin Mahmud, Ferdinando Fioretto, Shlomo Zilberstein, and Eugene Bagdasarian (2026).** [Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems](https://arxiv.org/abs/2602.15198). arXiv:2602.15198. Distinguishes communication-based and action-based collusion in controlled tasks.

23. **Xijie Zeng and Frank Rudzicz (2026).** [Voluntary Collusion with Secret Tools in Competing LLM Agents](https://arxiv.org/abs/2605.27593). Preprint. Evidence about tool adoption in two constructed strategic environments.

24. **Qi Pang, Virginia Smith, and Wenting Zheng (2026).** [Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion](https://arxiv.org/abs/2609.28900). Preprint, first posted 24 September 2026. A steganographic protocol and evaluation motivating scrutiny of transcript-only monitoring.
