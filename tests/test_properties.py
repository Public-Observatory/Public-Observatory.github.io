"""Properties that must hold for any history, checked on random ones.

Several labs claim, review, lease and pull from each other at random. Reviews include
refutations in prose, refutations by a failed run, counter-claims (some refuting each other in
cycles), self-checks, and a reviewer changing their mind. Whatever happens:
  * every lab's statuses of claims and questions, contested and disputed ones included, agree with
    a brute-force reading of its own objects, which ignores leases, so leases never move a status;
  * once every lab has pulled from every other, all labs hold the same objects and agree on
    every status and every conflict, whatever order the pulls happened in (merging is a union of
    sets).
"""

import os
import random
import tempfile
import time
import unittest
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

from evidence import Store, signing
from evidence.store import BROKEN, identity, now

SEEDS = range(int(os.environ.get("EV_SEEDS", "5")))


def oracle(store: Store) -> tuple[dict, dict]:
    """Statuses computed the slow, obvious way, from the rules as the README states them."""
    claims, reviews = store.objects("claim"), store.objects("review")
    withdrawn = {w["review"] for w in store.objects("withdrawal").values()
                 if w["review"] in reviews and identity(w["by"]) == identity(reviews[w["review"]]["by"])}
    # A reviewer's position on a claim is their latest review of it that is neither withdrawn nor inconclusive.
    position = {}
    for k, r in reviews.items():
        if k in withdrawn or r["verdict"] == "inconclusive":
            continue
        key = (r["claim"], identity(r["by"]))
        if key not in position or (r["created"], k) > (position[key][1]["created"], position[key][0]):
            position[key] = (k, r)

    def has_command(c):
        return any(e["kind"] == "command" for e in c["evidence"])

    topple = {h: [] for h in claims}         # verdicts that hold whatever else happens
    counters = {h: [] for h in claims}       # (review, counter-claim)
    objections = {h: set() for h in claims}
    reproducers = {h: set() for h in claims}
    self_checked = set()
    for (h, who), (k, r) in position.items():
        if h not in claims:
            continue
        own = who == identity(claims[h]["author"])
        env = r.get("environment")
        failed_run = r["verdict"] == "refuted" and isinstance(env, dict) and isinstance(env.get("output_sha256"), str)
        if r["verdict"] == "reproduced":
            if own:
                self_checked.add(h)
            else:
                reproducers[h].add(who)
        elif own or failed_run:
            topple[h].append(r["verdict"])
        elif r["verdict"] == "refuted" and r.get("counter") in claims and r["counter"] != h \
                and has_command(claims[r["counter"]]):
            counters[h].append((k, r["counter"]))
        else:
            objections[h].add(k)

    def upstream(h, seen):
        for d in claims[h]["depends_on"]:
            if d in claims and d not in seen:
                seen.add(d)
                upstream(d, seen)
        return seen

    ups = {h: upstream(h, set()) for h in claims}
    # fell[h]: True (refuted or superseded), False (stands on its own), None (not yet known).
    fell = {h: True if topple[h] else False if not counters[h] else None for h in claims}

    def stands(c):
        nodes = {c} | ups[c]
        if any(fell[n] is True for n in nodes):
            return False
        return True if all(fell[n] is False for n in nodes) else None

    changed = True
    while changed:
        changed = False
        for h in claims:
            if fell[h] is None:
                seen = [stands(c) for _, c in counters[h]]
                if True in seen or all(v is False for v in seen):
                    fell[h], changed = True in seen, True

    status = {}
    for h in claims:
        if fell[h]:
            verdicts = topple[h] + ["refuted" for _, c in counters[h] if stands(c)]
            state, disputed = ("refuted" if "refuted" in verdicts else "superseded"), set()
        else:
            state = "reproduced" if reproducers[h] else "proposed"
            disputed = objections[h] | {k for k, c in counters[h] if stands(c) is None}
        independent = len(reproducers[h]) if not fell[h] else 0
        status[h] = (state, {d for d in ups[h] if fell[d] is True}, h in self_checked, disputed, independent)

    def label(h):
        return "at-risk" if status[h][1] and status[h][0] not in BROKEN else status[h][0]

    answered = {}
    for q in store.objects("question"):
        labels = {label(h) for h, c in claims.items() if q in c.get("answers", [])}
        answered[q] = "answered" if "reproduced" in labels else "proposed" if "proposed" in labels else "open"
        standing = [c["value"] for h, c in claims.items()
                    if q in c.get("answers", []) and "value" in c and status[h][0] not in BROKEN]
        if any(disagrees(x, y) for x in standing for y in standing):
            answered[q] = "contested"
    return status, answered


