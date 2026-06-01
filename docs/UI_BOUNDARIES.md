# UI Boundaries

The current product remains a single-page vanilla JavaScript app. The near-term goal is to keep the same user workflows while shrinking `js/app.js` into orchestration code.

## Current Entry Points

- `index.html` loads compatibility modules from `js/modules/` before `js/app.js`.
- `js/app.js` still owns page orchestration, event binding, rendering, and many legacy calculation functions.
- The module files expose browser globals and CommonJS exports for tests.

## Module Ownership

- `js/modules/configPolicy.js`
  - Default trust configs.
  - Annual PD to monthly PD conversion.
  - Senior repayment default lookup.

- `js/modules/assetSchedule.js`
  - Asset type helpers.
  - Period normalization.
  - Future recoverable schedule.
  - Unified asset discount/pool contribution helpers.

- `js/modules/cashflowCore.js`
  - Pure fixture-level detailed cashflow calculation.
  - Used by executable tests to compare against the browser calculation behavior.

- `js/modules/exportAudit.js`
  - Formula audit row builders.
  - Excel sheet name quoting.

- `js/modules/apiClient.js`
  - Model-aware query builder.
  - Batch import normalization.
  - Model delete endpoint wrapper.

## UI Rule

Do not change button ids, visible workflow order, or export filenames unless a product requirement explicitly asks for it. Refactors should first add tests, then migrate internals behind the current UI.

