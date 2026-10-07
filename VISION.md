# The Public Observatory: vision

## 1. The aim

The Public Observatory should become the place where one finds out what is worth working on, what has already been tried, and what stands. A person with a question poses it once, as an agenda. Anyone with compute, whether a single researcher with one agent or a laboratory with thousands, takes up a piece of it, records what was found, failures included, and leaves the agenda more precise than it found it. A reader who wants to know the state of a question reads one page rather than a literature.

## 2. Why now

Agents can now do much of the exploratory work of research: they try an approach, run it, check another's result, and report. Two consequences follow. First, the scarce input is no longer labour but the choice of question. Open-problem lists record questions that are already sharp, but most of research consists of making questions sharp, and agents can now do that work too if they are given a place to do it. Second, many groups now attack the same famous problems with copies of the same models, and none of them sees the others' dead ends. Effort is duplicated wherever there is no common record of what has been tried, as it was in observational astronomy before public archives.

## 3. The model: an observatory, not a laboratory

An observatory holds an instrument, accepts proposals with a science case, allocates time among them, and puts every observation into a public archive, so that nobody points a telescope at the same field twice. The Public Observatory keeps the proposals and the archive and leaves the instrument time to others. An agenda is the proposal; its repository is the archive. Compute, models and money belong to whoever holds them; the Observatory tells them where these would be well spent and shows afterwards what they bought.

## 4. Principles

1. **Questions are public; standards are stated.** Anyone may pose an agenda, and its maintainers decide what enters it. They state in advance what counts as a check, and a claim is marked reproduced only when someone other than its author has checked it, and refuted only when the refutation can itself be checked.
2. **Nobody controls admission.** An agenda is any public repository with the topic `observatory-agenda`. The index lists it wherever it lives, so the Observatory cannot become a gatekeeper.
3. **Git is enough.** An agenda is a git repository: a file stating its question, issues for its questions and claims, and pull requests for code, data and proofs. The website is static and rebuilt from GitHub. There is no server to run, fund or trust, and any agenda can be copied by cloning it.
4. **Failure is part of the result.** A recorded dead end is worth as much to the next worker as a success, and an agenda is judged by how much it has settled, not only by what it has proved.
5. **Private now, public later.** A laboratory may work in a private fork and open its pull request when it chooses.
6. **People and agents on equal terms.** A claim is recorded through the same form whether a person or an agent writes it, and is judged by the same standard.

## 5. What it is not

The Observatory is not a journal: it does not referee, rank authors or confer prestige. It is not a funder, a harness or a laboratory: it runs no agents and allocates no compute. It is not a social network: there are no likes, follows or comments beyond those GitHub already provides. It does not replace the paper. A paper remains the right form when a major result must be explained to people, and an agenda is what it should cite.

## 6. Stages

1. **A handful of agendas, worked on in earnest.** Begin where checking is cheap: computation with known answers (counting primes is the first), Lean mathematics, and reproducible machine-learning experiments. *Success:* at least three agendas, each with contributions from at least two people or laboratories besides its maintainers, and at least one claim in each reproduced by someone other than its author.
2. **Agendas that decompose themselves.** When an agenda is posed, an agent proposes subquestions that can be checked; the index ranks agendas by how much of them is checkable. *Success:* most new agendas reach a decomposition into checkable questions within a week, without a maintainer writing it.
3. **A record that checks itself.** Issues and labels serve while agendas are small and their maintainers can follow every claim. Once they cannot, claims should carry a command that anyone can re-run, and whether a claim stands, and what rests on a refuted one, should follow mechanically from the checks on record rather than from a maintainer's label. *Success:* in one agenda, a refuted claim causes every claim built on it to be flagged without anyone doing so by hand.
4. **One list of work across all agendas.** The index should rank open questions and unchecked claims across all agendas, weighted by expected cost, so that someone with an idle cluster can ask what to run. *Success:* a contributor with no prior connection to any agenda takes an item from the list and has the result merged.
5. **Funders read the Observatory.** Those who allocate compute, whether companies, foundations or a publicly funded institute for AI-assisted science, use the agendas to choose what to support and to see what their support produced. *Success:* compute is granted against an agenda by someone other than its maintainers, with the outcome visible in it.
6. **Broad public questions.** Once agendas compose, so that one agenda's answered question becomes another's premise, the Observatory can hold questions too large for any one group, and answer them in a form that any reader can check.

## 7. Measures

The Observatory succeeds to the extent that work is not repeated and that what is claimed is checked. We shall therefore watch: the number of agendas and of independent contributors to them; the fraction of claims reproduced by someone other than their author; the number of dead ends recorded; the fraction of attempts that an earlier record could have prevented; and how much of each agenda a human must read to learn its state.

## 8. Open questions

How agendas that stay vague should be discouraged without a central editor; when an agenda has outgrown issues and labels, and what should replace them; how an agent should find, before it starts, that its approach has already been tried; and how credit for contributions should be shown without inviting the gaming that metrics invite.
