"""
PDF upload pipeline for the legal assistant: extract text, summarize with OpenAI,
match a client in client.json, then save a ruling or append case description.
"""

from __future__ import annotations

import io
import json
import re
from datetime import date
from typing import Any

from openai import OpenAI

from billing_payment import _load_clients, _normalize_rulings, _save_clients
from config import OPENAI_API_KEY

MAX_PDF_TEXT_CHARS = 100_000

# OpenAI function-tool schema (for agents / Chat Completions tools=…)
PDF_CLIENT_INTEL_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "save_pdf_insights_to_client",
        "description": (
            "After reading a PDF, provide structured fields so the app can match "
            "client.json and store a court ruling or case notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Attorney-facing summary; favorable outcome first if applicable.",
                },
                "is_court_ruling": {
                    "type": "boolean",
                    "description": "True for orders, rulings, minute entries, judge decisions.",
                },
                "client_name": {
                    "type": "string",
                    "description": "Client name as in firm records (match client.json name).",
                },
                "ruling_date": {
                    "type": "string",
                    "description": "Ruling date YYYY-MM-DD if known, else empty.",
                },
                "ruling_short_title": {
                    "type": "string",
                    "description": "One-line label for rulings list; empty if not a ruling.",
                },
                "case_notes_for_description": {
                    "type": "string",
                    "description": "If not a ruling, concise facts to store in case description.",
                },
            },
            "required": [
                "summary",
                "is_court_ruling",
                "client_name",
                "ruling_date",
                "ruling_short_title",
                "case_notes_for_description",
            ],
        },
    },
}


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Install pypdf to read PDFs: pip install pypdf") from e

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _truncate(text: str, limit: int = MAX_PDF_TEXT_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[... document truncated ...]"


def _iso_date_or_today(s: str) -> str:
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return date.today().isoformat()


def find_client_index_by_name(clients: list[dict], name_from_doc: str) -> int:
    if not name_from_doc or not str(name_from_doc).strip():
        return -1
    target = str(name_from_doc).strip().lower()
    for i, c in enumerate(clients):
        cn = str(c.get("name", "")).strip().lower()
        if cn == target:
            return i
    for i, c in enumerate(clients):
        cn = str(c.get("name", "")).strip().lower()
        if not cn:
            continue
        if target in cn or cn in target:
            return i
    return -1


def _analyze_pdf_text(pdf_text: str, filename: str) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    body = _truncate(pdf_text) if pdf_text else "[NO_TEXT_EXTRACTED_FROM_PDF]"
    user_msg = (
        f"Filename: {filename}\n\n"
        "Document text:\n"
        f"{body}\n\n"
        "Respond with a single JSON object only (no markdown), keys: "
        "summary (string), is_court_ruling (boolean), client_name (string), "
        "ruling_date (string YYYY-MM-DD or empty), ruling_short_title (string), "
        "case_notes_for_description (string, empty if this is a ruling)."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a paralegal for an Arizona family law practice. "
                    "Read the document text. Decide if it is a court ruling/order/decision. "
                    "Infer the client name that should match law firm records (party the firm "
                    "likely represents when obvious; otherwise best full name on the caption). "
                    "Summaries: put favorable outcome first when applicable. "
                    "Output valid JSON only."
                ),
            },
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "summary": raw[:4000],
            "is_court_ruling": False,
            "client_name": "",
            "ruling_date": "",
            "ruling_short_title": "",
            "case_notes_for_description": "",
        }


