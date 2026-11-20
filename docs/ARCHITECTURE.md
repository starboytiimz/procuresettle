# Architecture overview

This page is a high-level map of how the ProcureSettle repository fits
together: the on-chain contract, the off-chain scripts that exercise and check
it, the evidence bundles those scripts produce, and the CI pipeline that ties
them together. For claims, results, and limits, the authoritative documents are
[`EVIDENCE.md`](EVIDENCE.md) and [`LIMITATIONS.md`](LIMITATIONS.md).

## Workspace structure

```text
.
├── Cargo.toml / Cargo.lock      Rust workspace and committed lockfile
├── rust-toolchain.toml          Pinned Rust toolchain and wasm32v1-none target
├── contracts/
│   └── po-settlement/           The `procuresettle` Soroban contract
│       └── src/
│           ├── lib.rs           Contract types, storage, and entry points
│           └── test.rs          Host tests (Soroban SDK test environment)
├── scripts/                     Off-chain proof, verification, and audit tooling
├── evidence/                    Committed, checksummed proof bundles
├── docs/                        Evidence record, limitations, provenance, etc.
├── requirements-proof.txt       Pinned Python dependencies for proof scripts
└── .github/workflows/           CI (`ci.yml`) and security audit workflows
```

| Path | Role |
| --- | --- |
| `contracts/po-settlement` | The only on-chain code. Compiles to the WASM artifact that is deployed and measured. |
| `scripts/` | Python and shell tools that deploy the artifact, drive PO lifecycles through the Stellar CLI, check results, and verify evidence. They are never deployed. |
| `evidence/` | Raw outputs and manifests captured from script runs, each with a `SHA256SUMS` file. |
| `docs/` | Human-readable interpretation of the evidence and its limits. |

## On-chain layer vs off-chain verification

### On-chain layer

`contracts/po-settlement` implements accepted-quantity settlement. It stores a
purchase order (PO), its ordered lines with quantities and unit prices,
receipts, and cumulative accepted quantities. The entry points in
`contracts/po-settlement/src/lib.rs` follow the PO lifecycle:

1. `create_po` / `accept_po`: buyer defines the PO, supplier accepts.
2. `fund_po`: buyer funds the full PO value in the selected token.
3. `submit_receipt` / `reject_receipt`: supplier asserts delivered quantities.
4. `accept_receipt_and_settle`: buyer accepts, the contract rechecks the
   current remaining quantity and transfers the quantity-derived amount.
5. `cancel_po`: buyer and supplier together cancel an Accepted or Funded PO; a
   Funded PO refunds only the unpaid remainder.
6. `get_po`, `get_line`, `get_receipt`, `get_receipt_line`, `receipt_value`:
   read-only views.

Token movement goes through a Stellar Asset Contract (SAC) or compatible
token. The contract records supplier assertions and buyer acceptance; it does
not verify physical delivery.

### Off-chain verification

Everything that checks the contract from the outside lives in `scripts/` and
the tests:

| Component | What it does |
| --- | --- |
| `contracts/po-settlement/src/test.rs` | Host tests run in the Soroban SDK test environment. They cover contract logic, including boundary and failure cases, but do not establish ledger or network behavior. |
| `scripts/local-flagship-proof.py` | Runs the flagship settlement lifecycle against a fresh standalone local ledger. |
| `scripts/local-cancellation-proof.py` | Runs the joint cancellation and refund lifecycle against a local ledger. |
| `scripts/testnet-flagship-proof.py` | Repeats the flagship lifecycle on public Stellar Testnet. It creates public test transactions and spends Testnet fees, so it is not routine CI. |
| `scripts/movix-compatibility-proof.py` | Read-only check of a pinned Movix line-item fixture. It performs no ledger writes. |
| `scripts/movix-testnet-proof.py` | Executes the bounded Movix source-model proof on Testnet. Not routine CI. |
| `scripts/verify-evidence-checksums.py` | Verifies every `evidence/*/SHA256SUMS` file against the committed files. |
| `scripts/security-audit.sh` | Runs `cargo audit` against the lockfile. |

