# Benchmark results

Each run of a real agent on `bench/planted.py` is recorded here as one JSON file, so that results for different models and harnesses can be compared and the roadmap's acceptance test (VISION.md, item 1) can be checked from the files alone.

## Recording a run

```sh
python3 bench/planted.py run /tmp/run1 --model MODEL --harness HARNESS --cmd "AGENT COMMAND"
```

`run` sets up a fresh world in the given directory (which must not already hold one), starts the agent command in a shell with the task prompt on standard input, the working directory set to the agent's store, `EV_DIR` pointing at that store and the repository on `PYTHONPATH`, waits for it to finish (or for `--timeout` seconds), scores the agent's store, and writes two files:

- `bench/results/STAMP-MODEL.json`, the record of the run;
- `bench/results/transcripts/STAMP-MODEL.txt`, everything the command wrote to standard output and standard error.

The agent command is any program that reads a prompt on standard input and acts on it, for instance a coding agent in non-interactive mode. It should not be given this repository as its working directory, since `bench/planted.py` states which planted claims are false.

## The record

| field | meaning |
| --- | --- |
| `model` | the model the agent used, as given by `--model` |
| `harness` | the program that drove it (CLI or MCP client), as given by `--harness` |
| `command` | the exact agent command |
| `date` | when the run started, in UTC |
| `seconds` | wall-clock duration of the agent command |
| `exit` | its exit code, or `null` if it was stopped at the timeout |
| `scores` | the output of `planted.py score` (below) |
| `transcript` | the transcript's path, relative to this directory |

## The scores

| score | meaning | scripted baseline |
| --- | --- | --- |
| `errors_refuted` | fraction of the planted false counts that the agent's record shows refuted | 1.0 |
| `true_left_standing` | fraction of the true counts neither refuted nor superseded | 1.0 |
| `true_reproduced` | fraction of the true counts reproduced | 1.0 |
| `dependants_reclaimed` | fraction of the wrong derived claims for which the agent recorded a standing claim with the correct count, either naming both ends of the range or recorded as superseding the wrong claim | 0.0 |
| `questions_answered` | fraction of the open questions with a standing answer by the agent whose value (or, without a value, statement) is the correct count; reproduction is not required | 0.0 |
| `answers_wrong` | number of the agent's standing answers to those questions that state a wrong count | 0 |
| `contested_resolved` | 1.0 if the wrong answer to the contested question is refuted and the right one stands | 1.0 |
| `dead_end_repeated` | number of the agent's claims that try trial division again without engaging the recorded dead end; reviewing it, building on it, or recording a negative result is not a repeat | 0 |
| `claims_recorded` | number of claims the agent recorded | 0 |

The acceptance test for roadmap item 1 asks for at least three models with five runs each, through both the CLI and MCP, with a median agent that matches the baseline on `errors_refuted`, `true_left_standing`, `true_reproduced` and `contested_resolved`, reaches at least 0.5 on `questions_answered`, and has `dead_end_repeated` equal to 0 in every run.
