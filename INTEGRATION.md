# HealIN Frontend – FastAPI Integration Guide

## Quick Start

Windows PowerShell from the repo root:

```bash
# Frontend
npm.cmd install

# Copy environment template
Copy-Item .env.example .env.local

# Start development server (proxies /api → localhost:8000)
npm.cmd start
```

Backend setup now lives under `backend/`. See `backend/README.md` for the FastAPI commands and database setup steps.

---

## Architecture Overview

```
src/
├── api/index.js          ← ALL FastAPI calls live here
├── hooks/index.js        ← React data-fetching hooks wrapping the API
├── context/AppContext.jsx ← Global state (compare cart, uploaded docs, chat context)
├── components/
│   ├── common/           ← Topbar, Sidebar
│   ├── policy/           ← PolicyCard
│   ├── comparison/       ← ComparisonTable (mirrors TAXONOMY from policy_display_v2.py)
│   └── chat/             ← ChatPanel (streaming SSE consumer)
└── pages/
    ├── DashboardPage.jsx
    ├── CatalogPage.jsx
    ├── ComparePage.jsx
    ├── PolicyDetailPage.jsx
    ├── MyPoliciesPage.jsx
    └── OtherPages.jsx    ← HospitalsPage, ChatPage, ClaimChecklistPage, AdminPage

backend/
├── app/main.py          ← FastAPI app exposing the /api contract
├── comparison_pipeline/ ← Normalized schema + population scripts
├── rag_pipeline/        ← Legacy RAG utilities preserved for migration
├── data/                ← Sample extracted policy JSONs
└── storage/             ← Local JSON/file storage for hospitals/docs/logs
```

---

## Required FastAPI Endpoints

Every call in `src/api/index.js` maps to a FastAPI route.  
All routes are prefixed `/api`. In development, CRA's `"proxy": "http://localhost:8000"` in `package.json` handles CORS automatically.

### 1. Policy Catalog

```
GET  /api/variants
```
Query params: `q`, `policy_type`, `insurer`, `si_min`, `si_max`, `page`, `page_size`

