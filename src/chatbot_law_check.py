import os

from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def _attorney_signature_instruction() -> str:
    """Build system-prompt text from env (same vars as billing PDF)."""
    lines = [
        os.getenv("ATTORNEY_NAME", "").strip(),
        os.getenv("ATTORNEY_ADDRESS", "").strip(),
        os.getenv("ATTORNEY_PHONE", "").strip(),
        os.getenv("ATTORNEY_EMAIL", "").strip(),
    ]
    lines = [x for x in lines if x]
    if not lines:
        return ""
    block = "\n".join(lines)
    return (
        " When drafting client emails, end with this signature block (use these lines as given):\n"
        f"{block}"
    )


def _looks_like_email_draft_request(question: str) -> bool:
    """Heuristic: only attach signature instructions when the user wants an email/letter."""
    q = (question or "").lower()
    needles = (
        "email",
        "e-mail",
        "write to ",
        "draft a letter",
        "letter to ",
        "message to ",
        "correspond",
        "send a ",
    )
    return any(n in q for n in needles)


# Cap statute context to reduce oversized API requests.
_MAX_STATUTE_CHARS = 22_000
_TRUNC_NOTE = "\n\n[... truncated to stay within API size limits. ...]"


def _clip_chars(text, max_chars):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + _TRUNC_NOTE


def ask_gpt(question, context):
    """
    question: attorney instruction / question.
    context: statute excerpts from Arizona law scrape.
    """
    question = (question or "").strip()
    statute_only = _clip_chars(context or "", _MAX_STATUTE_CHARS)
    prompt = f"""
You are an Arizona family law research assistant.

Answer the question using ONLY the legal text provided.

Provide citations to the statute numbers when possible.

LEGAL TEXT:
{statute_only}

QUESTION:
{question}
"""
    system = (
        "You are an Arizona family law research assistant. Answer using only the legal text provided. "
        "Cite statute numbers when possible."
    )
    if _looks_like_email_draft_request(question):
        system += _attorney_signature_instruction()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""
