# Contributing to ProcureSettle

ProcureSettle is a Soroban purchase-order settlement contract. Keep changes
focused on the contract's accepted-quantity settlement workflow, its evidence,
or the contributor experience. Do not describe a proposed capability as
implemented until code and evidence support that claim.

## Required tools

The repository pins Rust and Cargo to **1.95.0** in `rust-toolchain.toml`, with
the `wasm32v1-none` target. The contract uses **soroban-sdk 28.0.0**, pinned in
`Cargo.toml` and `Cargo.lock`. Use **Stellar CLI 28.1.0** for contract builds
and CLI proof scripts. Python 3.11 or newer is required for the cancellation
harness; create an isolated environment and install its exact dependencies
from `requirements-proof.txt`. The Movix source checker uses only the Python
standard library and Git.

For host tests and builds, install Rust 1.95.0 with rustfmt and the target:

```sh
rustup toolchain install 1.95.0 --profile minimal --component rustfmt
rustup target add --toolchain 1.95.0 wasm32v1-none
```

Install Stellar CLI 28.1.0 using the [official Stellar CLI installation
instructions](https://developers.stellar.org/docs/tools/developer-tools/cli/stellar-cli).
For the cancellation harness dependencies:

```sh
python3 -m venv .venv-proof
. .venv-proof/bin/activate
python -m pip install -r requirements-proof.txt
```

The local-ledger proofs additionally require Docker, `curl`, and `jq`. The CI
workflow pins Quickstart to
`stellar/quickstart@sha256:4f8dfd693deba57fddef7f0bc722e4782c2e606c8675e3adc5438cebae249295`
(image version label `24.04`, revision
`91a64b5da2d7926bc82ae5a1f06048ef08cdcec2`) and verifies that Stellar CLI
starts the local network from those image bytes at protocol 28. The digest is
tagged locally because Stellar CLI 28.1.0 accepts a tag override rather than an
image digest. Historical evidence bundles that requested `latest` remain
unchanged and record the digest resolved for those runs.

To intentionally update Quickstart, select a candidate immutable digest,
`docker pull stellar/quickstart@sha256:<candidate>`, inspect its version and
revision labels, and update the digest and local alias in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). Run the complete local
ledger CI job and confirm the container image ID equals the image pulled by
digest, the ledger reports protocol 28, and both proofs pass. Record the new
digest, labels, CLI version, protocol, and run result in a new evidence record;
do not edit the historical manifests.

## Build and validate

From the repository root:

```sh
cargo +1.95.0 fmt --all -- --check
cargo +1.95.0 test --workspace --locked
stellar contract build --locked --package procuresettle
python3 scripts/verify-evidence-checksums.py
```

The lockfile is committed; keep `--locked` in validation commands. Add tests
for behavior changes, including boundary and failure cases. A passing host test
does not establish ledger execution or network behavior. Do not weaken existing
assertions to make a change pass.

## Reproduce the local flagship proof

The local proof sends transactions to a fresh standalone ledger, but never to
Testnet or Mainnet. It creates six isolated purchase orders and expects each
control PO to settle 56 then 44 units, close at funded/paid 100 and refunded 0;
a changed receipt settles 50; and an overlarge stale receipt fails with
`QuantityExceedsRemaining` without changing the recorded economic state.

The most complete, maintained setup is the `flagship` job in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). It pins Rust, CLI,
protocol 28, creates three local identities and an SAC, runs the proof script,
and records the Quickstart image identity. After running those setup steps (or
creating equivalent funded local identities and SAC), invoke:

```sh
python3 scripts/local-flagship-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"
```

On success the script exits 0 and prints
`PROCURESETTLE_LOCAL_FLAGSHIP_PROOF_SUMMARY` with `"verdict": "PASS"`.
Any failed command, missing CLI output, incorrect transfer, unexpected final
state, artifact size/hash mismatch, or stale-receipt result mismatch exits
nonzero. The log and summary are written to the report directory. See
[`docs/EVIDENCE.md`](docs/EVIDENCE.md) for the tested source revision,
environment, recorded result, and proof limits.

## Reproduce cancellation and refund

The cancellation proof deploys a fresh contract, creates and funds a 100-unit
PO, settles an accepted partial receipt for 56, verifies a cancellation attempt
signed only by the buyer is recorded as a failed ledger transaction with no PO
or SAC balance changes, then submits the cancellation with buyer and supplier
authorizations. Native XLM fees for the failed transaction are not measured. It
expects final status `Cancelled`, funded 100, paid 56, refunded 44, supplier
gain 56, and zero contract balance. It verifies every submitted transaction
with `stellar tx fetch result` and exits nonzero on a missing or failed result.

Use the same local network, identities, SAC, and WASM prepared by the
`flagship` CI job:

```sh
python3 scripts/local-cancellation-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"
```

The proof requires at least 100 base units in the buyer's SAC balance. It uses
only a protocol-28 standalone local network and has no Testnet or Mainnet
side-effects. Its transcript and summary identify the source commit, artifact,
network, transaction hashes, actual transaction outcomes, and observed state.

## Testnet evidence

The repository contains historical Testnet evidence and scripts, but running
them creates public ledger transactions, consumes funded XLM, and creates
test-only assets. The flagship script requires a private CLI config directory
containing funded issuer, buyer, and supplier identities. Review its help and
the exact historical manifest before use:

```sh
python3 scripts/testnet-flagship-proof.py --help
```

To reproduce the recorded public Testnet settlement run, use a private CLI
config containing funded Testnet issuer, buyer, and supplier identities. This
creates public test transactions and consumes Testnet fees:

```sh
python3 scripts/testnet-flagship-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity "$ISSUER_IDENTITY" \
  --buyer-identity "$BUYER_IDENTITY" \
  --supplier-identity "$SUPPLIER_IDENTITY"
```

The current harness also verifies the expected artifact hash and Testnet
protocol before its proof. Testnet is resettable and has no monetary value.
The Movix compatibility harness has the same public-network impact; it also
requires the pinned Movix checkout and is not routine CI. Historical results
are evidence for their recorded source revisions, not a claim that a new run
was performed for the current checkout.

For read-only source compatibility only, the Movix checker reads an existing
checkout at the pinned commit and performs no ledger writes:

```sh
python3 scripts/movix-compatibility-proof.py \
  --movix-checkout /path/to/Movix
```

It prints JSON with `"verdict": "PASS"` only when the pinned commit, fixture,
source blobs, independently calculated values, and stated workflow boundaries
match. This is source-level compatibility evidence, not an integration or
external maintainer validation.

## Evidence standards

For new execution evidence, record the exact source commit and tree, toolchain
versions, artifact size and digest, network/ledger and protocol, command or
harness, expected outcome, observed outcome, and relevant raw results. State
what the evidence cannot establish. Keep older evidence unchanged; add a new
dated or stage-named record and its checksums when results change. Never use a
screenshot or prose summary in place of execution output or fetched transaction
data.

## Useful first contributions

These are grounded in documented gaps; they are not promises that an issue is
already filed:

- Add a reviewer-facing evidence record for an independently performed
  settlement review or test. First agree on the fixture and safe test
  environment with the reviewer; preserve their actual results and distinguish
  review from integration or endorsement. See the proposed request in
  [`docs/EXTERNAL-VALIDATION.md`](docs/EXTERNAL-VALIDATION.md).

## Submitting changes

Open a focused pull request against `main`. Explain the user-visible or
reviewer-visible change, list the commands actually run, link any new evidence,
and state skipped checks with the reason. Include tests for contract behavior
changes and keep documentation claims aligned with the code and captured
results. Do not include seed phrases, private keys, or private CLI config files.
