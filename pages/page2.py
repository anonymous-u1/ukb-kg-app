import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Chatbot", layout="wide")
st.title("Chatbot")

st.info("🚧 RAG functionality will be integrated into this chatbot soon...")

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def rag_chat(llm, effort, api_key, base_url, prompt):
    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    if effort == "default":
        response = client.responses.create(
            model=llm,
            input=[
                {"role": "system", "content": "You are a medical researcher."},
                {"role": "user", "content": prompt}
            ],
            reasoning={"effort": effort},
            store=False
        )
    else:
        response = client.responses.create(
            model=llm,
            input=[
                {"role": "system", "content": "You are a medical researcher."},
                {"role": "user", "content": prompt}
            ],
            store=False
        )
    return response.output_text


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "How can I help you?"}
        ]


def reset_chat():
    st.session_state.messages = [
        {"role": "assistant", "content": "How can I help you?"}
    ]


init_session_state()

with st.sidebar:
    st.markdown("### OpenAI Settings")

    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        key="openai_api_key",
        help="Enter your OpenAI API key.",
    )

    openai_base_url = st.text_input(
        "Base URL",
        value=DEFAULT_BASE_URL,
        key="openai_base_url",
        help="Default: https://api.openai.com/v1",
    )

    model_name = st.text_input(
        "Model",
        value="gpt-5-mini",
        key="openai_model",
        help="For example: gpt-5, gpt-5-mini, gpt-4.1, etc.",
    )

    reasoning_effort = st.selectbox(
        "Reasoning effort",
        options=["default", "none", "minimal", "low", "medium", "high", "xhigh"],
        index=0,
        key="reasoning_effort",
        help="Leave blank to disable reasoning effort.",
    )

    st.caption(
        "GPT 5 supports minimal, low, medium (default), and high.\n\n"
        "GPT 5.2 supports none (default), low, medium, and high.\n\n"
        "GPT 5.4 supports none (default), low, medium, high, and xhigh."
    )

    if st.button("New Chat", use_container_width=True):
        reset_chat()
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

chat_enabled = bool(
    openai_api_key.strip()
    and openai_base_url.strip()
    and model_name.strip()
)

if not chat_enabled:
    st.info("Please enter your OpenAI API key, base URL, and model in the sidebar to enable chat.")

prompt = st.chat_input(
    "Ask something...",
    disabled=not chat_enabled,
)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                msg = rag_chat(
                    llm=model_name.strip(),
                    effort=reasoning_effort,
                    api_key=openai_api_key.strip(),
                    base_url=openai_base_url.strip(),
                    prompt=prompt,
                )
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

        st.write(msg)

    st.session_state.messages.append({"role": "assistant", "content": msg})