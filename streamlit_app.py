"""Minimal Streamlit testing client for the Doctoome chatbot."""

from typing import Any
from uuid import uuid4

import streamlit as st

import frontend_api
import frontend_auth
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


def authenticated_sender(sender):
    def send(payload):
        token = st.session_state.get("auth_token")
        try:
            return sender(payload, **({"token": token} if token else {}))
        except frontend_api.AnalyticsApiError as exc:
            if exc.status == 401:
                frontend_auth.clear_login()
                st.rerun()
            raise

    return send


def submit_message(message: str, display_message: str | None = None) -> None:
    pending = st.session_state.get("pending_message")
    if pending is None:
        pending = {
            "message": message,
            "conversation_id": st.session_state.conversation_id,
            "user_message_id": new_message_id(),
            "display_message": display_message,
        }
        st.session_state.pending_message = pending
        append_user_message(st.session_state, message, pending["user_message_id"], display_message)
    st.session_state.pending_options = []
    token = st.session_state.get("auth_token")
    try:
        response = frontend_api.send_message(
            pending["message"],
            pending["conversation_id"],
            pending["user_message_id"],
            st.session_state.user_id,
            **({"token": token} if token else {}),
        )
    except ChatApiError as exc:
        if exc.status == 401:
            frontend_auth.clear_login()
            st.rerun()
        if isinstance(exc.detail, dict):
            if exc.detail.get("conversation_id"):
                st.session_state.conversation_id = exc.detail["conversation_id"]
            if exc.detail.get("usage"):
                st.session_state.usage = exc.detail["usage"]
            pending["can_recover"] = exc.detail.get("retry_after") == 0
        language = st.session_state.ui_language
        if exc.status in (403, 404, 410, 422, 429):
            st.session_state.pending_message = None
        if exc.status in (404, 410):
            st.session_state.conversation_id = None
            st.session_state.conversation_expired = True
        text = (
            translate(language, "quota_reached")
            if exc.status == 429
            else translate(language, "conversation_expired")
            if exc.status == 410
            else str(exc)
        )
        st.session_state.messages.append({"role": "error", "content": text})
        return
    st.session_state.pending_message = None
    if response.get("usage"):
        st.session_state.usage = response["usage"]
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
            authenticated_sender(frontend_api.send_feedback),
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
            rate_assistant(
                st.session_state, message, "up", authenticated_sender(frontend_api.send_rating)
            )
            st.rerun()
    with down_column:
        if st.button(
            "👎",
            key=f"rating-down-{assistant_message_id}",
            type="primary" if selected_rating == "down" else "secondary",
        ):
            rate_assistant(
                st.session_state, message, "down", authenticated_sender(frontend_api.send_rating)
            )
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
                authenticated_sender(frontend_api.send_suggestion),
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
    if not frontend_auth.require_login():
        return
    language = render_sidebar()

    title, counter = st.columns([4, 1])
    with title:
        st.title("Doctoome Search Chatbot")
        st.caption(translate(language, "testing_interface"))
    with counter:
        frontend_auth.usage_card()
    st.sidebar.caption(st.session_state.get("account_email", ""))
    if st.sidebar.button(translate(language, "sign_out"), key="logout"):
        try:
            frontend_auth.logout(st.session_state.auth_token)
        except frontend_auth.AuthError as exc:
            if exc.status != 401:
                st.sidebar.error(translate(language, "logout_failed"))
                return
        frontend_auth.clear_login()
        st.rerun()
    quota = st.session_state.get("usage")
    can_start = quota is not None and quota["remaining"] > 0

    if st.button(
        translate(language, "new_conversation"), key="new-conversation", disabled=not can_start
    ):
        reset_conversation(st.session_state)
        st.rerun()

    for message in st.session_state.messages:
        render_message(message, language)

    for option in st.session_state.pending_options:
        render_option(option)

    pending = st.session_state.get("pending_message")
    if pending:
        if st.button(translate(language, "retry_message"), key="retry-message"):
            submit_message(pending["message"])
            st.rerun()
        if pending.get("can_recover") and st.button(
            translate(language, "continue_after_failure"), key="recover-message"
        ):
            st.session_state.pending_message = None
            st.rerun()
    user_message = st.chat_input(
        translate(language, "message_placeholder"),
        disabled=st.session_state.conversation_expired
        or bool(pending)
        or (not st.session_state.conversation_id and not can_start),
    )
    if user_message:
        submit_message(user_message)
        st.rerun()


if __name__ == "__main__":
    main()
