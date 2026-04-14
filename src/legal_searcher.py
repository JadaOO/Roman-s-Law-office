import streamlit as st


class ResearchAgent:
    """Arizona legal search and drafting (email, petition guidance, research) via GPT."""

    @staticmethod
    def run(user_message: str):
        from serper_search import search_az_family_law
        from azlaw_scraper import fetch_law_context
        from chatbot_law_check import ask_gpt

        search_q = (user_message or "").strip() or "Arizona family law"
        links = search_az_family_law(search_q)
        context = fetch_law_context(links)
        q = user_message.strip()
        answer = ask_gpt(q, context)
        return answer, links


def legal_searcher():
    """

    """
    st.write("Hi Roman, how can I help you today?")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.code(msg["content"], language="text")
            else:
                st.write(msg["content"])

    with st.form("legal_chat_inline_form", clear_on_submit=True):
        col_input, col_send = st.columns([8, 1.4])
        with col_input:
            prompt = st.text_input(
                "Message",
                placeholder="research AZ law, write email to X about Y, draft petitions and more...",
                key="legal_prompt_inline",
                label_visibility="collapsed",
            )
        with col_send:
            submitted = st.form_submit_button("Send")

    if submitted and prompt.strip():
        prompt = prompt.strip()
        st.chat_message("user").write(prompt)

        with st.spinner("Legal search and drafting…"):
            try:
                answer, sources = ResearchAgent.run(prompt)
            except Exception as e:
                st.error(f"Backend error: {e}")
                return

        if sources:
            src_lines = "\n".join(f"- [{url}]({url})" for url in sources)
            response = answer + "\n\n**Sources**\n\n" + src_lines
        else:
            response = answer

        with st.chat_message("assistant"):
            st.code(response, language="text")

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": response})
