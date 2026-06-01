# 美好生活资产现金管理系统

本系统是一个本地部署的结构化金融现金流分析工具，支持多信托模型、资产数据库管理、资产端现金流、信托端瀑布、压力测试、Excel 导出和 Word 报告。

当前重构原则：**保持现有功能和用户流程一致，逐步提升计算可验证性、数据库边界和代码可维护性。**

## 快速启动

```bash
python3 deploy_server.py --host 127.0.0.1 --port 8767
```

访问：

```text
http://127.0.0.1:8767/
```

## 核心文件

- `index.html`: 单页应用入口。
- `css/style.css`: 页面样式。
- `js/app.js`: 当前主应用入口，负责 UI 编排、事件绑定、渲染和遗留计算逻辑。
- `js/modules/`: 新增的稳定化模块边界。
- `deploy_server.py`: 本地静态服务和 JSON 数据库 REST API。
- `tests/`: 回归测试、计算 fixture、导出政策和服务端数据边界测试。
- `docs/CURRENT_CALCULATION_POLICY.md`: 当前计算政策。
- `docs/OPERATIONS.md`: 本地部署、数据库和验证命令。
- `docs/UI_BOUNDARIES.md`: 下一阶段 UI/模块边界。

## 当前计算口径

- `total_deduction` 是资产总代扣金额。
- `deducted_amount` 是已代扣金额，并在第一期体现为现金回款。
- 未来回款为 `total_deduction - deducted_amount`，按 `remaining_periods` 展开。
- 整装和局装分别使用统一折扣率，不再按局装期限分桶折扣。
- PD 输入是年化 PD，月度等效 PD 为 `1 - (1 - 年化PD)^(1/12)`。
- 信托端分配使用风险及费用后的净资产回款。
- 固定摊还使用配置的优先级固定摊还期数。

详见 [CURRENT_CALCULATION_POLICY.md](docs/CURRENT_CALCULATION_POLICY.md)。

## 数据库边界

本地数据库文件位于：

```text
data/structured_finance_assets.json
```

每条资产必须带有有效 `modelId`。服务端会拒绝创建或更新没有 `modelId` 的资产，批量导入会按照目标模型重置 `modelId`，避免孤立数据和跨模型污染。

## Excel 和报告校验

主要导出按钮应包含：

- 汇总级公式校验 sheet。
- 逐行公式校验 sheet。
- 与页面计算同口径的说明文字。

测试覆盖导出公式审计模块、资产现金流 fixture、服务端模型边界和历史回归规则。

## 验证命令

```bash
node --check js/app.js
node --check js/modules/configPolicy.js
node --check js/modules/assetSchedule.js
node --check js/modules/cashflowCore.js
node --check js/modules/exportAudit.js
node --check js/modules/apiClient.js
PYTHONPYCACHEPREFIX=/private/tmp/cashflow_pycache python3 -m py_compile deploy_server.py
python3 tests/calculation_fixture_tests.py
python3 tests/export_policy_tests.py
python3 tests/server_api_tests.py
python3 tests/review_regression_tests.py
```
