import streamlit as st


def _legal_chat_backend(question):
    """Run search + scrape + GPT. Imports here so app loads even if deps fail."""
    from serper_search import search_az_family_law
    from azlaw_scraper import fetch_law_context
    from chatbot_law_check import ask_gpt

    links = search_az_family_law(question)
    context = fetch_law_context(links)
    answer = ask_gpt(question, context)
    return answer, links


def legal_searcher():
    """Render the Arizona Family Law chat UI (used by app.py in the Legal Research tab)."""
    st.write("Ask questions about Arizona Family Law (Title 25).")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    prompt = st.chat_input("Ask a legal question")

    if prompt:
        st.chat_message("user").write(prompt)

        with st.spinner("Researching Arizona law..."):
            try:
                answer, sources = _legal_chat_backend(prompt)
            except Exception as e:
                st.error(f"Backend error: {e}")
                return
        response = answer + "\n\nSources:\n" + "\n".join(sources)

        st.chat_message("assistant").write(response)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": response})