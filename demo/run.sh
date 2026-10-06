#!/bin/sh
# Two agents from different labs work on one question through a shared, signed record.
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
ev() { PYTHONPATH="$ROOT" python3 -m evidence "$@"; }
W=$(mktemp -d)
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
SIGN=$(command -v ssh-keygen >/dev/null && echo --keygen || true)

ev init "$W/lab-a" --agent alice --model model-a --lab lab-a $SIGN >/dev/null
ev init "$W/lab-b" --agent bob --model model-b --lab lab-b $SIGN >/dev/null
if [ -n "$SIGN" ]; then
  (cd "$W/lab-a" && ev trust add lab-b "$W/lab-b/.evidence/key.pub" >/dev/null)
  (cd "$W/lab-b" && ev trust add lab-a "$W/lab-a/.evidence/key.pub" >/dev/null)
fi
(cd "$W/lab-a" && ev remote add b "$W/lab-b" >/dev/null)
(cd "$W/lab-b" && ev remote add a "$W/lab-a" >/dev/null)
# Each lab re-runs the other's code in a sandbox when the machine has one; this demo trusts its own scripts.
UNSAFE=--unsafe

say "lab-a: alice poses a question and breaks it into parts"
cd "$W/lab-a"
Q=$(ev ask "How does the density of primes change with magnitude?")
Q3=$(ev ask "How many primes are there below 1000?" --parent "$Q")
Q4=$(ev ask "How many primes are there below 10000?" --parent "$Q")
ev questions

say "lab-a: alice answers one part, checks it from a clean directory, and records a dead end"
PRIMES=$(ev claim "There are 168 primes below 1000." --file "$ROOT/demo/primes.py" \
  --cmd "python3 primes.py 1000 168" --answers "$Q3" --verify | head -1)
ev claim "Trial division up to n/2 is too slow beyond 10^7." --kind negative --note "timed out after 600s at n=10^7" >/dev/null
ev log

say "lab-b: bob pulls, asks whether anyone has tried his plan, and answers the other part, wrongly"
cd "$W/lab-b"
ev pull
ev search "count primes with trial division up to 10^8"
WRONG=$(ev claim "There are 1230 primes below 10000." --file "$ROOT/demo/primes.py" \
  --cmd "python3 primes.py 10000 1230" --answers "$Q4")
DENS=$(ev claim "Prime density falls from 0.168 below 1000 to 0.123 below 10000." --dep "$WRONG" --dep "$PRIMES" \
  --answers "$Q")

say "lab-a: alice pulls and asks what is worth doing"
cd "$W/lab-a"
ev pull
ev todo

say "lab-a: alice re-runs lab-b's work; bob re-runs hers"
ev verify "$WRONG" $UNSAFE || true
(cd "$W/lab-b" && ev pull >/dev/null && ev verify "$PRIMES" $UNSAFE)
ev pull >/dev/null

say "the record flags what was built on the error"
ev check || true

say "alice refutes the density claim in prose: without evidence this only disputes it, so she withdraws"
R=$(ev review "$DENS" refuted --method "rests on a refuted count")
ev show "$DENS"
ev withdraw "$R" --note "at risk is the right state; the claim itself was not checked" >/dev/null

say "what a human should read"
ev report

say "integrity of the record"
ev fsck
rm -rf "$W"
