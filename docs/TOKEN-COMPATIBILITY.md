# Token compatibility

ProcureSettle uses the Soroban token interface rather than reimplementing token
balances or transfer logic. The contract creates a token client for the
configured PO token with:

```rust
token::TokenClient::new(&env, &token_address)
```

The recorded evidence uses a classic Stellar asset wrapped in a Stellar Asset
Contract (SAC). Custom token behavior has not been established to the same
extent.

## Transfer authorization

The contract requires authorization from the relevant party before changing PO
state:

- Funding requires the recorded buyer's authorization and transfers the exact
  stored PO total from the buyer to the contract.
- Settlement requires the buyer's authorization and transfers the settled base
  units from the contract to the supplier.
- Mutual cancellation requires both parties and refunds the remaining funded
  value to the buyer.

The external token contract also enforces its own allowances, balances,
authorization, and transfer rules. A transfer failure rolls back the invocation
and all PO state changes made before it.

## SAC and custom SEP-41 contracts

SAC provides the Soroban interface for a classic Stellar asset. It inherits the
classic asset's issuer and account-policy behavior.

A custom contract that implements SEP-41 or the compatible Soroban token interface
may support the same `balance`, `transfer`, and other client calls, but the
contract may define different administrative behavior and failure conditions.
ProcureSettle does not inspect or assume issuer-specific behavior outside the
token interface.

Before using a custom token, deployment operators should verify and document:

- Interface compatibility and event behavior.
- Transfer and allowance semantics.
- Administrative mint, burn, pause, upgrade, and authorization behavior.
- Reversion behavior on failed transfers.

## Decimals and base unit accounting

ProcureSettle stores quantities and unit prices as integers. Its
`PurchaseOrder.total_value`, funded value, paid value, and refunded value are
positive token base units. The contract does not read or convert token decimals.

Integrations must convert human-readable amounts to the token's base-unit scale
before invoking the contract and convert base units back for display. In
particular, an amount that is exact in one decimal asset may not be representable
for another asset. Mismatched decimal assumptions can change transferred values
or prevent settlement.

## External risk factors

The following external token behaviors are outside ProcureSettle's control:

- Clawback or forced transfer behavior.
- Frozen or blocked accounts.
- Administrative pause or deauthorization.
- Asset issuer policy and issuer deauthorization.
- Custom-contract upgrade, reentrancy, callback, or accounting defects.
- Transfer hooks or fees that reduce or alter the amount received.

These risks and the repository's broader external assumptions are also
summarized in [`LIMITATIONS.md`](LIMITATIONS.md). Production use of a token
requires independent validation of the token implementation and issuer policy.
