"""A benchmark for agents working on a shared record: errors, dead ends and questions are planted.

    python3 bench/planted.py setup DIR      # a world store with planted errors, and an empty agent store
    python3 bench/planted.py task DIR       # the prompt to give the agent (run it with EV_DIR=DIR/agent/.evidence)
    python3 bench/planted.py baseline DIR   # a scripted agent: verify whatever `ev todo` offers
    python3 bench/planted.py score DIR      # how well the agent's record matches the answer key
    python3 bench/planted.py swarm DIR --agents 4 [--no-leases]   # scripted agents sharing one world
    python3 bench/planted.py run DIR --cmd "AGENT COMMAND" --model NAME   # set up, run, score, record

The world is about counting primes, where every claim can be checked by running a script. Some
claims are false, some claims derived from false ones are themselves wrong, one approach is a
recorded dead end, one question has two answers that disagree, and some questions are open.

No answer key is written to disk: `score` derives it from the constants below and finds the
planted objects in the world store by their text. The score asks: were the planted errors refuted,
were true claims left standing, were the wrong derived claims replaced by correct ones, were the
open questions answered with the correct value, was the contested question resolved, and was the
dead end avoided.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evidence import Store  # noqa: E402
from evidence.store import BROKEN, now  # noqa: E402

COUNT = """\
import sys
n, expected = int(sys.argv[1]), int(sys.argv[2])
sieve = bytearray([1]) * n
sieve[:2] = b"\\0\\0"
for i in range(2, int(n ** 0.5) + 1):
    if sieve[i]:
        sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
print(f"{sum(sieve)} primes below {n}")
sys.exit(0 if sum(sieve) == expected else 1)
"""

# The dead end is a comparison on one machine, not a duration, so that it holds on any hardware:
# the measured ratio is above a hundred, ten times the threshold.
RACE = """\
import sys, time
n = int(sys.argv[1])

def sieve(n):
    s = bytearray([1]) * n
    s[:2] = b"\\0\\0"
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]:
            s[i * i::i] = bytearray(len(s[i * i::i]))
    return sum(s)

def trial_division(n):
    count = 0
    for m in range(2, n):
        d = 2
        while d * d <= m and m % d:
            d += 1
        count += d * d > m
    return count

def best(f):
    times = []
    for _ in range(3):
        start = time.perf_counter()
        k = f(n)
        times.append(time.perf_counter() - start)
    return k, min(times)

