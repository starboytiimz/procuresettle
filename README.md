# ProcureSettle

![CI](https://github.com/starboytiimz/procuresettle/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)
![Rust Edition](https://img.shields.io/badge/Rust%20Edition-2021-orange.svg)

Accepted-quantity procurement settlement on Stellar.

ProcureSettle (formerly LineSettle) is a Soroban purchase-order settlement
contract. Supplier payouts are calculated from buyer-accepted per-line receipt
quantities at stored unit prices rather than from fixed milestone amounts.

Generic milestone escrow releases predetermined amounts. ProcureSettle stores
ordered quantities and unit prices, tracks cumulative accepted quantities, and
calculates each settlement from newly accepted receipt deltas.

## Implemented flow

Buyer creates a PO → supplier accepts → buyer funds the full PO → supplier
submits receipt quantities → buyer accepts and settles them → the contract
rechecks current quantity bounds and transfers the exact quantity-derived
settlement amount to the supplier. When every ordered quantity is accepted,
the PO closes automatically. Buyer and supplier may also cancel an Accepted or
Funded PO together; a Funded PO refunds only its remaining unpaid value to the
buyer.

## Receipt preflight valuation

`receipt_value(env, po_id, receipt_id)` is a read-only endpoint that preflights
the exact token payout of a receipt before the buyer settles it. Clients can
call it after `submit_receipt` and before `accept_receipt_and_settle` to show
the amount a settlement would attempt to transfer.

### How the value is calculated

For each line indexed by the receipt header, the contract reads the stored
`ReceiptLine.quantity_delta` and the current PO line's `unit_price`, then sums
`delta × unit_price` using checked `i128` multiplication and addition. This is
the same calculation routine used by settlement. For the flagship terms
(line 1: 10 units at 6, line 2: 8 units at 5), a receipt with deltas 6 and 4
returns `(6 × 6) + (4 × 5) = 56`.

For a `Submitted` receipt, each delta is also checked against the line's current
remaining quantity (`ordered_quantity - accepted_quantity`). A delta that no
longer fits returns `QuantityExceedsRemaining`; a zero delta or nonpositive
total returns `InvalidReceipt`; missing receipt-line or PO-line records return
`ReceiptNotFound` or `UnknownPoLine`; and arithmetic overflow returns
`ArithmeticOverflow`. A `Rejected` receipt returns `InvalidReceiptState`.
A `Settled` receipt is revalued from its immutable deltas and stored unit prices
without the remaining-quantity check, so no paid amount needs to be stored twice.

### Why the preflight has no ledger state effect

`receipt_value` requires no authorization, writes no PO, line, receipt, or
receipt-line entry, and performs no token transfer. It reads state and returns
an `i128` (or an error). Like every contract entry point, it calls the shared
`extend_contract_ttl` helper, which only touches the contract instance/code TTL,
not the PO or receipt entries. Clients use the normal simulation path (Stellar
CLI/RPC read-only call without `--send`), which does not commit any state change,
including that TTL renewal, to the ledger. Sending the same call as a transaction
would persist the instance TTL renewal; preflights should stay in simulation.

### Client usage

1. The supplier submits quantities with `submit_receipt` (a state-changing call).
2. The client simulates `receipt_value` and displays the result in the token's
   integer base units. If it returns an error, show that the receipt cannot
   currently settle instead of prompting the buyer.
3. After the buyer confirms the displayed amount, call
   `accept_receipt_and_settle`, which rechecks the value and returns the amount
   actually transferred.

```sh
# Preflight: simulation only, no transaction and no ledger state/TTL change
stellar contract invoke \
  --contract-id "$CONTRACT_ID" \
  --source-account "$BUYER_IDENTITY" \
  --network testnet \
  -- receipt_value --po_id 90 --receipt_id 1
# => 56

# Only after the buyer confirms the displayed amount:
stellar contract invoke \
  --contract-id "$CONTRACT_ID" \
  --source-account "$BUYER_IDENTITY" \
  --network testnet \
  -- accept_receipt_and_settle --po_id 90 --receipt_id 1
# => 56
```

### Previews are advisory, not reservations

Submitted receipts do not reserve quantity. When several receipts are
`Submitted` at once, each preview is computed against the same current accepted
quantities. `accept_receipt_and_settle` recomputes the payout from live state at
settlement time. If another receipt settles first and consumes the remaining
quantity, the stale receipt fails with `QuantityExceedsRemaining` (or a funding
guard such as `SettlementExceedsFunded`), remains `Submitted`, and leaves token
balances unchanged because the invocation is atomic. Clients should re-run
`receipt_value` immediately before requesting buyer approval and present the
result as an estimate rather than a guaranteed payout.

## Architecture and specifications

- [Repository architecture](docs/ARCHITECTURE.md): Workspace components,
  on-chain and off-chain responsibilities, evidence bundles, and CI
  verification.
- [Data model specification](docs/DATA-MODEL.md): Persistent storage layout, `DataKey` definitions, struct fields, and deserialization cost bounds.
- [State machine reference](docs/STATE-MACHINE.md): Unambiguous transition matrix, required authorizations, terminal states, and rejected transitions for `PoStatus` and `ReceiptStatus`.
- [Storage TTL and renewal](docs/STORAGE-TTL.md): TTL constants, bump-on-access policy, and ledger archival behavior.
- [Contract error reference](docs/ERRORS.md): Complete table of `PoError` codes, root causes, and recommended caller actions.
- [Contract events specification](docs/EVENTS.md): Event topics, positional data tuples, and lifecycle emission status.
- [Cancellation and refund economics](docs/CANCELLATION.md): Joint authorization, refund accounting, and atomicity.
- [Movix compatibility boundary](docs/MOVIX-COMPATIBILITY.md): Scope and verification method for the pinned fixture proof.
- [Offline receipt settlement calculator](docs/RECEIPT-VALUE-CALCULATOR.md): Input schemas and usage for the standalone Python payout calculator.

## CLI walkthrough

For step-by-step Stellar CLI commands that create and fund a PO, see
[docs/CLI-WALKTHROUGH.md](docs/CLI-WALKTHROUGH.md).

## Offline payout verification

`scripts/calc-receipt-value.py` rechecks a receipt payout from local JSON files
without a network connection or a running ledger:

```sh
python3 scripts/calc-receipt-value.py --po-file <path-to-po.json> --receipt-file <path-to-receipt.json>
```

See [the calculator documentation](docs/RECEIPT-VALUE-CALCULATOR.md) for the
expected input structures and validation rules.

## Evidence

The project has 64 host tests, hosted local-ledger proofs for the flagship
settlement and joint-cancellation/refund lifecycles, and public Stellar Testnet
evidence for settlement plus a bounded read-only compatibility proof against
Movix's pinned line-item fixture. See the
[evidence record](docs/EVIDENCE.md) and the
[durable evidence bundles](evidence/) for source/WASM identities, public
transaction references, proof results, limitations, and reproduction paths.

Run the checks from the repository root:

```sh
cargo fmt --all -- --check
cargo test --workspace --locked
stellar contract build --locked --package procuresettle
```

## License

ProcureSettle is available, at your choice, under either the [MIT License](LICENSE-MIT)
or the [Apache License, Version 2.0](LICENSE-APACHE). The contract crate declares
the same SPDX expression, `MIT OR Apache-2.0`.

## Contributing and provenance

See [CONTRIBUTING.md](CONTRIBUTING.md) for pinned tools, build and test commands,
proof reproduction, and contribution standards. If setup fails, see
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common problems and fixes.
The [provenance record](docs/PROVENANCE.md)
documents the LineSettle to ProcureSettle rename without rewriting history.

## Limits

- ProcureSettle has a public Stellar Testnet flagship proof; no Mainnet
  deployment or proof is claimed.
- The Movix evidence is a read-only compatibility proof against one pinned
  integer line-item model. It is not a Movix integration or endorsement.
- The contract records supplier delivery assertions and buyer quantity
  acceptance; it does not automatically verify physical delivery.
- There is no dispute arbitration, invoice financing, factoring, or PO
  amendment in v0.1.
- Each PO is limited to eight lines.
- Quantities are integers and settlement values use the selected token's
  integer base units; there is no decimal or currency conversion layer.
- Compatibility has been tested with the pinned SDK host and its Stellar Asset
  Contract fixture, not broadly with custom SEP-41 tokens.
- Cancellation and refund have a local-ledger proof on a protocol-28 standalone
  network; no public-network cancellation proof is claimed.
- Active contract calls renew the contract instance/code and the relevant live
  PO, line, receipt, and receipt-line entries to a bounded TTL window. This is
  not permanent storage: after sufficiently long inactivity, Soroban may archive
  an entry and an invocation will require normal ledger restoration first.
  See [storage TTL and renewal](docs/STORAGE-TTL.md) for the constants, renewal
  policy, and restoration behavior.

See [current limitations and possible future work](docs/LIMITATIONS.md) for
the full boundary and the gaps that still need evidence. See the
[contract error reference](docs/ERRORS.md) for codes and caller actions.

On successful PO creation, the contract emits a `po_created` event with topics
`(po_created, po_id)` and data `(buyer, supplier, total_value)`. The total uses
the selected token's base units.

Evidence produced before the product rename retains the historical LineSettle
name and artifact identity. Evidence produced after the rename uses
ProcureSettle.
