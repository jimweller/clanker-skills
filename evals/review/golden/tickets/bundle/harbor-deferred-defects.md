# Low-severity defects in harbor

Paths and line numbers refer to commit `4ef35ce0077924f16ca19a77c0823a644f521bb3`.

The file lists 1 defects, sorted by the first file each one touches.

## 1. No tests for encrypt/decrypt round trip and tamper detection

Categories are testing.

- `src/crypto.ts:10` `decrypt` No tests cover `encrypt` and `decrypt`, including the round trip and tamper detection.
