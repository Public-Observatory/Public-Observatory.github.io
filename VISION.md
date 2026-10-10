# The Public Observatory: vision

## 1. The aim

Research at the frontier now takes substantial compute, which is not available to everyone. The Public Observatory is shared infrastructure for opening it up: a public index of research agendas, each a well-posed question with its decomposition into smaller ones, worked on in public by people, laboratories and their agents. Those who hold compute take up a piece of an agenda, record what they found, failures included, and leave the agenda more precise than they found it. A reader who wants the state of a question reads one page rather than a literature.

## 2. The scarce input is the question

Agents can now do much of the exploratory work of research, so the scarce input is no longer labour but the choice of question. Open-problem lists record questions that are already sharp, but most of research consists of making questions sharp, and that work is rarely rewarded. Meanwhile many groups attack the same famous problems with copies of the same models, and none sees the others' dead ends.

The Observatory should therefore pay for what it needs most. We intend to seek funding so that people are paid to write and maintain good agendas, and to review the solutions that others submit. Compute, models and money for the work itself remain with whoever holds them; the Observatory shows them where these would be well spent and what they bought.

## 3. Principles

1. **Standards are stated.** An agenda's maintainers decide what enters it and state in advance what counts as a check. A claim is marked reproduced only when someone other than its author has checked it.
2. **Nobody controls admission.** An agenda is any public repository with the topic `observatory-agenda`, listed wherever it lives.
3. **Git is enough.** Problems and claims are issues; code, data and proofs are pull requests. The website is static, with no server to run, fund or trust.
4. **Failure is part of the result.** A recorded dead end is worth as much to the next worker as a success.
5. **Provenance is stated.** A claim says how its result was obtained, and ideally links a [Palomar](https://palomar-registry.org) submission.
6. **People and agents on equal terms.** A claim is recorded through the same form whoever writes it, and judged by the same standard.

## 4. What it is not

The Observatory is not a journal: it does not referee, rank authors or confer prestige. It runs no agents and allocates no compute. It does not replace the paper, which remains the right form for explaining a major result; an agenda is what the paper should cite.

## 5. Stages

1. **A handful of agendas, worked on in earnest.** Begin where checking is cheap: computation with known answers, Lean mathematics, and reproducible machine-learning experiments. *Success:* at least three agendas, each with contributions from at least two people or laboratories besides its maintainers, and at least one claim in each reproduced by someone other than its author.
2. **An advisory board and funding.** *Success:* an advisory board is in place, and funding is secured to pay agenda authors, maintainers and reviewers.
3. **Paid agendas and reviews.** Payment follows from the quality of an agenda and of the reviews of claims made in it. *Success:* agendas written by people with no prior connection to the Observatory are funded and then worked on by others.
4. **A record that checks itself.** Once maintainers can no longer follow every claim, claims should carry a command that anyone can re-run, and whether a claim stands should follow from the checks on record rather than from a label. *Success:* in one agenda, a refuted claim causes every claim built on it to be flagged automatically.
5. **One list of work across all agendas.** The index ranks open problems and unchecked claims by expected cost, so that someone with an idle cluster can ask what to run. *Success:* a contributor with no prior connection to any agenda takes an item from the list and has the result merged.

## 6. Open questions

How payment can reward a good agenda without inviting agendas written for the reward; how reviewers are chosen and their work judged; how vague agendas should be discouraged without a central editor; when an agenda has outgrown issues and labels; and how an agent should find, before it starts, that its approach has already been tried.
