# HealIN Backend

This backend now has a FastAPI entrypoint at `backend/app/main.py`.

What is wired:

- Catalog, detail, child-table, compare, and match routes use the normalized schema from `backend/comparison_pipeline/comparison_schema.sql`.
- Hospitals, document uploads, and refresh logs use simple JSON/file storage in `backend/storage/`.
- Claim checklist is generated from the same variant fields the frontend already renders.
- Chat and chat streaming are integrated to the frontend contract and return clause-aware fallback answers without changing the frontend API.

What is still a data-pipeline task:

- Uploaded document OCR/extraction is not present in the backend bundle you added. Uploads are stored, but you still need to connect your parser to build clause/fact indexes for user-uploaded PDFs.
- Hospital network data is empty until you populate `backend/storage/hospitals.json`.
- The older RAG pipeline is preserved in `backend/rag_pipeline/` for migration/reference.

Recommended commands from the repo root:

```powershell
Copy-Item backend\.env.example backend\.env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Database setup:

1. Create the normalized database/schema using `backend/comparison_pipeline/comparison_schema.sql`.
2. Populate policy variants using `backend/comparison_pipeline/populate_v2.py` and the JSON files in `backend/data/`.
3. If you still want the legacy RAG tables, populate them separately with `backend/rag_pipeline/populate_postgres.py`.
