(function attachConfigPolicy(root) {
    'use strict';

    const DEFAULT_TRUST_CONFIGS = {
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
            repaymentMethod: 'equal_payment'
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
            repaymentMethod: 'equal_principal',
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

    function getDefaultTrustConfigByType(modelType = 'holding_pool') {
        const type = DEFAULT_TRUST_CONFIGS[modelType] ? modelType : 'holding_pool';
        return { ...DEFAULT_TRUST_CONFIGS[type] };
    }

    function getDefaultConfigValue(key, modelType = 'holding_pool') {
        const resolvedType = DEFAULT_TRUST_CONFIGS[modelType] ? modelType : 'holding_pool';
        const config = DEFAULT_TRUST_CONFIGS[resolvedType];
        return config[key] ?? DEFAULT_TRUST_CONFIGS.holding_pool[key];
    }

    function annualProbabilityToMonthlyRate(annualPercent) {
        const annualRate = Math.max(0, (parseFloat(annualPercent) || 0) / 100);
        if (annualRate >= 1) return 1;
        return 1 - Math.pow(1 - annualRate, 1 / 12);
    }

    function getSeniorRepayQuarters(config = {}) {
        const configured = parseInt(config.seniorRepayQuarters);
        if (configured > 0) return configured;
        return getDefaultConfigValue('seniorRepayQuarters', config.modelType || 'holding_pool');
    }

    const api = {
        DEFAULT_TRUST_CONFIGS,
        getDefaultTrustConfigByType,
        getDefaultConfigValue,
        annualProbabilityToMonthlyRate,
        getSeniorRepayQuarters
    };

    root.CashflowConfigPolicy = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
