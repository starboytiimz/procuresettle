# Independent validation request

No request has been sent, and no external review, integration, or endorsement
is claimed. This is a copy-ready proposal for a Stellar/Soroban developer or
relevant project maintainer.

## Project and problem

ProcureSettle is a Soroban purchase-order settlement contract. Fixed milestone
escrow releases predetermined amounts, while a partial-delivery purchase order
needs each payout to follow the quantities the buyer actually accepts at the
stored unit prices. ProcureSettle calculates that amount from accepted receipt
deltas. It records buyer acceptance; it does not verify physical delivery.

The proposed review is deliberately bounded to one two-line PO and its
settlement, stale-receipt, and cancellation authorization behavior. The key
evidence is the [local flagship run](../evidence/local-2026-11-06/) and
[local cancellation run](../evidence/cancellation-authorization-2026-11-06/)
with their source, artifact, environment, commands, results, and checksums.
The broader [evidence record](EVIDENCE.md) and
[contributor reproduction guide](../CONTRIBUTING.md) contain historical and
Testnet context and the supported setup.

## Proposed request

> Hi [Name],
>
> I’m looking for an independent technical review or reproduction of
> ProcureSettle, a Soroban contract that calculates supplier payouts from
> buyer-accepted receipt quantities and stored purchase-order prices. Would
> you review the bounded settlement and authorization workflow, or independently
> run it on a disposable protocol-28 local ledger?
>
> Evidence and reproduction references: `docs/EVIDENCE.md`,
> `CONTRIBUTING.md`, `evidence/local-2026-11-06/`, and
> `evidence/cancellation-authorization-2026-11-06/`. The test uses a local
> test-only Stellar Asset Contract; it requires no Testnet/Mainnet funds or
> production systems. I’d value your view on the settlement arithmetic,
> Soroban authorization checks, and whether the evidence supports the stated
> behavior and limits. Please share any failed steps or concerns as well as
> successful results.
>
> This is a request for independent technical scrutiny only. It does not ask
> for integration, adoption, or endorsement. Please let me know whether you
> prefer code review, independent reproduction, or both, and what attribution
> you consent to if results are documented.

## Bounded workflow and questions

The normal proof creates and funds a two-line PO (10 x 6 and 8 x 5, total 100),
settles a buyer-accepted partial receipt of 6 and 4 units for 56, settles a
changed quantity case for 50, and rejects a receipt that exceeds the remaining
quantity after settlement. The cancellation proof checks that a buyer-only
cancel transaction fails due to missing supplier authorization, then checks
that joint buyer/supplier cancellation refunds the remaining 44 units. These
are separate fresh contract instances on the same isolated local ledger.

Questions for the reviewer:

- Does the contract calculate each payout from the accepted quantity delta and
  immutable stored unit price, including the 56 and 50 cases?
- Does the stale/excess receipt rejection preserve the PO, line, receipt, and
  settlement-token balance state?
- Does the failed buyer-only cancellation metadata identify missing supplier
  authorization, and does joint cancellation refund exactly the unpaid value?
- Do the evidence and reproduction instructions support their claims, and what
  important behavior or environment assumption remains untested?

## Reproduction instructions

Use the instructions in [`CONTRIBUTING.md`](../CONTRIBUTING.md) to install Rust
1.95.0, Stellar CLI 28.1.0, Python 3.11 or newer, the pinned packages in
[`requirements-proof.txt`](../requirements-proof.txt), and Docker. Prepare a
private Stellar CLI config with funded local `stage6-issuer`, `stage6-buyer`,
and `stage6-supplier` identities and a test-only SAC with at least 1000 units
for both proofs in sequence (600 funds the six flagship POs; the remainder
covers cancellation). Start a fresh standalone local ledger using the pinned
Quickstart digest in `.github/workflows/ci.yml` and protocol 28. The CI
flagship job records the complete, tested setup sequence.

Run both commands from the repository root after setting the variables shown
in the examples and completing that setup:

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

Each command exits nonzero on an unexpected transaction result, state, or
balance. The expected outcomes and exact observed hashes are in the linked
evidence records. The failed unauthorized transaction can consume local native
XLM fees; the cancellation proof compares purchase-order state and settlement
token balances.

## Bounded scope

- Review the contract authorization and settlement/refund arithmetic, or
  independently reproduce the local-ledger evidence, or do both.
- Use a disposable protocol-28 standalone network and a test-only SAC. Do not
  use Testnet/Mainnet funds, another project's production environment, or any
  real purchase-order data.
- Record findings against the exact source commit and proof harness revision.
  A source review alone should be labeled review; an independent run should be
  labeled reproduction.

## Compatibility is not integration

The Movix work is a bounded compatibility exercise: a read-only checker
inspects pinned Movix source/fixture data, and a separate ProcureSettle
Testnet run uses mapped numeric values. That run does not execute Movix code,
share a deployment, or change Movix state. There is no Movix integration or
external maintainer review recorded. Independent validation requested here
would also remain review or reproduction unless an actual, separately agreed
integration were implemented and evidenced.

## Evidence to retain if performed

Create a new dated evidence record containing the reviewer's name and role only
with their permission, their project affiliation if they choose to provide it,
the reviewed source commit and tree, harness revision, artifact size and
SHA-256, Rust/SDK/CLI/Python versions, Quickstart digest and protocol, commands,
expected and observed results, transaction hashes and fetched outcomes (or local
state/balance assertions), and any findings or failed attempts. Preserve the
reviewer's response or a redacted record only with their consent. State whether
the work was code review, independent execution, maintainer validation, or an
integration; do not infer the latter two from a review or successful run.
