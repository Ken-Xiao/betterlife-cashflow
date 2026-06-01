(function attachAssetSchedule(root) {
    'use strict';

    function isFullAsset(assetType) {
        const type = (assetType || '').toString().trim();
        return type === '整装' || type === '整装资产';
    }

    function isPartialAsset(assetType) {
        const type = (assetType || '').toString().trim();
        return type === '局装' || type === '局装资产';
    }

    function normalizeAssetPeriods(asset) {
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

    function getAssetFutureSchedule(asset) {
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

    function getUnifiedAssetDiscountRate(assetType, config = {}, defaults = {}) {
        const fullDiscountRate = config.fullDiscountRate ?? defaults.fullDiscountRate ?? 88;
        const partialDiscountRate = config.partialDiscountRate ?? defaults.partialDiscountRate ?? 95;
        return isPartialAsset(assetType) ? partialDiscountRate : fullDiscountRate;
    }

    function calculateTrustPoolContribution(asset, config = {}, defaults = {}) {
        const totalDeduction = parseFloat(asset?.total_deduction) || 0;
        const discountRate = getUnifiedAssetDiscountRate(asset?.asset_type, config, defaults);
        return {
            totalDeduction,
            discountRate,
            contribution: totalDeduction * (discountRate / 100)
        };
    }

    const api = {
        isFullAsset,
        isPartialAsset,
        normalizeAssetPeriods,
        getAssetFutureSchedule,
        getUnifiedAssetDiscountRate,
        calculateTrustPoolContribution
    };

    root.CashflowAssetSchedule = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
