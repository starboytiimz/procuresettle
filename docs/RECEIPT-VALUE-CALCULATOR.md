# Offline receipt settlement calculator

`scripts/calc-receipt-value.py` reproduces the contract's receipt payout
calculation from local JSON files. It needs no network access, Stellar CLI,
server, or third-party package; only Python 3 is required. It does not change
ledger state and is intended for verifying the amount an operator expects from
`receipt_value` or `accept_receipt_and_settle`.

## Run it

```sh
python3 scripts/calc-receipt-value.py --po-file <path-to-po.json> --receipt-file <path-to-receipt.json>
```

Both `--po-file` and `--receipt-file` are required. `--help` prints usage.
A valid calculation prints an itemized table (line ID, optional description,
delta, remaining quantity, unit price, and line payout) followed by
`Total payout` in the same units as the stored unit prices (integer base units
for contract values). Validation or
input errors print `error: ...` to stderr and exit non-zero without printing a
total.

For a quick check with the repository's canonical examples:

```sh
python3 scripts/calc-receipt-value.py \
  --po-file schemas/examples/valid-po.json \
  --receipt-file schemas/examples/valid-receipt.json
# Total payout: 56
```

## Input files

### PO file

The PO file uses the [`LineInput` array](../schemas/line-input.schema.json) from
`create_po`, or an object with a `lines` array such as the JSON printed by
`scripts/inspect-po.py`. Each line requires:

| Field | Type | Meaning |
| --- | --- | --- |
| `line_id` | integer | Unique positive identifier for the PO line. |
| `ordered_quantity` | integer | Whole quantity units ordered (positive). |
| `unit_price` | integer or string | Positive token base units charged per whole quantity unit. |

Optional fields: `accepted_quantity` (non-negative integer, default `0`) and
`description`/`item` (string, shown in the table). When a `header` object with
`po_id` is present, it must agree with the receipt's `po_id`.

Example (`schemas/examples/valid-po.json`):

```json
[
  { "line_id": 1, "ordered_quantity": 10, "unit_price": "6" },
  { "line_id": 2, "ordered_quantity": 8, "unit_price": "5" }
]
```

Use `scripts/inspect-po.py` output to include current `accepted_quantity`
values for a deployed PO; otherwise the calculator assumes nothing has been
accepted yet.

### Receipt file

The receipt file uses the
[`ReceiptQuantityInput` shape](../schemas/receipt-input.schema.json): an object
with a `quantities` array, optionally with `receipt_id` and `po_id`. Each entry
requires `line_id` (matching a PO line) and `quantity_delta` (positive integer).
An array of quantity objects is also accepted.

Example (`schemas/examples/valid-receipt.json`):

```json
{
  "receipt_id": 1,
  "quantities": [
    { "line_id": 1, "quantity_delta": 6 },
    { "line_id": 2, "quantity_delta": 4 }
  ]
}
```

## Matching, validation, and calculation

- Receipt entries are matched to PO lines by `line_id`. An unmatched line, a
  missing identifier, or a duplicate `line_id` on either side is an error.
- Remaining quantity is `ordered_quantity - accepted_quantity`. A delta larger
  than this remaining amount is rejected, as are non-positive or non-integer
  quantities, non-positive unit prices, inconsistent `po_id` values, more than
  eight lines, missing files, and malformed JSON.
- Each line pays `delta * unit_price`, and the total is the sum of line payouts.
  JSON decimal prices are read with `decimal.Decimal` (never binary floats), so
  no rounding changes the result. Prices should be supplied in the token's
  base units as stored by the contract; see
  [quantities, unit prices and token decimals](DECIMALS.md) for scaling.

The calculation mirrors `calculate_receipt_value` in the contract: it is a
read-only preview and cannot guarantee that another receipt will not consume
the remaining quantity before settlement.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Sample inputs live in `tests/fixtures/` and cover single and multiple lines,
remaining-quantity boundaries, decimal prices, and validation failures.
