"""Usage: python3 primes.py N EXPECTED — succeed iff there are EXPECTED primes below N."""
import sys

n, expected = int(sys.argv[1]), int(sys.argv[2])
sieve = bytearray([1]) * n
sieve[:2] = b"\0\0"
for i in range(2, int(n ** 0.5) + 1):
    if sieve[i]:
        sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
count = sum(sieve)
print(f"{count} primes below {n}")
sys.exit(0 if count == expected else 1)
