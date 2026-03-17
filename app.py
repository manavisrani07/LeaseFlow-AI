from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from extract_lease_groq import LeaseProcessingResult, build_processor_from_env, sanitize_filename

app = FastAPI(title="Lease Extraction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _result_to_response(result: LeaseProcessingResult) -> dict[str, Any]:
    return {
        "id": result.lease_id,
        "filename": result.filename,
        "status": result.status,
        "storage_path_original": result.storage_path_original,
        "storage_path_generated": result.storage_path_generated,
        "extracted": result.extracted,
    }


async def _process_uploaded_file(file: UploadFile) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported")

    try:
        processor = build_processor_from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        with TemporaryDirectory() as tmp_dir:
            safe_name = sanitize_filename(file.filename)
            temp_path = Path(tmp_dir) / safe_name
            temp_path.write_bytes(content)

            result: LeaseProcessingResult = processor.process_file(temp_path, filename=file.filename)
        return _result_to_response(result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc


@app.post("/leases/process")
async def process_lease(file: UploadFile = File(...)) -> dict[str, Any]:
    return await _process_uploaded_file(file)


@app.post("/leases/process-batch")
async def process_leases_batch(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results: list[dict[str, Any]] = []
    for item in files:
        try:
            processed = await _process_uploaded_file(item)
            processed["ok"] = True
            results.append(processed)
        except HTTPException as exc:
            results.append(
                {
                    "filename": item.filename,
                    "ok": False,
                    "status": "failed",
                    "error": exc.detail,
                }
            )

    completed = sum(1 for row in results if row.get("ok") is True)
    failed = len(results) - completed
    return {
        "total": len(results),
        "completed": completed,
        "failed": failed,
        "results": results,
    }


@app.get("/leases/{lease_id}")
def get_lease(lease_id: str) -> dict:
    try:
        processor = build_processor_from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    row = processor.get_lease_row(lease_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lease not found")
    return row


@app.get("/leases")
def list_leases(limit: int = 100) -> dict[str, Any]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    try:
        processor = build_processor_from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    return {"items": processor.list_leases(limit=limit)}


@app.get("/config")
def get_config() -> dict[str, str]:
    try:
        processor = build_processor_from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    config = processor.runtime_config()
    config["app_name"] = "LeaseFlow AI"
    return config


@app.get("/leases/{lease_id}/download")
def download_welcome_pack(lease_id: str) -> Response:
    try:
        processor = build_processor_from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    try:
        filename, file_bytes = processor.download_generated_welcome_pack(lease_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Download failed: {exc}") from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
