"""Minimal Streamlit testing client for the Doctoome chatbot."""

from typing import Any
from uuid import uuid4

import streamlit as st

import frontend_api
from frontend_api import ChatApiError
from frontend_state import (
    append_assistant_response,
    append_user_message,
    initialize_state,
    rate_assistant,
    reset_conversation,
    submit_feedback_event,
    submit_suggestion_event,
)
from localization import feedback_reason_options, translate


def new_message_id() -> str:
    return str(uuid4())


def submit_message(message: str, display_message: str | None = None) -> None:
    user_message_id = new_message_id()
    append_user_message(st.session_state, message, user_message_id, display_message)
    st.session_state.pending_options = []
    try:
        response = frontend_api.send_message(
            message,
            st.session_state.conversation_id,
            user_message_id,
            st.session_state.user_id,
        )
    except ChatApiError as exc:
        st.session_state.messages.append({"role": "error", "content": str(exc)})
        return
    append_assistant_response(st.session_state, response)


def render_feedback_form(message: dict[str, Any], language: str) -> None:
    assistant_message_id = message["assistant_message_id"]
    rating_state = st.session_state.ratings_by_message[assistant_message_id]
    feedback_state = st.session_state.feedback_ui_state.get(assistant_message_id, {})
    down_event_id = rating_state.get("latest_down_event_id")
    if feedback_state.get("submitted_rating_event_id") == down_event_id:
        st.success(translate(language, "feedback_success"))
        return

    reason_labels = feedback_reason_options(language)
    label_to_key = {label: key for key, label in reason_labels.items()}
    selected_labels = st.multiselect(
        translate(language, "feedback_question"),
        options=list(label_to_key),
        key=f"feedback-reasons-{assistant_message_id}",
    )
    feedback_text = st.text_area(
        translate(language, "feedback_more"),
        key=f"feedback-text-{assistant_message_id}",
    )
    can_submit = bool(selected_labels or feedback_text.strip())
    if st.button(
        translate(language, "submit"),
        key=f"feedback-submit-{assistant_message_id}",
        disabled=not can_submit,
    ):
        submit_feedback_event(
            st.session_state,
            message,
            [label_to_key[label] for label in selected_labels],
            feedback_text,
            frontend_api.send_feedback,
        )
        st.rerun()

    feedback_state = st.session_state.feedback_ui_state.get(assistant_message_id, {})
    if feedback_state.get("error"):
        st.error(translate(language, "feedback_error"))


def render_rating_controls(message: dict[str, Any], language: str) -> None:
    assistant_message_id = message.get("assistant_message_id")
    if not assistant_message_id:
        return

    rating_state = st.session_state.ratings_by_message.get(assistant_message_id, {})
    selected_rating = rating_state.get("rating")
    up_column, down_column, _ = st.columns([1, 1, 8])
    with up_column:
        if st.button(
            "👍",
            key=f"rating-up-{assistant_message_id}",
            type="primary" if selected_rating == "up" else "secondary",
        ):
            rate_assistant(st.session_state, message, "up", frontend_api.send_rating)
            st.rerun()
    with down_column:
        if st.button(
            "👎",
            key=f"rating-down-{assistant_message_id}",
            type="primary" if selected_rating == "down" else "secondary",
        ):
            rate_assistant(st.session_state, message, "down", frontend_api.send_rating)
            st.rerun()

    rating_state = st.session_state.ratings_by_message.get(assistant_message_id, {})
    if rating_state.get("error"):
        st.error(translate(language, "rating_error"))
    if rating_state.get("rating") == "down":
        render_feedback_form(message, language)


def render_message(message: dict[str, Any], language: str) -> None:
    role = message["role"]
    with st.chat_message("assistant" if role == "error" else role):
        if role == "error":
            st.error(message["content"])
            return
        st.text(message["content"])
        if message.get("url"):
            st.markdown(f"[{message['url']}]({message['url']})")
        if role == "assistant":
            render_rating_controls(message, language)


def render_option(option: dict[str, Any]) -> None:
    details = "\n".join([option["label"], *option.get("offices", [])])
    if st.button(details, key=f"option-{option['number']}"):
        submit_message(str(option["number"]), display_message=details)
        st.rerun()


def render_sidebar() -> str:
    current_language = st.session_state.ui_language
    language_labels = [
        translate(current_language, "english"),
        translate(current_language, "french"),
    ]
    selected_label = st.sidebar.radio(
        translate(current_language, "interface_language"),
        language_labels,
        index=0 if current_language == "en" else 1,
        horizontal=True,
        key="ui-language-selector",
    )
    language = "fr" if selected_label == translate(current_language, "french") else "en"
    st.session_state.ui_language = language

    with st.sidebar.expander(translate(language, "suggestion_title")):
        st.caption(translate(language, "suggestion_help"))
        suggestion_text = st.text_area(
            translate(language, "suggestion_placeholder"),
            key="suggestion-text",
        )
        if st.button(
            translate(language, "submit"),
            key="suggestion-submit",
            disabled=not suggestion_text.strip(),
        ):
            submit_suggestion_event(
                st.session_state,
                suggestion_text,
                frontend_api.send_suggestion,
            )
            st.rerun()

        suggestion_state = st.session_state.suggestion_ui_state
        if suggestion_state.get("error"):
            st.error(translate(language, "suggestion_error"))
        elif suggestion_state.get("success"):
            st.success(translate(language, "suggestion_success"))
    return language


def main() -> None:
    st.set_page_config(page_title="Doctoome Search Chatbot")
    initialize_state(st.session_state)
    language = render_sidebar()

    st.title("Doctoome Search Chatbot")
    st.caption(translate(language, "testing_interface"))

    if st.button(translate(language, "new_conversation"), key="new-conversation"):
        reset_conversation(st.session_state)
        st.rerun()

    for message in st.session_state.messages:
        render_message(message, language)

    for option in st.session_state.pending_options:
        render_option(option)

    user_message = st.chat_input(translate(language, "message_placeholder"))
    if user_message:
        submit_message(user_message)
        st.rerun()


if __name__ == "__main__":
    main()
