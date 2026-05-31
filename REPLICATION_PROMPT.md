# 美好生活资产现金管理系统 - 完整复刻开发指南

## 🎯 系统概述

**项目名称**：美好生活资产现金管理 | Better Life Asset Management  
**设计风格**：摩根士丹利专业金融浅色系  
**技术栈**：HTML5 + CSS3 + JavaScript (ES6+) + Chart.js + SheetJS + docx.js  
**版本**：v3.45.66+

### 核心功能定位

这是一个**结构化金融产品现金流管理系统**，支持：
1. **资产分类管理**：整装资产（18-48期）和局装资产（8-12期）
2. **双模式信托分析**：过手摊还 vs 固定摊还
3. **双类型信托模型**：持有型承接池信托 vs 流转型放款池信托
4. **压力测试**：6种场景的风险分析
5. **专业报告导出**：Excel多Sheet + Word专业报告

---

## 📊 数据架构设计

### 1. 数据库表结构

#### 表1：structured_finance_assets（资产数据表）
```json
{
  "id": "text, 唯一标识符",
  "asset_id": "text, 资产编号/房源编码",
  "asset_type": "text, 整装/局装",
  "total_deduction": "number, 总代扣金额（元）",
  "deducted_amount": "number, 已代扣金额（元）",
  "lease_start_date": "datetime, 资产起租日",
  "total_periods": "number, 代扣总期数",
  "period_deduction": "number, 每期代扣金额（元）",
  "modelId": "text, 所属信托模型ID（数据隔离关键字段）"
}
```

#### 表2：trust_config（信托配置表）
```json
{
  "id": "text, 唯一标识符",
  "config_name": "text, 配置名称",
  "initial_pool_size": "number, 初始资产规模",
  "full_discount_rate": "number, 整装折扣率(%)，默认88",
  "partial_discount_rate": "number, 局装折扣率(%)，默认95",
  "senior_ratio": "number, 优先级比例(%)，默认75",
  "senior_rate": "number, 优先级年化利率(%)，默认4",
  "subordinate_ratio": "number, 劣后级比例(%)，默认25",
  "subordinate_rate": "number, 劣后级期间利率(%)，默认7",
  "repayment_mode": "text, 过手摊还/固定摊还",
  "fixed_repayment_amount": "number, 固定摊还金额",
  "trust_start_date": "datetime, 信托起始日",
  "trust_periods": "number, 信托期数，默认36-60"
}
```

### 2. 多信托模型数据隔离架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户界面 (UI Layer)                          │
├─────────────┬─────────────┬──────────────┬──────────┬───────────┤
│   仪表盘    │  资产管理   │ 资产端现金流 │ 信托端   │ 压力测试  │
├─────────────┴─────────────┴──────────────┴──────────┴───────────┤
│                     AppState (内存状态)                          │
│    AppState.assets = [...] ← 当前模型的资产数据                  │
├─────────────────────────────────────────────────────────────────┤
│                     API Layer (数据访问层)                       │
│    getAllAssets() → 自动按 ModelManager.currentModelId 过滤      │
│    createAsset()  → 自动添加 modelId 字段                        │
├─────────────────────────────────────────────────────────────────┤
│                   数据库 (RESTful Table API)                     │
│    记录: { asset_id, asset_type, ..., modelId: 'model_xxx' }     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ 核心模块设计

### 模块1：仪表盘 (Dashboard)

#### 功能需求
- 资产分类统计：整装/局装分别显示数量、金额
- 图表展示：
  - 月度现金流预测（分类堆叠图）
  - 资产结构分布（饼图）
  - 资产期限分布（条形图）
  - 每期现金流流入（堆叠条形图）
- 一键操作：
  - "运行全部分析"按钮
  - "下载全部结果"按钮（Excel 8 Sheets）
  - "生成最终报告"按钮（Word专业报告）

#### 关键计算
```javascript
// 资产统计
fullAssets = assets.filter(a => a.asset_type === '整装');
partialAssets = assets.filter(a => a.asset_type === '局装');

// 代扣金额计算
totalDeduction = Σ(total_deduction);
deductedAmount = Σ(deducted_amount);
remainingAmount = totalDeduction - deductedAmount;
```

---

### 模块2：资产管理 (Assets)

