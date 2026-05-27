# bookCoverValidator

Book cover QA platform with OCR validation, review workflow, and local Airtable-style spreadsheet sync.

## Features
- Upload cover files and run automated QA checks
- OCR + layout validation pipeline
- Review dashboard and detailed book reports
- Customer Email and Airtable Sync pages
- Local spreadsheet sync (`storage/processed/airtable_local_sheet.csv`)

## Project Structure
```text
book-cover-validator/
|- backend/
|- frontend/
|- storage/
|- docs/
|- README.md
```

## Tech Stack
- Frontend: React, Vite, TailwindCSS
- Backend: FastAPI, Python 3.11
- Storage: local filesystem directories under `storage/`

## Local Run

### Backend
```bash
cd backend
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend default: `http://localhost:5173`
Backend default: `http://localhost:8000`

## Environment Variables (Backend)
- `FRONTEND_URL` (for production CORS)
- `AIRTABLE_API_KEY` (optional)
- `AIRTABLE_BASE_ID` (optional)
- `AIRTABLE_TABLE_NAME` (optional)

If Airtable env vars are not configured, sync data is stored locally in:
- `storage/processed/airtable_local_sheet.csv`

## Deployment (Render)
- Backend: Render Web Service (`backend` root)
- Frontend: Render Static Site (`frontend` root)
- Set frontend env `VITE_API_BASE_URL` to your backend `/api` URL
- Set backend env `FRONTEND_URL` to your frontend URL
