"""Internal login, server-authoritative usage and UI gate."""

from html import escape
import requests
import streamlit as st
import frontend_api
from frontend_state import reset_conversation
from localization import translate


class AuthError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def _call(method, path, token=None, payload=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    try:
        response = requests.request(
            method,
            frontend_api.api_url().rsplit("/chat", 1)[0] + path,
            json=payload,
            headers=headers,
            timeout=15,
        )
        if response.status_code >= 400:
            raise AuthError("Authentication service error", response.status_code)
        if response.status_code == 204:
            return None
        result = response.json()
        validate_account(result)
        if path == "/auth/login" and (
            not isinstance(result.get("token"), str) or not result["token"]
        ):
            raise ValueError("Missing token")
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise AuthError("Authentication service unavailable") from None


def validate_account(result):
    account, quota = result["account"], result["usage"]
    if not isinstance(account.get("id"), str) or not isinstance(account.get("email"), str):
        raise ValueError("Invalid account")
    if quota.get("unlimited") is True:
        if any(quota[key] is not None for key in ("remaining", "limit", "resets_at")):
            raise ValueError("Invalid unlimited usage")
        return
    if (
        type(quota["remaining"]) is not int
        or type(quota["limit"]) is not int
        or not 0 <= quota["remaining"] <= quota["limit"]
        or not isinstance(quota["resets_at"], str)
    ):
        raise ValueError("Invalid usage")


def login(email, password):
    return _call("POST", "/auth/login", payload={"email": email, "password": password})


def current_account(token):
    return _call("GET", "/auth/me", token=token)


def logout(token):
    return _call("POST", "/auth/logout", token=token)


def clear_login():
    # Remove all per-user widget values as well as messages/feedback.
    language = st.session_state.get("ui_language", "en")
    for key in list(st.session_state):
        del st.session_state[key]
    from frontend_state import initialize_state

    initialize_state(st.session_state)
    st.session_state.ui_language = language
    st.session_state.auth_token = None


def perform_login():
    language = st.session_state.ui_language
    try:
        result = login(
            st.session_state.get("login-email", ""), st.session_state.get("login-password", "")
        )
        reset_conversation(st.session_state)
        st.session_state.auth_token = result["token"]
        st.session_state.user_id = result["account"]["id"]
        st.session_state.account_email = result["account"]["email"]
        st.session_state.usage = result["usage"]
        st.session_state.login_error = None
    except AuthError as exc:
        st.session_state.login_error = translate(
            language,
            "invalid_login"
            if exc.status == 401
            else "login_limited"
            if exc.status == 429
            else "access_unavailable",
        )
    finally:
        st.session_state["login-password"] = ""


def require_login():
    language = st.session_state.ui_language
    if not st.session_state.get("auth_token"):
        language = st.selectbox(
            "Language / Langue",
            ["en", "fr"],
            index=0 if language == "en" else 1,
            key="login-language",
        )
        st.session_state.ui_language = language
        st.title("Doctoome Search Chatbot")
        st.caption(translate(language, "internal_login"))
        with st.form("login-form", clear_on_submit=True):
            st.text_input(translate(language, "email"), key="login-email")
            st.text_input(translate(language, "password"), type="password", key="login-password")
            st.form_submit_button(
                translate(language, "sign_in"), key="login-submit", on_click=perform_login
            )
        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
        return False
    try:
        result = current_account(st.session_state.auth_token)
        previous = st.session_state.get("user_id")
        if previous is not None and previous != result["account"]["id"]:
            clear_login()
            st.rerun()
        st.session_state.user_id = result["account"]["id"]
        st.session_state.account_email = result["account"]["email"]
        st.session_state.usage = result["usage"]
    except AuthError as exc:
        st.session_state.usage = None
        if exc.status == 401:
            clear_login()
            st.rerun()
        st.error(translate(language, "access_unavailable"))
        if st.button(translate(language, "retry"), key="retry-access"):
            st.rerun()
        return False
    return True


@st.fragment(run_every="30s")
def usage_card():
    language = st.session_state.ui_language
    try:
        result = current_account(st.session_state.auth_token)
        old = st.session_state.get("usage")
        st.session_state.usage = result["usage"]
        if old != result["usage"]:
            st.rerun()
    except AuthError as exc:
        if exc.status == 401:
            clear_login()
            st.rerun()
        st.session_state.usage = None
    quota = st.session_state.get("usage")
    value = (
        (
            translate(language, "unlimited")
            if quota.get("unlimited") is True
            else f"{quota['remaining']} / {quota['limit']}"
        )
        if quota
        else "—"
    )
    caption = translate(language, "conversations_left" if quota else "usage_unavailable")
    st.markdown(
        f'<div style="border:1px solid #d9e2ec;border-radius:10px;padding:14px;text-align:center;max-width:180px;margin-left:auto"><div style="font-size:28px;font-weight:650">{escape(value)}</div><div style="font-size:13px">{escape(caption)}</div></div>',
        unsafe_allow_html=True,
    )
    if quota and quota["remaining"] == 0:
        st.caption(translate(language, "quota_reset") + " " + quota["resets_at"])
