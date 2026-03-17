# Lease Welcome Pack Generator

This project processes lease agreements (`.pdf` or `.docx`), extracts structured lease fields using Groq LLM, generates a Tenant Welcome Pack DOCX from a template, stores both files in Supabase Storage, stores metadata and extracted fields in Supabase Postgres, and lets users download the generated welcome pack.

## Features

- Upload lease file in PDF or DOCX format
- Extract lease fields via Groq LLM
- Generate welcome pack DOCX from template (`materials/Tenant Welcome Pack Template.docx`)
- Persist processing lifecycle and extracted JSON in Supabase table `leases`
- Upload original lease and generated DOCX to Supabase bucket `leases`
- FastAPI backend with REST endpoints
- Minimal Streamlit frontend for upload, extraction preview, and download

## Architecture

1. User uploads a lease file from Streamlit
2. Streamlit calls FastAPI `POST /leases/process`
3. FastAPI uses `LeaseProcessor` (`extract_lease_groq.py`)
4. Processor inserts `processing` row into Supabase table
5. Processor uploads original file to Supabase Storage
6. Processor extracts text + calls Groq + normalizes fields
7. Processor generates welcome pack DOCX from template
8. Processor uploads generated DOCX to Storage
9. Processor updates DB row to `completed` (or `failed` on errors)
10. Streamlit calls `GET /leases/{id}/download` and offers file download

## Supabase Requirements

### Storage bucket

- Name: `leases`

### Database table

- Name: `leases`
- Schema:
  - `id uuid primary key`
  - `filename text`
  - `storage_path_original text`
  - `storage_path_generated text`
  - `status text`
  - `extracted jsonb`
  - `model_response text`
  - `created_at timestamptz`
  - `updated_at timestamptz`

## Environment Variables

Create a `.env` file in project root:

```dotenv
GROQ_API_KEY=your_groq_key
SUPBASE_URL=https://your-project.supabase.co
SUPBASE_SERVICE_KEY=your_supabase_service_role_key
GROQ_MODEL=openai/gpt-oss-120b
API_BASE_URL=http://127.0.0.1:8000
```

Notes:
- The code intentionally uses `SUPBASE_URL` and `SUPBASE_SERVICE_KEY` to match your existing naming.
- `API_BASE_URL` is used by Streamlit frontend.

## Local Setup

1. Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run FastAPI backend

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

4. Run Streamlit frontend (new terminal)

```bash
streamlit run frontend_streamlit.py --server.port 8501
```

5. Open Streamlit UI

- http://127.0.0.1:8501

## API Endpoints

### `GET /health`

Health check.

### `POST /leases/process`

Upload and process a lease file.

- Content type: `multipart/form-data`
- Form field: `file`
- Supported files: `.pdf`, `.docx`

Example response:

```json
{
  "id": "ef65a8cc-37c8-44c0-a6d8-d341e13b8f17",
  "filename": "Lease Agreement - Raj Patel.docx",
  "status": "completed",
  "storage_path_original": "originals/ef65a8cc-37c8-44c0-a6d8-d341e13b8f17/Lease_Agreement_-_Raj_Patel.docx",
  "storage_path_generated": "generated/ef65a8cc-37c8-44c0-a6d8-d341e13b8f17/Lease_Agreement_-_Raj_Patel_welcome_pack.docx",
  "extracted": {
    "tenant_name": "Raj Patel",
    "property_address": "..."
  }
}
```

### `GET /leases/{lease_id}`

Fetch lease row metadata from DB.

### `GET /leases/{lease_id}/download`

Download generated welcome pack DOCX for a processed lease ID.

## Streamlit Frontend

File: `frontend_streamlit.py`

What it does:
- Lets user upload PDF or DOCX
- Sends file to backend `/leases/process`
- Displays extracted fields JSON
- Downloads generated welcome pack through `/leases/{id}/download`

## Deployability

This project can be deployed as two services:

- Backend service: FastAPI (`uvicorn app:app`)
- Frontend service: Streamlit (`streamlit run frontend_streamlit.py`)

### Option A: Deploy separately (recommended)

1. Deploy FastAPI service (Render/Railway/Fly/EC2)
2. Set backend env vars (`GROQ_API_KEY`, `SUPBASE_URL`, `SUPBASE_SERVICE_KEY`, `GROQ_MODEL`)
3. Deploy Streamlit service (Streamlit Community Cloud/Render)
4. Set Streamlit `API_BASE_URL` to deployed FastAPI URL

### Option B: Dockerize each service

Use separate Dockerfiles (one for API, one for Streamlit) and set env vars in platform settings.

## Troubleshooting

- `Only .pdf and .docx files are supported`:
  - Upload a valid file type
- `Configuration error`:
  - Check `.env` for required keys
- `Processing failed`:
  - Check API logs for Groq/Supabase errors
- Download endpoint returns not found:
  - Confirm processing completed and `storage_path_generated` exists in DB row

## Security Notes

- Do not commit `.env` to version control
- Rotate keys immediately if secrets are exposed
- For production, set stricter CORS origins in `app.py` instead of wildcard `*`

## Project Files

- `app.py`: FastAPI endpoints
- `extract_lease_groq.py`: processing service and Supabase/Groq integration
- `frontend_streamlit.py`: Streamlit upload and download UI
- `materials/Tenant Welcome Pack Template.docx`: DOCX template
- `requirements.txt`: dependencies
