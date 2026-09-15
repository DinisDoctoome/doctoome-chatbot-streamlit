"""Minimal Streamlit testing client for the Doctoome chatbot."""

from typing import Any

import streamlit as st

from frontend_api import ChatApiError, send_message


def initialize_state() -> None:
    st.session_state.setdefault("conversation_id", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_options", [])


def reset_conversation() -> None:
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.pending_options = []


def _append_assistant_response(response: dict[str, Any]) -> None:
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response["message"],
            "url": response["url"],
        }
    )
    if response["conversation_id"] is not None:
        st.session_state.conversation_id = response["conversation_id"]
    st.session_state.pending_options = response["options"]


def submit_message(message: str, display_message: str | None = None) -> None:
    st.session_state.messages.append(
        {"role": "user", "content": display_message or message}
    )
    st.session_state.pending_options = []
    try:
        response = send_message(message, st.session_state.conversation_id)
    except ChatApiError as exc:
        st.session_state.messages.append({"role": "error", "content": str(exc)})
        return
    _append_assistant_response(response)


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        st.text(message["content"])
        if message.get("url"):
            st.markdown(f"[{message['url']}]({message['url']})")


def render_option(option: dict[str, Any]) -> None:
    details = "\n".join([option["label"], *option.get("offices", [])])
    if st.button(details, key=f"option-{option['number']}"):
        submit_message(str(option["number"]), display_message=details)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Doctoome Search Chatbot")
    initialize_state()
    st.title("Doctoome Search Chatbot")
    st.caption("Testing interface")

    if st.button("New conversation"):
        reset_conversation()
        st.rerun()

    for message in st.session_state.messages:
        render_message(message)

    if st.session_state.pending_options:
        for option in st.session_state.pending_options:
            render_option(option)

    user_message = st.chat_input("Message the chatbot")
    if user_message:
        submit_message(user_message)
        st.rerun()


if __name__ == "__main__":
    main()
