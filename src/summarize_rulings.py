import base64
import datetime
import uuid

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from billing_payment import _load_clients, _normalize_rulings, _save_clients
from config import OPENAI_API_KEY

CHATGPT_URL = "https://chatgpt.com/"

_SS_SUMMARY = "rulings_summary_text"
_SS_CLIENT_IDX = "rulings_summary_client_idx"
_SS_SAVED = "rulings_summary_saved_to_client"


def _clipboard_copy_button_top_right(text: str, button_label: str = "Copy") -> None:
    """Tiny HTML button that copies UTF-8 text (Streamlit component iframe)."""
    if not (text or "").strip():
        return
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    btn_id = f"rulings-copy-{uuid.uuid4().hex[:12]}"
    safe_label = button_label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    components.html(
        f"""
        <div style="text-align:right;padding:0.1rem 0 0.35rem 0;">
          <button type="button" id="{btn_id}"
            style="cursor:pointer;padding:0.35rem 0.85rem;border-radius:6px;border:1px solid rgba(49,51,63,0.2);background:#f0f2f6;font-size:0.875rem;">
            {safe_label}
          </button>
        </div>
        <script>
        (function() {{
          const b64 = "{b64}";
          const btn = document.getElementById("{btn_id}");
          if (!btn) return;
          btn.addEventListener("click", function() {{
            try {{
              const bin = atob(b64);
              const bytes = new Uint8Array(bin.length);
              for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
              const decoded = new TextDecoder("utf-8").decode(bytes);
              navigator.clipboard.writeText(decoded);
            }} catch (e) {{ console.error(e); }}
          }});
        }})();
        </script>
        """,
        height=52,
    )


def _append_summary_to_client_rulings(client_idx: int, summary_text: str) -> None:
    """Append one ruling row: date = today, ruling_name = full summary body."""
    text = (summary_text or "").strip()
    if not text:
        return
    clients = _load_clients()
    if client_idx is None or not (0 <= client_idx < len(clients)):
        return
    c = dict(clients[client_idx])
    rulings = list(_normalize_rulings(c.get("rulings")))
    rulings.append(
        {
            "date": datetime.date.today().isoformat(),
            "ruling_name": text,
        }
    )
    c["rulings"] = rulings
    clients[client_idx] = c
    _save_clients(clients)


def _build_rulings_bundle(client: dict | None, pasted_text: str) -> str:
    parts = []
    client = client or {}
    name = str(client.get("name", "")).strip()
    cn = str(client.get("case_number", "")).strip()
    if name or cn:
        if name and cn:
            parts.append(f"Client: {name} (Case no. {cn})")
        elif name:
            parts.append(f"Client: {name}")
        else:
            parts.append(f"Case no. {cn}")

    rulings = _normalize_rulings(client.get("rulings"))
    if rulings:
        lines = [f"- {r['date']} — {r['ruling_name']}" for r in rulings]
        parts.append("Rulings on file:\n" + "\n".join(lines))

    pasted = (pasted_text or "").strip()
    if pasted:
        parts.append("Additional ruling / order text (pasted):\n" + pasted)

    return "\n\n".join(parts).strip()


