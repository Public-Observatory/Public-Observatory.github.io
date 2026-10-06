"""The MCP server, spoken to the way an agent's client does: JSON-RPC lines over stdio."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class McpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {**os.environ, "PYTHONPATH": str(ROOT), "EV_DIR": str(Path(self.tmp.name) / ".evidence")}
        subprocess.run([sys.executable, "-m", "evidence", "init", self.tmp.name, "--agent", "claude", "--lab", "a"],
                       env=env, check=True, capture_output=True)
        self.proc = subprocess.Popen([sys.executable, "-m", "evidence", "mcp"], env=env, text=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.next_id = 0

    def tearDown(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.proc.stdout.close()
        self.tmp.cleanup()

    def rpc(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.next_id += 1
            msg["id"] = self.next_id
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        if not notify:
            reply = json.loads(self.proc.stdout.readline())
            self.assertEqual(reply["id"], self.next_id)
            return reply

    def tool(self, name, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        return result["content"][0]["text"], result["isError"]

    def test_session(self):
        init = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "test", "version": "0"}})["result"]
        self.assertIn("ev search", init["instructions"])
        self.rpc("notifications/initialized", notify=True)
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"search", "todo", "claim", "verify", "ask", "push"} <= names)

        q, err = self.tool("ask", text="How many primes are below 100?")
        self.assertFalse(err)
        c, err = self.tool("claim", statement="There are 25 primes below 100.", cmd="true", answers=[q], value="25")
        self.assertFalse(err)
        self.assertEqual(json.loads(self.tool("show", id=c)[0])["value"], {"exact": 25})
        text, err = self.tool("verify", ids=[c])
        self.assertFalse(err)
        hits = json.loads(self.tool("search", query="primes below 100")[0])
        self.assertEqual({h["id"] for h in hits}, {q, c})
        shown = json.loads(self.tool("show", id=q[:8])[0])
        self.assertEqual(shown["status"], "answered")

        parent, _ = self.tool("ask", text="How dense are the primes?")
        _, err = self.tool("lease", id=parent, duration="30m", note="thinking")
        self.assertFalse(err)
        todo = json.loads(self.tool("todo")[0])
        self.assertTrue(todo[0]["leased"][0]["mine"])
        self.assertFalse(self.tool("release", id=parent)[1])
        self.assertEqual(json.loads(self.tool("todo")[0])[0]["leased"], [])

        applied, err = self.tool("apply", lines=[{"ask": "Is 91 prime?", "ref": "q"},
                                                 {"claim": "91 = 7 * 13 is not prime.", "answers": ["q"],
                                                  "value": False, "ref": "c"}])
        self.assertFalse(err, applied)
        refs = json.loads(applied)["refs"]
        self.assertEqual(json.loads(self.tool("show", id=refs["c"])[0])["answers"], [refs["q"]])
        text, err = self.tool("apply", lines=[{"claim": "x", "depends_on": ["nowhere"]}])
        self.assertTrue(err)
        self.assertIn("line 1", text)

        text, err = self.tool("show", id="nope")
        self.assertTrue(err)
        self.assertIn("unknown id", text)
        self.assertIn("error", self.rpc("tools/call", {"name": "rm -rf", "arguments": {}}))


if __name__ == "__main__":
    unittest.main()
