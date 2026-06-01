# Current Calculation Policy

This document records the current business calculation policy used by the cashflow system. It is intended to stay aligned with `js/app.js` and the executable tests under `tests/`.

## Asset Schedule

- `total_deduction` is the total deduction amount for the asset.
- `deducted_amount` is cash already deducted before the projection start.
- `deducted_amount` is included in the first projection period.
- Future recoverable cashflow is `max(total_deduction - deducted_amount, 0)`.
- Future recoverable cashflow is spread over `remaining_periods`.
- Empty and zero values are treated the same for numeric cashflow fields.

## Asset Types and Discounts

- Full asset: `整装` / `整装资产`.
- Partial asset: `局装` / `局装资产`.
- Full asset pool contribution uses the unified full discount rate.
- Partial asset pool contribution uses the unified partial discount rate.
- Partial asset discount no longer depends on remaining period buckets.

## Risk and Fees

- PD inputs are annualized PD values.
- Monthly equivalent PD is calculated as:

```text
monthly_pd = 1 - (1 - annual_pd)^(1/12)
```

- LGD is applied after default.
- Net asset inflow is after risk and fee adjustments.
- Trust waterfall analysis uses net asset inflow, not pre-risk gross collection.
- Recovery tail amounts can appear after the main projection window and should be disclosed instead of silently ignored.

## Funding and Amortization

- Holding-pool default senior repayment quarters: 8.
- Circulation-pool default senior repayment quarters: 20.
- Fixed amortization uses the configured senior repayment quarter count.
- Defaults should be read from `DEFAULT_TRUST_CONFIGS` or `js/modules/configPolicy.js`.

## Export and Report Tie-out

- Excel exports should include a summary formula audit sheet where applicable.
- Primary calculation exports should include row-level formula audit sheets.
- Word/report wording should match the current policy:
  - annualized PD, not `PD / 12`;
  - first-period deducted amount;
  - net asset inflow after risk and fees;
  - unified full/partial discount rates.

