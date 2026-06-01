(function attachCashflowCore(root) {
    'use strict';

    const scheduleApi = root.CashflowAssetSchedule || {};

    function addMonths(date, months) {
        const result = new Date(date);
        result.setMonth(result.getMonth() + months);
        return result;
    }

    function formatMonth(date) {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    }

    function calculateDetailedCashflowCore(startDate, months, assets, options = {}) {
        const getSchedule = options.getAssetFutureSchedule || scheduleApi.getAssetFutureSchedule;
        const isFullAsset = options.isFullAsset || scheduleApi.isFullAsset || (() => false);
        if (typeof getSchedule !== 'function') {
            throw new Error('getAssetFutureSchedule is required');
        }

        const result = {
            periods: [],
            totalIncome: 0,
            avgMonthly: 0,
            peakMonth: '',
            peakAmount: 0,
            maturingAssets: 0,
            totalDeductedAmount: 0,
            futureCashflowTotal: 0,
            totalDeductionSum: 0,
            cashflowIncludesDeductedAmount: true,
            deductedAmountTiming: 'first_period'
        };

        const schedules = (assets || []).map(asset => ({ asset, schedule: getSchedule(asset) }));
        result.totalDeductionSum = schedules.reduce((sum, row) => sum + row.schedule.totalDeduction, 0);
        result.totalDeductedAmount = schedules.reduce((sum, row) => sum + row.schedule.deductedAmount, 0);
        result.futureCashflowTotal = schedules.reduce((sum, row) => sum + row.schedule.futureRecoverable, 0);

        let cumulative = 0;
        for (let index = 0; index < months; index++) {
            let fullAmount = 0;
            let partialAmount = 0;
            let activeAssets = 0;
            let maturingAssets = 0;
            const deductedAmount = index === 0 ? result.totalDeductedAmount : 0;

            schedules.forEach(({ asset, schedule }) => {
                if (index >= schedule.remainingPeriods || schedule.monthlyFutureAmount <= 0) return;
                activeAssets++;
                if (isFullAsset(asset.asset_type)) {
                    fullAmount += schedule.monthlyFutureAmount;
                } else {
                    partialAmount += schedule.monthlyFutureAmount;
                }
                if (index === schedule.remainingPeriods - 1) {
                    maturingAssets++;
                }
            });

            const futureAmount = fullAmount + partialAmount;
            const totalAmount = deductedAmount + futureAmount;
            cumulative += totalAmount;
            result.totalIncome += totalAmount;
            const label = formatMonth(addMonths(startDate, index));
            if (totalAmount > result.peakAmount) {
                result.peakAmount = totalAmount;
                result.peakMonth = label;
            }
            result.maturingAssets += maturingAssets;
            result.periods.push({
                label,
                fullAmount,
                partialAmount,
                deductedAmount,
                futureAmount,
                totalAmount,
                cumulative,
                activeAssets,
                maturingAssets
            });
        }

        result.avgMonthly = months > 0 ? result.totalIncome / months : 0;
        result.differenceAnalysis = {
            totalDeductionSum: result.totalDeductionSum,
            totalDeductedAmountSum: result.totalDeductedAmount,
            futureCashflowSum: result.futureCashflowTotal,
            theoreticalTotal: result.futureCashflowTotal,
            periodBasedTotal: result.futureCashflowTotal,
            actualTotal: result.totalIncome,
            difference: result.totalDeductionSum - result.totalIncome
        };
        return result;
    }

    const api = { calculateDetailedCashflowCore };
    root.CashflowCore = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
