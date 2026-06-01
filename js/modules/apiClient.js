(function attachApiClient(root) {
    'use strict';

    function createCashflowApiClient(options = {}) {
        const baseUrl = options.baseUrl || 'tables/structured_finance_assets';
        const fetcher = options.fetcher || root.fetch;
        const getCurrentModelId = options.getCurrentModelId || (() => 'default');
        const maxLimit = options.maxLimit || 1000;

        async function requestJson(url, requestOptions) {
            const response = await fetcher(url, requestOptions);
            if (!response.ok) {
                throw new Error(`API request failed: ${response.status}`);
            }
            return response.json();
        }

        function buildAssetQuery({ page = 1, limit = 100, modelId = null, q = '' } = {}) {
            const params = new URLSearchParams();
            params.append('page', String(page));
            params.append('limit', String(Math.min(limit, maxLimit)));
            if (modelId) params.append('modelId', modelId);
            if (q) params.append('q', q);
            return `${baseUrl}?${params.toString()}`;
        }

        async function getAssets(page = 1, limit = 100, q = '') {
            const modelId = getCurrentModelId();
            return requestJson(buildAssetQuery({ page, limit, modelId, q }));
        }

        async function createAssetsBatch(rows, modelId = getCurrentModelId()) {
            const timestamp = Date.now();
            const normalizedRows = (rows || []).map((row, index) => ({
                ...row,
                modelId,
                _batchId: `batch_${timestamp}`,
                _batchIndex: index
            }));
            return requestJson(`${baseUrl}/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rows: normalizedRows })
            });
        }

        async function deleteAssetsByModel(modelId = getCurrentModelId()) {
            return requestJson(`${baseUrl}/by-model/${encodeURIComponent(modelId)}`, { method: 'DELETE' });
        }

        return {
            baseUrl,
            maxLimit,
            buildAssetQuery,
            getAssets,
            createAssetsBatch,
            deleteAssetsByModel
        };
    }

    const api = { createCashflowApiClient };
    root.CashflowApiClient = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : window);
