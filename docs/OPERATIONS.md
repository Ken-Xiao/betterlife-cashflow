# Operations

## Local Deployment

Run the local server from the project root:

```bash
python3 deploy_server.py --host 127.0.0.1 --port 8767
```

Open:

```text
http://127.0.0.1:8767/
```

The server provides both static files and the local REST table API.

## Local Database

The local database file is:

```text
data/structured_finance_assets.json
```

This file is ignored by git. The server writes through a temporary file and `DATA_LOCK` to reduce corruption risk.

## Model Boundaries

Every asset row must have a real `modelId`.

- Single create: `POST /tables/structured_finance_assets`
- Batch create: `POST /tables/structured_finance_assets/batch`
- Model delete: `DELETE /tables/structured_finance_assets/by-model/:modelId`
- Model query: `GET /tables/structured_finance_assets?modelId=:modelId`

The server rejects new or updated rows without `modelId`, so future imports should not create orphan data.

## Import Policy

Batch import should set all imported rows to the selected target model. External template `modelId` values are ignored by the client during import and replaced with the selected target model id.

After import, the app clears the asset cache and reloads from the database so the UI reflects persisted rows rather than appended preview data.

## Verification

Run the main verification set:

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

