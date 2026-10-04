#!/bin/sh
# Two agents from different labs build on each other's work through plain files.
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
ev() { PYTHONPATH="$ROOT" python3 -m evidence "$@"; }
W=$(mktemp -d)
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

ev init "$W/lab-a" --agent alice --model model-a --lab lab-a >/dev/null
ev init "$W/lab-b" --agent bob --model model-b --lab lab-b >/dev/null

say "lab-a: alice records a computational result and a dead end"
cd "$W/lab-a"
PRIMES=$(ev claim "There are 168 primes below 1000." --file "$ROOT/demo/primes.py" --cmd "python3 primes.py 1000 168")
ev claim "Trial division up to n/2 is too slow beyond 10^7." --kind negative --note "timed out after 600s at n=10^7" >/dev/null
ev log

say "lab-b: bob pulls, builds on the result, and makes a mistake"
cd "$W/lab-b"
ev pull "$W/lab-a"
GAP=$(ev claim "The average gap between primes below 1000 is about 6." --dep "$PRIMES" --note "1000/168 ≈ 5.95")
WRONG=$(ev claim "There are 1230 primes below 10000." --file "$ROOT/demo/primes.py" --cmd "python3 primes.py 10000 1230")
DENS=$(ev claim "Prime density halves from 10^3 to 10^4." --dep "$WRONG" --dep "$PRIMES")
ev log

say "lab-a: alice pulls and independently re-runs everything"
cd "$W/lab-a"
ev pull "$W/lab-b"
ev verify "$PRIMES"
ev verify "$WRONG" || true

say "the record flags what was built on the broken claim"
ev check || true

say "what a human should read"
ev digest

say "full history of one claim"
ev show "$DENS"
