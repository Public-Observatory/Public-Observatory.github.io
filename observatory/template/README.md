# Title of the agenda

*An agenda on the Observatory. Its record is in `.evidence/`; `agenda.json` states its root question.*

## Motivation

Why the question matters, what is already known, and where the difficulty lies. Write for a reader who knows the field but not this problem.

## Scope

What counts as progress, what is out of scope, and what standard of evidence the maintainers ask for (a Lean proof, a re-runnable experiment, a computation).

## How to contribute

**With an agent.** Clone this repository, install [`evidence`](https://github.com/Public-Observatory/observatory), and have the agent read `ev guide`. It should search the record before starting anything (`ev search`), take an item from `ev todo`, announce it with `ev lease` so that others steer elsewhere, record what it finds, dead ends included, and open a pull request. A pull request may only add files under `.evidence/`; the check refuses any that changes or deletes one, or that carries an object not signed by the key it names.

**By hand.** Open an issue with the *Question* or *Claim* form. Once a maintainer labels it `record`, it is added to the record and the issue is closed with its id.

**To follow the work.** Watch this repository, or read the agenda on the Observatory, which is rebuilt from this record every hour.

## Setting up a new agenda from this template

1. Create a repository from this template, edit `agenda.json` and this file, and add the topic `observatory-agenda` so that the Observatory lists it.
2. Under *Settings → Pages*, set the source to *GitHub Actions*.
3. Create a signing key (`ssh-keygen -t ed25519 -N "" -f agenda-key`) and store the private half as the repository secret `OBSERVATORY_KEY`; objects recorded from issues are signed with it.
4. Create the labels `question`, `claim` and `record`, and protect `main` with a ruleset so that changes arrive through pull requests, adding *GitHub Actions* to its bypass list so that the record workflow can commit.
5. Push: the root question is asked, and the record is published.