#### 功能需求
- CRUD操作：新增/编辑/删除/查询资产
- 分页搜索：支持关键词搜索，每页50条
- 数据导入：Excel/CSV文件上传，上限10000条
- 数据导出：按当前筛选条件导出

#### 资产类型判断规则
```javascript
// 品牌为舒里/简逸 → 局装，其他 → 整装
function getAssetType(brand) {
  return ['舒里', '简逸'].includes(brand) ? '局装' : '整装';
}
```

---

### 模块3：资产端现金流分析 (Cashflow)

#### 核心计算逻辑

```javascript
/**
 * 资产端现金流计算 - 核心函数
 * @param assets 资产列表
 * @param startDate 分析起始日
 * @param months 分析期数（默认60个月）
 */
function calculateDetailedCashflow(assets, startDate, months) {
  // 1. 初始化期数数组
  let periods = Array(months).fill(null).map(() => ({
    fullAmount: 0,      // 整装回款
    partialAmount: 0,   // 局装回款
    totalAmount: 0,     // 合计回款
    fullCount: 0,       // 整装资产数
    partialCount: 0     // 局装资产数
  }));

  // 2. 遍历每个资产
  for (let asset of assets) {
    // 计算剩余金额和期数
    const remainingAmount = asset.total_deduction - asset.deducted_amount;
    const remainingPeriods = asset.total_periods;
    const periodAmount = remainingAmount / remainingPeriods;
    
    // 确定有效起始月（基于起租日）
    const leaseStart = new Date(asset.lease_start_date);
    const deductedPeriods = Math.floor(asset.deducted_amount / asset.period_deduction);
    const effectiveStart = addMonths(leaseStart, deductedPeriods);
    const startOffset = monthDiff(startDate, effectiveStart);
    
    // 分配到各期
    for (let i = 0; i < remainingPeriods; i++) {
      const targetMonth = startOffset + i;
      if (targetMonth >= 0 && targetMonth < months) {
        if (asset.asset_type === '整装') {
          periods[targetMonth].fullAmount += periodAmount;
          periods[targetMonth].fullCount++;
        } else {
          periods[targetMonth].partialAmount += periodAmount;
          periods[targetMonth].partialCount++;
        }
        periods[targetMonth].totalAmount += periodAmount;
      }
    }
  }
  
  // 3. 第一月加入已代扣金额（安全垫）
  const totalDeducted = assets.reduce((sum, a) => sum + a.deducted_amount, 0);
  periods[0].totalAmount += totalDeducted;
  periods[0].deductedAmount = totalDeducted;
  
  return { periods, totalDeducted };
}
```

#### 空置期处理逻辑

```javascript
/**
 * 含空置期的现金流计算
 * 空置期机制：整装资产每12个月续租时推迟0.5个月
 */
function calculateCashflowWithVacancy(assets, startDate, months, vacancyConfig) {
  const vacancyPeriod = vacancyConfig.vacancyPeriod || 0.5;  // 默认15天
  const renewalCycle = vacancyConfig.renewalCycle || 12;     // 默认12个月续租

  for (let asset of fullAssets) {
    // 计算累计空置延迟
    const renewalCount = Math.floor(effectivePeriod / renewalCycle);
    const totalVacancyDelay = renewalCount * vacancyPeriod;
    
    // 将回款时间向后推移
    const delayedMonth = originalMonth + Math.ceil(totalVacancyDelay);
    // ... 分配到延迟后的月份
  }
}

// 空置期影响 = 含空置期回款 - 原始回款
// 正数：前期推迟的回款移入当期
// 负数：当期回款被推迟到后期
```

---

### 模块4：信托端分析 (Trust Analysis)

#### 4.1 入池规模计算

