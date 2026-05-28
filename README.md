# Book Cover Validator

Automated quality-control platform for BookLeaf publishing covers, designed to detect layout risks with a strong focus on **badge-zone overlap** before human review.

## Overview
This project validates uploaded book covers (`PDF`/`PNG`) and classifies them as:
- `PASS`
- `REVIEW_NEEDED`

The system performs OCR, safe-zone checks, overlap detection, quality checks, annotation generation, Airtable-style sync payload generation, and customer email preview generation.

## Key Capabilities
- Critical badge-zone conflict detection (reserved bottom area for award badge)
- Author-name conflict detection against protected zones
- Left/right safe-margin validation
- Back-cover alignment signal
- OCR confidence and image-quality checks
- Annotated output for reviewer clarity
- Local Airtable sheet fallback when API keys are absent
- Local email preview artifacts for communication QA

## Tech Stack
- Frontend: React + Vite + Tailwind CSS
- Backend: FastAPI + SQLAlchemy + EasyOCR + OpenCV + PyMuPDF
- Storage: Local filesystem artifacts under `storage/`

## Project Structure
```text
book-cover-validator/
|- backend/
|  |- app/
|  |- requirements.txt
|- frontend/
|  |- src/
|- storage/
|  |- uploads/
|  |- annotations/
|  |- processed/
|     |- ocr_results/
|     |- reports/
|     |- notifications/
|     |- benchmarks/
|- README.md
```

## Local Setup (Windows PowerShell)

### 1) Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API base:
- `http://localhost:8000/api`

### 2) Frontend
Open a second terminal:
```powershell
cd frontend
npm install
npm run dev
```

Frontend:
- `http://localhost:5173`

## Environment Variables (Optional)
Set these only if you want real Airtable sync:
- `FRONTEND_URL`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_TABLE_NAME`

Without Airtable credentials, sync records are written locally:
- `storage/processed/airtable_local_sheet.csv`

## End-to-End Demo Flow
1. Open Dashboard (`/`)
2. Upload cover from Upload page using required format:
   - `ISBN_text.pdf` or `ISBN_text.png`
   - Example: `9789378652616_text.png`
3. Watch Live Pipeline stages progress in sidebar/dashboard
4. Review status, issues, annotated preview, and correction guidance
5. Open:
   - Airtable Sync page for record payload details
   - Customer Email page for generated notification details

## Input Rules
- Accepted formats: `PDF`, `PNG`
- Filename format: `13-digit-ISBN_text.ext`
- Valid examples:
  - `1234567890123_text.pdf`
  - `1234567890123_text.png`

Invalid naming is captured as `INVALID_FILENAME` with remediation details in UI.

## Benchmark
Run benchmark locally:
```powershell
cd .
$env:PYTHONPATH='backend'
python -c "from app.core.database import Base, engine; from app.models.cover_job import CoverJob; Base.metadata.create_all(bind=engine); from app.core.database import SessionLocal; from app.services.benchmark_service import run_benchmark; db=SessionLocal(); print(run_benchmark(db).model_dump()); db.close()"
```

Generated artifacts:
- `storage/processed/benchmarks/latest_benchmark.json`
- historical benchmark snapshots in `storage/processed/benchmarks/`

## API Highlights
- `POST /api/covers/upload` -> full workflow run
- `GET /api/covers/results/{job_id}` -> OCR result
- `POST /api/covers/validate/{job_id}` -> validation output
- `GET /api/covers/annotations/{job_id}` -> annotated image
- `POST /api/admin/dataset/ingest` -> ingest one sample file
- `GET /api/admin/dataset/status` -> ingestion + pipeline state
- `GET /api/admin/airtable/local-sheet` -> local sheet CSV

## Team Notes
- The UI now surfaces workflow progress as live pipeline stages.
- Invalid file cases are fully explained across Upload, Book Details, Airtable Sync, and Customer Email views.
- `.gitignore` is tuned for recruiter/demo submission while retaining benchmark evidence.

## Troubleshooting
- If OCR modules fail, ensure backend venv is active and dependencies are installed.
- If no data appears, run one ingestion/upload cycle first.
- If Airtable is not configured, verify local fallback output in:
  - `storage/processed/airtable_local_sheet.csv`

## Submission Checklist
- Backend and frontend run locally
- One valid file processed end-to-end
- One invalid filename case demonstrated
- Benchmark artifact generated
- Airtable/local-sheet and email-preview flows visible in UI
