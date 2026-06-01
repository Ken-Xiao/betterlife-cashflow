#!/usr/bin/env python3
"""Executable calculation fixtures for browser cashflow logic."""

from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "js" / "app.js"
FIXTURE = ROOT / "tests" / "fixtures" / "simple_assets.json"
MODULES = [
    ROOT / "js" / "modules" / "configPolicy.js",
    ROOT / "js" / "modules" / "assetSchedule.js",
    ROOT / "js" / "modules" / "cashflowCore.js",
]


def run_node_fixture() -> dict:
    script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const noop = () => {{}};
        const context = {{
          console: {{ log: noop, warn: noop, error: noop }},
          window: {{}},
          document: {{
            getElementById: () => null,
            addEventListener: noop,
            querySelector: () => null,
            querySelectorAll: () => []
          }},
          localStorage: {{ getItem: () => null, setItem: noop, removeItem: noop }},
          location: {{}},
          navigator: {{}},
          Chart: function() {{}},
          XLSX: {{ utils: {{}}, writeFile: noop }},
          setTimeout,
          clearTimeout,
          performance: {{ now: () => 0 }},
          confirm: () => true,
          alert: noop
        }};
        context.window = context;
        vm.createContext(context);
        for (const file of {json.dumps([str(path) for path in MODULES])}) {{
          vm.runInContext(fs.readFileSync(file, 'utf8'), context);
        }}
        vm.runInContext(fs.readFileSync({json.dumps(str(APP_JS))}, 'utf8'), context);
        const assets = JSON.parse(fs.readFileSync({json.dumps(str(FIXTURE))}, 'utf8'));
        const result = context.calculateDetailedCashflow(new Date('2026-01-01'), 12, assets);
        const coreResult = context.CashflowCore.calculateDetailedCashflowCore(new Date('2026-01-01'), 12, assets);
        process.stdout.write(JSON.stringify({{
          totalIncome: result.totalIncome,
          coreTotalIncome: coreResult.totalIncome,
          totalDeductedAmount: result.totalDeductedAmount,
          coreFirstPeriodTotal: coreResult.periods[0].totalAmount,
          futureCashflowTotal: result.futureCashflowTotal,
          totalDeductionSum: result.totalDeductionSum,
          firstPeriodTotal: result.periods[0].totalAmount,
          firstPeriodDeducted: result.periods[0].deductedAmount,
          seventhPeriodTotal: result.periods[6].totalAmount,
          eleventhPeriodTotal: result.periods[10].totalAmount,
          difference: result.differenceAnalysis.difference,
          includesDeducted: result.cashflowIncludesDeductedAmount,
          deductedTiming: result.deductedAmountTiming
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


class CalculationFixtureTests(unittest.TestCase):
    def test_detailed_cashflow_keeps_deducted_amount_in_first_period(self):
        result = run_node_fixture()

        self.assertEqual(result["totalDeductionSum"], 180000)
        self.assertEqual(result["totalDeductedAmount"], 20000)
        self.assertEqual(result["futureCashflowTotal"], 160000)
        self.assertEqual(result["totalIncome"], 180000)
        self.assertEqual(result["difference"], 0)
        self.assertTrue(result["includesDeducted"])
        self.assertEqual(result["deductedTiming"], "first_period")

    def test_detailed_cashflow_future_schedule_uses_remaining_periods(self):
        result = run_node_fixture()

        self.assertEqual(result["firstPeriodTotal"], 40000)
        self.assertEqual(result["firstPeriodDeducted"], 20000)
        self.assertEqual(result["seventhPeriodTotal"], 10000)
        self.assertEqual(result["eleventhPeriodTotal"], 0)

    def test_extracted_core_matches_browser_cashflow_fixture(self):
        result = run_node_fixture()

        self.assertEqual(result["coreTotalIncome"], result["totalIncome"])
        self.assertEqual(result["coreFirstPeriodTotal"], result["firstPeriodTotal"])


if __name__ == "__main__":
    unittest.main()
