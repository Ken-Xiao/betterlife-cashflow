(function attachExportAudit(root) {
    'use strict';

    function quoteExcelSheetName(sheetName) {
        const safeName = String(sheetName || '').replace(/'/g, "''");
        return `'${safeName}'`;
    }

    function normalizeAuditItem(item, index) {
        return {
            index: index + 1,
            label: item.label || item.name || `校验项${index + 1}`,
            jsValue: item.jsValue ?? item.value ?? 0,
            formula: item.formula || '',
            tolerance: item.tolerance ?? 0.01,
            note: item.note || ''
        };
    }

    function buildFormulaAuditRows(items) {
        return (items || []).map(normalizeAuditItem);
    }

    function buildRowFormulaAuditRows(rows) {
        return (rows || []).map((row, index) => ({
            rowNumber: row.rowNumber ?? index + 2,
            button: row.button || row.sourceButton || '',
            field: row.field || row.label || '',
            jsValue: row.jsValue ?? row.value ?? 0,
            formula: row.formula || '',
            tolerance: row.tolerance ?? 0.01,
            note: row.note || ''
        }));
    }

    const api = {
        quoteExcelSheetName,
        buildFormulaAuditRows,
        buildRowFormulaAuditRows
    };

    root.CashflowExportAudit = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