```javascript
/**
 * 入池规模计算（基于总代扣金额）
 */
function calculatePooledAssets(assets, config) {
  // 分类统计
  const fullAssets = assets.filter(a => a.asset_type === '整装');
  const partialAssets = assets.filter(a => a.asset_type === '局装');
  
  // 总代扣金额
  const fullTotal = fullAssets.reduce((sum, a) => sum + a.total_deduction, 0);
  const partialTotal = partialAssets.reduce((sum, a) => sum + a.total_deduction, 0);
  
  // 折扣后入池规模
  const fullPooled = fullTotal * (config.fullDiscountRate / 100);    // 88%
  const partialPooled = partialTotal * (config.partialDiscountRate / 100); // 95%
  
  const actualPoolSize = fullPooled + partialPooled;  // 可用规模(100%)
  const guaranteeFund = actualPoolSize * (config.guaranteeFundRate / 100);  // 信保基金(1%)
  const totalRaisingSize = actualPoolSize + guaranteeFund;  // 募集规模(101%)
  
  // 优先级/劣后级本金
  const seniorPrincipal = totalRaisingSize * (config.seniorRatio / 100);
  const subordinatePrincipal = totalRaisingSize * (config.subordinateRatio / 100);
  
  return {
    fullTotal, partialTotal,
    fullPooled, partialPooled,
    actualPoolSize, guaranteeFund, totalRaisingSize,
    seniorPrincipal, subordinatePrincipal
  };
}
```

#### 4.2 过手摊还模式 (Pass-Through)

```javascript
/**
 * 过手摊还现金流计算
 * 特点：每季度资产回款全部用于偿还，偿还完毕后剩余为超额收益
 */
function calculatePassThroughCashflow(assetCashflow, config, pooledAssets) {
  const periods = [];
  let seniorBalance = pooledAssets.seniorPrincipal;
  let subordinateBalance = pooledAssets.subordinatePrincipal;
  let totalExcess = 0;
  
  // 按季度处理（每3个月）
  for (let quarter = 0; quarter < Math.ceil(config.trustPeriods / 3); quarter++) {
    // 1. 汇总季度资产回款（含已代扣、空置期影响）
    const quarterInflow = getQuarterlyInflow(assetCashflow, quarter);
    
    // 2. 计算风险影响
    const defaultAmount = quarterInflow * (config.pdFull / 100);
    const recoveryAmount = defaultAmount * (1 - config.lgdFull / 100);
    const managementFee = quarterInflow * (config.totalFeeRate / 100 / 4);
    
    // 3. 净回款
    const netInflow = quarterInflow - defaultAmount + recoveryAmount - managementFee;
    
    // 4. 偿还顺序瀑布
    let available = netInflow;
    
    // 4.1 前置费用（仅第一季度）
    const upfrontFee = quarter === 0 ? config.totalUpfrontFee : 0;
    available -= upfrontFee;
    
    // 4.2 税金
    const taxAmount = netInflow * config.taxableRatio * config.effectiveTaxRate;
    available -= taxAmount;
    
    // 4.3 优先级利息
    const seniorInterest = seniorBalance * (config.seniorRate / 100 / 4);
    available -= seniorInterest;
    
    // 4.4 劣后级利息
    const subordinateInterest = subordinateBalance * (config.subordinateRate / 100 / 4);
    available -= subordinateInterest;
    
    // 4.5 优先级本金
    const seniorPrincipalRepay = Math.min(available, seniorBalance);
    available -= seniorPrincipalRepay;
    seniorBalance -= seniorPrincipalRepay;
    
    // 4.6 劣后级本金（优先级还清后）
    let subordinatePrincipalRepay = 0;
    if (seniorBalance <= 0.01) {
      subordinatePrincipalRepay = Math.min(available, subordinateBalance);
      available -= subordinatePrincipalRepay;
      subordinateBalance -= subordinatePrincipalRepay;
    }
    
    // 4.7 超额收益
    const excessReturn = Math.max(0, available);
    totalExcess += excessReturn;
    
    periods.push({
      quarter: quarter + 1,
      assetInflow: quarterInflow,
      defaultAmount, recoveryAmount, managementFee,
      netInflow, upfrontFee, taxAmount,
      seniorInterest, subordinateInterest,
      seniorPrincipalRepay, subordinatePrincipalRepay,
      seniorBalance, subordinateBalance,
      excessReturn, cumulativeExcess: totalExcess
    });
  }
  
  return { periods, totalExcess };
}
```

#### 4.3 固定摊还模式 (Fixed Amortization)

