# Backend Service

FastAPI backend for Book Cover Validator.

## Run
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Base
- `http://localhost:8000/api`

## Main Workflow Endpoint
- `POST /api/covers/upload` (multipart file field: `file`)

## Notes
- Supports `PDF` and `PNG`
- Enforces filename format: `ISBN_text.ext`
- Produces OCR, validation, annotations, reports, notification payloads, and Airtable sync payloads
