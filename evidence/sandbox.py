"""Running other labs' commands without trusting them.

`ev verify` executes commands written by whoever made the claim. Their output goes into a review,
which is shared, so a command that could read a secret could publish it; and a command that could
leave files behind could change what later commands do. Under seatbelt and bwrap the policy is:

Reading.  The home directory is hidden as a whole, and so are the shared temporary directories
(on macOS /Users, /Volumes, /tmp, /var/tmp and /var/folders; on Linux /home, /root, /tmp, /var/tmp
and /run). Of these a command may read only its scratch directory and the places where toolchains
live: TOOLCHAINS, the directories on PATH, those named by TOOL_VARS, and those listed under
`sandbox_read` in config.json. Credentials inside them (HIDDEN), the verifying store and its
signing key stay hidden even so. On macOS the directories leading to these may be examined but not
listed. The rest of the system (/usr, /opt, /etc, /Library) stays readable, since interpreters and
compilers live there.

Writing.  Only the scratch directory, which is deleted afterwards. Setup steps may download, but
into the scratch directory: the usual cache locations are pointed there (CACHE_VARS), so nothing a
setup step fetches outlives the verification or reaches a later one. Toolchains already installed
are read-only.

Network.  None for the command. Setup steps may reach the internet but no unix socket (the ssh
agent, a Docker daemon, a session bus), except, on macOS, the system's DNS resolver. On Linux the
command also runs in fresh PID and IPC namespaces under a new session, and /tmp and /run are empty.

Environment.  Only the variables in ENV and TOOL_VARS pass, so tokens and keys held in variables
(EV_KEY, cloud credentials, SSH_AUTH_SOCK) do not.

On macOS the command may not ask LaunchServices or Apple Events to start other programs, which
would run outside the sandbox, nor ask the keychain or the pasteboard for their contents.

What remains. Files outside the home directory that the user can read stay readable, so a store
or key kept elsewhere is protected only when it is the verifying store's own. A setup step can
reach services listening on the loopback interface, and, on Linux, abstract unix sockets. Docker
isolates by its own rules: only the scratch directory is mounted.

Modes:
    seatbelt   macOS `sandbox-exec`
    bwrap      Linux bubblewrap
    docker     a container (image from EV_IMAGE, default python:3.12-slim)
    none       no isolation; `verify` then refuses another lab's claims unless told `--unsafe`
    auto       seatbelt or bwrap when present, otherwise none
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import EvidenceError

MODES = ("auto", "seatbelt", "bwrap", "docker", "none")
# Readable under the home directory: where toolchains and the user's own packages are installed.
TOOLCHAINS = (".elan", ".cargo", ".rustup", ".julia", ".ghcup", ".cabal", ".stack", ".opam", ".pyenv",
              ".rbenv", ".nvm", ".volta", ".deno", ".bun", ".sdkman", ".asdf", ".tool-versions",
              ".local/bin", ".local/lib", ".local/share/uv", ".local/share/mise", "Library/Python",
              "miniconda3", "anaconda3", "miniforge3", "mambaforge", ".conda")
# Credentials kept inside a toolchain directory.
HIDDEN = (".cargo/credentials", ".cargo/credentials.toml")
# Variables naming a toolchain: passed to the command, and the directories they name are readable.
TOOL_VARS = ("ELAN_HOME", "CARGO_HOME", "RUSTUP_HOME", "JULIA_DEPOT_PATH", "JAVA_HOME", "GOROOT", "GOPATH",
             "PYENV_ROOT", "CONDA_PREFIX", "VIRTUAL_ENV")
# Other variables passed to the command (and every LC_*).
ENV = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LANGUAGE", "TERM", "TZ")
# Caches pointed into the scratch directory, so that what a setup step fetches does not persist.
CACHE_VARS = {"XDG_CACHE_HOME": ".cache", "PIP_CACHE_DIR": ".cache/pip", "UV_CACHE_DIR": ".cache/uv",
              "npm_config_cache": ".cache/npm"}
# Mach services through which a command could start programs outside the sandbox or read secrets.
MACH = ("com.apple.coreservices.launchservicesd", "com.apple.coreservices.appleevents",
        "com.apple.SecurityServer", "com.apple.securityd.xpc", "com.apple.pasteboard.1")
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


def _home() -> str:
    return os.path.realpath(Path.home())


def readable(read=()) -> list[str]:
    """Paths a command may read besides its scratch directory, where they would otherwise be hidden.

    Each is given both as named and resolved: seatbelt matches resolved paths, while bwrap must
    recreate a path as named when a symbolic link leading to it lies in a hidden directory.
    """
    home = _home()
    named = [p for v in ("PATH", *TOOL_VARS) for p in os.environ.get(v, "").split(os.pathsep)]
    # A PATH that names the home directory itself, or a parent of it, does not open it.
    named = [p for p in named if os.path.isabs(p) and not Path(home).is_relative_to(os.path.realpath(p))]
    paths = [os.path.join(home, p) for p in TOOLCHAINS] + named + [os.path.join(home, os.path.expanduser(p)) for p in read]
    return sorted({q for p in paths for q in (os.path.normpath(p), os.path.realpath(p))})


def hidden(hide=()) -> list[str]:
    """Paths a command may not read even inside a readable directory."""
    cargo = [os.environ["CARGO_HOME"]] if os.path.isabs(os.environ.get("CARGO_HOME", "")) else []
    paths = [os.path.join(_home(), p) for p in HIDDEN] + [os.path.join(c, Path(p).name) for c in cargo for p in HIDDEN]
    return sorted({os.path.realpath(p) for p in [*paths, *map(str, hide)]})


def environment(work: str, mode: str) -> dict[str, str]:
    """The variables a command sees: under a sandbox only those it needs, with caches in `work`."""
    env = {**os.environ} if mode in ("none", "docker") else {
        k: v for k, v in os.environ.items() if k in ENV or k in TOOL_VARS or k.startswith("LC_")}
    if mode not in ("none", "docker"):
        env.update({k: os.path.join(work, v) for k, v in CACHE_VARS.items()})
    return {**env, "TMPDIR": os.path.join(work, ".tmp")}


def _quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _subpaths(paths) -> str:
    return " ".join(f"(subpath {_quote(p)})" for p in paths)


def seatbelt_profile(work: str, network: bool, read=(), hide=()) -> str:
    # Later rules take precedence over earlier ones.
    try:
        temp = os.confstr("CS_DARWIN_USER_TEMP_DIR") or ""
    except (ValueError, OSError, AttributeError):
        temp = ""
    temp = temp and os.path.realpath(temp)
    rules = ["(version 1)", "(allow default)", "(deny file-write*)",
             f"(allow file-write* (subpath {_quote(work)})"
             ' (literal "/dev/null") (literal "/dev/dtracehelper") (regex #"^/dev/(tty|fd/|std)"))',
             "(deny file-read* " + _subpaths([_home(), "/Users", "/Volumes", "/private/tmp", "/private/var/tmp",
                                              "/private/var/folders"]) + ")",
             f"(allow file-read* {_subpaths([*readable(read), work])}"
             # The `xcrun` shims in /usr/bin keep a cache of where tools are in the temporary directory.
             + (f' (regex #"^{re.escape(temp)}/xcrun_db")' if temp else "") + ")",
             # Programs such as `mkdir -p` look at each directory on the way to the ones they may use.
             "(allow file-read-metadata " + " ".join(f"(literal {_quote(str(a))})" for a in sorted(
                 {str(a) for p in [*readable(read), work] for a in Path(p).parents})) + ")",
             f"(deny file-read* file-write* {_subpaths(hidden(hide))})",
             "(deny mach-lookup " + " ".join(f'(global-name "{m}")' for m in MACH) + ")"]
    if network:
        rules.append('(deny network-outbound (remote unix-socket))'
                     '(allow network-outbound (remote unix-socket (path-literal "/private/var/run/mDNSResponder")))')
    else:
        rules.append("(deny network*)")
    return "".join(rules)


def bwrap_argv(work: str, network: bool, read=(), hide=()) -> list[str]:
    home = _home()
    # Order matters: each mount covers what an earlier one put at the same place.
    out = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
           "--tmpfs", "/tmp", "--tmpfs", "/var/tmp", "--tmpfs", "/run"]
    for d in dict.fromkeys(["/home", "/root", home]):
        if os.path.isdir(d):
            out += ["--tmpfs", d]
    if network and (dns := os.path.realpath("/etc/resolv.conf")).startswith("/run/"):
        out += ["--ro-bind-try", dns, dns]
    for p in readable(read):
        out += ["--ro-bind-try", p, p]
    out += ["--bind", work, work]
    for p in hidden(hide):
        if os.path.isdir(p):
            out += ["--tmpfs", p]
        elif os.path.exists(p):
            out += ["--ro-bind", "/dev/null", p]
    return out + ["--unshare-all", *(["--share-net"] if network else []), "--new-session",
                  "--die-with-parent", "--chdir", work]


def argv(cmd: str, work: str, mode: str, network: bool, read=(), hide=()) -> list[str]:
    """The argument vector that runs `cmd` in `work` under the given (resolved) mode."""
    if mode == "none":
        return ["sh", "-c", cmd]
    if mode == "seatbelt":
        return ["sandbox-exec", "-p", seatbelt_profile(work, network, read, hide), "sh", "-c", cmd]
    if mode == "bwrap":
        return bwrap_argv(work, network, read, hide) + ["sh", "-c", cmd]
    if mode == "docker":
        image = os.environ.get("EV_IMAGE", "python:3.12-slim")
        return ["docker", "run", "--rm", *([] if network else ["--network", "none"]),
                "-v", f"{work}:/work", "-w", "/work", image, "sh", "-c", cmd]
    raise EvidenceError(f"unknown sandbox {mode}")


def run(cmd: str, work: str, timeout: int, mode: str = "none", network: bool = False,
        read=(), hide=()) -> tuple[int | None, str]:
    """Run `cmd` in `work`. `read` adds readable paths (relative to home); `hide` hides more."""
    work = os.path.realpath(work)
    (Path(work) / ".tmp").mkdir(exist_ok=True)
    try:
        r = subprocess.run(argv(cmd, work, mode, network, read, hide), cwd=work, capture_output=True,
                           text=True, timeout=timeout, env=environment(work, mode))
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, f"sandbox unavailable: {e}"


def denied(mode: str, output: str) -> bool:
    return mode != "none" and any(d in output for d in DENIED)
