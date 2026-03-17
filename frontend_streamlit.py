from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE = "http://127.0.0.1:8000"
API_BASE_URL = os.getenv("API_BASE_URL", DEFAULT_API_BASE).rstrip("/")

st.set_page_config(page_title="LeaseFlow AI", page_icon="LF", layout="wide")


@st.cache_data(ttl=15)
def get_runtime_config() -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}/config", timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=10)
def get_history(limit: int = 100) -> list[dict[str, Any]]:
    response = requests.get(f"{API_BASE_URL}/leases", params={"limit": limit}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    return payload.get("items", [])


@st.cache_data(ttl=10)
def get_lease_details(lease_id: str) -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}/leases/{lease_id}", timeout=60)
    response.raise_for_status()
    return response.json()


def process_files_sequentially(files: list[Any]) -> list[dict[str, Any]]:
    total = len(files)
    progress = st.progress(0, text="Preparing files...")
    results: list[dict[str, Any]] = []

    for idx, uploaded_file in enumerate(files, start=1):
        progress.progress((idx - 1) / total, text=f"Processing {idx}/{total}: {uploaded_file.name}")
        file_payload = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        }

        try:
            response = requests.post(f"{API_BASE_URL}/leases/process", files=file_payload, timeout=300)
            if response.status_code == 200:
                row = response.json()
                row["ok"] = True
                results.append(row)
            else:
                results.append(
                    {
                        "filename": uploaded_file.name,
                        "status": "failed",
                        "ok": False,
                        "error": response.text.strip() or f"HTTP {response.status_code}",
                    }
                )
        except requests.RequestException as exc:
            results.append(
                {
                    "filename": uploaded_file.name,
                    "status": "failed",
                    "ok": False,
                    "error": str(exc),
                }
            )

        progress.progress(idx / total, text=f"Completed {idx}/{total}")

    return results


def try_download_pack(lease_id: str) -> tuple[str, bytes] | None:
    response = requests.get(f"{API_BASE_URL}/leases/{lease_id}/download", timeout=120)
    if response.status_code != 200:
        return None

    disposition = response.headers.get("Content-Disposition", "")
    filename = "welcome_pack.docx"
    marker = 'filename="'
    if marker in disposition:
        filename = disposition.split(marker, 1)[1].split('"', 1)[0]
    return filename, response.content


st.title("LeaseFlow AI")
st.caption("Upload lease agreements, process them in sequence, and manage every generated welcome pack from one place.")

left, right = st.columns([2, 1])
with right:
    st.subheader("System Config")
    try:
        config = get_runtime_config()
        st.json(config)
    except requests.RequestException as exc:
        st.error(f"Could not load config: {exc}")

with left:
    st.subheader("Process Lease Files")
    uploads = st.file_uploader(
        "Upload one or more lease agreements",
        type=["pdf", "docx"],
        accept_multiple_files=True,
    )
    run = st.button("Run Sequential Processing", type="primary", disabled=not uploads)

if "batch_results" not in st.session_state:
    st.session_state["batch_results"] = []

if run and uploads:
    with st.spinner("Running pipeline..."):
        st.session_state["batch_results"] = process_files_sequentially(uploads)
        get_history.clear()
        get_lease_details.clear()

batch_results: list[dict[str, Any]] = st.session_state.get("batch_results", [])
if batch_results:
    st.subheader("Latest Run")
    st.dataframe(
        [
            {
                "filename": row.get("filename", ""),
                "status": row.get("status", ""),
                "lease_id": row.get("id", ""),
                "ok": row.get("ok", False),
            }
            for row in batch_results
        ],
        use_container_width=True,
        hide_index=True,
    )

    for row in batch_results:
        if row.get("ok") is True and row.get("id"):
            with st.expander(f"Extracted: {row.get('filename', 'lease')}"):
                st.json(row.get("extracted", {}))
        elif row.get("ok") is False:
            with st.expander(f"Error: {row.get('filename', 'lease')}"):
                st.error(str(row.get("error", "Processing failed")))

st.divider()

history_col, refresh_col = st.columns([3, 1])
with history_col:
    st.subheader("History")
with refresh_col:
    if st.button("Refresh History"):
        get_history.clear()
        get_lease_details.clear()
        st.rerun()

try:
    history_items = get_history(limit=200)
except requests.RequestException as exc:
    st.error(f"Could not load history: {exc}")
    history_items = []

if history_items:
    options = {
        f"{item.get('filename', 'lease')} | {item.get('status', '')} | {item.get('id', '')}": item.get("id", "")
        for item in history_items
    }
    selected_label = st.selectbox("Select a processed lease", list(options.keys()))
    selected_id = options[selected_label]

    if selected_id:
        try:
            details = get_lease_details(selected_id)
            st.markdown("### Record Details")
            detail_left, detail_right = st.columns(2)
            with detail_left:
                st.write(f"Lease ID: {details.get('id', '')}")
                st.write(f"Filename: {details.get('filename', '')}")
                st.write(f"Status: {details.get('status', '')}")
            with detail_right:
                st.write(f"Created At: {details.get('created_at', '')}")
                st.write(f"Updated At: {details.get('updated_at', '')}")
                st.write(f"Generated Path: {details.get('storage_path_generated', '')}")

            st.markdown("### Extracted Information")
            st.json(details.get("extracted", {}))

            downloaded = try_download_pack(selected_id)
            if downloaded:
                file_name, file_bytes = downloaded
                st.download_button(
                    label="Download Welcome Pack",
                    data=file_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                st.info("Welcome pack is not available for download yet.")
        except requests.RequestException as exc:
            st.error(f"Could not load selected record: {exc}")
else:
    st.info("No history found yet. Process files to populate records.")

st.caption(f"Connected API: {API_BASE_URL}")