```javascript
/**
 * 固定摊还现金流计算
 * 特点：优先级按固定期限摊还，剩余资金沉淀，期末释放
 */
function calculateFixedAmortizationCashflow(assetCashflow, config, pooledAssets) {
  const periods = [];
  let seniorBalance = pooledAssets.seniorPrincipal;
  let subordinateBalance = pooledAssets.subordinatePrincipal;
  let cashReserve = 0;  // 累计沉淀
  let totalExcess = 0;
  
  // 固定摊还参数
  const seniorRepayQuarters = config.seniorRepayQuarters || 8;  // 默认2年（8季度）
  const repaymentMethod = config.repaymentMethod || 'equal_principal_interest';
  
  // 计算每季度应还优先级本金
  const quarterlyPrincipal = seniorBalance / seniorRepayQuarters;
  
  for (let quarter = 0; quarter < Math.ceil(config.trustPeriods / 3); quarter++) {
    const isWithinRepayPeriod = quarter < seniorRepayQuarters;
    const prevCumulativeReserve = cashReserve;
    
    // 1-3. 同过手摊还（资产回款、风险、净回款）
    const netInflow = calculateNetInflow(assetCashflow, quarter, config);
    
    // 4. 偿还顺序
    let available = netInflow;
    
    // 4.1-4.4 前置费、税金、优先级利息、劣后级利息
    // ... 同过手摊还
    
    // 4.5 优先级本金（按固定计划）
    let seniorPrincipalRepay = 0;
    if (isWithinRepayPeriod && seniorBalance > 0.01) {
      // 等额本息 or 等额本金
      if (repaymentMethod === 'equal_principal') {
        seniorPrincipalRepay = Math.min(quarterlyPrincipal, seniorBalance);
      } else {
        // PMT公式计算等额本息
        seniorPrincipalRepay = calculatePMT(seniorBalance, config.seniorRate / 4, seniorRepayQuarters - quarter);
      }
      seniorPrincipalRepay = Math.min(seniorPrincipalRepay, available);
      available -= seniorPrincipalRepay;
      seniorBalance -= seniorPrincipalRepay;
    }
    
    // 4.6 当期沉淀/超额
    let periodReserveIncrease = 0;
    let excessReturn = 0;
    
    if (seniorBalance > 0.01) {
      // 优先级未还清：剩余资金沉淀
      periodReserveIncrease = available;
      cashReserve = prevCumulativeReserve + periodReserveIncrease;
    } else if (subordinateBalance > 0.01) {
      // 优先级已还清，劣后级未还清
      available += prevCumulativeReserve;  // 动用累计沉淀
      const subordinatePrincipalRepay = Math.min(available - subordinateInterest, subordinateBalance);
      subordinateBalance -= subordinatePrincipalRepay;
      periodReserveIncrease = available - subordinatePrincipalRepay - subordinateInterest;
      cashReserve = Math.max(0, prevCumulativeReserve + periodReserveIncrease);
    } else {
      // 全部还清：剩余为超额收益
      excessReturn = available;
      totalExcess += excessReturn;
      cashReserve = 0;
    }
    
    periods.push({
      quarter: quarter + 1,
      // ... 其他字段
      periodReserveIncrease, cashReserve, excessReturn
    });
  }
  
  return { periods, totalExcess, finalReserve: cashReserve };
}
```

#### 4.4 闲置资金利息收入计算

```javascript
/**
 * 闲置资金利息收入计算
 * 三个来源：信保基金利息、季度暂存利息、沉淀/超额利息
 */
function calculateInterestIncome(config, cashflowPeriods) {
  const monthlyRate = (config.idleFundRate || 0.8) / 100 / 12;
  
  // 1. 信保基金利息
  // 信保基金全程存放（期数-1个月产生利息）
  const guaranteeFundInterest = config.guaranteeFundAmount * monthlyRate * (config.trustPeriods - 1);
  
  // 2. 季度暂存利息
  // 每月回款在季末才支付，期间产生利息
  // 第1月存2个月，第2月存1个月，第3月当季支出无利息
  let quarterlyInterest = 0;
  for (let quarter of cashflowPeriods) {
    const month1 = quarter.months[0]?.amount || 0;
    const month2 = quarter.months[1]?.amount || 0;
    quarterlyInterest += month1 * monthlyRate * 2 + month2 * monthlyRate * 1;
  }
  
  // 3. 沉淀/超额资金利息（固定摊还特有）
  // 上期累计沉淀在本季度存放3个月
  let reserveInterest = 0;
  for (let i = 1; i < cashflowPeriods.length; i++) {
    const prevReserve = cashflowPeriods[i - 1].cashReserve || 0;
    reserveInterest += prevReserve * monthlyRate * 3;
  }
  
  return {
    guaranteeFundInterest,
    quarterlyInterest,
    reserveInterest,
    totalInterest: guaranteeFundInterest + quarterlyInterest + reserveInterest
  };
}
```

