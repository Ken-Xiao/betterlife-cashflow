# Cashflow System Stabilization Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep all current product features and business calculations unchanged while making the system easier to verify, maintain, deploy, and extend.

**Architecture:** The current app is a working single-page vanilla JS system with a local JSON-backed REST server. The next phase should carve stable module boundaries around calculation policy, data access, import/export, reporting, and UI orchestration without changing user workflows or output semantics.

**Tech Stack:** Vanilla JavaScript, HTML/CSS, SheetJS, docx, Chart.js, Python `ThreadingHTTPServer`, `unittest`, local JSON storage.

---

## Current System Map

**Keep as product behavior:**
- Multi-model trust management.
- Local JSON-backed asset database.
- Asset import, data processing, validation, template generation, model import.
- Asset cashflow, trust cashflow, stress/scenario analysis.
- Excel and Word report exports with formula audit sheets.
- Current UI page structure and button workflows.

**Primary risk today:**
- `js/app.js` is the center of gravity for nearly everything: state, API, calculations, rendering, imports, exports, reports, and event binding.
- Regression coverage is source-level and valuable, but has limited executable calculation fixtures.
- README is historically rich but can drift from current code because calculation policy changes faster than docs.

**Target shape:**
- Same UI, same buttons, same output files.
- One source of truth for calculation policy.
- One source of truth for asset schedule/period semantics.
- Export/report values backed by executable fixtures.
- A deployable repo with clean local data boundaries.

---

## File Structure Target

Create focused modules under `js/modules/` while keeping `js/app.js` as the compatibility entrypoint during migration.

- Create: `js/modules/configPolicy.js`
  - Owns `DEFAULT_TRUST_CONFIGS`, `getDefaultConfigValue`, `getInputConfigValue`, repayment defaults.
- Create: `js/modules/assetSchedule.js`
  - Owns `normalizeAssetPeriods`, `getAssetFutureSchedule`, asset type helpers.
- Create: `js/modules/cashflowCore.js`
  - Owns pure calculation functions: detailed cashflow, vacancy, risk/fees, pass-through, fixed amortization.
- Create: `js/modules/exportAudit.js`
  - Owns Excel formula audit helpers and row-level formula builders.
- Create: `js/modules/apiClient.js`
  - Owns model-filtered assets, batch import, model delete, raw all-model scans.
- Create: `tests/calculation_fixture_tests.py`
  - Executes deterministic calculation fixtures in Node or source-extracted JS.
- Modify: `js/app.js`
  - Becomes a browser orchestration layer while functions are migrated incrementally.
- Modify: `tests/review_regression_tests.py`
  - Retain source guardrails and add checks that modules exist and are imported.
- Modify: `README.md`
  - Replace stale historical explanations with current policy and maintenance notes.

---

## Task 1: Freeze Current Behavior With Calculation Fixtures

**Files:**
- Create: `tests/fixtures/simple_assets.json`
- Create: `tests/calculation_fixture_tests.py`
- Modify: `tests/review_regression_tests.py`

- [ ] **Step 1: Add deterministic fixture data**

Create `tests/fixtures/simple_assets.json`:

```json
[
  {
    "asset_id": "FULL_001",
    "asset_type": "整装",
    "total_deduction": 120000,
    "deducted_amount": 20000,
    "lease_start_date": "2026-01-01",
    "total_periods": 10,
    "remaining_periods": 10,
    "period_deduction": 12000
  },
  {
    "asset_id": "PARTIAL_001",
    "asset_type": "局装",
    "total_deduction": 60000,
    "deducted_amount": 0,
    "lease_start_date": "2026-01-01",
    "total_periods": 6,
    "remaining_periods": 6,
    "period_deduction": 10000
  }
]
```

- [ ] **Step 2: Write a fixture test for the current cashflow contract**