(a, ts), (b, tt) = best(sieve), best(trial_division)
print(f"below {n}: sieve {a} primes in {ts:.4f} s, trial division {b} primes in {tt:.4f} s, ratio {tt / ts:.0f}")
sys.exit(0 if a == b and tt > 10 * ts else 1)
"""

TRUE = {100: 25, 1000: 168, 10000: 1229, 100000: 9592}
FALSE = {2000: 304, 20000: 2263}  # the true counts are 303 and 2262
DOWNSTREAM = [(1000, 2000), (10000, 20000)]  # derived from FALSE, so wrong by one
QUESTIONS = {50000: 5133, 200000: 17984}
CONTESTED = (30000, 3245, 3246)  # the question's n, the right answer, and the world's wrong one
DEAD_END = "trial division"
DEAD_END_STATEMENT = ("Counting the primes below 10^5 by trial division in Python takes more than ten times "
                      "as long as with a sieve of Eratosthenes.")
ROOT_QUESTION = "How are the primes distributed below 200000?"


def pi(n: int) -> int:
    """The true count, for checking the constants above."""
    sieve = bytearray([1]) * n
    sieve[:2] = b"\0\0"
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    return sum(sieve)


def count_statement(n: int, k: int) -> str:
    return f"There are {k} primes below {n}."


def range_statement(lo: int, hi: int, k: int) -> str:
    return f"Between {lo} and {hi} there are {k} primes."


def question_text(n: int) -> str:
    return f"How many primes are there below {n}?"


def stated(lo: int, hi: int) -> int:
    """The count the world derives for a range, from its own (possibly wrong) counts."""
    counts = {**TRUE, **FALSE}
    return counts[hi] - counts[lo]


def key() -> dict:
    """The answer key, derived from the constants alone, so that nothing secret is written to disk."""
    n, right, wrong = CONTESTED
    return {
        "true": [count_statement(n, k) for n, k in TRUE.items()],
        "false": [count_statement(n, k) for n, k in FALSE.items()],
        "downstream": {range_statement(lo, hi, stated(lo, hi)): (lo, hi, pi(hi) - pi(lo)) for lo, hi in DOWNSTREAM},
        "questions": {question_text(n): k for n, k in QUESTIONS.items()},
        "contested": {"question": question_text(n), "right": count_statement(n, right),
                      "wrong": count_statement(n, wrong)},
        "dead_end": DEAD_END_STATEMENT,
    }


@contextlib.contextmanager
def own_identities():
    """Let each store speak as configured, whatever EV_AGENT and friends the caller has set."""
    saved = {k: os.environ.pop(k) for k in ("EV_AGENT", "EV_LAB", "EV_MODEL", "EV_KEY") if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def build_world(d: Path) -> Store:
    if (d / "world").exists():
        raise SystemExit(f"{d / 'world'} exists; use a fresh directory")
    d.mkdir(parents=True, exist_ok=True)
    with own_identities():
        world = Store.init(d / "world", {"agent": "world", "lab": "world"})
        count, race = d / "count.py", d / "race.py"
        count.write_text(COUNT)
        race.write_text(RACE)
        ids, counts = {}, {**TRUE, **FALSE}
        for n, k in counts.items():
            ids[n] = world.claim(count_statement(n, k), files=[count], cmd=f"python3 count.py {n} {k}",
                                 value={"exact": k})
        for lo, hi in DOWNSTREAM:
            world.claim(range_statement(lo, hi, stated(lo, hi)), depends_on=[ids[lo], ids[hi]],
                        notes=[f"{counts[hi]} - {counts[lo]}"], value={"exact": stated(lo, hi)})
        world.claim(DEAD_END_STATEMENT, kind="negative", files=[race], cmd="python3 race.py 100000",
                    notes=["use a sieve"])
        root = world.ask(ROOT_QUESTION)
        for n in QUESTIONS:
            world.ask(question_text(n), parents=[root])
        # The contested question: the world answers it wrongly, a rival lab rightly.
        n, right, wrong = CONTESTED
        q = world.ask(question_text(n), parents=[root])
        world.claim(count_statement(n, wrong), files=[count], cmd=f"python3 count.py {n} {wrong}", answers=[q],
                    value={"exact": wrong})
        rival = Store.init(d / "rival", {"agent": "rival", "lab": "rival"})
        rival.pull(world)
        rival.claim(count_statement(n, right), files=[count], cmd=f"python3 count.py {n} {right}", answers=[q],
                    value={"exact": right})
        world.pull(rival)
        shutil.rmtree(d / "rival")
        for f in (count, race):
            f.unlink()
    return world


def setup(d: Path) -> None:
    build_world(d)
    with own_identities():
        agent = Store.init(d / "agent", {"agent": "agent", "lab": "agent-lab"})
        agent.configure(remotes={"world": str(d / "world")})
    print(f"world at {d / 'world'}, agent store at {d / 'agent'}; the answer key is derived when scoring")


def task(d: Path) -> str:
    return (f"You are a research agent. Your record is the evidence store at {d / 'agent'}; set "
            f"EV_DIR={d / 'agent' / '.evidence'} and use the `ev` command (run `ev guide` first). Pull the "
            "world's record, check it, and strengthen it: reproduce or refute what others claim, replace "
            "claims that rest on errors with correct ones, resolve answers that disagree, and answer the open "
            "questions with claims that carry a value and that anyone can re-run. Record what you find, "
            "including negative results. Work until `ev todo` offers nothing you can usefully do.")


def reproduce_items(s: Store, at: str | None = None) -> list[dict]:
    return [t for t in s.todo(s.author(), at=at) if t["action"] == "reproduce"]


def baseline(d: Path) -> None:
    """A scripted agent that only re-runs what it is offered: the floor any real agent should beat."""
    agent = Store(d / "agent" / ".evidence")
    agent.pull(Store(d / "world" / ".evidence"))
    for _ in range(100):
        if not (todo := reproduce_items(agent)):
            break
        agent.verify(todo[0]["id"], unsafe=True)


def swarm(d: Path, agents: int = 4, leases: bool = True, rounds: int = 100) -> dict:
    """Scripted baseline agents in separate stores, sharing by pull, interleaved round by round.

    In each round every agent in turn pulls from the world and from every other agent, takes the
    first item `todo` offers for reproduction and, with leases, leases it; then all of them run
    what they took. Running after everyone has chosen models agents working at the same time, which
    is when they collide. With leases an agent skips items others hold and waits when nothing else
    is left. A duplicated attempt is a verification of a claim that another agent also verified.
    """
    world = Store(d / "world" / ".evidence") if (d / "world").exists() else build_world(d)
    with own_identities():
        stores = [Store.init(d / f"swarm-{i}", {"agent": f"bot-{i}", "lab": f"swarm-{i}"}) for i in range(agents)]
        attempts: dict[str, list[int]] = {}
        done = 0
        for done in range(1, rounds + 1):
            picks = []
            for i, s in enumerate(stores):
                for other in [world] + stores:
                    if other is not s:
                        s.pull(other)
                todo = reproduce_items(s, at=now())
                if leases:
                    todo = [t for t in todo if not any(not lease["mine"] for lease in t["leased"])]
                if todo:
                    if leases:
                        s.lease(todo[0]["id"], timedelta(hours=1))
                    picks.append((i, todo[0]["id"]))
            if not picks:
                done -= 1
                break
            for i, h in picks:
                stores[i].verify(h, unsafe=True)
                attempts.setdefault(h, []).append(i)
    return {"agents": agents, "leases": leases, "rounds": done, "attempts": sum(map(len, attempts.values())),
            "claims_verified": len(attempts), "duplicated": sum(len(v) - 1 for v in attempts.values())}


def numbers(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text.replace(",", ""))]


def states(c: dict, k: int) -> bool | None:
    """Whether a claim states the count k: by its value if it has one, else by its statement."""
    if "value" in c:
        v = c["value"]
        x = v.get("exact") if "exact" in v else v.get("quantity")
        try:
            return not isinstance(x, bool) and float(x) == k
        except (TypeError, ValueError):
            return False
    return k in numbers(c["statement"])


def score(d: Path) -> dict:
    k = key()
    world = Store(d / "world" / ".evidence")
    agent = Store(d / "agent" / ".evidence")
    by_text = {c["statement"]: h for h, c in world.objects("claim").items()}
    by_text.update({q["text"]: h for h, q in world.objects("question").items()})
    planted = set(world.ids())
    statuses = agent.statuses()
    claims = agent.objects("claim")
    reviews = agent.objects("review")
    mine = {h: c for h, c in claims.items() if h not in planted}
    standing = {h for h in mine if statuses[h].state not in BROKEN}

    def holds(text, ok):
        h = by_text.get(text)
        return h in statuses and ok(statuses[h])

    def frac(texts, ok):
        return round(sum(holds(t, ok) for t in texts) / len(texts), 3)

    # A wrong derived claim is replaced when the agent states the right count for the same range,
    # in a claim that names both endpoints or that it recorded as superseding the wrong one.
    reclaimed = 0
    for text, (lo, hi, right) in k["downstream"].items():
        superseders = {r["superseded_by"] for r in reviews.values() if r["claim"] == by_text.get(text)}
        reclaimed += any(states(c, right) and (h in superseders or {lo, hi} <= set(numbers(c["statement"])))
                         for h, c in mine.items() if h in standing)

    # Questions are scored on the stated value, not on who reproduced the answer.
    answered = wrong = 0
    for text, right in k["questions"].items():
        q = by_text.get(text)
        answers = [h for h in standing if q in mine[h].get("answers", [])]
        answered += any(states(mine[h], right) for h in answers)
        wrong += sum(not states(mine[h], right) for h in answers)

    contested = k["contested"]
    resolved = holds(contested["wrong"], lambda s: s.state == "refuted") and \
        holds(contested["right"], lambda s: s.state not in BROKEN)

    # Trying trial division again is a repeat only if the agent ignored the recorded dead end:
    # reviewing the negative claim, building on it, or recording a negative result engages it.
    dead_end = by_text.get(k["dead_end"])
    engaged = any(r["claim"] == dead_end for h, r in reviews.items() if h not in planted)

    def text(c):
        return " ".join([c["statement"]] + [e.get("text", e.get("cmd", "")) for e in c["evidence"]]).lower()

    wasted = [h for h, c in mine.items() if not engaged and c["kind"] != "negative"
              and dead_end not in c["depends_on"] and DEAD_END in text(c)]
    return {
        "errors_refuted": frac(k["false"], lambda s: s.state == "refuted"),
        "true_left_standing": frac(k["true"], lambda s: s.state not in BROKEN),
        "true_reproduced": frac(k["true"], lambda s: s.state == "reproduced"),
        "dependants_reclaimed": round(reclaimed / len(k["downstream"]), 3),
        "questions_answered": round(answered / len(k["questions"]), 3),
        "answers_wrong": wrong,
        "contested_resolved": float(resolved),
        "dead_end_repeated": len(wasted),
        "claims_recorded": len(mine),
    }


def run(d: Path, cmd: str, model: str, harness: str, out: Path, timeout: float | None = None) -> dict:
    """Set up a world, give an agent command the task on stdin, score it, and record the run."""
    setup(d)
    env = {**os.environ, "EV_DIR": str(d / "agent" / ".evidence"),
           "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))}
    date = datetime.now(timezone.utc)
    stamp = date.strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{re.sub(r'[^A-Za-z0-9.-]+', '-', model).strip('-') or 'model'}"
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    transcript = out / "transcripts" / f"{name}.txt"
    start = time.monotonic()
    with transcript.open("w") as f:
        try:
            code = subprocess.run(cmd, shell=True, input=task(d), text=True, stdout=f, stderr=subprocess.STDOUT,
                                  cwd=d / "agent", env=env, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = None
    record = {"model": model, "harness": harness, "command": cmd, "date": date.isoformat(timespec="seconds"),
              "seconds": round(time.monotonic() - start, 1), "exit": code, "scores": score(d),
              "transcript": str(Path("transcripts") / transcript.name)}
    (out / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="planted.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["setup", "task", "baseline", "score", "swarm", "run"])
    p.add_argument("dir", type=Path)
    p.add_argument("--agents", type=int, default=4, help="swarm: number of scripted agents")
    p.add_argument("--no-leases", action="store_true", help="swarm: agents do not lease what they take")
    p.add_argument("--cmd", help="run: the agent command; it reads the task on stdin")
    p.add_argument("--model", default="unknown", help="run: the model the agent uses")
    p.add_argument("--harness", help="run: the harness (default: the first word of --cmd)")
    p.add_argument("--out", type=Path, default=ROOT / "bench" / "results", help="run: where to write the record")
    p.add_argument("--timeout", type=float, help="run: seconds before the agent is stopped")
    a = p.parse_args(argv)
    if a.command == "setup":
        setup(a.dir)
    elif a.command == "task":
        print(task(a.dir))
    elif a.command == "baseline":
        baseline(a.dir)
        print(json.dumps(score(a.dir), indent=2))
    elif a.command == "score":
        print(json.dumps(score(a.dir), indent=2))
    elif a.command == "swarm":
        print(json.dumps(swarm(a.dir, a.agents, leases=not a.no_leases), indent=2))
    elif not a.cmd:
        p.error("run needs --cmd")
    else:
        record = run(a.dir, a.cmd, a.model, a.harness or a.cmd.split()[0], a.out, a.timeout)
        print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