---

### 模块5：压力测试 (Stress Test)

#### 6种压力测试场景

```javascript
/**
 * 持有型信托压力测试场景
 */
const holdingStressScenarios = [
  {
    name: '场景0 - 无违约基准',
    description: '移除违约风险的理想参考',
    params: { pdMultiplier: 0, vacancyDays: 15 }
  },
  {
    name: '场景1 - 当前参数',
    description: '当前配置下的实际预期',
    params: { pdMultiplier: 1, vacancyDays: 15 }
  },
  {
    name: '场景2 - 违约上升',
    description: 'PD × 1.5倍',
    params: { pdMultiplier: 1.5, vacancyDays: 15 }
  },
  {
    name: '场景3 - 空置延长',
    description: '空置期增加到40天',
    params: { pdMultiplier: 1, vacancyDays: 40 }
  },
  {
    name: '场景4 - 双重压力',
    description: 'PD×1.5 + 40天空置',
    params: { pdMultiplier: 1.5, vacancyDays: 40 }
  },
  {
    name: '场景5 - 临界分析',
    description: '反算使超额收益为0的临界PD',
    params: { findCriticalPD: true }
  }
];

/**
 * 临界PD反算（二分法）
 */
function findCriticalPD(baseConfig, pooledAssets) {
  let lowPD = 0, highPD = 50;  // PD范围0-50%
  let criticalPD = 0;
  
  for (let i = 0; i < 50; i++) {  // 最多50次迭代
    const midPD = (lowPD + highPD) / 2;
    const testConfig = { ...baseConfig, pdFull: midPD };
    const result = calculatePassThroughCashflow(assetCashflow, testConfig, pooledAssets);
    
    if (Math.abs(result.totalExcess) < 1000) {  // 超额收益接近0
      criticalPD = midPD;
      break;
    }
    
    if (result.totalExcess > 0) {
      lowPD = midPD;  // 还有超额，提高PD
    } else {
      highPD = midPD;  // 已亏损，降低PD
    }
    criticalPD = midPD;
  }
  
  return criticalPD;
}
```

---

### 模块6：数据加工 (Data Processing)

#### 双数据源字段映射

```javascript
/**
 * 房源维度物资底表 → 结构化金融产品字段映射
 */
const fieldMapping = {
  // 核心字段
  'asset_id': ['房源编码', '房源ID', '房源编号', '资产编号'],
  'asset_type': {
    source: '品牌',
    transform: (brand) => ['舒里', '简逸'].includes(brand) ? '局装' : '整装'
  },
  'total_deduction': ['MIN金融机构可转让', '总代扣金额'],
  'deducted_amount': ['贝壳已租金代扣金额合计', '已代扣金额'],
  'lease_start_date': ['首次付款日期', '首次支付时间'],
  'total_periods': ['预计代扣周期-当前剩余资金', '预计代扣周期'],
  'period_deduction': ['每期应付款金额', '代扣比例×出房价格']
};

/**
 * 入池条件校验
 */
function validateForPooling(record, rentalRecords) {
  // 条件1：总代扣金额必须>0
  if (!record.total_deduction || record.total_deduction <= 0) {
    return { valid: false, reason: '总代扣金额缺失或为0' };
  }
  
  // 条件2：代扣表收房/出房价格不能同时为空
  const hasValidPrice = rentalRecords.some(r => 
    !isNullOrEmpty(r.收房价格) || !isNullOrEmpty(r.出房价格)
  );
  if (!hasValidPrice) {
    return { valid: false, reason: '已解约，无法入池（收房和出房价格同时为null）' };
  }
  
  return { valid: true };
}
```

#### 数据交叉校验规则

