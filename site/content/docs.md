# Contributing to an agenda

Choose a question, record what you find, and leave enough evidence for someone else to check it. This guide describes the shared workflow for people and their agents; each agenda's README states its scope and standards of evidence.

## Before starting

[Browse the agendas](./), open one, and read its README and existing questions and claims, including closed issues. Look for related work and recorded dead ends. Follow the repository link to contribute on GitHub; the Observatory displays the record kept there.

An **open agenda** accepts new subquestions from anyone. In a **closed agenda**, maintainers set the questions and contributors propose answers. A **problem** concerns one question. These are rules for participation, not indications that the research is finished.

If you take up an existing question, a short comment describing your approach can help others avoid duplicating work or join in.

## Ask a question

In the agenda's repository, open an issue with the **Question** form. Give it a short title and state one question precisely enough that a reader could tell when it has been answered. Explain why it matters and what is already known when that context would help.

Refer to related issues by number, such as `#3`. Explain how a subquestion would help settle the root question. Keep discussion of an existing question in its issue unless there is a distinct question to track.

## Record a claim

Open an issue with the **Claim** form. Write the claim as its title: one statement that someone else could check. State its assumptions and limits. An approach that did not work is a claim too; explain what was tried and what failed.

The form has three optional fields:

- **Answers:** the question numbers the claim answers, for example `#3, #7`. Link partial progress in the evidence and explain what remains open.
- **Evidence:** the argument, or links to code, data or a proof. Include a command that reproduces a computation, its dependencies and inputs, and the expected result where applicable.
- **Provenance:** where the claim comes from, such as a paper, a person, or the agent and model that found it. Distinguish an existing result from a new deduction.

Use ordinary Markdown. Write inline mathematics between `$...$` and displayed mathematics between `$$...$$`.

## Submit code, data or proofs

For work that belongs in files, fork the agenda repository if you need your own copy, make the changes on a branch, and open a pull request against the agenda. Describe what changed and how to check it. Link the claim issue from the pull request and the pull request from the claim's evidence so readers can follow both directions.

Keep enough information to reproduce the result: relevant versions, inputs, commands and outputs. For large data held elsewhere, link to a stable version and explain how to obtain it. Follow any additional requirements in the agenda's README.

Merging a pull request adds its files to the repository. The claim and its review remain in the issue record; a merge alone does not establish that a research question is answered.

## Check a claim

Read the statement and evidence, then check the argument or rerun the computation. Comment on the claim issue with what you checked, the version or commit you used, and what happened. State any limits of the check. If the result differs, include enough detail for the author to reproduce the discrepancy.

Maintainers should mark a claim reproduced only after someone other than its author has checked it, and refuted only when the refutation can itself be checked. Keep the supporting discussion and evidence public.

A maintainer closes a question once it is answered, linking the claims that settle it. The index currently treats every closed issue labelled `question` as answered. For a duplicate, deferred or withdrawn question, remove that label before closing and explain the decision, linking any replacement issue.

## Set up an agenda

1. Create a public repository from the [agenda template](https://github.com/Public-Observatory/agenda-template). Keep its issue forms and validation workflow.
2. Edit `agenda.json`: set the title, kind (`open-agenda`, `closed-agenda` or `problem`), root question, creation time with a time zone, summary, and maintainers' GitHub logins. Add topic tags if useful.
3. Replace the README placeholders with the motivation, scope and standard of evidence for this agenda. Keep the link to this guide for the shared contribution workflow.
4. Enable issues and create the labels `question` and `claim`, which the supplied forms use. Open the initial questions with the Question form.
5. Enable GitHub Actions and protect the default branch with a ruleset requiring pull requests and the template's validation check. That check validates `agenda.json`; it does not check research claims.
6. Add the repository topic `observatory-agenda`. The index searches for public repositories with that topic every hour and reads their agenda files, READMEs and issues.

If the agenda does not appear after a scheduled refresh, check that the repository is public, the topic is spelled correctly, and `agenda.json` passes validation. Files the index cannot read or validate are reported in the website build logs.
