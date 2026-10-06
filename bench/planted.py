"""A benchmark for agents working on a shared record: errors, dead ends and questions are planted.

    python3 bench/planted.py setup DIR      # a world store with planted errors, and an empty agent store
    python3 bench/planted.py task DIR       # the prompt to give the agent (run it with EV_DIR=DIR/agent/.evidence)
    python3 bench/planted.py baseline DIR   # a scripted agent: verify whatever `ev todo` offers
    python3 bench/planted.py score DIR      # how well the agent's record matches the hidden answer key

The world is about counting primes, where every claim can be checked by running a script. Some
claims are false, some true claims rest on false ones, one approach is a recorded dead end, and
some questions are open. The answer key is kept outside both stores.

The score asks: were the planted errors refuted, were true claims left standing, were the
claims resting on errors flagged, were the open questions answered correctly and reproducibly,
and was the dead end avoided.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence import Store  # noqa: E402

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

TRUE = {100: 25, 1000: 168, 10000: 1229, 100000: 9592}
FALSE = {2000: 304, 20000: 2263}  # the true counts are 303 and 2262
QUESTIONS = {50000: 5133, 200000: 17984}
DEAD_END = "trial division"


def pi(n: int) -> int:
    """The true count, for checking the constants above."""
    sieve = bytearray([1]) * n
    sieve[:2] = b"\0\0"
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    return sum(sieve)


def setup(d: Path) -> None:
    world = Store.init(d / "world", {"agent": "world", "lab": "world"})
    script = d / "count.py"
    script.write_text(COUNT)
    key = {"true": [], "false": [], "downstream": [], "questions": {}}
    ids = {}
    for n, k in {**TRUE, **FALSE}.items():
        h = world.claim(f"There are {k} primes below {n}.", files=[script], cmd=f"python3 count.py {n} {k}")
        ids[n] = h
        key["false" if n in FALSE else "true"].append(h)
    key["downstream"].append(world.claim(
        "Between 1000 and 2000 there are 136 primes.", depends_on=[ids[1000], ids[2000]], notes=["304 - 168"]))
    key["downstream"].append(world.claim(
        "Between 10000 and 20000 there are 1034 primes.", depends_on=[ids[10000], ids[20000]], notes=["2263 - 1229"]))
    world.claim("Counting primes below 10^7 by trial division takes over ten minutes in Python.", kind="negative",
                notes=["use a sieve"])
    root = world.ask("How are the primes distributed below 200000?")
    for n, k in QUESTIONS.items():
        key["questions"][world.ask(f"How many primes are there below {n}?", parents=[root])] = k
    agent = Store.init(d / "agent", {"agent": "agent", "lab": "agent-lab"})
    agent.configure(remotes={"world": str(d / "world")})
    (d / "key.json").write_text(json.dumps(key, indent=2))
    print(f"world at {d / 'world'}, agent store at {d / 'agent'}, answer key at {d / 'key.json'}")


def task(d: Path) -> str:
    return (f"You are a research agent. Your record is the evidence store at {d / 'agent'}; set "
            f"EV_DIR={d / 'agent' / '.evidence'} and use the `ev` command (run `ev guide` first). Pull the "
            "world's record, check it, and strengthen it: reproduce or refute what others claim, flag what rests "
            "on errors, and answer the open questions with claims that anyone can re-run. Record what you find, "
            "including negative results. Work until `ev todo` offers nothing you can usefully do.")


def baseline(d: Path) -> None:
    """A scripted agent that only re-runs what it is offered: the floor any real agent should beat."""
    agent = Store(d / "agent" / ".evidence")
    with_world = Store(d / "world" / ".evidence")
    agent.pull(with_world)
    for _ in range(100):
        todo = [t for t in agent.todo(agent.author()) if t["action"] == "reproduce"]
        if not todo:
            break
        agent.verify(todo[0]["id"], unsafe=True)


def score(d: Path) -> dict:
    key = json.loads((d / "key.json").read_text())
    agent = Store(d / "agent" / ".evidence")
    statuses = agent.statuses()
    claims = agent.objects("claim")

    def frac(xs, ok):
        return round(sum(1 for x in xs if x in statuses and ok(statuses[x])) / len(xs), 3)

    answered = 0
    for q, k in key["questions"].items():
        for h, c in claims.items():
            # Nobody else re-runs the agent's answers here, so a self-check counts as reproducible.
            reran = statuses[h].label == "reproduced" or (statuses[h].label == "proposed" and statuses[h].self_checked)
            if q in c.get("answers", []) and reran and str(k) in re.findall(
                    r"\d+", c["statement"].replace(",", "")):
                answered += 1
                break
    wasted = [h for h, c in claims.items() if c["author"].get("agent") != "world" and DEAD_END in c["statement"].lower()
              and c["kind"] != "negative"]
    out = {
        "errors_refuted": frac(key["false"], lambda s: s.state == "refuted"),
        "true_left_standing": frac(key["true"], lambda s: s.state not in ("refuted", "superseded")),
        "true_reproduced": frac(key["true"], lambda s: s.state == "reproduced"),
        "downstream_flagged": frac(key["downstream"], lambda s: s.label in ("at-risk", "refuted")),
        "questions_answered": round(answered / len(key["questions"]), 3),
        "dead_end_repeated": len(wasted),
        "claims_recorded": sum(1 for c in claims.values() if c["author"].get("agent") != "world"),
    }
    return out


def main(argv: list[str]) -> None:
    cmd, d = argv[0], Path(argv[1])
    if cmd == "setup":
        setup(d)
    elif cmd == "task":
        print(task(d))
    elif cmd == "baseline":
        baseline(d)
        print(json.dumps(score(d), indent=2))
    elif cmd == "score":
        print(json.dumps(score(d), indent=2))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