def disagrees(x: dict, y: dict) -> bool:
    """Disagreement over the values the simulation uses, written out case by case."""
    def number(v):
        if "quantity" in v:
            return Fraction(v["quantity"]), Fraction(v.get("uncertainty", "0")), v.get("unit")
        e = v["exact"]
        return None if isinstance(e, (bool, str)) else (Fraction(e), Fraction(0), None)

    a, b = number(x), number(y)
    if a is None and b is None:
        return type(x["exact"]) == type(y["exact"]) and x["exact"] != y["exact"]
    if a is None or b is None or a[2] != b[2]:
        return False
    return not (a[0] - a[1] <= b[0] + b[1] and b[0] - b[1] <= a[0] + a[1])


VALUES = [None, None, {"exact": 168}, {"exact": 170}, {"quantity": "169", "uncertainty": "1"},
          {"quantity": "168.5"}, {"quantity": "169", "unit": "primes"}, {"exact": True}, {"exact": False},
          {"exact": "Riemann"}, {"exact": "Euler"}]


def observed(store: Store) -> tuple[dict, dict]:
    return ({h: (s.state, set(s.at_risk_because), s.self_checked, set(s.disputed),
                 s.independent if s.state not in BROKEN else 0) for h, s in store.statuses().items()},
            {h: q.state for h, q in store.question_statuses().items()})


def simulate(seed: int, root: Path, labs: int = 3, steps: int = 150, signed: bool = False) -> list[Store]:
    rng = random.Random(seed)
    stores = [Store.init(root / f"lab{i}", {"agent": f"agent{i}", "lab": f"lab{i}"}) for i in range(labs)]
    if signed:
        for s in stores:
            signing.generate(s.root / "key")
            s.configure(key="key")
    for step in range(steps):
        i = rng.randrange(labs)
        s = stores[i]
        claims = list(s.objects("claim"))
        runnable = [h for h, c in s.objects("claim").items() if any(e["kind"] == "command" for e in c["evidence"])]
        reviewed = [r["claim"] for r in s.objects("review").values() if identity(r["by"]) == identity(s.author())]
        questions = list(s.objects("question"))
        roll = rng.random()
        if roll < 0.08:
            s.ask(f"question {seed}.{step}", parents=rng.sample(questions, k=min(len(questions), rng.choice([0, 1]))))
        elif roll < 0.45 or not claims:
            deps = rng.sample(claims, k=min(len(claims), rng.choice([0, 0, 1, 2, 3])))
            answers = rng.sample(questions, k=min(len(questions), rng.choice([0, 0, 1])))
            # Some claims carry a command, and some of those are counter-claims against others.
            cmd = rng.choice([None, "true"])
            refutes = [t for t in rng.sample(claims, k=min(len(claims), rng.choice([0, 0, 0, 1])))
                       if t not in deps] if cmd else []
            s.claim(f"claim {seed}.{step} by lab{i}", kind=rng.choice(["result", "negative", "conjecture"]),
                    depends_on=deps, answers=answers, value=rng.choice(VALUES) if answers else None,
                    cmd=cmd, refutes=refutes)
        elif roll < 0.52:
            mine = [h for h, r in s.objects("review").items() if identity(r["by"]) == identity(s.author())]
            if mine:
                s.withdraw(rng.choice(mine))
        elif roll < 0.60:
            # Leases are advice for `todo`; the oracle ignores them, so they must not move a status.
            s.lease(rng.choice(claims + questions), timedelta(minutes=rng.randint(1, 600)))
        elif roll < 0.63:
            held = [t for t, ls in s.leases(now()).items() if any(l["by"] == s.author() for l in ls)]
            if held:
                s.release(rng.choice(held))
        elif roll < 0.75:
            # Often a claim this reviewer has reviewed before, so that positions change.
            target = rng.choice(reviewed if reviewed and rng.random() < 0.4 else claims)
            how = rng.choice(["reproduced", "reproduced", "prose", "run", "counter", "superseded", "inconclusive",
                              "by hand"])
            if how == "prose":
                s.review(target, "refuted", "I disagree")
            elif how == "run":
                s.review(target, "refuted", "re-ran", environment={"output_sha256": "0" * 64})
            elif how == "counter" and [c for c in runnable if c != target]:
                s.review(target, "refuted", "counter", counter=rng.choice([c for c in runnable if c != target]))
            elif how == "by hand":
                # A counter that the store would not write: no command, or the target itself.
                s._record({"type": "review", "claim": target, "verdict": "refuted", "by": s.author(),
                           "method": "m", "note": "", "superseded_by": None, "counter": rng.choice(claims),
                           "created": now()})
            elif how in ("reproduced", "superseded", "inconclusive"):
                by = rng.choice(claims) if how == "superseded" else None
                s.review(target, how, "random", superseded_by=by)
        else:
            s.pull(stores[rng.choice([j for j in range(labs) if j != i])])
    return stores


