"""Signatures with SSH keys, the way git signs commits: `ssh-keygen -Y sign` and `-Y verify`.

An object's id is the SHA-256 of its content, so signing the id signs the content. Signatures are
objects of their own, so signing never changes an id and unsigned stores remain valid. An object
whose author names a key is accepted from another store only together with a valid signature by
that key; this is what makes a lab's name, and hence an independent reproduction, unforgeable.
"""

from __future__ import annotations

import base64
import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import EvidenceError

NAMESPACE = "evidence"
KEY = re.compile(r"[a-z0-9@.-]+ [A-Za-z0-9+/]+=*")


def available() -> bool:
    return shutil.which("ssh-keygen") is not None


def _ssh(*args: str, data: bytes | None = None) -> subprocess.CompletedProcess:
    if not available():
        raise EvidenceError("signing needs ssh-keygen (OpenSSH 8.1 or later)")
    return subprocess.run(["ssh-keygen", *args], input=data, capture_output=True)


def generate(path: Path, comment: str = "evidence") -> Path:
    path = Path(path)
    r = _ssh("-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(path))
    if r.returncode:
        raise EvidenceError(f"ssh-keygen: {r.stderr.decode().strip()}")
    return path


def public_key(keyfile: Path) -> str:
    """The public half of a private key, as `type base64` without the comment."""
    pub = Path(str(keyfile) + ".pub")
    if pub.exists():
        text = pub.read_text()
    else:
        r = _ssh("-y", "-f", str(keyfile))
        if r.returncode:
            raise EvidenceError(f"cannot read key {keyfile}: {r.stderr.decode().strip()}")
        text = r.stdout.decode()
    return normalise(text)


def normalise(text: str) -> str:
    parts = text.split()
    key = " ".join(parts[:2])
    if len(parts) < 2 or not KEY.fullmatch(key):
        raise EvidenceError(f"not an SSH public key: {text[:40]!r}")
    return key


def fingerprint(key: str) -> str:
    blob = base64.b64decode(key.split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def sign(keyfile: Path, data: bytes) -> str:
    r = _ssh("-Y", "sign", "-q", "-f", str(keyfile), "-n", NAMESPACE, data=data)
    if r.returncode:
        raise EvidenceError(f"signing failed: {r.stderr.decode().strip()}")
    return r.stdout.decode()


def verify(key: str, data: bytes, signature: str) -> bool:
    if not KEY.fullmatch(key):
        return False
    with tempfile.TemporaryDirectory() as d:
        allowed, sig = Path(d) / "allowed", Path(d) / "sig"
        allowed.write_text(f'signer namespaces="{NAMESPACE}" {key}\n')
        sig.write_text(signature)
        r = _ssh("-Y", "verify", "-f", str(allowed), "-I", "signer", "-n", NAMESPACE, "-s", str(sig),
                 data=data)
        return r.returncode == 0
