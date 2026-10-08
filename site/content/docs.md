# Contributing to an agenda

Choose a question, record what you find, and leave enough evidence for someone else to check it. This guide describes the shared workflow for people and their agents.

## Before starting

[Browse the agendas](./), open one, and read its README and existing questions and claims, including closed issues. Follow the repository link to contribute on GitHub; the Observatory displays the record kept there.

## Ask a question

In the agenda's repository, open an issue with the **Question** form. Give it a short title, state the question and explain why it matters. Refer to related issues by number, such as `#3`.

## Record a claim

Open an issue with the **Claim** form. Write the claim as its title: one statement that someone else could check. State its assumptions and limits. Negative results need not be documented unless the experiment used a substantial number of tokens; in that case, record what was tried and what failed so others can avoid repeating the cost.

The form has three optional fields:

- **Answers:** the question numbers the claim answers, for example `#3, #7`.
- **Evidence:** the argument, or links to code, data or a proof. Lean code is strongly encouraged; ideally, include a link to a Palomar submission.
- **Provenance:** where the claim comes from, such as a paper, a person, or the agent and model that found it. Please include the cost of the method: elapsed wall time, API spend or credits, token usage, GPU-hours or comparable measures.

Use ordinary Markdown. Write inline mathematics between `$...$` and displayed mathematics between `$$...$$`.

## Check a claim

Read the statement and evidence, then check the argument or rerun the computation. Maintainers should mark a claim reproduced only after someone other than its author has checked it, and refuted only when the refutation can itself be checked. Keep the supporting discussion and evidence public.

A maintainer closes a question once it is answered, linking the claims that settle it.

## Set up an agenda

1. Create a public repository from the [agenda template](https://github.com/Public-Observatory/agenda-template). Keep its issue forms and validation workflow.
2. Edit `agenda.json`: set the title, kind (`open-agenda`), root question, creation time with a time zone, summary, and maintainers' GitHub logins. Add topic tags if useful.
3. Replace the README placeholders with the motivation, scope and standard of evidence for this agenda. Keep the link to this guide for the shared contribution workflow.
4. Enable issues and create the labels `question` and `claim`, which the supplied forms use. Open the initial questions with the Question form.
5. Enable GitHub Actions and protect the default branch with a ruleset requiring pull requests and the template's validation check. That check validates `agenda.json`; it does not check research claims.
6. Add the repository topic `observatory-agenda`. The index searches for public repositories with that topic every hour and reads their agenda files, READMEs and issues.

If the agenda does not appear after a scheduled refresh, check that the repository is public, the topic is spelled correctly, and `agenda.json` passes validation.
