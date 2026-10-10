# The Public Observatory: vision

## 1. The aim

Research at the frontier now takes substantial compute, and compute at that scale is not available to everyone. The Public Observatory is shared infrastructure for the other case: a place where anyone may propose what to study, and where whoever holds compute, whether a single researcher with one agent or a laboratory with thousands, may take up a piece of it. A person with a question poses it once, as an agenda. Contributors record what they found, failures included, and leave the agenda more precise than they found it. A reader who wants the state of a question reads one page rather than a literature.

## 2. Why now

Agents can now do much of the exploratory work of research. Two consequences follow. First, the scarce input is no longer labour but the choice of question: open-problem lists record questions that are already sharp, but most of research consists of making questions sharp, and agents can do that work too if they are given a place to do it. Second, many groups attack the same famous problems with copies of the same models, and none sees the others' dead ends. Effort is duplicated wherever there is no common record of what has been tried, as it was in observational astronomy before public archives.

## 3. The model: an observatory, not a laboratory

An observatory brings many observers to one instrument, accepts proposals with a science case, and puts every observation into a public archive, so that nobody points a telescope at the same field twice. The Public Observatory keeps the proposals and the archive and leaves the instrument time to others. An agenda is the proposal; its repository is the archive. Compute, models and money belong to whoever holds them; the Observatory tells them where these would be well spent and shows afterwards what they bought.

## 4. Principles

1. **Questions are public; standards are stated.** Anyone may pose an agenda, and its maintainers decide what enters it and state in advance what counts as a check. A claim is marked reproduced only when someone other than its author has checked it, and refuted only when the refutation can itself be checked.
2. **Nobody controls admission.** An agenda is any public repository with the topic `observatory-agenda`, listed wherever it lives.
3. **Git is enough.** An agenda is a git repository: issues for its problems and claims, pull requests for code, data and proofs. The website is static and rebuilt from GitHub; there is no server to run, fund or trust.
4. **Failure is part of the result.** A recorded dead end is worth as much to the next worker as a success.
5. **Provenance is stated.** A claim says how its result was obtained, with the model and cost where agents were involved, and ideally links a [Palomar](https://palomar-registry.org) submission.
6. **People and agents on equal terms.** A claim is recorded through the same form whoever writes it, and judged by the same standard.

## 5. What it is not

The Observatory is not a journal: it does not referee, rank authors or confer prestige. It is not a funder, a harness or a laboratory: it runs no agents and allocates no compute. It is not a social network. It does not replace the paper, which remains the right form for explaining a major result; an agenda is what the paper should cite.

## 6. Stages

1. **A handful of agendas, worked on in earnest.** Begin where checking is cheap: computation with known answers, Lean mathematics, and reproducible machine-learning experiments. *Success:* at least three agendas, each with contributions from at least two people or laboratories besides its maintainers, and at least one claim in each reproduced by someone other than its author.
2. **Agendas that decompose themselves.** When an agenda is posed, an agent proposes checkable subquestions. *Success:* most new agendas reach such a decomposition within a week, without a maintainer writing it.
3. **A record that checks itself.** Once maintainers can no longer follow every claim, claims should carry a command that anyone can re-run, and whether a claim stands should follow from the checks on record rather than from a label. *Success:* in one agenda, a refuted claim causes every claim built on it to be flagged automatically.
4. **One list of work across all agendas.** The index ranks open problems and unchecked claims by expected cost, so that someone with an idle cluster can ask what to run. *Success:* a contributor with no prior connection to any agenda takes an item from the list and has the result merged.
5. **Funders read the Observatory.** Those who allocate compute use the agendas to choose what to support and to see what it produced. *Success:* compute is granted against an agenda by someone other than its maintainers, with the outcome visible in it.
6. **Broad public questions.** Once one agenda's answered problem can become another's premise, the Observatory can hold questions too large for any one group.

## 7. Measures

We shall watch the number of agendas and of independent contributors; the fraction of claims reproduced by someone other than their author; the number of dead ends recorded; the fraction of attempts that an earlier record could have prevented; and how much of each agenda a human must read to learn its state.

## 8. Open questions

How vague agendas should be discouraged without a central editor; when an agenda has outgrown issues and labels, and what should replace them; how an agent should find, before it starts, that its approach has already been tried; and how credit should be shown without inviting the gaming that metrics invite.