```javascript
/**
 * 三项数据交叉校验
 */
const validationRules = [
  {
    name: 'Check 1: 出房价格一致性',
    rule: '房源表.出房价格 = 代扣表.出房价格',
    tolerance: 1000  // 容差±1000元
  },
  {
    name: 'Check 2: 代扣总金额校验',
    rule: 'Σ代扣表.代扣总金额(按订单号去重) - 房源表.已租金代扣到账合计 ≈ 房源表.(已代扣未付款 + 贝壳未代扣)',
    tolerance: '±10元或±1%'
  },
  {
    name: 'Check 3: 每期应付金额校验',
    rule: '代扣表.出房价格 × 代扣表.代扣比例 ≈ 代扣表.每期代扣金额',
    tolerance: 1  // 容差±1元
  }
];
```

---

### 模块7：局装占比风险预警

```javascript
/**
 * 局装占比风险预警计算
 * 核心逻辑：确保局装到期后的"空窗期"整装回款能覆盖优先级本息
 */
function calculatePartialRatioWarning(config, pooledAssets, faCashflow) {
  // 1. 计算局装资产的最大期数（通常8-12期）
  const partialMaxPeriods = 12;  // 局装最长期限
  
  // 2. 关键风险期：局装到期后、整装继续还款的季度
  const criticalQuarters = Math.ceil(partialMaxPeriods / 3);  // 约Q5-Q8
  
  // 3. 计算空窗期每季度整装回款能力
  const fullRepaymentPerQuarter = pooledAssets.fullPooled / (config.trustPeriods / 3);
  
  // 4. 每季度应付优先级本息
  const quarterlyDue = calculateQuarterlyDue(pooledAssets.seniorPrincipal, config);
  
  // 5. 覆盖率 = 整装回款 / 应付本息
  const coverageRatio = fullRepaymentPerQuarter / quarterlyDue * 100;
  
  // 6. 最大安全局装占比（确保覆盖率≥110%）
  const maxSafePartialRatio = calculateMaxSafeRatio(config, pooledAssets);
  
  // 7. 风险状态判断
  const currentRatio = pooledAssets.partialPooled / pooledAssets.actualPoolSize * 100;
  const riskLevel = coverageRatio >= 110 ? '安全' : coverageRatio >= 100 ? '注意' : '风险';
  
  return {
    currentPartialRatio: currentRatio,
    maxSafePartialRatio: maxSafePartialRatio,
    minCoverageRatio: coverageRatio,
    criticalQuarter: criticalQuarters,
    riskLevel,
    additionalPartialAllowed: (maxSafePartialRatio - currentRatio) * pooledAssets.actualPoolSize / 100
  };
}
```

---

## 🎨 UI设计规范

### 配色方案（摩根士丹利专业金融浅色系）

```css
:root {
  /* 主色调 */
  --primary-color: #2d3748;      /* 深灰蓝 */
  --primary-dark: #1a202c;
  --primary-light: #4a5568;
  
  /* 强调色 */
  --accent-color: #3182ce;       /* 专业蓝 */
  --accent-blue: #4299e1;
  
  /* 状态色（低饱和度） */
  --success-color: #38a169;      /* 绿色 */
  --warning-color: #d69e2e;      /* 黄色 */
  --danger-color: #e53e3e;       /* 红色 */
  --info-color: #3182ce;
  
  /* 背景色 */
  --bg-primary: #f8f9fa;         /* 极浅灰主背景 */
  --bg-card: #ffffff;            /* 纯白卡片 */
  --bg-sidebar: #2d3748;         /* 深灰蓝侧边栏 */
  
  /* 文字色 */
  --text-primary: #111827;
  --text-secondary: #1f2937;
  --text-muted: #6b7280;
  
  /* 边框和阴影 */
  --border-color: #e2e8f0;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 4px rgba(0,0,0,0.05);
  
  /* 布局 */
  --sidebar-width: 240px;
  --topbar-height: 50px;
  
  /* 字体 */
  --font-primary: 'Inter', -apple-system, sans-serif;
  --font-numbers: 'Tabular Nums', 'SF Mono', monospace;
}
```

### 字体规范