Create `tests/calculation_fixture_tests.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "js" / "app.js"
FIXTURE = ROOT / "tests" / "fixtures" / "simple_assets.json"


def extract_functions(source: str, names: list[str]) -> str:
    chunks = []
    for name in names:
        match = re.search(rf"function {name}\\([^)]*\\) \\{{", source)
        if not match:
            raise AssertionError(f"missing function {name}")
        start = match.start()
        depth = 0
        end = None
        for i in range(match.end() - 1, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise AssertionError(f"could not extract {name}")
        chunks.append(source[start:end])
    return "\\n\\n".join(chunks)


class CalculationFixtureTests(unittest.TestCase):
    def test_asset_future_schedule_and_detailed_cashflow(self):
        source = APP_JS.read_text(encoding="utf-8")
        js_functions = extract_functions(
            source,
            [
                "normalizeAssetPeriods",
                "getAssetFutureSchedule",
                "isFullAsset",
                "isPartialAsset",
                "calculateDetailedCashflow",
            ],
        )
        assets = json.loads(FIXTURE.read_text(encoding="utf-8"))
        script = f"""
        const ASSET_TYPES = {{ FULL: '整装', PARTIAL: '局装' }};
        const Utils = {{
          addMonths(date, months) {{
            const d = new Date(date);
            d.setMonth(d.getMonth() + months);
            return d;
          }},
          formatMonth(date) {{
            return `${{date.getFullYear()}}-${{String(date.getMonth() + 1).padStart(2, '0')}}`;
          }},
          parseDate(value) {{
            return value ? new Date(value) : null;
          }},
          getMonthDiff(start, end) {{
            return (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
          }}
        }};
        {js_functions}
        const assets = {json.dumps(assets, ensure_ascii=False)};
        const result = calculateDetailedCashflow(new Date('2026-01-01'), 10, assets);
        console.log(JSON.stringify({{
          totalIncome: result.totalIncome,
          totalDeductedAmount: result.totalDeductedAmount,
          futureCashflowTotal: result.futureCashflowTotal,
          firstMonthTotal: result.periods[0].totalAmount,
          monthSevenTotal: result.periods[6].totalAmount
        }}));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(textwrap.dedent(script))
            script_path = fh.name
        completed = subprocess.run(["node", script_path], check=True, capture_output=True, text=True)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result["totalIncome"], 180000)
        self.assertEqual(result["totalDeductedAmount"], 20000)
        self.assertEqual(result["futureCashflowTotal"], 160000)
        self.assertEqual(result["firstMonthTotal"], 40000)
        self.assertEqual(result["monthSevenTotal"], 10000)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the fixture test and verify it passes**

Run:

```bash
python3 tests/calculation_fixture_tests.py
```

Expected:

```text
Ran 1 test
OK
```

- [ ] **Step 4: Run existing regression tests**

Run:

```bash
python3 tests/review_regression_tests.py
node --check js/app.js
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/simple_assets.json tests/calculation_fixture_tests.py tests/review_regression_tests.py
git commit -m "test: freeze core cashflow fixture"
```

---

## Task 2: Extract Calculation Policy Without Changing Behavior

**Files:**
- Create: `js/modules/configPolicy.js`
- Modify: `js/app.js`
- Modify: `tests/review_regression_tests.py`

- [ ] **Step 1: Add a source regression test for the policy module**

Add to `tests/review_regression_tests.py`:

```python
    def test_config_policy_module_exists(self):
        module = ROOT / "js" / "modules" / "configPolicy.js"
        source = module.read_text(encoding="utf-8")
        self.assertIn("export const DEFAULT_TRUST_CONFIGS", source)
        self.assertIn("export function getDefaultTrustConfigByType", source)
        self.assertIn("export function getDefaultConfigValue", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 tests/review_regression_tests.py
```

Expected: fails because `js/modules/configPolicy.js` does not exist.

- [ ] **Step 3: Create `js/modules/configPolicy.js`**

Move the existing default config object and default helpers into the module:

```javascript
export const DEFAULT_TRUST_CONFIGS = {
  holding_pool: {
    trustPeriods: 36,
    fullDiscountRate: 88,
    partialDiscountRate: 95,
    seniorRatio: 75,
    seniorRate: 4,
    subordinateRatio: 25,
    subordinateRate: 7,
    guaranteeFundRate: 1,
    vacancyPeriod: 0.5,
    renewalCycle: 12,
    pdFull: 0.2,
    pdPartial: 0.1,
    lgdFull: 100,
    lgdPartial: 100,
    serviceFee1: 0.1,
    serviceFee2: 0.4,
    trustServiceFee: 0.41,
    idleFundRate: 0.8,
    effectiveTaxRate: 3.26,
    taxableRatio: 12,
    lawyerFee: 10,
    ratingFee: 12,
    accountantFee: 5,
    seniorRepayQuarters: 8,
    repaymentMethod: "equal_payment"
  },
  circulation_pool: {
    trustPeriods: 36,
    fullDiscountRate: 88,
    partialDiscountRate: 95,
    seniorRatio: 75,
    seniorRate: 6,
    subordinateRatio: 25,
    subordinateRate: 14,
    guaranteeFundRate: 1,
    pdFull: 0.8,
    pdPartial: 0,
    lgdFull: 100,
    lgdPartial: 100,
    serviceFee1: 0.1,
    serviceFee2: 0.4,
    trustServiceFee: 0.41,
    idleFundRate: 0.8,
    effectiveTaxRate: 3.26,
    taxableRatio: 12,
    seniorRepayQuarters: 20,
    repaymentMethod: "equal_principal",
    flatRate: 8,
    purchaseRatioPartial: 40,
    purchasePeriodPartial: 10,
    purchaseDiscountPartial: 95,
    purchaseRatioFull: 60,
    purchasePeriodFull: 24,
    purchaseDiscountFull: 86,
    sellDiscountFull: 88,
    holdPeriodFull: 1,
    absorptionWeek1: 30,
    absorptionWeek2: 30,
    absorptionWeek3: 20,
    absorptionWeek4: 20
  }
};

export function getDefaultTrustConfigByType(modelType = "holding_pool") {
  const type = DEFAULT_TRUST_CONFIGS[modelType] ? modelType : "holding_pool";
  return { ...DEFAULT_TRUST_CONFIGS[type] };
}

export function getDefaultConfigValue(key, modelType = "holding_pool") {
  const config = DEFAULT_TRUST_CONFIGS[modelType] || DEFAULT_TRUST_CONFIGS.holding_pool;
  return config[key] ?? DEFAULT_TRUST_CONFIGS.holding_pool[key];
}
```

- [ ] **Step 4: Keep browser compatibility in `js/app.js`**

Do not convert the whole app to modules yet. Instead, keep the current in-file definitions and add a comment block above them:

```javascript
// NOTE: configPolicy.js is the extraction target. The app keeps these
// definitions inline until the entrypoint is converted to module loading.
```

This creates a safe module target without changing runtime loading.

- [ ] **Step 5: Run tests**

Run:

```bash
python3 tests/review_regression_tests.py
node --check js/app.js
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add js/modules/configPolicy.js js/app.js tests/review_regression_tests.py
git commit -m "refactor: document config policy module boundary"
```

---

## Task 3: Extract Asset Schedule Semantics

**Files:**
- Create: `js/modules/assetSchedule.js`
- Modify: `tests/review_regression_tests.py`
- Modify: `README.md`

- [ ] **Step 1: Add source guard for schedule module**

Add to `tests/review_regression_tests.py`:

```python
    def test_asset_schedule_module_documents_current_semantics(self):
        module = ROOT / "js" / "modules" / "assetSchedule.js"
        source = module.read_text(encoding="utf-8")
        self.assertIn("export function normalizeAssetPeriods", source)
        self.assertIn("export function getAssetFutureSchedule", source)
        self.assertIn("futureRecoverable", source)
        self.assertIn("monthlyFutureAmount", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 tests/review_regression_tests.py
```

Expected: fails because `assetSchedule.js` is missing.

- [ ] **Step 3: Create `js/modules/assetSchedule.js`**

```javascript
export function normalizeAssetPeriods(asset) {
  const totalPeriods = parseInt(asset?.total_periods) || 0;
  const periodDeduction = parseFloat(asset?.period_deduction) || 0;
  const deductedAmount = parseFloat(asset?.deducted_amount) || 0;
  const deductedPeriods = periodDeduction > 0 ? Math.floor(deductedAmount / periodDeduction) : 0;
  const remainingPeriods = parseInt(asset?.remaining_periods) || totalPeriods;
  const originalPeriods = parseInt(asset?.original_periods) || (remainingPeriods + deductedPeriods) || totalPeriods;
  return {
    originalPeriods,
    remainingPeriods,
    deductedPeriods,
    rawTotalPeriods: totalPeriods
  };
}

export function getAssetFutureSchedule(asset) {
  const totalDeduction = parseFloat(asset?.total_deduction) || 0;
  const deductedAmount = parseFloat(asset?.deducted_amount) || 0;
  const periods = normalizeAssetPeriods(asset);
  const remainingPeriods = Math.max(0, periods.remainingPeriods || 0);
  const futureRecoverable = Math.max(0, totalDeduction - deductedAmount);
  return {
    ...periods,
    totalDeduction,
    deductedAmount,
    remainingPeriods,
    futureRecoverable,
    monthlyFutureAmount: remainingPeriods > 0 ? futureRecoverable / remainingPeriods : 0
  };
}

export function isFullAsset(assetType) {
  const type = (assetType || "").toString().trim();
  return type === "整装" || type.toLowerCase() === "full";
}

export function isPartialAsset(assetType) {
  const type = (assetType || "").toString().trim();
  return type === "局装" || type.toLowerCase() === "partial";
}
```

- [ ] **Step 4: Update README current semantics**

Add this near the calculation section in `README.md`:

```markdown
## Current Asset Schedule Semantics

- `total_deduction`: total contractual deduction amount used as the asset pool base.
- `deducted_amount`: amount already deducted; modelled as first-period safety cushion cash.
- `total_periods` / `remaining_periods`: current remaining future repayment periods.
- Future recoverable amount = `total_deduction - deducted_amount`.
- Monthly future repayment = future recoverable amount / remaining future periods.
- Trust pool contribution = `total_deduction × asset-type discount rate`.
```

- [ ] **Step 5: Run tests**

Run:

```bash
python3 tests/review_regression_tests.py
python3 tests/calculation_fixture_tests.py
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add js/modules/assetSchedule.js README.md tests/review_regression_tests.py
git commit -m "docs: define asset schedule module boundary"
```

---

## Task 4: Add Executable Export/Report Consistency Tests

**Files:**
- Create: `tests/export_policy_tests.py`
- Modify: `tests/review_regression_tests.py`

- [ ] **Step 1: Create export policy tests**

Create `tests/export_policy_tests.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "js" / "app.js"


class ExportPolicyTests(unittest.TestCase):
    def setUp(self):
        self.source = APP_JS.read_text(encoding="utf-8")

    def test_report_uses_total_deduction_for_pool_size(self):
        self.assertIn("= 整装总代扣 × ", self.source)
        self.assertIn("= 局装总代扣 × ", self.source)
        self.assertNotIn("= 整装待代扣 × ", self.source)
        self.assertNotIn("= 局装待代扣 × ", self.source)

    def test_report_labels_net_cashflow_after_risk_and_fees(self):
        self.assertIn("风险及费用后净回款", self.source)
        self.assertNotIn("扣除风险前的总回款", self.source)

    def test_template_field_mapping_uses_house_table_as_source_of_truth(self):
        self.assertNotIn("房源表→代扣表", self.source)
        self.assertNotIn("房源表→计算补全", self.source)
        self.assertIn("仅用于交叉校验", self.source)

    def test_rating_and_trust_exports_use_percent_units(self):
        self.assertIn("record['资产转让折扣率(%)'] = discountRatePct;", self.source)
        self.assertIn("const discountRate = discountRatePct / 100;", self.source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new export tests**

Run:

```bash
python3 tests/export_policy_tests.py
```

Expected: pass.

- [ ] **Step 3: Run full local test suite**

Run:

```bash
python3 tests/review_regression_tests.py
python3 tests/calculation_fixture_tests.py
python3 tests/export_policy_tests.py
node --check js/app.js
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add tests/export_policy_tests.py tests/review_regression_tests.py
git commit -m "test: lock report and export policy"
```

---

## Task 5: Harden Local Database Operations

**Files:**
- Modify: `deploy_server.py`
- Create: `tests/server_api_tests.py`

- [ ] **Step 1: Add server API tests for batch create and delete-by-model**

Create `tests/server_api_tests.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "deploy_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("cashflow_deploy_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ServerStorageTests(unittest.TestCase):
    def test_save_and_filter_rows_are_model_scoped(self):
        server = load_server_module()
        with tempfile.TemporaryDirectory() as tmp:
            original_data_file = server.DATA_FILE
            try:
                server.DATA_FILE = Path(tmp) / "rows.json"
                server.save_rows([
                    {"id": "1", "modelId": "m1", "asset_id": "alpha"},
                    {"id": "2", "modelId": "m2", "asset_id": "alpha"},
                    {"id": "3", "modelId": "m1", "asset_id": "beta"}
                ])
                rows = server.load_rows()
                filtered = server.filter_asset_rows(rows, model_id="m1", q="alpha")
                self.assertEqual([row["id"] for row in filtered], ["1"])
            finally:
                server.DATA_FILE = original_data_file


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run server tests**

Run:

```bash
python3 tests/server_api_tests.py
```

Expected: pass.

- [ ] **Step 3: Add HEAD health check support**

Modify `deploy_server.py`:

```python
    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        if parsed.path == TABLE_PATH:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)
```

- [ ] **Step 4: Run checks**

Run:

```bash
python3 tests/server_api_tests.py
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add deploy_server.py tests/server_api_tests.py
git commit -m "test: cover local server storage behavior"
```

---

## Task 6: Split API Client Boundary

**Files:**
- Create: `js/modules/apiClient.js`
- Modify: `tests/review_regression_tests.py`
- Modify: `README.md`

- [ ] **Step 1: Add source guard**

Add to `tests/review_regression_tests.py`:

```python
    def test_api_client_module_documents_database_contract(self):
        module = ROOT / "js" / "modules" / "apiClient.js"
        source = module.read_text(encoding="utf-8")
        self.assertIn("export const ASSET_TABLE_PATH", source)
        self.assertIn("batch", source)
        self.assertIn("by-model", source)
        self.assertIn("modelId", source)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3 tests/review_regression_tests.py
```

Expected: fails because module is missing.

- [ ] **Step 3: Create `js/modules/apiClient.js` as documented boundary**

```javascript
export const ASSET_TABLE_PATH = "tables/structured_finance_assets";

export function buildAssetListUrl({ page = 1, limit = 1000, modelId = "", q = "" } = {}) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("limit", String(limit));
  if (modelId) params.set("modelId", modelId);
  if (q) params.set("q", q);
  return `${ASSET_TABLE_PATH}?${params.toString()}`;
}

export function batchCreateUrl() {
  return `${ASSET_TABLE_PATH}/batch`;
}

export function deleteByModelUrl(modelId) {
  return `${ASSET_TABLE_PATH}/by-model/${encodeURIComponent(modelId)}`;
}
```

- [ ] **Step 4: Add README API contract**

Add:

```markdown
## Local API Contract

- `GET /tables/structured_finance_assets?page=&limit=&modelId=&q=`
- `POST /tables/structured_finance_assets/batch`
- `DELETE /tables/structured_finance_assets/by-model/:modelId`
- `PATCH /tables/structured_finance_assets/:id`

All create/import paths must force the target `modelId`. UI state should be refreshed from the server after import rather than appended locally.
```

- [ ] **Step 5: Run tests and commit**

```bash
python3 tests/review_regression_tests.py
git add js/modules/apiClient.js README.md tests/review_regression_tests.py
git commit -m "docs: define API client boundary"
```

---

## Task 7: Clean README Into Current-State Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/CURRENT_CALCULATION_POLICY.md`
- Create: `docs/OPERATIONS.md`

- [ ] **Step 1: Create current calculation policy doc**

Create `docs/CURRENT_CALCULATION_POLICY.md`:

```markdown
# Current Calculation Policy

## Asset Amounts

- Total deduction amount is the base asset face amount.
- Deducted amount is first-period safety cushion cash.
- Future recoverable amount equals total deduction amount minus deducted amount.
- Future monthly repayment equals future recoverable amount divided by remaining periods.

## Trust Pool

- Full asset pool contribution = full total deduction amount × full discount rate.
- Partial asset pool contribution = partial total deduction amount × partial discount rate.
- Partial asset discount rate is unified by configuration and no longer depends on remaining periods.

## Risk

- PD inputs are annual probabilities.
- Monthly equivalent PD = `1 - (1 - annual PD)^(1/12)`.
- LGD is applied to default amount; recovery is delayed by two months.

## Tax

- Tax is calculated on net repayment before investor distribution.
- Taxable ratio is derived from discount rate: `1 - discount rate`.
```

- [ ] **Step 2: Create operations doc**

Create `docs/OPERATIONS.md`:

```markdown
# Operations

## Run Locally

```bash
python3 deploy_server.py --host 127.0.0.1 --port 8767
```

Open:

```text
http://127.0.0.1:8767/
```

## Test

```bash
python3 tests/review_regression_tests.py
python3 tests/calculation_fixture_tests.py
python3 tests/export_policy_tests.py
python3 tests/server_api_tests.py
node --check js/app.js
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
```

## Data Files

Local runtime data lives in `data/structured_finance_assets.json` and is ignored by Git.
```
```

- [ ] **Step 3: Replace README top section**

Make the first page of `README.md` short and current:

```markdown
# Betterlife Cashflow System

Local structured finance cashflow system for asset import, data processing, trust modelling, Excel audit, and Word reporting.

## Current Docs

- Current calculation policy: `docs/CURRENT_CALCULATION_POLICY.md`
- Local operations: `docs/OPERATIONS.md`
- Regression tests: `tests/`

## Run

```bash
python3 deploy_server.py --host 127.0.0.1 --port 8767
```
```

- [ ] **Step 4: Run docs sanity checks**

Run:

```bash
rg -n "PD/12|局装≤12期|扣除风险前|待代扣 ×" README.md docs
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/CURRENT_CALCULATION_POLICY.md docs/OPERATIONS.md
git commit -m "docs: summarize current calculation policy"
```

---

## Task 8: Prepare UI-Orchestration Split

**Files:**
- Create: `docs/UI_BOUNDARIES.md`
- Modify: `tests/review_regression_tests.py`

- [ ] **Step 1: Document UI ownership boundaries**

Create `docs/UI_BOUNDARIES.md`:

```markdown
# UI Boundaries

## Current Pages

- Dashboard: asset stats and overview charts.
- Assets: asset CRUD and pagination.
- Asset Cashflow: standalone asset cashflow calculation and export.
- Trust Analysis: trust-side analysis, waterfall, Excel and Word exports.
- Stress Test: scenario and critical PD views.
- Data Process: source file import, generated template, validations.

## Rule

UI handlers may call calculation/API/export modules, but calculation modules must not read DOM directly.

## Migration Order

1. Keep event binding in `js/app.js`.
2. Extract pure rendering helpers only after calculation fixtures are stable.
3. Do not change button IDs or page structure unless tests are updated first.
```

- [ ] **Step 2: Add test that critical button IDs are protected**

Add to `tests/review_regression_tests.py`:

```python
    def test_critical_button_ids_are_stable(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        for button_id in [
            "runAnalysis",
            "exportAssetCashflow",
            "runTrustAnalysis",
            "exportTrustCashflow",
            "trustExportExcel",
            "trustExportWord",
            "generateTemplateBtn",
            "confirmImport",
        ]:
            self.assertIn(f'id="{button_id}"', html)
```

- [ ] **Step 3: Run tests**

```bash
python3 tests/review_regression_tests.py
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add docs/UI_BOUNDARIES.md tests/review_regression_tests.py
git commit -m "docs: define UI boundaries"
```

---

## Task 9: Final Verification And Release Tag

**Files:**
- Modify: none unless verification finds issues.

- [ ] **Step 1: Run full test set**

```bash
python3 tests/review_regression_tests.py
python3 tests/calculation_fixture_tests.py
python3 tests/export_policy_tests.py
python3 tests/server_api_tests.py
node --check js/app.js
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
```

Expected: all pass.

- [ ] **Step 2: Smoke-test local server**

Start server:

```bash
python3 deploy_server.py --host 127.0.0.1 --port 8767
```

Check:

```bash
curl -s -o /tmp/cashflow_home.html -w "%{http_code} %{size_download}\n" http://127.0.0.1:8767/
curl -s -o /tmp/cashflow_app.js -w "%{http_code} %{size_download}\n" http://127.0.0.1:8767/js/app.js
```

Expected:

```text
200 <nonzero size>
200 <nonzero size>
```

- [ ] **Step 3: Confirm clean Git state**

```bash
git status --short
```

Expected: no output.

- [ ] **Step 4: Tag stable planning baseline**

```bash
git tag -a v0.2-stabilization-plan -m "Stabilization planning baseline"
git push origin main --tags
```

---

## Self-Review

**Spec coverage:** This plan preserves existing behavior and focuses only on stabilization, modular boundaries, fixture tests, documentation, and deployment safety.

**Placeholder scan:** No task contains TBD/TODO placeholders. Each task has concrete files, commands, and expected outputs.

**Type consistency:** Shared names are consistent across tasks: `getAssetFutureSchedule`, `normalizeAssetPeriods`, `DEFAULT_TRUST_CONFIGS`, `batchCreateUrl`, `deleteByModelUrl`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-01-system-stabilization-refactor.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fastest for this large file.
2. **Inline Execution** - execute tasks in this session using checkpoints after each task.
