#!/usr/bin/env python3
"""Regression checks for the cashflow system review fixes."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "js" / "app.js"
INDEX_HTML = ROOT / "index.html"
SERVER_PY = ROOT / "deploy_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("cashflow_deploy_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SourceRegressionTests(unittest.TestCase):
    def test_asset_api_uses_explicit_model_filter_not_duplicate_search(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("params.append('modelId', modelId)", source)
        self.assertIn("params.append('q', search)", source)
        self.assertNotIn("params.append('search', `modelId:${modelId}`)", source)

    def test_current_model_assets_are_not_persisted_to_local_storage(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("model.data.assets = [];", source)
        self.assertNotIn("model.data.assets = [...AppState.assets]", source)

    def test_dashboard_always_refreshes_when_model_changes(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("AppState.assetsModelId === API.getCurrentModelId()", source)
        self.assertIn("AppState.assetsModelId = modelId;", source)

    def test_initial_pool_size_id_is_unique(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertEqual(html.count('id="initialPoolSize"'), 1)
        self.assertIn('id="circulationInitialPoolSize"', html)

    def test_local_server_supports_patch_and_model_query(self):
        source = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn("def do_PATCH", source)
        self.assertIn('query.get("modelId"', source)
        self.assertIn('query.get("q"', source)

    def test_sidebar_is_compact_and_collapsible(self):
        css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("--sidebar-width: 292px;", css)
        self.assertIn("body.sidebar-collapsed .sidebar", css)
        self.assertIn('id="sidebarToggle"', html)

    def test_data_flow_guide_and_excel_formula_audit_exist(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('id="dataFlowGuide"', html)
        self.assertIn("function updateDataFlowGuide()", source)
        self.assertIn("function appendFormulaAuditSheet", source)
        self.assertIn("公式校验", source)
        self.assertIn("SUMPRODUCT", source)

    def test_calculation_policy_helpers_are_single_source_of_truth(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("const DEFAULT_TRUST_CONFIGS", source)
        self.assertIn("function getDefaultConfigValue", source)
        self.assertIn("function normalizeAssetPeriods", source)
        self.assertIn("function calculateTrustPoolContribution", source)
        self.assertNotIn("totalPeriods <= 12 ? 95 : 88", source)

    def test_deducted_amount_contract_and_difference_are_explicit(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("cashflowIncludesDeductedAmount: true", source)
        self.assertIn("deductedAmountTiming: 'first_period'", source)
        self.assertIn("difference: totalDeductionSum - result.totalIncome", source)

    def test_annual_pd_and_recovery_tail_are_modelled(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function annualProbabilityToMonthlyRate", source)
        self.assertIn("pdFullMonthly", source)
        self.assertIn("recoveryTailAmount", source)
        self.assertIn("回收提示", source)

    def test_fixed_amortization_period_and_row_level_audit_exist(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("getSeniorRepayQuarters", source)
        self.assertNotIn("const totalQuarters = 20;", source)
        self.assertIn("function appendRowFormulaAuditSheet", source)
        self.assertIn("按钮", source)
        self.assertIn("行级公式校验", source)

    def test_json_database_writes_are_locked_and_batchable(self):
        source = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn("DATA_LOCK", source)
        self.assertIn("def create_rows_batch", source)
        self.assertIn("def delete_rows_by_model", source)

    def test_model_stats_use_unfiltered_database_scan(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("async getAllModelAssetsRaw()", source)
        self.assertIn("const allAssets = await this.getAllModelAssetsRaw();", source)
        self.assertNotIn("await this.getAllAssets(true);\n        }\n        const stats = {};", source)

    def test_import_refreshes_from_database_after_batch_create(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("forceModelId", source)
        self.assertIn("await loadAssets(1, '', true)", source)
        self.assertNotIn("AppState.assets = [...existingAssets, ...assetsWithModelId];", source)

    def test_template_and_report_text_match_current_calculation_policy(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("局装统一折扣率", source)
        self.assertIn("月度等效PD = 1 - (1 - 年化PD)^(1/12)", source)
        self.assertNotIn("局装≤12期→95%，>12期→88%", source)
        self.assertNotIn("PD/12", source)

    def test_export_fallback_uses_shared_pool_calculation_and_template_row_audit(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("calculatePooledAssetsWithDiscount(assets, config)", source)
        self.assertIn("导入模板逐行公式校验", source)
        self.assertIn("templateRowAuditRows", source)
        self.assertNotIn("const fullRemainingAmount = fullAssets.reduce", source)

    def test_cashflow_export_button_ids_are_distinct(self):
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="exportAssetCashflow"', html)
        self.assertIn("safeAddEvent('exportAssetCashflow'", source)
        self.assertNotIn("safeAddEvent('exportCashflow', 'click', exportCashflow)", source)
        self.assertNotIn("safeAddEvent('exportCashflow', 'click', () => exportTrustCashflowByMode('fa'))", source)

    def test_cashflow_schedule_helper_drives_period_based_views(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function getAssetFutureSchedule", source)
        self.assertIn("const lastPaymentMonth = offsetFromStart + remainingPeriods;", source)
        self.assertNotIn("const lastPaymentMonth = offsetFromStart + totalPeriods;", source)
        self.assertNotIn("fullMonthlyRepayments[m] = (fullMonthlyRepayments[m] || 0) + periodDeduction;", source)
        self.assertNotIn("partialMonthlyRepayments[m] = (partialMonthlyRepayments[m] || 0) + periodDeduction;", source)

    def test_report_and_template_language_uses_current_total_deduction_policy(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("= 整装总代扣 × ", source)
        self.assertIn("= 局装总代扣 × ", source)
        self.assertIn("风险及费用后净回款", source)
        self.assertIn("房源表唯一", source)
        self.assertNotIn("扣除风险前的总回款", source)
        self.assertNotIn("房源表→代扣表", source)
        self.assertNotIn("房源表→计算补全", source)

    def test_rating_and_trust_exports_use_percent_discount_values(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("record['资产转让折扣率(%)'] = discountRatePct;", source)
        self.assertIn("const discountRatePct = getUnifiedAssetDiscountRate", source)
        self.assertNotIn("record['资产转让折扣率(%)'] = discountRate;", source)


class ServerFilterTests(unittest.TestCase):
    def test_filter_rows_supports_model_id_and_text_query(self):
        server = load_server_module()
        rows = [
            {"id": "1", "modelId": "m1", "asset_id": "alpha"},
            {"id": "2", "modelId": "m2", "asset_id": "alpha"},
            {"id": "3", "modelId": "m1", "asset_id": "beta"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            original_data_file = server.DATA_FILE
            try:
                server.DATA_FILE = Path(tmp) / "rows.json"
                server.save_rows(rows)
                filtered = server.filter_asset_rows(server.load_rows(), model_id="m1", q="alpha")
                self.assertEqual([row["id"] for row in filtered], ["1"])
            finally:
                server.DATA_FILE = original_data_file


if __name__ == "__main__":
    unittest.main()
