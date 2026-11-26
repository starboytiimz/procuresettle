# Storage TTL and renewal

Soroban gives every contract data and code entry a time-to-live (TTL) measured
in ledgers. ProcureSettle uses the standard bump-on-access pattern so that an
actively used purchase order stays live, without claiming permanent storage.
TTL is a storage-lifecycle mechanism, not a business deadline or an
authorization control.

When an entry's TTL reaches zero the entry stops being live: persistent and
instance entries become **archived** and must be restored before they can be
used again, while temporary entries would be deleted permanently. ProcureSettle
stores no temporary data.

This page documents the renewal policy implemented in
[`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs)
and what integrators and operators should expect when an entry is archived. It
describes current behavior; it does not change the policy. For the
product-level boundary, see [`docs/LIMITATIONS.md`](LIMITATIONS.md).

For protocol background, see the Stellar documentation on
[State Archival](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival)
and [storage strategies](https://developers.stellar.org/docs/build/guides/storage/storage-strategies).

## TTL constants

Both constants are declared near the top of `lib.rs`:

| Constant | Value | Meaning at the usual ~5 s ledger cadence |
| --- | --- | --- |
| `TTL_RENEW_THRESHOLD_LEDGERS` | `2_073_601` | Renew when fewer than 120 days plus one ledger remain. |
| `TTL_RENEW_TO_LEDGERS` | `2_592_000` | Renewal target of about 150 days. |

These values are ledger counts, not wall-clock durations. The ~5 second close
time is a network setting, so the day equivalents are approximations and can
change with protocol or network-setting upgrades.

`extend_ttl(threshold, extend_to)` is conditional: if the entry's current TTL
is **at least** `threshold`, the call is a no-op; otherwise the TTL is raised
to `extend_to`. The contract therefore renews an entry at most once every
`2_592_000 - 2_073_601 = 518_399` ledgers (roughly 30 days) of progress,
instead of paying rent on every invocation. The constants do not promise that
an entry stays live for 150 days of wall-clock time, only that a qualifying
call raises its TTL to that many ledgers.

The threshold sits one ledger above the currently documented network minimum
persistent TTL of `2_073_600` ledgers (~120 days), so a bump is requested as
soon as an entry would otherwise fall to the minimum. The 150-day target sits
below the currently documented maximum entry TTL of `3_110_400` ledgers
(~180 days). That margin matters because an `extend_to` above the network
maximum minus one causes the transaction to fail; a target below the ceiling
also avoids unnecessary rent. The TTL host tests configure the SDK host with
these same network values so the policy is exercised against realistic bounds
rather than the SDK defaults.

Network TTL limits are configuration parameters and can change. The values
above were checked against the Stellar documentation on
[State Archival](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival),
the resource-limits reference linked there, and
[CAP-46 State Archival Interface](https://raw.githubusercontent.com/stellar/stellar-protocol/master/core/cap-0046-12.md)
on 2026-11-19. Re-check them before relying on the day equivalents; the
[Stellar Lab network limits](https://lab.stellar.org/network-limits) or the
network settings tooling report live values.

## What is renewed and when

All storage keys used by the contract (`Header`, `Line`, `Receipt`, and
`ReceiptLine`) are **persistent** entries. Each persistent entry has its own
independent TTL and must be extended by key. The contract instance is a
separate entry, and the Wasm code entry behind it has its own TTL as well.

| Entry | Storage | Renewal path |
| --- | --- | --- |
| Contract instance and Wasm code | instance + code | `extend_contract_ttl()` runs at the start of every public function. `env.storage().instance().extend_ttl()` extends both the instance and the code entry, with an independent threshold check for each. |
| PO header (`DataKey::Header`) | persistent | Created and extended in `create_po`; renewed by `extend_po_ttl()` in `accept_po`, `fund_po`, `submit_receipt`, `reject_receipt`, `accept_receipt_and_settle`, and `cancel_po`. |
| PO lines (`DataKey::Line`) | persistent | Created and extended in `create_po`; `extend_po_ttl()` renews the header **and every line listed in the header**, including lines not touched by a partial receipt. The list is bounded by `MAX_LINES` (8). |
| Receipt (`DataKey::Receipt`) | persistent | Created and extended in `submit_receipt`; renewed by `extend_receipt_ttl()` in `reject_receipt` and `accept_receipt_and_settle`. |
| Receipt lines (`DataKey::ReceiptLine`) | persistent | Created and extended in `submit_receipt`; `extend_receipt_ttl()` renews each line indexed by the receipt. |

The two persistent-entry helpers verify that the header, lines, receipt, and
receipt lines still exist before calling `extend_ttl`, returning `NotFound` /
`InvalidLine` or `ReceiptNotFound` / `InvalidReceipt` if an indexed entry is
missing, so a PO can never be partially renewed. Newly created entries are
extended immediately after they are written, so they start at the 150-day
target rather than the network minimum.

### Renewal per mutating call

| Call | Instance / code | Persistent business records renewed |
| --- | --- | --- |
| `create_po` | yes | new header and every new PO line, extended right after `set` |
| `accept_po` | yes | existing header and all of its PO lines |
| `fund_po` | yes | existing header and all of its PO lines |
| `submit_receipt` | yes | header and all PO lines; new receipt and every new receipt line |
| `reject_receipt` | yes | header and all PO lines; receipt and all of its receipt lines |
| `accept_receipt_and_settle` | yes | header and all PO lines; receipt and all of its receipt lines |
| `cancel_po` | yes | header and all PO lines (no receipt records are needed) |

Renewing *all* lines rather than only the lines named in a receipt is
deliberate: the header and every line participate in quantity, conservation,
and closeout checks, so a later partial settlement must not find an untouched
line that has aged out.

For mutating calls, the instance/code bump is attempted at function entry,
before authentication and validation. The persistent-entry bumps follow
authentication and validation and occur before the related state writes and
token transfers. Soroban invocation atomicity rolls back TTL extensions along
with storage and token effects when an invocation fails, so a failed
settlement or cancellation does not leave partially renewed state behind.

## Why read-only getters do not renew business records

The read-only functions `get_po`, `get_line`, `get_funded_value`,
`get_receipt`, `get_receipt_line`, and `receipt_value` do **not** call
`extend_po_ttl()` or `extend_receipt_ttl()`. They leave the TTLs of PO, line,
receipt, and receipt-line entries untouched. They do still call
`extend_contract_ttl()` at entry, so an inspection call can renew the shared
contract instance and code entries when those entries are below the threshold.

This split is deliberate:

- Persistent entries are separate ledger entries with separate TTLs. Renewing
  each of them on every read would turn a read-only inspection into a
  multi-entry write with additional footprint and rent costs.
- A query does not advance PO state, so there is no coherent set of records to
  protect. Bumping just the one key a getter touches would leave the rest of
  the PO at different TTLs without preserving the whole lifecycle.
- Renewal of business records is tied to lifecycle activity: every successful
  state-changing call renews the records it depends on, so the fee payer funds
  a full, consistent set for a logical operation and rent usage stays
  proportional to actual PO progress rather than to the number of reads.
- Keeping the instance and code live is enough to keep the contract callable.
  Persistent data is then governed by its own activity: a PO that is only
  queried can still age out and need restoration.
- TTL is not an access-control boundary. Anyone may extend an entry's TTL with
  an external `ExtendFootprintTTLOp`, so limiting getter-side bumps is a cost
  and resource policy, not a security guarantee.

These getters are therefore suitable for monitoring, preflight, and value
previews without changing business-record TTLs. A `receipt_value` preview
remains advisory: settlement rechecks current quantity bounds before paying.

Note that `extend_ttl` is an explicit resource operation even inside a getter.
Integrators should simulate the final transaction so the declared resources and
fees include any instance/code bump that actually fires.

## Archived entries and restoration

An entry is live while `current_ledger <= liveUntilLedger`; once the current
ledger is greater, it is archived (persistent/instance) or dead (temporary).
Archived persistent entries cannot be re-created under the same key. They must
be restored first; only after restoration can they be read, modified, or
deleted.

Contract code never executes against an archived entry:

- A transaction that includes an archived persistent key in its footprint
  without the key in the restore list fails during apply, before contract code
  runs. Contract code cannot observe or handle an archived entry.
- Since Protocol 23, a normal invocation whose simulation detects an archived
  entry adds that entry to the transaction's **restore list**. The network
  restores those entries before `InvokeHostFunction` runs, and normal rent and
  fees apply. Use the simulation result as-is when assembling and submitting
  the final transaction.
- A manually built transaction that omits required archived entries from its
  restore list fails before contract execution. Do not strip or replace the
  restore list produced by simulation.
- In rare cases, restoration can be done separately with `RestoreFootprintOp`
  (the CLI wraps this as `stellar contract restore`), for example to pay
  restoration fees from a keeper account or when automatic restoration would
  make the invocation too large. The contract instance and its Wasm code are
  distinct ledger keys and can archive independently; if either is archived,
  no invocation can load the contract to perform the bumps above. Archived PO,
  line, receipt, and receipt-line entries can be restored individually by key.
- A restored entry comes back at the network minimum TTL (currently
  `2_073_600` ledgers, about 120 days), not automatically at ProcureSettle's
  150-day target. Neither restoration nor an ordinary read/write invocation
  extends TTL by itself; a later successful **mutating** lifecycle call, or an
  explicit TTL extension, raises it to the target. A getter alone will not.

External TTL management remains available: `ExtendFootprintTTLOp` (the CLI
wraps this as `stellar contract extend`) can extend any live entry, is not
restricted to the contract's parties, and charges rent proportional to entry
size and the number of ledgers added. This makes keeper-based extension
possible for POs that must survive long periods of inactivity.

## Operational guidance

- Treat the 150-day target as activity-based, not as permanent storage. An idle
  PO, receipt, or even the deployed instance can eventually archive; the README
  and [`docs/LIMITATIONS.md`](LIMITATIONS.md) state the same boundary.
- Always simulate the final transaction and preserve the simulation's restore
  list, so archived entries are restored automatically and rent/resource fees
  are declared. Retry restoration plus the original call when an archived entry
  is detected.
- For POs that must survive long periods with no buyer or supplier activity,
  arrange an off-chain keeper to submit `ExtendFootprintTTLOp` for the header,
  all lines, and each live receipt and receipt line (and, if needed, the
  instance and code keys). That operation uses a read-only footprint, must be
  the only operation in its transaction, and cannot bump already-archived
  entries; restore those first.
- Anyone may extend or restore an entry without authorization, and TTLs are
  not a security or expiry mechanism. Authorization and lifecycle rules in the
  contract remain the source of truth.
- Verify current minimum and maximum TTL network parameters before relying on
  the day-equivalent figures above.

## Verification

The policy is covered by host tests in
[`contracts/po-settlement/src/test.rs`](../contracts/po-settlement/src/test.rs):

- `ttl_policy_covers_full_lifecycle_beyond_default_boundary_and_rebumps` runs
  the funded settlement lifecycle past unextended network bounds and checks
  that a later receipt re-bumps the header and every PO line.
- `ttl_getters_do_not_renew_business_records_but_active_write_does` advances
  entries below the threshold, confirms getters renew only instance/code, and
  confirms the following settlement restores all business-record TTLs to the
  target.
- The outgoing-transfer rollback tests confirm that failed token transfers
  leave both values and TTLs unchanged.

Reproduce with the repository-root checks:

```sh
cargo fmt --all -- --check
cargo test --workspace --locked
stellar contract build --locked --package procuresettle
```

## Sources

- [State Archival — Stellar Developer Docs](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival)
- [Storage strategies — bump on access](https://developers.stellar.org/docs/build/guides/storage/storage-strategies)
- [CAP-46 State Archival Interface](https://raw.githubusercontent.com/stellar/stellar-protocol/master/core/cap-0046-12.md)
- [Stellar Lab network limits](https://lab.stellar.org/network-limits)
