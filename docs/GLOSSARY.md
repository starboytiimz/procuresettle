# Glossary

Concise definitions of the procurement and Stellar/Soroban terms used across
this repository, in alphabetical order.

**Host Test**
: A Rust test that runs the contract natively against the Soroban SDK's
  in-process host environment, without a network or ledger. Run with
  `cargo test --workspace --locked`. Host tests are distinct from the hosted
  local-ledger proofs, which submit real transactions to a standalone network.

**Line Item**
: One ordered product or service on a Purchase Order, with an ordered quantity
  and a stored unit price. A PO is limited to eight lines. Settlement for a line
  is its newly accepted quantity multiplied by its unit price.

**Milestone Escrow**
: A generic escrow pattern that releases predetermined amounts when milestones
  are marked complete. Payouts are fixed in advance and do not depend on
  delivered quantities. See also *Quantity-Derived Settlement*.

**Partial Settlement**
: A settlement of only part of a PO's value, made when the buyer accepts some,
  but not all, of the ordered quantities. A PO can be settled in several steps;
  it closes automatically once every ordered quantity has been accepted.

**Purchase Order (PO)**
: The buyer's order to a supplier, listing line items, quantities, and unit
  prices. In ProcureSettle the buyer creates the PO, the supplier accepts it,
  and the buyer funds its full value before any receipts are settled.

**Quantity-Derived Settlement**
: ProcureSettle's payout model. Each payment is calculated from the newly
  accepted receipt quantity at the stored unit price, not from a fixed
  amount. The contract rechecks current quantity bounds before transferring
  funds. Contrast with *Milestone Escrow*.

**Receipt**
: The supplier's delivery assertion, listing quantities delivered per line.
  A receipt does not prove physical delivery; it becomes payable only when the
  buyer accepts and settles it.

**Restoration**
: The ledger operation that brings an archived entry back to live state. After
  *State Archival*, an invocation touching the entry requires restoration
  first. See also *TTL*.

**SAC (Stellar Asset Contract)**
: The Soroban contract that wraps a classic Stellar asset and exposes it
  through the Soroban token interface. ProcureSettle's recorded external
  execution uses a SAC for funding and payouts.

**Standalone Network**
: A private, local Stellar network started from scratch, used for local-ledger
  proofs. Transactions sent there never reach Testnet or Mainnet.

**State Archival**
: The Soroban mechanism that removes persistent entries from live ledger state
  once their *TTL* expires. Archived entries are not deleted; they can be
  recovered through *Restoration*.

**Stroop**
: The smallest unit of the native Stellar asset (XLM): 1 XLM = 10,000,000
  stroops. Settlement values in ProcureSettle use the selected token's integer
  base units, with no decimal or currency conversion layer.

**TTL (Time-To-Live)**
: The number of ledgers an entry stays live before it can be archived.
  Active contract calls extend the TTL of the contract instance/code and the
  relevant PO, line, receipt, and receipt-line entries. This is a bounded
  renewal, not permanent storage.