The proof scripts drive the compiled WASM through the Stellar CLI and verify
submitted transactions with `stellar tx fetch result`, exiting nonzero on any
missing or failed result or unexpected final state.

## Evidence bundles

Each directory under `evidence/` is a self-contained record of one execution
or validation. A bundle typically contains:

- `manifest.txt`: execution time, source SHA and tree, toolchain versions,
  network and protocol, contract and asset IDs, WASM size and SHA-256, and
  transaction hashes.
- A proof transcript or summary (for example `local-flagship-proof.txt`,
  `testnet-flagship-proof.txt`, `local-cancellation-proof.txt`).
- Structured data where relevant (for example `transactions.json` with fetched
  transaction results, or the Movix `mapping.json` and `source-verification.json`).
- `SHA256SUMS`: SHA-256 digests of the bundle's files.

| Bundle | Records |
| --- | --- |
| `evidence/local-2026-11-06`, `evidence/procuresettle` | Local-ledger flagship settlement runs. |
| `evidence/stage6`, `evidence/stage9` | Hosted (GitHub Actions) flagship runs recorded before the rename, under the LineSettle name. |
| `evidence/cancellation`, `evidence/cancellation-authorization-2026-11-06` | Local-ledger joint cancellation and refund runs. |
| `evidence/testnet` | Public Stellar Testnet flagship settlement run. |
| `evidence/movix` | Movix line-item compatibility proof, including Testnet transactions. |

### How the cryptographic proof is maintained

Evidence ties an outcome to specific bytes at three levels:

1. **Artifact identity.** The manifest records the WASM size and SHA-256 and
   the source commit and tree it was built from, so a result is attributable
   to an exact contract build.
2. **Execution identity.** Testnet bundles record public transaction hashes
   and the fetched results in `transactions.json`; local bundles record
   transaction hashes and results in the transcript. Anyone can re-fetch
   public Testnet transactions and compare. Local ledgers are ephemeral, so
   local evidence is the preserved transcript rather than a re-queryable ledger.
   Local runs also record the pinned Quickstart image digest.
3. **Bundle integrity.** `SHA256SUMS` fixes the content of every file in the
   bundle. `scripts/verify-evidence-checksums.py` recomputes the digests and
   fails on a mismatch, a malformed entry, a missing file, or a path outside
   `evidence/`.

Historical bundles are never edited. Changed results get a new dated or
stage-named bundle with its own checksums. Evidence shows what a recorded run
observed for its recorded revision; it does not by itself establish behavior
for other revisions, a Mainnet deployment, or physical delivery.

## CI pipeline

`.github/workflows/ci.yml` runs two jobs:

- **`verify`**: checks out the exact PR head, then runs `cargo fmt --check`,
  `cargo clippy -D warnings`, and `cargo test` with the pinned toolchain and
  `--locked`. It then runs `py_compile` on `scripts/*.py`, verifies evidence
  checksums, and builds the WASM with the pinned Stellar CLI.
- **`flagship`**: builds the contract, starts a fresh local Stellar network from
  the pinned Quickstart image digest, creates test identities and an SAC, and
  runs the local flagship and cancellation proofs. Raw proof output is uploaded
  as a workflow artifact.

`.github/workflows/security-audit.yml` runs `scripts/security-audit.sh` on pull
requests, on pushes to `main`, and weekly.

Testnet and Movix Testnet proofs are run manually and are not part of CI.

## How the pieces relate

```text
contracts/po-settlement ──build──▶ procuresettle.wasm
        │                                │
   host tests (test.rs)       deploy + invoke via Stellar CLI
        │                                │
        ▼                                ▼
   cargo test (CI)          scripts/*-proof.py (local in CI, Testnet manual)
                                         │
                                         ▼
                        evidence/<bundle>/ (manifest, transcript, SHA256SUMS)
                                         │
                                         ▼
                      scripts/verify-evidence-checksums.py (CI)
```

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for tool versions and the commands
to rebuild and reproduce each proof.
