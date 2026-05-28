# Book Cover Validator

Automated publishing QA system for validating book cover layout issues, with priority on detecting text overlap in the reserved **"21st Century Emily Dickinson Award"** badge zone.

## What Recruiters Can Run Directly
- Upload `ISBN_text.pdf` or `ISBN_text.png`
- Run OCR + safe-zone checks + badge-overlap detection
- Get `PASS` / `REVIEW_NEEDED` with confidence score
- Generate annotated output and correction guidance
- Generate Airtable-style sync payload + email preview
- Run benchmark and inspect `latest_benchmark.json`

## Project Structure
```text
book-cover-validator/
|- backend/
|- frontend/
|- storage/
|  |- processed/benchmarks/latest_benchmark.json
|- README.md
```

## Quick Start (Windows PowerShell)

### 1) Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2) Frontend
```powershell
cd frontend
npm install
npm run dev
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000/api`

## Core Assignment Mapping
- Input format validation (`ISBN_text.ext`): implemented
- Critical badge overlap detection: implemented
- Author-name conflict detection: implemented
- Safe margin checks: implemented
- Back-cover alignment validator: implemented
- Image quality checks: implemented
- Airtable integration (API or local fallback): implemented
- Email preview generation: implemented

## Benchmark
Run:
```powershell
cd ..
$env:PYTHONPATH='backend'
python -c "from app.core.database import Base, engine; from app.models.cover_job import CoverJob; Base.metadata.create_all(bind=engine); from app.core.database import SessionLocal; from app.services.benchmark_service import run_benchmark; db=SessionLocal(); print(run_benchmark(db).model_dump()); db.close()"
```

Latest benchmark artifact:
- `storage/processed/benchmarks/latest_benchmark.json`

## Optional Environment Variables
- `FRONTEND_URL`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_TABLE_NAME`

If Airtable credentials are missing, records are saved locally in:
- `storage/processed/airtable_local_sheet.csv`