Response shape:
```json
{
  "items": [
    {
      "variant_id": "uuid",
      "policy_name": "Easy Health",
      "variant_name": "Exclusive",
      "insurer_name": "Care Health",
      "policy_type": "Individual",
      "si_min_inr": 300000,
      "si_max_inr": 10000000,
      "si_options_text": "3L, 5L, 7L, 10L",
      "ped_waiting_months": 36,
      "room_rent_type": "no_limit",
      "room_rent_limit_text": null,
      "cashless_available": true,
      "maternity_covered": false,
      "restoration_covered": true,
      "opd_covered": false,
      "mental_health_covered": true,
      "ayush_covered": true,
      "extraction_date": "2024-11-01"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

```
GET  /api/variants/{variant_id}
```
Returns the full variant row (all columns from `policy_variants` JOIN `policies` JOIN `insurers`),
**plus** nested arrays:

```json
{
  "variant_id": "...",
  "policy_name": "...",
  "exclusions": [
    {
      "exclusion_name": "Cosmetic Surgery",
      "exclusion_category": "standard",
      "description": "...",
      "exception_conditions": null,
      "page_number": 14
    }
  ],
  "waiting_periods": [...],
  "sublimits": [...]
}
```

---

```
GET  /api/variants/{variant_id}/exclusions
GET  /api/variants/{variant_id}/waiting-periods
GET  /api/variants/{variant_id}/sublimits
```
Separate endpoints for lazy-loading child tables (used on detail page).

---

### 2. Comparison

```
POST /api/compare
```
Body:
```json
{ "variant_id_a": "uuid-a", "variant_id_b": "uuid-b" }
```
Response:
```json
{
  "variant_a": { /* full variant object */ },
  "variant_b": { /* full variant object */ },
  "diff_fields": ["room_rent_type", "maternity_covered", "ped_waiting_months"],
  "exclusions_a": [...],
  "exclusions_b": [...]
}
```

The frontend `ComparisonTable` component computes diffs client-side too,  
but `diff_fields` from the backend is used for the summary count banner.

---

### 3. Match Score

```
POST /api/match
```
Body:
```json
{
  "age": 32,
  "family_size": 2,
  "si_required": "1000000",
  "key_needs": ["Maternity", "No Co-pay"],
  "city": "Mumbai"
}
```
Response:
```json
[
  {
    "variant_id": "uuid",
    "score": 87,
    "rationale": "Covers maternity with 24-month waiting. No co-pay. SI up to ₹25L.",
    "variant": { /* summary variant object */ }
  }
]
```

---

### 4. Cashless Hospitals

```
GET /api/hospitals
```
Query params: `city`, `pincode`, `insurer`, `page`, `page_size`

Response:
```json
{
  "items": [
    {
      "hospital_name": "Apollo Hospital",
      "address": "Sarita Vihar",
      "city": "Delhi",
      "pincode": "110076",
      "phone": "011-2692-5858",
      "network_type": "Preferred Provider",
      "last_updated": "2025-01-15"
    }
  ]
}
```

---

### 5. Document Upload

```
POST /api/documents/upload        (multipart/form-data, field: "file")
GET  /api/documents               (list user's documents)
DELETE /api/documents/{doc_id}
```

Upload response:
```json
{
  "doc_id": "uuid",
  "filename": "star_health_policy.pdf",
  "status": "processing",   // "processing" | "ready" | "low_confidence" | "error"
  "page_count": 48,
  "extraction_confidence": 94,
  "uploaded_at": "2025-03-20T10:30:00Z"
}
```

The frontend polls or expects a webhook/SSE to update `status` from `processing` → `ready`.
Low confidence (< 80%) triggers an "Unverified" warning per the SRS.

---

### 6. Chat / Q&A (SSE Streaming)

```
POST /api/chat/stream
```
Body:
```json
{
  "message": "Is knee replacement covered?",
  "context_type": "variant",
  "context_id": "uuid",
  "history": [
    { "role": "user", "content": "What is the PED waiting period?" },
    { "role": "assistant", "content": "The PED waiting period is 36 months." }
  ]
}
```

The endpoint must return `Content-Type: text/event-stream` (SSE).  
The frontend `useChat` hook reads the stream and parses these event shapes:

```
data: {"token": "The knee"}
data: {"token": " replacement"}
data: {"token": " procedure is..."}
data: {"citations": [{"section": "Clause 4.2", "page": 12, "text": "..."}]}
data: {"caveat": "Coverage is subject to waiting periods and policy conditions."}
```

Non-streaming fallback:
```
POST /api/chat
```
Returns:
```json
{
  "answer": "...",
  "citations": [...],
  "caveat": "..."
}
```

---

### 7. Claim Checklist

```
POST /api/claim-checklist
```
Body:
```json
{
  "variant_id": "uuid",
  "claim_type": "cashless",
  "procedure": "Appendectomy"
}
```
Response:
```json
{
  "sections": [
    {
      "title": "Before Admission",
      "timeline": "48 hours before planned admission",
      "items": [
        { "label": "Call cashless helpline: 1800-xxx-xxxx", "note": "Have your policy number ready" },
        { "label": "Submit pre-auth form at hospital TPA desk", "note": null }
      ]
    }
  ]
}
```

---

### 8. Admin

```
GET    /api/admin/variants
POST   /api/admin/variants
PUT    /api/admin/variants/{id}
DELETE /api/admin/variants/{id}
GET    /api/admin/refresh-logs
POST   /api/admin/refresh/{source_id}
```

---

## FastAPI CORS Configuration

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # add production URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Auth (Future)

The API client (`src/api/index.js`) already reads `localStorage.getItem("healin_token")`  
and attaches it as `Authorization: Bearer <token>` on every request.

When you add FastAPI auth (JWT via `python-jose` or OAuth2):
1. Store the token in `localStorage` as `healin_token` after login
2. Add a `/api/auth/login` and `/api/auth/logout` endpoint
3. The frontend is already wired — no changes needed

---

## Data Freshness & Stale Warnings

The frontend shows warnings when:
- `extraction_date` is present (always shown in policy detail)
- Data older than 90 days triggers a stronger stale warning

The backend should include `extraction_date` in all variant responses.  
If a field is `null`, the frontend renders `—` (never shows "null" or crashes).

---

## SRS Feature → Frontend Route Mapping

| SRS Feature                  | Route                   | Component                      |
|------------------------------|-------------------------|--------------------------------|
| Policy catalog + search      | `/catalog`              | `CatalogPage`                  |
| Policy comparison            | `/compare`              | `ComparePage` + `ComparisonTable` |
| Match score + explanation    | `/` (Dashboard)         | `DashboardPage` match section  |
| Cashless hospital lookup     | `/hospitals`            | `HospitalsPage`                |
| Coverage/exclusion clarity   | `/policy/:id`           | `PolicyDetailPage`             |
| Clause-linked policy Q&A     | `/chat`, inline panels  | `ChatPanel`                    |
| Claim-readiness checklist    | `/checklist`            | `ClaimChecklistPage`           |
| Upload & verify own policy   | `/my-policies`          | `MyPoliciesPage`               |
| Admin & data ops             | `/admin`                | `AdminPage`                    |
