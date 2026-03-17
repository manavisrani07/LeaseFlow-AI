from __future__ import annotations

import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE = "http://127.0.0.1:8000"
API_BASE_URL = os.getenv("API_BASE_URL", DEFAULT_API_BASE).rstrip("/")

st.set_page_config(page_title="Lease Welcome Pack Generator", page_icon="DOC", layout="centered")
st.title("Lease Welcome Pack Generator")
st.caption("Upload a lease agreement (.pdf or .docx), extract fields with Groq, and download the generated welcome pack.")

uploaded_file = st.file_uploader("Upload lease agreement", type=["pdf", "docx"])

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_download" not in st.session_state:
    st.session_state["last_download"] = None

if st.button("Generate Welcome Pack", type="primary", disabled=uploaded_file is None):
    if uploaded_file is None:
        st.warning("Please upload a lease agreement file first.")
    else:
        file_suffix = Path(uploaded_file.name).suffix.lower()
        if file_suffix not in {".pdf", ".docx"}:
            st.error("Only PDF and DOCX files are supported.")
        else:
            with st.spinner("Processing lease document..."):
                try:
                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    }
                    response = requests.post(f"{API_BASE_URL}/leases/process", files=files, timeout=300)
                    if response.status_code != 200:
                        error_text = response.text.strip() or "Unknown API error"
                        st.error(f"Processing failed ({response.status_code}): {error_text}")
                    else:
                        payload = response.json()
                        st.session_state["last_result"] = payload
                        st.success("Welcome pack generated successfully.")

                        lease_id = payload.get("id")
                        if lease_id:
                            download_response = requests.get(
                                f"{API_BASE_URL}/leases/{lease_id}/download",
                                timeout=120,
                            )
                            if download_response.status_code == 200:
                                st.session_state["last_download"] = {
                                    "filename": payload.get("filename", "welcome_pack").rsplit(".", 1)[0]
                                    + "_welcome_pack.docx",
                                    "bytes": download_response.content,
                                }
                            else:
                                st.session_state["last_download"] = None
                                st.warning("Generated file is saved in storage but could not be downloaded right now.")
                except requests.RequestException as exc:
                    st.error(f"API connection failed: {exc}")

result = st.session_state.get("last_result")
if result:
    st.subheader("Extraction Result")
    st.write(f"Lease ID: {result.get('id', '')}")
    st.write(f"Status: {result.get('status', '')}")
    st.json(result.get("extracted", {}))

file_info = st.session_state.get("last_download")
if file_info and file_info.get("bytes"):
    st.download_button(
        label="Download Welcome Pack",
        data=file_info["bytes"],
        file_name=file_info.get("filename", "welcome_pack.docx"),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

st.divider()
st.caption(f"API Base URL: {API_BASE_URL}")
