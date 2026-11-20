# Worked example: multi-line partial fulfillment

This walkthrough follows one purchase order (PO) with three lines through three
partial receipts. All amounts are integer token base units; there is no
decimal, tax, fee, or discount layer. The same numbers are asserted by the host
test `worked_example_three_lines_three_partial_receipts` in
[`contracts/po-settlement/src/test.rs`](../contracts/po-settlement/src/test.rs).

## Contract formulas

For each line `l`, with `unit_price(l)` and `ordered_quantity(l)` fixed at PO
creation, and `accepted_quantity(l)` starting at 0:

```text
line_value(l)       = quantity * unit_price(l)
total_value         = sum(ordered_quantity(l) * unit_price(l))
settlement(receipt) = sum(quantity_delta(l) * unit_price(l))      over lines in the receipt
paid_value'         = paid_value + settlement(receipt)
accepted_quantity'  = accepted_quantity + quantity_delta          per line
remaining_quantity  = ordered_quantity - accepted_quantity
escrow remaining    = funded_value - paid_value - refunded_value
```

Invariants checked on every settlement: `quantity_delta <= remaining_quantity`,
`paid_value == sum(accepted_quantity(l) * unit_price(l))`, and
`paid_value <= funded_value`. The PO becomes `Closed` automatically when every
line has `accepted_quantity == ordered_quantity`.

## Scenario setup

| Line | Item   | Ordered qty | Unit price | Line value |
|-----:|--------|------------:|-----------:|-----------:|
| 1    | Cement | 100         | 5          | 500        |
| 2    | Steel  | 40          | 25         | 1,000      |
| 3    | Timber | 60          | 10         | 600        |
|      | **Total** |          |            | **2,100**  |

`total_value = 100*5 + 40*25 + 60*10 = 500 + 1,000 + 600 = 2,100`.

The buyer starts with 10,000 tokens; the supplier and the contract start with 0.

## Step 0: create, accept, fund

The buyer creates the PO, the supplier accepts it, and the buyer funds the exact
stored total (2,100) into the contract.

| Holder   | Before | Change  | After  |
|----------|-------:|--------:|-------:|
| Buyer    | 10,000 | -2,100  | 7,900  |
| Contract | 0      | +2,100  | 2,100  |
| Supplier | 0      | 0       | 0      |

PO state: `Funded`, `funded_value = 2,100`, `paid_value = 0`.

## Step 1: Receipt 1, partial Cement and Steel

The supplier submits Cement 60 and Steel 40. The buyer accepts and settles.

| Line | Delta | Remaining before | Unit price | Value |
|-----:|------:|-----------------:|-----------:|------:|
| 1 Cement | 60 | 100 | 5  | 300   |
| 2 Steel  | 40 | 40  | 25 | 1,000 |

`settlement 1 = 60*5 + 40*25 = 300 + 1,000 = 1,300`

| Line | Accepted after | Remaining after |
|-----:|---------------:|----------------:|
| 1 Cement | 60 | 40 |
| 2 Steel  | 40 | 0  |
| 3 Timber | 0  | 60 |

Check: `paid_value = 1,300 = 60*5 + 40*25 + 0*10`. The PO stays `Funded`.

| Holder   | Before | Change  | After  |
|----------|-------:|--------:|-------:|
| Buyer    | 7,900  | 0       | 7,900  |
| Contract | 2,100  | -1,300  | 800    |
| Supplier | 0      | +1,300  | 1,300  |

## Step 2: Receipt 2, balance of Cement and partial Timber

The supplier submits Cement 40 (the balance) and Timber 25.

| Line | Delta | Remaining before | Unit price | Value |
|-----:|------:|-----------------:|-----------:|------:|
| 1 Cement | 40 | 40 | 5  | 200 |
| 3 Timber | 25 | 60 | 10 | 250 |

`settlement 2 = 40*5 + 25*10 = 200 + 250 = 450`

| Line | Accepted after | Remaining after |
|-----:|---------------:|----------------:|
| 1 Cement | 100 | 0  |
| 2 Steel  | 40  | 0  |
| 3 Timber | 25  | 35 |

Check: `paid_value = 1,300 + 450 = 1,750 = 100*5 + 40*25 + 25*10`. The PO stays
`Funded`; escrow remaining is `2,100 - 1,750 = 350`.

| Holder   | Before | Change | After |
|----------|-------:|-------:|------:|
| Buyer    | 7,900  | 0      | 7,900 |
| Contract | 800    | -450   | 350   |
| Supplier | 1,300  | +450   | 1,750 |

## Step 3: Receipt 3, final Timber and automatic closeout

The supplier submits Timber 35, exactly the remaining quantity.

`settlement 3 = 35*10 = 350`

Check: `paid_value = 1,750 + 350 = 2,100 = total_value`, and every line now has
`accepted_quantity == ordered_quantity`, so the contract sets the PO status to
`Closed` in the same call. No refund is due: `refunded_value = 0` and the
remaining escrow is `2,100 - 2,100 - 0 = 0`.

| Holder   | Before | Change | After  |
|----------|-------:|-------:|-------:|
| Buyer    | 7,900  | 0      | 7,900  |
| Contract | 350    | -350   | 0      |
| Supplier | 1,750  | +350   | 2,100  |

## Ledger summary

| Step | Event | Settlement | Buyer | Contract | Supplier | PO status |
|-----:|-------|-----------:|------:|---------:|---------:|-----------|
| 0 | Fund 2,100 | n/a   | 7,900 | 2,100 | 0     | Funded |
| 1 | Receipt 1  | 1,300 | 7,900 | 800   | 1,300 | Funded |
| 2 | Receipt 2  | 450   | 7,900 | 350   | 1,750 | Funded |
| 3 | Receipt 3  | 350   | 7,900 | 0     | 2,100 | Closed |

Token conservation holds at every step: `buyer + contract + supplier = 10,000`.
The sum of settlements is `1,300 + 450 + 350 = 2,100 = total_value`.

## Boundary behavior

- A receipt line whose `quantity_delta` exceeds the remaining quantity at
  settlement time fails with `QuantityExceedsRemaining`. For example, if
  Receipt 3 had asked for Timber 36, it would fail and no state would change.
- Settlement uses the quantities accepted at the time of settlement, not at the
  time of submission, so a stale preview from `receipt_value` is advisory only.
- A cancelled PO is not part of this scenario; see
  [`docs/EVIDENCE.md`](EVIDENCE.md) for the cancellation and refund proof.