def _append_case_description(client: dict, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    existing = (client.get("case_description") or "").strip()
    sep = "\n\n---\n\n" if existing else ""
    client["case_description"] = f"{existing}{sep}{text}"


def apply_analysis_to_clients(clients: list[dict], analysis: dict[str, Any]) -> tuple[list[dict], str]:
    """Mutates a copy of the matched client and returns (new_clients_list, status_message)."""
    summary = str(analysis.get("summary", "") or "").strip()
    is_ruling = bool(analysis.get("is_court_ruling"))
    client_name = str(analysis.get("client_name", "") or "").strip()
    ruling_date = str(analysis.get("ruling_date", "") or "").strip()
    ruling_title = str(analysis.get("ruling_short_title", "") or "").strip()
    case_notes = str(analysis.get("case_notes_for_description", "") or "").strip()

    idx = find_client_index_by_name(clients, client_name)
    if idx < 0:
        names = [c.get("name", "") for c in clients]
        return clients, (
            f"No client matched for name “{client_name or '(none)'}”. "
            f"Known clients: {names}. Nothing was saved.\n\nSummary:\n{summary}"
        )

    updated = [dict(c) for c in clients]
    c = dict(updated[idx])
    if "rulings" not in c or not isinstance(c.get("rulings"), list):
        c["rulings"] = []

    if is_ruling:
        if ruling_title.strip():
            title = ruling_title.strip()
        elif summary:
            title = (summary[:200] + "…") if len(summary) > 200 else summary
        else:
            title = "Court ruling"
        rd = _iso_date_or_today(ruling_date)
        rulings = _normalize_rulings(c["rulings"])
        rulings.append({"date": rd, "ruling_name": title.strip()})
        c["rulings"] = rulings
        updated[idx] = c
        _save_clients(updated)
        return updated, (
            f"Saved court ruling for **{c.get('name', '')}** ({rd}: {title.strip()}).\n\n{summary}"
        )

    block = "\n\n".join(x for x in (summary, case_notes) if x).strip() or summary
    _append_case_description(c, block)
    updated[idx] = c
    _save_clients(updated)
    return updated, (
        f"Appended document notes to **case description** for **{c.get('name', '')}**.\n\n{summary}"
    )


def process_pdf_bytes_and_update_client(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    End-to-end: extract PDF text, analyze with OpenAI, update client.json.

    Returns a dict with keys: ok (bool), summary, message (user-facing), filename,
    error (optional).
    """
    try:
        text = extract_pdf_text(pdf_bytes)
    except Exception as e:
        return {
            "ok": False,
            "summary": "",
            "message": f"Could not read PDF: {e}",
            "filename": filename,
            "error": str(e),
        }

    try:
        analysis = _analyze_pdf_text(text, filename)
    except Exception as e:
        return {
            "ok": False,
            "summary": "",
            "message": f"Analysis failed: {e}",
            "filename": filename,
            "error": str(e),
        }

    clients = _load_clients()
    if not clients:
        return {
            "ok": False,
            "summary": str(analysis.get("summary", "") or ""),
            "message": "client.json has no clients; nothing was saved.",
            "filename": filename,
        }

    _, msg = apply_analysis_to_clients(clients, analysis)
    ok = "Nothing was saved" not in msg and "no clients" not in msg.lower()
    return {
        "ok": ok,
        "summary": str(analysis.get("summary", "") or ""),
        "message": msg,
        "filename": filename,
    }


def run_pdf_intel_on_uploads(uploaded_files: list[Any]) -> str | None:
    """Process each PDF in Streamlit UploadedFile list; returns combined assistant text or None."""
    if not uploaded_files:
        return None
    pdfs = [f for f in uploaded_files if getattr(f, "name", "").lower().endswith(".pdf")]
    if not pdfs:
        return None
    blocks: list[str] = []
    for f in pdfs:
        data = f.getvalue()
        result = process_pdf_bytes_and_update_client(data, f.name)
        blocks.append(
            f"**{result.get('filename', 'document.pdf')}**\n\n{result.get('message', '')}"
        )
    return "\n\n---\n\n".join(blocks)


def save_pdf_insights_to_client(
    summary: str,
    is_court_ruling: bool,
    client_name: str,
    ruling_date: str,
    ruling_short_title: str,
    case_notes_for_description: str,
) -> str:
    """
    Callable matching PDF_CLIENT_INTEL_TOOL — for tool-calling agents.
    Persists using the same rules as PDF upload analysis.
    """
    analysis = {
        "summary": summary,
        "is_court_ruling": is_court_ruling,
        "client_name": client_name,
        "ruling_date": ruling_date,
        "ruling_short_title": ruling_short_title,
        "case_notes_for_description": case_notes_for_description,
    }
    clients = _load_clients()
    if not clients:
        return "No clients in client.json."
    _, msg = apply_analysis_to_clients(clients, analysis)
    return msg
