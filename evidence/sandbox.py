"""Running other labs' commands without trusting them.

`ev verify` executes commands written by whoever made the claim. Under a sandbox the command may
write only inside its scratch directory, may not read the usual places secrets live, and, unless
it is a setup step, may not use the network; its output is what goes into the review, so it could
otherwise leak a secret into the shared record.

Modes:
    seatbelt   macOS `sandbox-exec`
    bwrap      Linux bubblewrap
    docker     a container (image from EV_IMAGE, default python:3.12-slim)
    none       no isolation; `verify` then refuses another lab's claims unless told `--unsafe`
    auto       seatbelt or bwrap when present, otherwise none
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import EvidenceError

MODES = ("auto", "seatbelt", "bwrap", "docker", "none")
SECRETS = (".ssh", ".aws", ".gnupg", ".config", ".docker", ".kube", ".netrc", ".git-credentials",
           ".pypirc", "Library/Keychains")
# Setup steps download toolchains and caches into these.
CACHES = (".cache", ".elan", ".cargo", ".rustup", ".julia", ".npm")
# A sandboxed command that fails with one of these was most likely stopped by the sandbox.
DENIED = ("Operation not permitted", "Permission denied", "Read-only file system",
          "Could not resolve host", "Network is unreachable", "Temporary failure in name resolution")


def resolve(mode: str) -> str:
    if mode not in MODES:
        raise EvidenceError(f"sandbox must be one of {MODES}")
    if mode != "auto":
        return mode
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return "seatbelt"
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bwrap"
    return "none"


def _quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def seatbelt_profile(work: str, network: bool) -> str:
    home = os.path.realpath(Path.home())
    writable = [work] + ([f"{home}/{c}" for c in CACHES] if network else [])
    rules = ["(version 1)", "(allow default)", "(deny file-write*)",
             "(allow file-write* " + " ".join(f"(subpath {_quote(p)})" for p in writable)
             + ' (literal "/dev/null") (literal "/dev/dtracehelper") (regex #"^/dev/(tty|fd/|std)"))',
             "(deny file-read* " + " ".join(f"(subpath {_quote(f'{home}/{s}')})" for s in SECRETS) + ")"]
    if not network:
        rules.append("(deny network*)")
    return "".join(rules)


def argv(cmd: str, work: str, mode: str, network: bool) -> list[str]:
    """The argument vector that runs `cmd` in `work` under the given (resolved) mode."""
    if mode == "none":
        return ["sh", "-c", cmd]
    if mode == "seatbelt":
        return ["sandbox-exec", "-p", seatbelt_profile(work, network), "sh", "-c", cmd]
    if mode == "bwrap":
        home = str(Path.home())
        out = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
               "--bind", work, work, "--die-with-parent", "--chdir", work]
        for s in SECRETS:
            if (Path(home) / s).is_dir():
                out += ["--tmpfs", f"{home}/{s}"]
        if network:
            for c in CACHES:
                if (Path(home) / c).is_dir():
                    out += ["--bind", f"{home}/{c}", f"{home}/{c}"]
        else:
            out.append("--unshare-net")
        return out + ["sh", "-c", cmd]
    if mode == "docker":
        image = os.environ.get("EV_IMAGE", "python:3.12-slim")
        return ["docker", "run", "--rm", *([] if network else ["--network", "none"]),
                "-v", f"{work}:/work", "-w", "/work", image, "sh", "-c", cmd]
    raise EvidenceError(f"unknown sandbox {mode}")


def run(cmd: str, work: str, timeout: int, mode: str = "none",
        network: bool = False) -> tuple[int | None, str]:
    work = os.path.realpath(work)
    tmp = Path(work) / ".tmp"
    tmp.mkdir(exist_ok=True)
    env = {**os.environ, "TMPDIR": str(tmp)}
    try:
        r = subprocess.run(argv(cmd, work, mode, network), cwd=work, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, f"sandbox unavailable: {e}"


def denied(mode: str, output: str) -> bool:
    return mode != "none" and any(d in output for d in DENIED)
