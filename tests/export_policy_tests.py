#!/usr/bin/env python3
"""Checks that exports and reports remain tied to calculation policy."""

from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "js" / "app.js"
EXPORT_AUDIT_JS = ROOT / "js" / "modules" / "exportAudit.js"


def run_export_audit_module() -> dict:
    script = textwrap.dedent(
        f"""
        const audit = require({json.dumps(str(EXPORT_AUDIT_JS))});
        const rows = audit.buildRowFormulaAuditRows([
          {{
            button: '资产端现金流',
            sourceSheet: '资产现金流',
            sourceRow: 2,
            label: '当月总回款',
            jsValue: 40000,
            formula: 'C2+D2',
            tolerance: 0.01,
            note: '第一期含已代扣金额'
          }}
        ]);
        process.stdout.write(JSON.stringify({{
          quoted: audit.quoteExcelSheetName(\"现金流'校验\"),
          rowCount: rows.length,
          first: rows[0]
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


class ExportPolicyTests(unittest.TestCase):
    def test_export_audit_module_builds_independent_row_formula_records(self):
        result = run_export_audit_module()

        self.assertEqual(result["quoted"], "'现金流''校验'")
        self.assertEqual(result["rowCount"], 1)
        first = result["first"]
        self.assertEqual(first["button"], "资产端现金流")
        self.assertEqual(first["field"], "当月总回款")
        self.assertEqual(first["jsValue"], 40000)
        self.assertEqual(first["formula"], "C2+D2")
        self.assertEqual(first["tolerance"], 0.01)

    def test_each_primary_excel_export_has_summary_and_row_level_audit(self):
        source = APP_JS.read_text(encoding="utf-8")

        expected_pairs = [
            ("exportWaterfallToExcel", "偿付瀑布按钮公式校验", "偿付瀑布行级公式校验"),
            ("exportCashflow", "资产端现金流按钮公式校验", "现金流行级公式校验"),
            ("exportTrustCashflowByMode", "按钮公式校验", "行级公式校验"),
            ("exportGeneratedTemplate", "导入模板按钮公式校验", "导入模板逐行公式校验"),
        ]
        for function_name, summary_title, row_sheet in expected_pairs:
            self.assertIn(f"function {function_name}", source)
            self.assertIn(summary_title, source)
            self.assertIn(row_sheet, source)

    def test_report_language_matches_current_calculation_policy(self):
        source = APP_JS.read_text(encoding="utf-8")

        policy_terms = [
            "资产端净回款",
            "风险及费用后净回款",
            "月度等效PD = 1 - (1 - 年化PD)^(1/12)",
            "已代扣金额（第一月到账）",
            "总回款 = 已代扣 + 未来回收",
        ]
        for term in policy_terms:
            self.assertIn(term, source)
        self.assertNotIn("PD/12", source)
        self.assertNotIn("扣除风险前的总回款", source)


if __name__ == "__main__":
    unittest.main()
