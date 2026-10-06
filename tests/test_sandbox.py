import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evidence import EvidenceError, Store
from evidence import sandbox

MODE = sandbox.resolve("auto")


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("EV_AGENT", None)
        os.environ.pop("EV_SANDBOX", None)
        self.a = Store.init(Path(self.tmp.name) / "a", {"agent": "alice", "lab": "lab-a"})
        self.b = Store.init(Path(self.tmp.name) / "b", {"agent": "bob", "lab": "lab-b"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_refuses_other_labs_code_without_sandbox(self):
        h = self.a.claim("x", cmd="true")
        self.b.pull(self.a)
        with self.assertRaises(EvidenceError):
            self.b.verify(h, sandbox_mode="none")
        self.assertEqual(self.b.verify(h, sandbox_mode="none", unsafe=True)[1], "reproduced")
        self.assertEqual(self.a.verify(h, sandbox_mode="none")[1], "reproduced")  # our own code

    def test_review_records_sandbox(self):
        h = self.a.claim("x", cmd="true")
        review = self.a.get(self.a.verify(h, sandbox_mode="none")[0])
        self.assertEqual(review["environment"]["sandbox"], "none")


@unittest.skipIf(MODE == "none", "no sandbox on this machine")
class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(os.path.realpath(self.tmp.name))
        self.a = Store.init(self.dir / "a", {"agent": "alice", "lab": "lab-a"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_cannot_write_outside_work_directory(self):
        target = self.dir / "escaped"
        h = self.a.claim("harmless", cmd=f"touch {target}")
        verdict = self.a.verify(h, sandbox_mode=MODE)[1]
        self.assertFalse(target.exists())
        self.assertEqual(verdict, "inconclusive")

    def test_cannot_read_ssh_keys(self):
        secret = Path.home() / ".ssh"
        if not secret.is_dir():
            self.skipTest("no ~/.ssh")
        h = self.a.claim("reads keys", cmd=f"ls {secret}")
        self.assertNotEqual(self.a.verify(h, sandbox_mode=MODE)[1], "reproduced")

    def test_no_network_in_command(self):
        h = self.a.claim("online", cmd="python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\"")
        self.assertNotEqual(self.a.verify(h, sandbox_mode=MODE, timeout=20)[1], "reproduced")

    def test_ordinary_work_runs(self):
        script = self.dir / "s.py"
        script.write_text("import tempfile\nopen('out.txt', 'w').write('x')\ntempfile.mkstemp()\n")
        h = self.a.claim("writes locally", files=[script], cmd="python3 s.py")
        self.assertEqual(self.a.verify(h, sandbox_mode=MODE)[1], "reproduced")


class BwrapArgvTest(unittest.TestCase):
    """The bubblewrap policy, checked on any platform by reading the arguments it produces."""

    def test_home_hidden_toolchains_and_scratch_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = os.path.realpath(tmp)
            home, work, key = f"{tmp}/home", f"{tmp}/home/work", f"{tmp}/home/lab/key"
            os.makedirs(f"{home}/lab")
            Path(key).write_text("secret")
            with mock.patch.dict(os.environ, {"HOME": home, "PATH": f"/usr/bin:{home}:{home}/go/bin"}):
                args = sandbox.bwrap_argv(work, network=False, hide=[key])
                online = sandbox.bwrap_argv(work, network=True)
        pairs = list(zip(args, args[1:]))
        at = lambda *pair: pairs.index(pair)
        self.assertLess(at("--tmpfs", home), at("--ro-bind-try", f"{home}/.elan"))
        self.assertLess(at("--ro-bind-try", f"{home}/.elan"), at("--bind", work))
        self.assertLess(at("--bind", work), at("--ro-bind", "/dev/null"))
        self.assertIn(("--ro-bind-try", f"{home}/go/bin"), pairs)
        self.assertNotIn(("--ro-bind-try", home), pairs)  # a PATH naming home does not open it
        for d in ("/tmp", "/run"):
            self.assertIn(("--tmpfs", d), pairs)
        self.assertIn("--unshare-all", args)
        self.assertIn("--new-session", args)
        self.assertNotIn("--share-net", args)
        self.assertIn("--share-net", online)

    def test_environment_keeps_only_what_commands_need(self):
        with mock.patch.dict(os.environ, {"AWS_SECRET_ACCESS_KEY": "x", "EV_KEY": "k", "LC_ALL": "C",
                                          "ELAN_HOME": "/opt/elan"}):
            env = sandbox.environment("/w", "bwrap")
            self.assertEqual(sandbox.environment("/w", "none")["EV_KEY"], "k")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("EV_KEY", env)
        self.assertEqual((env["LC_ALL"], env["ELAN_HOME"]), ("C", "/opt/elan"))
        self.assertEqual((env["TMPDIR"], env["XDG_CACHE_HOME"]), ("/w/.tmp", "/w/.cache"))


@unittest.skipIf(MODE == "none", "no sandbox on this machine")
class HomeTest(unittest.TestCase):
    """Under a temporary HOME planted with secrets, a verified command reads none of them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(os.path.realpath(self.tmp.name))
        self.home = self.dir / "home"
        planted = {".aws/credentials": "AWS-SECRET", ".npmrc": "NPM-SECRET", "notes/plan.txt": "PLAN-SECRET",
                   "other/.evidence/config.json": "STORE-SECRET", ".cargo/credentials.toml": "CARGO-SECRET",
                   ".elan/toolchain.txt": "a toolchain"}
        for name, text in planted.items():
            (self.home / name).parent.mkdir(parents=True, exist_ok=True)
            (self.home / name).write_text(text)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "GITHUB_TOKEN": "ENV-SECRET"})
        self.env.start()
        self.a = Store.init(self.home / "lab", {"agent": "alice", "lab": "lab-a"})
        self.a.configure(key=str(self.home / "lab-key"))
        (self.home / "lab-key").write_text("KEY-SECRET")
        self.a.configure(key=None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def verify(self, cmd: str, setup: str = "") -> tuple[str, str]:
        h = self.a.claim("probe", cmd=cmd, setup=[setup] if setup else [])
        review = self.a.get(self.a.verify(h, sandbox_mode=MODE, timeout=20)[0])
        return review["verdict"], review["note"]

    def test_cannot_read_planted_secrets(self):
        for path in (".aws/credentials", ".npmrc", "notes/plan.txt", "other/.evidence/config.json",
                     ".cargo/credentials.toml", "lab/.evidence/config.json"):
            with self.subTest(path=path):
                verdict, note = self.verify(f"cat {self.home / path}")
                self.assertNotEqual(verdict, "reproduced")
                self.assertNotIn("SECRET", note)
                self.assertNotIn("alice", note)

    def test_cannot_list_home_or_see_secret_variables(self):
        self.assertNotEqual(self.verify(f"ls {self.home}")[0], "reproduced")
        verdict, note = self.verify('echo "[$GITHUB_TOKEN]"')
        self.assertEqual((verdict, note), ("reproduced", "[]"))

    def test_toolchains_stay_readable(self):
        self.assertEqual(self.verify(f"cat {self.home / '.elan/toolchain.txt'}"), ("reproduced", "a toolchain"))

    def test_cannot_write_outside_scratch_even_in_setup(self):
        for target in (self.home / "planted", self.home / ".cache" / "planted", self.home / ".elan" / "planted"):
            with self.subTest(target=target):
                self.verify("true", setup=f"mkdir -p {target.parent} && touch {target}")
                self.assertFalse(target.exists())

    def test_setup_caches_go_to_scratch(self):
        verdict, note = self.verify('test -f "$XDG_CACHE_HOME/x" && echo "$XDG_CACHE_HOME"',
                                    setup='mkdir -p "$XDG_CACHE_HOME" && touch "$XDG_CACHE_HOME/x"')
        self.assertEqual(verdict, "reproduced")
        self.assertFalse(note.startswith(str(self.home)))

    def test_setup_cannot_reach_unix_sockets(self):
        path = self.dir / "agent.sock"
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(path))
        server.listen()
        server.setblocking(False)
        try:
            connect = f"python3 -c \"import socket; socket.socket(socket.AF_UNIX).connect('{path}')\""
            self.assertEqual(self.verify("true", setup=connect)[0], "inconclusive")
            with self.assertRaises(BlockingIOError):  # nobody knocked
                server.accept()
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
