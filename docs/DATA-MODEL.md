# Data model

This page documents the persistent storage used by the `procuresettle`
contract in [`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs).
Field and variant names match that file; if they diverge, the source is
authoritative.

## Overview

All purchase-order state lives in Soroban **persistent** storage, addressed by
the private `DataKey` enum. The contract keeps no PO data in instance or
temporary storage; instance storage is only touched to renew the contract
instance and code TTL.

```text
Header(po_id)                         -> PurchaseOrder
Line(po_id, line_id)                  -> PoLine          (one entry per PO line)
Receipt(po_id, receipt_id)            -> Receipt
ReceiptLine(po_id, receipt_id, line_id) -> ReceiptLine   (one entry per receipt line)
```

## `DataKey`

`DataKey` is a `#[contracttype]` enum and is not exported by the contract. Its
variants are the persistent keys:

| Variant | Key parts | Value type | Written by |
|---|---|---|---|
| `Header(u64)` | `po_id` | `PurchaseOrder` | `create_po`; updated by `accept_po`, `fund_po`, `accept_receipt_and_settle`, `cancel_po` |
| `Line(u64, u32)` | `po_id`, `line_id` | `PoLine` | `create_po`; `accepted_quantity` updated by `accept_receipt_and_settle` |
| `Receipt(u64, u64)` | `po_id`, `receipt_id` | `Receipt` | `submit_receipt`; status updated by `reject_receipt` and `accept_receipt_and_settle` |
| `ReceiptLine(u64, u64, u32)` | `po_id`, `receipt_id`, `line_id` | `ReceiptLine` | `submit_receipt` (never modified afterwards) |

Identifiers are scoped by PO: `receipt_id` is unique only within its `po_id`,
and `line_id` only within its PO (or receipt). `po_id`, `receipt_id` and
`line_id` must be non-zero.

## Structs

### `PurchaseOrder`

Stored under `Header(po_id)`.

| Field | Type | Description |
|---|---|---|
| `po_id` | `u64` | PO identifier (non-zero). |
| `buyer` | `Address` | Creates and funds the PO; authorizes receipt acceptance/rejection. |
| `supplier` | `Address` | Accepts the PO and submits receipts; receives settlement payments. Must differ from `buyer`. |
| `token` | `Address` | Token contract used for funding, payouts and refunds. |
| `status` | `PoStatus` | `Draft`, `Accepted`, `Funded`, `Closed` or `Cancelled`. |
| `total_value` | `i128` | Derived at creation as the sum of `ordered_quantity * unit_price` over all lines, in token base units. Always positive. |
| `funded_value` | `i128` | `0` until `fund_po` transfers the entire `total_value` into the contract, then equal to `total_value`. |
| `paid_value` | `i128` | Sum of settled receipt values paid to the supplier. Equals the value of all `accepted_quantity` across lines. |
| `refunded_value` | `i128` | Value returned to the buyer by mutual cancellation (`funded_value - paid_value` at cancel time). |
| `line_count` | `u32` | Number of lines (1 to `MAX_LINES`, currently 8). |
| `line_ids` | `Vec<u32>` | Bounded index of the PO's `line_id`s, used to enumerate `Line` entries for closeout, TTL renewal and the accepted-value invariant checks. |

Accounting invariant while funded: `paid_value + refunded_value <= funded_value
== total_value`. A cancelled funded PO ends with
`paid_value + refunded_value == funded_value`.

### `PoLine`

Stored under `Line(po_id, line_id)`.

| Field | Type | Description |
|---|---|---|
| `line_id` | `u32` | Line identifier (non-zero, unique within the PO). |
| `ordered_quantity` | `u64` | Integer quantity ordered (non-zero). Immutable. |
| `unit_price` | `i128` | Positive token base units per whole quantity unit. Immutable. |
| `accepted_quantity` | `u64` | Cumulative quantity already accepted and paid. Starts at `0`, never exceeds `ordered_quantity`. |

Remaining quantity for a line is `ordered_quantity - accepted_quantity`. The PO
closes (`Closed`) when every line has `accepted_quantity == ordered_quantity`.

`LineInput` (`line_id`, `ordered_quantity`, `unit_price`) is the argument type
of `create_po` and is not stored.

### `Receipt`

Stored under `Receipt(po_id, receipt_id)`. It is the supplier's assertion of
delivered quantities.

| Field | Type | Description |
|---|---|---|
| `receipt_id` | `u64` | Receipt identifier (non-zero, unique within the PO). |
| `po_id` | `u64` | Owning PO. |
| `status` | `ReceiptStatus` | `Submitted`, `Rejected` or `Settled`. |
| `line_count` | `u32` | Number of lines in the receipt (1 to the PO's `line_count`). |
| `line_ids` | `Vec<u32>` | Bounded index of the receipt's `line_id`s, used to enumerate `ReceiptLine` entries. |

Status transitions: `Submitted -> Rejected` (buyer, `reject_receipt`) or
`Submitted -> Settled` (buyer, `accept_receipt_and_settle`). `Rejected` and
`Settled` are terminal, and the `receipt_id` stays consumed in both cases.

### `ReceiptLine`

Stored under `ReceiptLine(po_id, receipt_id, line_id)`.

| Field | Type | Description |
|---|---|---|
| `line_id` | `u32` | The PO line this entry refers to. |
| `quantity_delta` | `u64` | Quantity asserted *in this receipt* (an increment, not a running total). Non-zero and at most the line's remaining quantity. |

`ReceiptQuantityInput` (`line_id`, `quantity_delta`) is the argument type of
`submit_receipt` and is not stored.

A receipt's value is `sum(quantity_delta * unit_price)` over its lines, using
the current `PoLine.unit_price`. It is not stored: it is recomputed by
`receipt_value` and `accept_receipt_and_settle`, against the quantities
accepted at that moment (earlier previews are advisory).

## Why lines are separate keys

Soroban charges for reading and deserializing every entry an invocation
touches, and entries have size limits. If the lines were embedded in the
`PurchaseOrder` (or the receipt lines in `Receipt`), every call would pay to
load and decode the entire collection, even calls that only need the header,
such as `accept_po`, `fund_po` or `cancel_po`.

Storing each `PoLine` and `ReceiptLine` as its own entry means:

- Header-only operations deserialize one small struct.
- Receipt submission and settlement only read and write the lines named in the
  receipt, not every PO line.
- Per-invocation work stays bounded by `MAX_LINES` and by the explicit
  `line_ids` index, rather than by an unbounded in-struct collection.

The `line_ids` vectors in `PurchaseOrder` and `Receipt` are the only embedded
collections. They hold `u32` identifiers only and are capped by `MAX_LINES`,
so the contract can enumerate entries without scanning storage.

## TTL

Persistent entries expire unless renewed. Contract calls extend the
instance, the PO header and lines, and, where relevant, the receipt and its
lines, when fewer than `TTL_RENEW_THRESHOLD_LEDGERS` (2,073,601) ledgers
remain, up to `TTL_RENEW_TO_LEDGERS` (2,592,000). This is not permanent
storage: after long inactivity an entry may be archived and must be restored
before use. See [LIMITATIONS.md](LIMITATIONS.md).