class PropertyTest(unittest.TestCase):
    def test_statuses_match_brute_force(self):
        for seed in SEEDS:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as tmp:
                for s in simulate(seed, Path(tmp)):
                    self.assertEqual(observed(s), oracle(s))

    def test_labs_converge_after_pulling_in_any_order(self):
        for seed in SEEDS:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as tmp:
                stores = simulate(seed, Path(tmp))
                rng = random.Random(seed)
                pairs = [(a, b) for a in stores for b in stores if a is not b]
                for _ in range(2):  # two rounds reach everyone
                    rng.shuffle(pairs)
                    for a, b in pairs:
                        a.pull(b)
                fresh = [Store(s.root) for s in stores]  # nothing cached
                self.assertTrue(all(set(s.ids()) == set(fresh[0].ids()) for s in fresh))
                views = [{h: (st.state, set(st.at_risk_because), st.independent)
                          for h, st in s.statuses().items()} for s in fresh]
                self.assertTrue(all(v == views[0] for v in views))
                # Judged at one time, leases steer every lab's todo alike.
                at = now()
                todos = [[(t["id"], t["action"], [l["id"] for l in t["leased"]]) for t in s.todo(at=at)]
                         for s in fresh]
                self.assertTrue(all(t == todos[0] for t in todos))
                questions = [{h: (q.state, q.answers, q.conflicts) for h, q in s.question_statuses().items()}
                             for s in fresh]
                self.assertTrue(all(v == questions[0] for v in questions))
                self.assertEqual(observed(fresh[0]), oracle(fresh[0]))

    @unittest.skipUnless(signing.available(), "needs ssh-keygen")
    def test_signed_labs_converge_and_pass_fsck(self):
        with tempfile.TemporaryDirectory() as tmp:
            stores = simulate(0, Path(tmp), steps=60, signed=True)
            for a in stores:
                for b in stores:
                    if a is not b:
                        a.pull(b)
            for b in stores:
                stores[0].pull(b)
            fresh = Store(stores[0].root)
            self.assertEqual(fresh.fsck(), [])
            self.assertEqual(observed(fresh), oracle(fresh))


class ScaleTest(unittest.TestCase):
    """A record the size a few agents produce in a day must stay instant to query."""

    def test_thousands_of_claims(self):
        n = int(os.environ.get("EV_SCALE", "3000"))
        rng = random.Random(0)
        with tempfile.TemporaryDirectory() as tmp:
            s = Store.init(Path(tmp), {"agent": "a", "lab": "l"})
            hs = []
            for i in range(n):
                deps = rng.sample(hs[-50:], k=min(len(hs), 2))
                hs.append(s.claim(f"claim {i}", depends_on=deps))
            s.review(hs[0], "refuted", "counterexample")
            fresh = Store(s.root)
            start = time.perf_counter()
            statuses = fresh.statuses()
            fresh.todo()
            fresh.search("claim 17")
            elapsed = time.perf_counter() - start
            self.assertGreater(sum(1 for st in statuses.values() if st.label == "at-risk"), n // 2)
            self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