```css
/* 主文本 */
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* 数字和代码（等宽） */
font-family: 'Tabular Nums', 'SF Mono', 'Menlo', 'Consolas', monospace;
font-variant-numeric: tabular-nums;  /* 确保数字等宽对齐 */

/* 字号规范 */
--font-size-number: 10px;
--font-size-number-sm: 9px;
--font-size-number-lg: 11px;
```

### 会计格式显示

```javascript
/**
 * 负数显示为括号格式（会计惯例）
 */
function formatCurrencyAccounting(value) {
  if (value < 0) {
    return `(${Math.abs(value).toLocaleString('zh-CN')})`;
  }
  return value.toLocaleString('zh-CN');
}

// CSS配合
.negative-value {
  color: var(--danger-color);
}
```

---

## 📤 报告导出功能

### Excel导出（8个Sheet）

```javascript
/**
 * 下载全部结果 - Excel 8 Sheets
 */
function downloadAllResults() {
  const wb = XLSX.utils.book_new();
  
  // Sheet 1: 分析概要
  addSummarySheet(wb, fullAnalysisResults);
  
  // Sheet 2: 勾稽汇总
  addReconciliationSheet(wb, fullAnalysisResults);
  
  // Sheet 3: 资产端现金流
  addCashflowSheet(wb, fullAnalysisResults.cashflowAnalysis);
  
  // Sheet 4: 过手摊还明细
  addPassThroughSheet(wb, fullAnalysisResults.trustAnalysis.passThroughMode);
  
  // Sheet 5: 固定摊还明细
  addFixedAmortSheet(wb, fullAnalysisResults.trustAnalysis.fixedAmortizationMode);
  
  // Sheet 6: 利息收入分析
  addInterestIncomeSheet(wb, fullAnalysisResults);
  
  // Sheet 7: 空置期影响分析
  addVacancyImpactSheet(wb, fullAnalysisResults);
  
  // Sheet 8: 局装占比风险预警
  addPartialRatioWarningSheet(wb, fullAnalysisResults);
  
  // Sheet 9: 压力测试
  addStressTestSheet(wb, fullAnalysisResults.stressTest);
  
  // Sheet 10: 计算说明
  addCalculationNotes(wb);
  
  XLSX.writeFile(wb, `美好生活资产现金管理_全部分析结果_${dateStr}.xlsx`);
}
```

### Word报告（专业格式）

```javascript
/**
 * 生成最终报告 - Word专业报告
 * 使用 docx.js 库生成
 */
async function generateFinalReport() {
  const doc = new docx.Document({
    styles: { ... },
    sections: [
      // 封面页
      createCoverPage(modelName, reportDate),
      
      // 目录页
      createTOCPage(),
      
      // 一、报告摘要
      createSummarySection(results),
      
      // 二、项目背景与交易结构
      createBackgroundSection(config),
      
      // 三、基础资产池分析
      createAssetPoolSection(pooledAssets),
      
      // 四、现金流模型方法论
      createMethodologySection(),
      
      // 五、信托结构设计
      createTrustStructureSection(config),
      
      // 六、资产端现金流分析
      createCashflowAnalysisSection(cashflowAnalysis),
      
      // 七、信托端偿付分析
      createRepaymentAnalysisSection(trustAnalysis),
      
      // 八、压力测试与敏感性分析
      createStressTestSection(stressTest),
      
      // 九、季度现金流明细
      createQuarterlyCashflowTables(periods),
      
      // 十、风险提示与免责声明
      createDisclaimerSection(),
      
      // 附录：术语解释
      createGlossaryAppendix()
    ]
  });
  
  const blob = await docx.Packer.toBlob(doc);
  saveAs(blob, `外贸信托-${modelName}现金流预测报告_${dateStr}.docx`);
}
```

---

## 🔧 关键配置参数默认值

