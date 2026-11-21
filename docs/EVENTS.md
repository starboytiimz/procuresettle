# Soroban contract events

Indexers can subscribe to these contract events to follow the purchase-order
lifecycle. Each event is emitted only after its corresponding contract call has
completed its validation and state changes.

## `po_funded`

Published by `fund_po` after the exact stored total has been transferred into
the contract and the PO header has been persisted as funded.

- Topics: `("po_funded", po_id)`
- Data: `(buyer, total_value)`

| Field         | Type      | Description                                     |
| ------------- | --------- | ----------------------------------------------- |
| `po_id`       | `u64`     | Identifier of the funded purchase order.        |
| `buyer`       | `Address` | Buyer recorded on the purchase order.           |
| `total_value` | `i128`    | Value transferred, in positive token base units. |

## `receipt_submitted`

Published by `submit_receipt` after the supplier assertion and its receipt lines
have been persisted.

- Topics: `("receipt_submitted", po_id, receipt_id)`
- Data: `supplier`

| Field        | Type      | Description                                       |
| ------------ | --------- | ------------------------------------------------- |
| `po_id`      | `u64`     | Identifier of the funded purchase order.          |
| `receipt_id` | `u64`     | Identifier of the newly submitted receipt.        |
| `supplier`   | `Address` | Supplier recorded on the purchase order.          |
