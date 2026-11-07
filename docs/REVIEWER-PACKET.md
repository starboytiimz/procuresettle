# ProcureSettle independent review packet

## Review target

- **Latest tested revision:** [`ebeefae7a2e6765a2cb166d3b77be63656fd3d56`](https://github.com/starboytiimz/procuresettle/commit/ebeefae7a2e6765a2cb166d3b77be63656fd3d56)
- **Latest hosted Actions run:** [42155230066](https://github.com/starboytiimz/procuresettle/actions/runs/42155230066)
- **Verify job:** [127687683885](https://github.com/starboytiimz/procuresettle/actions/runs/42155230066/job/127687683885)
- **Flagship proof job:** [127687683545](https://github.com/starboytiimz/procuresettle/actions/runs/42155230066/job/127687683545)
- **Hosted proof artifact:** `procuresettle-hosted-flagship-proof`, artifact ID `13474451394`; [download ZIP](https://api.github.com/repos/starboytiimz/procuresettle/actions/artifacts/13474451394/zip). It expires December 6, 2026.

The earlier successful run [42148702120](https://github.com/starboytiimz/procuresettle/actions/runs/42148702120) tested revision [`25726ae01f2e53e56cd94f43521db414992fa18b`](https://github.com/starboytiimz/procuresettle/commit/25726ae01f2e53e56cd94f43521db414992fa18b). No contract files changed between `25726ae` and `ebeefae`; the newer run is the latest hosted proof record, while the earlier run remains valid evidence for its tested revision. Both are project-controlled hosted executions, not independent external reproduction or review.

ProcureSettle is a Soroban purchase-order settlement contract. It computes
supplier payouts from buyer-accepted receipt quantity deltas and stored unit
prices. This review scope is limited to the tested two-line settlement,
stale-receipt rejection, cancellation authorization, and remaining-funds refund
behavior. The contract records buyer acceptance; it does not verify physical
delivery.

## Reproduction

Use the repository's [contributor guide](../CONTRIBUTING.md) and
[hosted workflow](../.github/workflows/ci.yml) for prerequisites and the exact
fresh-ledger setup. The tested environment used Rust/Cargo 1.95.0, Stellar CLI
28.1.0, `stellar-sdk` 13.1.0, protocol 28, and
`stellar/quickstart@sha256:4f8dfd693deba57fddef7f0bc722e4782c2e606c8675e3adc5438cebae249295`.
Use a disposable standalone ledger and test-only Stellar Asset Contract.
Do not use Testnet/Mainnet funds or production data for these proofs.

From the repository root, build and run repository checks:

```sh
cargo +1.95.0 fmt --all -- --check
cargo +1.95.0 test --workspace --locked
stellar contract build --locked --package procuresettle
python3 -m venv .venv-proof
. .venv-proof/bin/activate
python -m pip install -r requirements-proof.txt
python3 scripts/verify-evidence-checksums.py
```

After completing the local setup from the `flagship` job, run both proofs with
the same local config, built WASM, identities, SAC, and report directory:

```sh
python3 scripts/local-flagship-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"

python3 scripts/local-cancellation-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"
```

Both scripts return nonzero on unexpected results. The CI workflow runs the
settlement proof and then the cancellation proof; cancellation still runs if
settlement fails, as long as common setup succeeded. The full historical and
hosted records are in [EVIDENCE.md](EVIDENCE.md), and checksummed execution
bundles are under [`evidence/`](../evidence/).

## Expected outcomes in the hosted run

- For ordered lines `10 x 6` and `8 x 5` (total 100), accepted deltas `6` and
  `4` pay 56; the remaining accepted deltas `4` and `4` pay 44. The PO closes
  with paid 100, refunded 0, and zero contract token balance.
- A changed-quantity receipt pays 50.
- A previously submitted receipt that exceeds the remaining quantity is
  rejected with `QuantityExceedsRemaining`; PO, line, receipt, and token
  balance snapshots remain equal.
- Buyer-only cancellation is rejected as a failed transaction and does not
  change PO or settlement-token balances. Joint cancellation succeeds with
  final state `Cancelled`, funded 100, paid 56, refunded 44, and contract token
  balance zero.

## Known limits

- No Mainnet deployment or proof; cancellation is demonstrated only on a local
  standalone ledger.
- No physical delivery verification, dispute arbitration, PO amendments,
  invoice financing, or factoring.
- At most eight PO lines; quantities and token values use integer base units.
- Arbitrary custom SEP-41 token compatibility is not established; execution
  used a classic asset wrapped as a Stellar Asset Contract.
- Soroban storage is TTL-bounded and long-inactive entries can be archived.
- The proofs do not measure native XLM fees from failed transactions and are
  not a third-party security audit.
- The Movix work is bounded read-only/source-fixture compatibility testing,
  not integration, maintainer validation, adoption, or endorsement.

## Questions for the reviewer

1. Is each payout calculated from the accepted quantity delta at the stored
   unit price, including the 56, 44, and 50 outcomes?
2. Do the authorization rules require both parties for cancellation, and does
   the failed buyer-only transaction evidence the missing supplier authority?
3. Are the `Funded`, `Closed`, and `Cancelled` transitions and paid/refunded
   accounting consistent with the observed token balances?
4. Do the stale-receipt and unauthorized-cancellation failures preserve the
   claimed economic state? Are there other failure paths or fee effects the
   harness should make explicit?
5. Which assumptions in the proof setup, token model, TTL handling, or evidence
   process need more scrutiny?

No independent review or reproduction has yet been performed. Please identify
the exact source revision, environment, commands, observed results, and failed
steps in any response. Record attribution only with the reviewer's consent.
