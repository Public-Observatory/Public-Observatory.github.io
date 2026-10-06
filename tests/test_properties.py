"""Properties that must hold for any history, checked on random ones.

Several labs claim, review and pull from each other at random. Whatever happens:
  * every lab's statuses agree with a brute-force reading of its own objects;
  * once every lab has pulled from every other, all labs hold the same objects and agree on
    every status, whatever order the pulls happened in (merging is a union of sets).
"""

import os
import random
import tempfile
import time
import unittest
from pathlib import Path

from evidence import Store, signing
from evidence.store import BROKEN, PRECEDENCE, identity

SEEDS = range(int(os.environ.get("EV_SEEDS", "5")))


def oracle(store: Store) -> dict:
    """Statuses computed the slow, obvious way."""
    claims, reviews = store.objects("claim"), store.objects("review")
    withdrawn = {w["review"] for w in store.objects("withdrawal").values()
                 if w["review"] in reviews and identity(w["by"]) == identity(reviews[w["review"]]["by"])}
    own = {}
    for h in claims:
        verdicts = {r["verdict"] for k, r in reviews.items() if r["claim"] == h and k not in withdrawn} | {"proposed"}
        own[h] = next(v for v in PRECEDENCE if v in verdicts)

    def upstream(h, seen):
        for d in claims[h]["depends_on"]:
            if d in claims and d not in seen:
                seen.add(d)
                upstream(d, seen)
        return seen

    status = {h: (own[h], {d for d in upstream(h, set()) if own[d] in BROKEN}) for h in claims}

    def label(h):
        return "at-risk" if status[h][1] and own[h] not in BROKEN else own[h]

    answered = {}
    for q in store.objects("question"):
        labels = {label(h) for h, c in claims.items() if q in c.get("answers", [])}
        answered[q] = "answered" if "reproduced" in labels else "proposed" if "proposed" in labels else "open"
    return status, answered


def observed(store: Store) -> tuple[dict, dict]:
    return ({h: (s.state, set(s.at_risk_because)) for h, s in store.statuses().items()},
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
        questions = list(s.objects("question"))
        roll = rng.random()
        if roll < 0.08:
            s.ask(f"question {seed}.{step}", parents=rng.sample(questions, k=min(len(questions), rng.choice([0, 1]))))
        elif roll < 0.45 or not claims:
            deps = rng.sample(claims, k=min(len(claims), rng.choice([0, 0, 1, 2, 3])))
            answers = rng.sample(questions, k=min(len(questions), rng.choice([0, 0, 1])))
            s.claim(f"claim {seed}.{step} by lab{i}", kind=rng.choice(["result", "negative", "conjecture"]),
                    depends_on=deps, answers=answers)
        elif roll < 0.52:
            mine = [h for h, r in s.objects("review").items() if identity(r["by"]) == identity(s.author())]
            if mine:
                s.withdraw(rng.choice(mine))
        elif roll < 0.75:
            verdict = rng.choice(["reproduced", "reproduced", "refuted", "superseded", "inconclusive"])
            target = rng.choice(claims)
            by = rng.choice(claims) if verdict == "superseded" else None
            s.review(target, verdict, "random", superseded_by=by)
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
