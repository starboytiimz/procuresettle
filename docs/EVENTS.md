# Contract events specification

This document specifies the Soroban contract events of ProcureSettle (the
`po-settlement` contract), their topics, data schemas, and how an indexer
should parse them.

> **Implementation status.** At this revision `contracts/po-settlement` does
> **not** yet publish any events; the emission work is tracked in
> [#32](https://github.com/starboytiimz/procuresettle/issues/32) (`po_created`),
> [#33](https://github.com/starboytiimz/procuresettle/issues/33) (`po_accepted`),
> [#34](https://github.com/starboytiimz/procuresettle/issues/34) (`po_funded`),
> [#35](https://github.com/starboytiimz/procuresettle/issues/35) (`receipt_submitted`),
> [#36](https://github.com/starboytiimz/procuresettle/issues/36) (`receipt_settled`),
> [#115](https://github.com/starboytiimz/procuresettle/issues/115) (receipt rejection) and
> [#116](https://github.com/starboytiimz/procuresettle/issues/116) (`po_cancelled`).
> This file is the target schema those changes must follow. Until they land,
> indexers cannot observe these events on-chain. The only events present in
> transactions today are those emitted by the token contract (for example the
> SEP-41 `transfer` event produced by funding, settlement and refunds).

## Conventions

Events follow the standard Soroban SDK convention,
`env.events().publish(topics, data)`:

- `topics` is a tuple whose first element is the event name as a `Symbol`,
  followed by identifiers used for filtering.
- `data` is the event body (a single value or a tuple, encoded as a Soroban
  `ScVal`).
- Identifiers (`po_id`, `receipt_id`) are `u64`; addresses are `Address`;
  amounts are `i128` in the selected token's integer base units.
- `symbol_short!` accepts at most 9 characters, so names longer than that
  (for example `po_created`, `receipt_submitted`) must be built with
  `Symbol::new(&env, "...")`.

## Event reference

| Event | Topics | Data | Emitted by |
|-------|--------|------|------------|
| `po_created` | `("po_created", po_id)` | `(buyer, supplier, total_value)` | `create_po` |
| `po_accepted` | `("po_accepted", po_id)` | `supplier` | `accept_po` |
| `po_funded` | `("po_funded", po_id)` | `(buyer, total_value)` | `fund_po` |
| `receipt_submitted` | `("receipt_submitted", po_id, receipt_id)` | `supplier` | `submit_receipt` |
| `receipt_settled` | `("receipt_settled", po_id, receipt_id)` | `payout` | `accept_receipt_and_settle` |
| `po_cancelled` | `("po_cancelled", po_id)` | `refund` | `cancel_po` |

### Schemas

| Event | Topic fields | Data fields |
|-------|--------------|-------------|
| `po_created` | `Symbol`, `po_id: u64` | `buyer: Address`, `supplier: Address`, `total_value: i128` (sum of `ordered_quantity * unit_price`) |
| `po_accepted` | `Symbol`, `po_id: u64` | `supplier: Address` |
| `po_funded` | `Symbol`, `po_id: u64` | `buyer: Address`, `total_value: i128` (equals the funded amount) |
| `receipt_submitted` | `Symbol`, `po_id: u64`, `receipt_id: u64` | `supplier: Address` |
| `receipt_settled` | `Symbol`, `po_id: u64`, `receipt_id: u64` | `payout: i128` (value transferred to the supplier, equal to the return value of `accept_receipt_and_settle`) |
| `po_cancelled` | `Symbol`, `po_id: u64` | `refund: i128` (returned to the buyer; `0` when cancelled before funding) |

Events are published only on the success path of the corresponding call.
Soroban invocation atomicity discards events of a failed invocation together
with its state changes, so an observed event always corresponds to a committed
transition.

## PO lifecycle and event order

```
po_created -> po_accepted -> po_funded -> receipt_submitted -> receipt_settled
                  \                \--------------------------> po_cancelled
                   \-> po_cancelled
```

- A PO may emit many `receipt_submitted` / `receipt_settled` pairs; the PO
  closes when all lines are fully accepted (no separate close event).
- `po_cancelled` is only valid from Accepted or Funded status and is terminal.
- Receipt rejection (`reject_receipt`) is not part of this specification yet;
  see [#115](https://github.com/starboytiimz/procuresettle/issues/115).

## Indexer parsing recommendations

1. **Filter by contract ID**, then read `topics[0]` as a `Symbol` to select the
   event type. Ignore unknown names so future events do not break the indexer.
2. **Decode by arity.** `po_*` events have 2 topics; `receipt_*` events have 3.
   `topics[1]` is always `po_id`; `topics[2]`, when present, is `receipt_id`.
   Index `(po_id)` and `(po_id, receipt_id)` for lookups.
3. **Decode data by event type**: tuples for `po_created` and `po_funded`, a
   single `Address` for `po_accepted` / `receipt_submitted`, a single `i128`
   for `receipt_settled` / `po_cancelled`. Treat `i128` as a big integer; do not
   use floating point. Amounts are base units of the PO's token (read the token
   from `get_po`; it is not in the event).
4. **Use ledger order for state.** Order events by `(ledger, transaction
   index, event index)`. A `receipt_settled` for a PO must follow its
   `po_funded`; ignore or flag sequences that violate the lifecycle above.
5. **Reconcile with contract state.** Events are notifications, not the source
   of truth: use `get_po`, `get_receipt` and `get_line` to confirm balances
   (`funded_value`, `paid_value`, `refunded_value`) when accuracy matters.
6. **Handle retention and reorgs.** RPC nodes keep events for a limited
   window; persist events on ingestion and backfill from archives if needed.
   Only treat events from finalized ledgers as final.
7. **Idempotency.** Key stored events by `(tx_hash, event index)` so replays
   and overlapping polling windows do not duplicate rows.
