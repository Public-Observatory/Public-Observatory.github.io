# Title of the agenda

*An agenda on the [Public Observatory](https://public-observatory.github.io/). `agenda.json` states its root question; its questions and claims are this repository's issues.*

## Motivation

Why the question matters, what is already known, and where the difficulty lies. Write for a reader who knows the field but not this problem.

## Scope

What counts as progress, what is out of scope, and what standard of evidence the maintainers ask for (a Lean proof, a re-runnable experiment, a computation).

## How to contribute

**Before starting.** Read the open questions and the claims among the issues, so as not to repeat a known dead end.

**Questions and claims.** Open an issue with the *Question* or *Claim* form, by hand or through an agent with access to GitHub. Refer to other questions and claims by their issue numbers. Write mathematics in LaTeX, between `$...$` inline or `$$...$$` displayed; GitHub and the Observatory both typeset it. A claim states one thing precisely enough that someone else could check it; an approach that did not work is recorded as a claim too, so that nobody repeats it.

**Code, data and proofs.** Open a pull request and link it from the claim. Give the command that reproduces the claim, if there is one.

**Checks.** To check a claim, re-run it and say in its issue what you did and what happened. A maintainer closes a question once it is answered.

## Setting up a new agenda from this template

1. Create a repository from this template, edit `agenda.json` and this file, and add the topic `observatory-agenda` so that the Observatory lists it.
2. Create the labels `question` and `claim`.
3. Protect `main` with a ruleset so that changes arrive through pull requests, which the `check` workflow runs on.
