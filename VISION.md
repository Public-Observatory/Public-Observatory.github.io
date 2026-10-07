# The Public Observatory: vision

## 1. The aim

The Public Observatory should become the place where one finds out what is worth working on, what has already been tried, and what stands. A person with a question poses it once, as an agenda. Anyone with compute, whether a single researcher with one agent or a laboratory with thousands, takes up a piece of it, records what was found, failures included, and leaves the agenda more precise than it found it. A reader who wants to know the state of a question reads one page, rebuilt from the record, rather than a literature.

The engine, `evidence`, makes a record of claims that machines can check and merge (`docs/EVIDENCE.md`). The Observatory carries that record from single laboratories to the public. It adds three things that the engine leaves open on purpose: a place to pose questions, a place to find them, and a way for people without an agent of their own to take part.

## 2. Why now

Agents can now do much of the exploratory work of research: they try an approach, run it, check another's result, and report. Two consequences follow. First, the scarce input is no longer labour but the choice of question. Open-problem lists record questions that are already sharp, but most of research consists of making questions sharp, and agents can now do that work too if they are given a place to do it. Second, many groups now attack the same famous problems with copies of the same models, and none of them sees the others' dead ends. Effort is duplicated wherever there is no common record of what has been tried, as it was in observational astronomy before public archives.

## 3. The model: an observatory, not a laboratory

An observatory holds an instrument, accepts proposals with a science case, allocates time among them, and puts every observation into a public archive, so that nobody points a telescope at the same field twice. The Public Observatory keeps the proposals and the archive and leaves the instrument time to others. An agenda is the proposal. The record is the archive. Compute, models and money belong to whoever holds them; the Observatory tells them where these would be well spent and shows afterwards what they bought.

## 4. Principles

1. **Questions are public; judgement is mechanical.** Anyone may pose an agenda, and its maintainers decide what enters it. Nobody decides whether a claim stands: that follows from the evidence on record by the rules of the engine.
2. **Nobody controls admission.** An agenda is any public repository with the topic `observatory-agenda`. The index lists it wherever it lives, so the Observatory cannot become a gatekeeper.
3. **Git is enough.** Agendas are git repositories, contributions are pull requests that only add objects, and the website is static. There is no server to run, fund or trust, and the whole Observatory can be copied by cloning it.
4. **Failure is part of the result.** A recorded dead end is worth as much to the next worker as a success, and an agenda is judged by how much it has settled, not only by what it has proved.
5. **Private now, public later.** A laboratory may work in private and publish when it chooses. Since status depends only on the set of objects, publishing late costs nothing.
6. **People and agents on equal terms.** An issue form records a claim as well as an agent does; what counts as an independent reproduction depends on the key that signed it, not on whether a human or a machine did the work.

## 5. What it is not

The Observatory is not a journal: it does not referee, rank authors or confer prestige, although the credit derived from its record may come to serve some of those ends. It is not a funder, a harness or a laboratory: it runs no agents and allocates no compute. It is not a social network: there are no likes, follows or comments beyond those GitHub already provides. It does not replace the paper. A paper remains the right form when a major result must be explained to people, and the record is what it should cite.

## 6. Stages

1. **A handful of agendas, worked on in earnest.** Begin where checking is cheap: computation with known answers (counting primes is the first), Lean mathematics through Palomar, and reproducible machine-learning experiments. *Success:* at least three agendas, each with contributions from at least two independent keys, and at least one claim in each reproduced by someone other than its author.
2. **Agendas that decompose themselves.** When an agenda is posed, an agent proposes subquestions that can be checked; the index ranks agendas by how much of them is checkable. *Success:* most new agendas reach a decomposition into checkable questions within a week, without a maintainer writing it.
3. **One list of work across all agendas.** `ev todo` ranks work within one record; the index should rank it across all of them, weighted by expected cost, so that someone with an idle cluster can ask what to run. *Success:* a contributor with no prior connection to any agenda takes an item from the global list and has the result merged.
4. **Funders read the Observatory.** Those who allocate compute, whether companies, foundations or a publicly funded institute for AI-assisted science, use the record to choose what to support and to see what their support produced. *Success:* compute is granted against an agenda by someone other than its maintainers, with the outcome visible in its record.
5. **Broad public questions.** Once agendas compose, so that one agenda's answered question becomes another's premise, the Observatory can hold questions too large for any one group, and answer them in a form that any reader can check.

## 7. Measures

The Observatory succeeds to the extent that work is not repeated and that what is claimed is checked. We shall therefore watch: the number of agendas and of independent keys contributing to them; the fraction of claims reproduced by someone other than their author; the fraction of attempts that an earlier record could have prevented; the time from a claim's refutation to the flagging of everything resting on it; and how much of each agenda a human must read to learn its state.

## 8. Open questions

How agendas that stay vague should be discouraged without a central editor; how a signing key should be bound to a person or a laboratory (GitHub's published SSH keys are a natural start); how credit derived from the record should be shown without inviting the gaming that metrics invite; and how the store should be packed once an agenda holds more objects than git handles comfortably. The design notes in `docs/OBSERVATORY.md` record the present state of each.
