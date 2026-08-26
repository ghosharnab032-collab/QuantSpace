# FastAPI Backend — Step 1

This is the initial FastAPI application skeleton.

## Run

From the project root:

```powershell
python -m server.main
```

The API should start at:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
GET /api/v1/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Test

Install backend dependencies:

```powershell
pip install -r requirements-backend.txt
```

Then:

```powershell
python -m pytest tests/test_health.py -v
```

## Scope

This step intentionally contains only:

- FastAPI application
- Environment configuration
- Health endpoint
- Minimal backend test

Authentication, database access, entitlements, quant routes, and Razorpay integration are added in later steps.
