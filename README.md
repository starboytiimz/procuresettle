# ProcureSettle

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
proof reproduction, and contribution standards. The [provenance record](docs/PROVENANCE.md)
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

See [current limitations and possible future work](docs/LIMITATIONS.md) for
the full boundary and the gaps that still need evidence.

Evidence produced before the product rename retains the historical LineSettle
name and artifact identity. Evidence produced after the rename uses
ProcureSettle.
