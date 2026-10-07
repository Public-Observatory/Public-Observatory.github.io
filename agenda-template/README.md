# Title of the agenda

*An agenda on the [Public Observatory](https://public-observatory.github.io/). `agenda.json` states its root question; its questions and claims are this repository's issues.*

## Motivation

Why the question matters, what is already known, and where the difficulty lies. Write for a reader who knows the field but not this problem.

## Scope

What counts as progress, what is out of scope, and what standard of evidence the maintainers ask for (a Lean proof, a re-runnable experiment, a computation).

## How to contribute

**To ask a question,** open an issue with the *Question* form and write the question as its title.

**To record a claim,** open an issue with the *Claim* form and write the claim as its title: one statement that someone else could check. An approach that did not work is a claim too, and recording it saves the next person the trouble. Give the evidence in the issue, or link to a pull request with the code, data or proof.

**To check a claim,** re-run it and say in its issue what you did and what happened. A maintainer closes a question once it is answered.

Read the open questions and claims before starting, so as not to repeat a known dead end. Refer to other issues by number, e.g. #3. Write mathematics in LaTeX, between `$...$` or `$$...$$`.

## Setting up a new agenda from this template

1. Create a repository from this template, edit `agenda.json` and this file, and add the topic `observatory-agenda` so that the Observatory lists it.
2. Create the labels `question` and `claim`.
3. Protect `main` with a ruleset so that changes arrive through pull requests, which the `check` workflow runs on.