def _summarize_with_openai(bundle: str, attorney_notes: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set (add it to your .env).")

    notes = (attorney_notes or "").strip()
    bundle = (bundle or "").strip()
    if len(bundle) > 50_000:
        bundle = bundle[:50_000].rstrip() + "\n\n[Truncated for API size; paste shorter excerpts if needed.]"
    user_content = f"""
Summarize the following court ruling(s) / order(s) for an Arizona family law attorney.
Summarize ALL the relevant information from the ruling(s) / order(s) for the client.
Prioritize any outcome that helps the client, then give a balanced picture.
Use clear headings and bullet points. Include important dates and deadlines mentioned.
Summarize the ruling(s) / order(s) for both parties.
Put the client's ruling(s) / order(s) first, then the other party's ruling(s) / order(s).

MATERIAL:
{bundle}

{f"ATTORNEY NOTES / FOCUS:{chr(10)}{notes}" if notes else ""}
"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a paralegal summarizing court documents for a licensed Arizona family law attorney. "
                    "Stick to the text supplied; flag uncertainty clearly."
                    "Output the summary in the same language as the input text."
                ),
            },
            {"role": "user", "content": user_content},
        ],
        max_tokens=2048,
    )
    return response.choices[0].message.content or ""


def summarize_rulings_page():
    """Streamlit UI aligned with the rest of Roman Kostenko's Law Office app."""
    st.subheader("Summarize court rulings")
    if st.session_state.pop("_ruling_just_saved", False):
        st.success("Saved this summary to the client's rulings.")
    st.caption(
        "Pull rulings from a client record, add pasted order text if needed, then generate a summary. "
    )

    top_a = st.columns([1])[0]
    with top_a:
        st.link_button("Open ChatGPT in browser", CHATGPT_URL)

    clients = _load_clients()
    selected = None
    sel_idx = None
    if not clients:
        st.info(
            "No clients in `db/client.json` yet. Add a client under **Billing & Payment**, "
        )
    else:
        labels = ["— Find Your Client Here—"] + [
            f"{i}: {c.get('name', 'Unnamed')}" for i, c in enumerate(clients)
        ]
        choice = st.selectbox("Client (for rulings saved on file)", options=labels, index=0)
        if not choice.startswith("—"):
            sel_idx = int(choice.split(":", 1)[0].strip())
            selected = clients[sel_idx]

    pasted = st.text_area(
        "Paste ruling / order / minute entry text (optional)",
        height=160,
        placeholder="Paste excerpts or full text from a PDF or court portal…",
    )

    notes = st.text_input(
        "Focus or instructions (optional)",
        placeholder="e.g. Emphasize parenting time and child support paragraphs.",
    )

    if selected:
        rulings = _normalize_rulings(selected.get("rulings"))
        with st.expander(
            f"Rulings on file for {selected.get('name', 'client')}", expanded=bool(rulings)
        ):
            if rulings:
                cname = selected.get("name", "client")
                copy_text = (
                    f"Rulings on file — {cname}\n\n"
                    + "\n\n".join(f"{r['date']}\n{r['ruling_name']}" for r in rulings)
                )
                head_l, head_r = st.columns([4, 1])
                with head_l:
                    st.caption("Saved rulings for this client")
                with head_r:
                    _clipboard_copy_button_top_right(copy_text, button_label="Copy")
                for r in rulings:
                    st.write(f"**{r['date']}** — {r['ruling_name']}")
            else:
                st.caption(
                    "No rulings saved yet. Use **Billing & Payment → Update Client**, or paste text above."
                )

    bundle = _build_rulings_bundle(selected, pasted)
    has_paste = bool(pasted.strip())
    has_stored = bool(selected and _normalize_rulings(selected.get("rulings")))

    if not has_paste and not has_stored:
        st.warning("Choose a client with saved rulings, paste order text, or both — then click **Summarize rulings**.")

    if st.button("Summarize rulings", type="primary", disabled=not (has_paste or has_stored)):
        with st.spinner("Generating summary…"):
            try:
                out = _summarize_with_openai(bundle, notes)
            except Exception as e:
                st.error(str(e))
                return
        st.session_state[_SS_SUMMARY] = out
        st.session_state[_SS_CLIENT_IDX] = sel_idx
        st.session_state.pop(_SS_SAVED, None)

    summary_text = st.session_state.get(_SS_SUMMARY)
    summary_client_idx = st.session_state.get(_SS_CLIENT_IDX)
    if summary_text:
        hdr_l, hdr_r = st.columns([4, 1])
        with hdr_l:
            st.markdown("### Summary")
        with hdr_r:
            can_save = summary_client_idx is not None
            already_saved = bool(st.session_state.get(_SS_SAVED))
            if st.button(
                "Save for the Client",
                disabled=not can_save or already_saved,
                use_container_width=True,
                key="save_ruling_summary_for_client",
            ):
                _append_summary_to_client_rulings(summary_client_idx, summary_text)
                st.session_state["_ruling_just_saved"] = True
                st.session_state[_SS_SAVED] = True
                st.rerun()
        if not can_save:
            st.caption("Select a **client** (not “Pasted text only”) before summarizing to enable saving.")
        elif already_saved:
            st.caption("This summary is already saved to the client’s rulings.")
        st.code(summary_text, language="text")
