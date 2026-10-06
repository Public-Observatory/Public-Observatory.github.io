import tempfile
import unittest
from pathlib import Path

from evidence import Store
from evidence.palomar import Palomar


def entry(pid, version=1, title="T", related=(), registered="2026-09-01T00:00:00Z"):
    return {
        "id": pid, "version": version, "status": "registered", "title": title, "abstract": "an abstract",
        "registered_at": registered, "authors": [{"name": "A. Author"}],
        "source": {"repository": "someone/repo", "commit": "c" * 40, "project_path": None},
        "formalization": {"theorem_names": ["Foo.bar"], "project_dependencies": [
            {"name": "mathlib", "repository": "leanprover-community/mathlib4", "revision": "r"},
            {"name": "vendored", "path": "deps/vendored"}]},
        "provenance": {
            "mathematical_sources": [{"relationship": "formalizes", "title": "A paper",
                                      "identifier": "arXiv:2401.00001", "type": "paper", "authors": []}],
            "related_formalizations": [{"relationship": r, "identifier": i, "note": ""} for r, i in related],
            "result_origin": "source-based",
        },
        "verification": {"kernels": [{"name": "nanoda"}], "challenge_sha256": "s" * 64},
        "review": {"outcome": "neutral", "reviewer_models": ["some-model"]},
        "trust": {"level": "high"},
    }


A, B, C = "PALOMAR-2026-09-01-000001", "PALOMAR-2026-09-02-000001", "PALOMAR-2026-09-03-000001"
REGISTRY = {
    f"entries/{A}-v1.json": entry(A, title="Base lemma"),
    f"entries/{B}-v1.json": entry(B, title="Theorem", related=[
        ("builds-on", A), ("background", "https://github.com/x/y"), ("other", C)]),
    f"entries/{C}-v1.json": entry(C, title="Unrelated"),
    f"entries/{A}-v2.json": entry(A, version=2, title="Base lemma, fixed", registered="2026-09-05T00:00:00Z"),
}


class PalomarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store.init(Path(self.tmp.name) / "a", {"agent": "alice"})
        self.registry = {k: v for k, v in REGISTRY.items() if not k.endswith("v2.json")}
        self.pal = Palomar(self.store, fetch=self.registry.get)

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_is_reproduced_by_palomar(self):
        h = self.pal.import_entry(A)
        status = self.store.statuses()[h]
        self.assertEqual(status.state, "reproduced")
        self.assertIn("language model", status.reviews[0]["method"])

    def test_misformalisation_refutes_and_flags_dependents(self):
        hb = self.pal.import_entry(B)
        ha = self.pal.local(A)[1]
        # An objection in prose disputes the entry; a counter-claim with a check of its own refutes it.
        r = self.store.review(ha, "refuted", "formal statement drops a hypothesis of the paper")
        s = self.store.statuses()
        self.assertEqual((s[ha].state, s[ha].disputed, s[hb].at_risk_because), ("reproduced", [r], []))
        self.store.claim("The formal statement of the base lemma holds without the paper's hypothesis H.",
                         cmd="lake build Counterexample", refutes=[ha])
        s = self.store.statuses()
        self.assertEqual(s[ha].state, "refuted")
        self.assertEqual(s[hb].at_risk_because, [ha])

    def test_builds_on_becomes_dependency_but_other_relations_do_not(self):
        hb = self.pal.import_entry(B)
        claim = self.store.get(hb)
        self.assertEqual(len(claim["depends_on"]), 1)
        self.assertEqual(self.store.get(claim["depends_on"][0])["source"]["id"], A)
        self.assertEqual(self.pal.local(C), {})
        refs = {e["identifier"] for e in claim["evidence"] if e["kind"] == "reference"}
        self.assertIn("arXiv:2401.00001", refs)

    def test_import_is_deterministic_across_stores(self):
        other = Store.init(Path(self.tmp.name) / "b", {"agent": "bob"})
        self.assertEqual(self.pal.import_entry(B), Palomar(other, fetch=self.registry.get).import_entry(B))

    def test_new_version_supersedes_old_and_flags_dependents(self):
        hb = self.pal.import_entry(B)
        old = self.pal.local(A)[1]
        self.registry[f"entries/{A}-v2.json"] = REGISTRY[f"entries/{A}-v2.json"]
        new = self.pal.import_entry(A)
        s = self.store.statuses()
        self.assertNotEqual(old, new)
        self.assertEqual(s[old].state, "superseded")
        self.assertEqual(s[hb].at_risk_because, [old])

    def test_depth_limits_recursion(self):
        hb = self.pal.import_entry(B, depth=0)
        self.assertEqual(self.store.get(hb)["depends_on"], [])


    def test_forged_import_in_the_store_is_not_taken_for_the_entry(self):
        # Anyone can write a claim that says it came from Palomar; the importer must not believe it.
        forged = {**Palomar.to_claim(entry(A, title="Forged"), []), "statement": "Forged"}
        bad = self.store.put_object(forged)
        newer = self.store.put_object({**forged, "source": {**forged["source"], "version": 9}})
        h = self.pal.import_entry(A)
        self.assertNotIn(h, (bad, newer))
        self.assertEqual(self.store.get(h)["statement"], "Base lemma")
        self.assertEqual(self.store.statuses()[h].state, "reproduced")

if __name__ == "__main__":
    unittest.main()
