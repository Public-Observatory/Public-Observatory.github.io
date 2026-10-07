# Research agendas

## Safe cooperation in open-source game theory

[The new agenda](open-source-game-theory/README.md) studies safe cooperation among agents that inspect one another’s programs. It includes five proposed questions, a first-year plan, and 24 annotated references, with explicit attribution to AI-Safety for Mathematicians and Lionel Levine. Its `agenda.json` and `issues.json` support local previews; the questions have not been posted as GitHub issues.

```sh
python3 site/build.py local /tmp/observatory-game-theory-preview agendas/open-source-game-theory
```

## Revisions of the existing agendas

Local revisions of the two agendas indexed by the Observatory, prepared on 7 October 2026. The live repositories and issues have not been changed. Each directory contains a proposed `agenda.json`, a README, and the main questions in the `issues.json` format accepted by `site/build.py local`.

The selection is five questions:

1. **Lacunarity:** does every fixed gap ratio give uniform stability for sine phase retrieval?
2. **Density:** can a stable sine spectrum have growth exponent greater than one third?
3. **Integrability:** does stable sine phase retrieval force an improvement from $L^2$ to some $L^p$, $p>2$?
4. **Zero-free regions:** can the marked fourth-moment estimate be extended below its present parameter range, and does that improve seven eighths?
5. **Zeros on the line:** can a weaker, one-sided substitute for the proposed higher-moment asymptotics prove a proportion of at least 68%?

The first three ask what makes recovery possible; the last two ask for specific analytic advances. Proof verification remains necessary supporting work. An exact constant for one example, a general request to check a paper, and a restatement of a conditional result already in that paper are not separate research priorities.

The sine agenda includes a proof that polynomial density is already available by combining a greedy additive construction with an existing stability criterion. This raises the old density question beyond merely beating logarithmic growth. The Riemann questions explicitly retain the unverified status of the inputs on which they depend. These are proposed research questions, not a certification that no answer exists elsewhere in the literature.

## Consolidating the existing issues

| Agenda | Existing issues | Proposed treatment |
| --- | --- | --- |
| Sine | #1, #4 | Combine as #1: uniform lacunary stability; keep the dyadic case as the first test. |
| Sine | #2 | Replace by the density-exponent question, with the polynomial baseline linked. |
| Sine | #3 | Keep the necessity of higher integrability. Defer the separate Sidon sufficiency question. |
| Sine | #5, #6 | Defer sampling and fixed Fourier modulus; both require a different set of tools. |
| Sine | claims #7, #8 and answered question #9 | Preserve their statements, evidence, and history. |
| Riemann | #5 | Replace by the specific fourth-moment extension question. |
| Riemann | #9 | Replace by the one-sided higher-moment question. |
| Riemann | #1, #4, #8 | Retain as supporting verification tasks, linked from the relevant main question. |
| Riemann | #2, #3, #6 | Preserve as consolidated or deferred, not answered. |

The current index interprets every closed issue labelled `question` as answered. Consequently, closing a question just to shorten the agenda misstates its mathematical status. Until the index distinguishes deferred and consolidated questions, remove the `question` label from such issues and retain an explicit status explanation. The local preview contains only the five proposed main questions; it is not a replacement for the live issue archive.

To build the proposed selection separately from the live cache:

```sh
python3 site/build.py local /tmp/observatory-agenda-preview agendas/sine-phase-retrieval agendas/riemann-hypothesis
```
