# Current limitations and possible future work

This page describes the implemented contract and the evidence currently in
the repository. A possible future direction is not an implemented capability.

## Current limitations

- **Network:** a public Stellar Testnet flagship execution is recorded. There
  is no Mainnet deployment or Mainnet proof. Testnet assets have no monetary
  value and the network may be reset.
- **Delivery:** suppliers submit receipt quantities and buyers accept them.
  The contract does not inspect physical goods, shipping systems, or delivery
  evidence.
- **Disputes and amendments:** there is no dispute arbitration, exception
  resolution, or purchase-order amendment workflow.
- **Financing:** there is no invoice financing or factoring.
- **Purchase-order size:** a purchase order can contain at most eight lines
  (`MAX_LINES`).
- **Numeric model:** quantities are integers. Unit prices, totals, funding,
  payouts, and refunds are integer token base units. There is no decimal
  quantity scale, currency conversion, tax, fee, discount, shipping, quality
  adjustment, or tolerance calculation.
- **Assets:** the contract calls the Soroban token interface. The recorded
  external execution uses a classic Stellar asset wrapped as a Stellar Asset
  Contract. Compatibility with arbitrary custom SEP-41 tokens has not been
  established; issuer behavior and asset policy remain external assumptions.
- **Storage:** active calls renew the contract instance/code and the live PO,
  line, receipt, and receipt-line entries to a bounded target TTL. Renewal
  depends on activity and does not make storage permanent. Long-inactive data
  can be archived and may need normal ledger restoration before access.
- **Cancellation evidence:** joint cancellation and remaining-value refund are
  demonstrated in a protocol-28 standalone local-ledger proof. This is local
  execution evidence, not a public Testnet or Mainnet cancellation proof.
- **External validation:** the Movix exercise checks a pinned source fixture
  and performs a ProcureSettle Testnet experiment using mapped numeric terms.
  It is not a Movix integration, policy implementation, maintainer review,
  endorsement, or adoption.
- **Security:** the repository evidence is not a third-party security audit or
  a production readiness assessment.

## Possible future directions

These are evaluation opportunities, not committed scope:

- Obtain an independent review of contract authorization, token assumptions,
  arithmetic, lifecycle, and TTL behavior.
- With another project's maintainer agreement, validate a narrow settlement
  flow against that project's own independently maintained test fixture or
  test harness. See the proposed request and evidence scope in
  [`docs/EXTERNAL-VALIDATION.md`](EXTERNAL-VALIDATION.md).
- Revisit asset compatibility only with a clearly defined token policy and
  additional execution evidence.