```javascript
const DEFAULT_CONFIG = {
  // 信托基础
  trustPeriods: 36,              // 信托期数（默认3年）
  trustStartDate: new Date(),    // 信托起始日
  
  // 入池折扣
  fullDiscountRate: 88,          // 整装折扣率
  partialDiscountRate: 95,       // 局装折扣率
  
  // 优先/劣后结构
  seniorRatio: 75,               // 优先级比例
  seniorRate: 4,                 // 优先级年利率
  subordinateRatio: 25,          // 劣后级比例
  subordinateRate: 7,            // 劣后级年利率
  
  // 固定摊还
  seniorRepayQuarters: 8,        // 优先级还款期限（8季度=2年）
  repaymentMethod: 'equal_principal_interest',  // 等额本息
  
  // 信保基金
  guaranteeFundRate: 1,          // 信保基金比例
  
  // 空置期（仅整装资产）
  vacancyPeriod: 0.5,            // 空置期（月），默认15天
  renewalCycle: 12,              // 续租周期（月）
  
  // 风险参数
  pdFull: 0.2,                   // 整装PD（年化）
  pdPartial: 0.1,                // 局装PD（年化）
  lgdFull: 100,                  // 整装LGD
  lgdPartial: 100,               // 局装LGD
  
  // 费用参数
  serviceFee1: 0.1,              // 服务机构1（千一）
  serviceFee2: 0.4,              // 服务机构2（千四）
  trustServiceFee: 0.41,         // 信托服务费
  
  // 税金
  taxableRatioFull: 12,          // 整装应税比例 = 100 - 88
  taxableRatioPartial: 5,        // 局装应税比例 = 100 - 95
  effectiveTaxRate: 3.26,        // 有效税率
  
  // 闲置资金
  idleFundRate: 0.8,             // 闲置资金年化利率
  
  // 前置费用
  lawyerFee: 0,                  // 律师费
  ratingFee: 0,                  // 评级费
  accountantFee: 0               // 会计师费
};
```

---

## 📋 勾稽关系验证

### 核心勾稽公式

```javascript
/**
 * 勾稽验证规则
 */
const reconciliationRules = {
  // 1. 资产端勾稽
  '总代扣金额 = 已代扣金额 + 未来回收金额': 
    (data) => data.totalDeduction === data.deductedAmount + data.futureRecovery,
  
  // 2. 现金流勾稽
  '现金流总额 ≈ 总代扣金额':
    (data) => Math.abs(data.cashflowTotal - data.totalDeduction) / data.totalDeduction < 0.02,
  
  // 3. 信托端勾稽
  '募集规模 = 可用规模 × (1 + 信保基金比例)':
    (data) => data.totalRaisingSize === data.actualPoolSize * (1 + data.guaranteeFundRate / 100),
  
  // 4. 优先劣后勾稽
  '优先级本金 + 劣后级本金 = 募集规模':
    (data) => Math.abs(data.seniorPrincipal + data.subordinatePrincipal - data.totalRaisingSize) < 1,
  
  // 5. 空置期勾稽
  '空置期影响 = 含空置期回款 - 原始回款':
    (data) => data.vacancyEffect === data.vacancyCashflow - data.originalCashflow
};
```

---

## 🚀 开发实施建议

### 开发顺序建议

1. **Phase 1 - 基础框架（1周）**
   - 项目结构搭建
   - UI框架和样式系统
   - 数据表结构设计
   - API层封装

2. **Phase 2 - 核心模块（2周）**
   - 资产管理CRUD
   - 资产端现金流计算
   - 仪表盘图表

3. **Phase 3 - 信托分析（2周）**
   - 过手摊还计算
   - 固定摊还计算
   - 空置期处理
   - 利息收入计算

4. **Phase 4 - 高级功能（1周）**
   - 压力测试
   - 局装占比风险预警
   - 数据加工模块

5. **Phase 5 - 报告导出（1周）**
   - Excel多Sheet导出
   - Word专业报告
   - 勾稽验证

### 技术依赖

```html
<!-- CDN引入 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx/dist/xlsx.full.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/docx@7/build/index.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/file-saver@2/dist/FileSaver.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css">
```

---

## ⚠️ 注意事项

1. **数据精度**：金融计算使用 `toFixed(2)` 保留两位小数，避免浮点误差
2. **并发控制**：批量API操作使用50-100并发，避免服务端限流
3. **缓存策略**：资产数据缓存1分钟，切换模型时从缓存过滤
4. **错误处理**：所有API调用添加try-catch，显示友好错误提示
5. **性能优化**：大数据量使用分页加载，图表使用虚拟滚动

---

**文档版本**：v1.0  
**最后更新**：2026-02-07  
**适用系统版本**：v3.45.66+
