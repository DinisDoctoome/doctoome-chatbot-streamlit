from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from tests.test_frontend_api import response_with, valid_response

APP = Path(__file__).parents[1] / "streamlit_app.py"
ME = {
    "account": {"id": "alice", "email": "alice.s@doctoome.com"},
    "usage": {"remaining": 3, "limit": 5, "resets_at": "2026-11-04T00:00:00+01:00"},
}


def test_login_gate_hides_chat():
    app = AppTest.from_file(APP).run()
    assert not app.chat_input
    assert app.text_input(key="login-email")
    assert app.text_input(key="login-password")


def test_login_shows_remaining_and_logout_clears_state():
    with (
        patch("frontend_auth.login", return_value={**ME, "token": "secret"}),
        patch("frontend_auth.current_account", return_value=ME),
        patch("frontend_auth.logout"),
    ):
        app = AppTest.from_file(APP).run()
        app.text_input(key="login-email").set_value("alice.s@doctoome.com")
        app.text_input(key="login-password").set_value("fixed-password-example")
        app.button(key="login-submit").click().run()
        assert app.chat_input
        assert any("3 / 5" in value.value for value in app.markdown)
        assert app.session_state["user_id"] == "alice"
        app.button(key="logout").click().run()
        assert not app.chat_input
        assert app.session_state["messages"] == []
        assert app.session_state["auth_token"] is None


def test_zero_allows_existing_chat_but_blocks_new():
    me = {**ME, "usage": {**ME["usage"], "remaining": 0}}
    with patch("frontend_auth.current_account", return_value=me):
        app = AppTest.from_file(APP)
        app.session_state["auth_token"] = "secret"
        app.session_state["conversation_id"] = "existing"
        app.run()
        assert app.button(key="new-conversation").disabled
        assert not app.chat_input[0].disabled
        app.session_state["conversation_id"] = None
        app.run()
        assert app.chat_input[0].disabled


def test_authenticated_chat_sends_token_and_message_id():
    from frontend_api import send_message

    with patch("frontend_api.requests.post", return_value=response_with(valid_response())) as post:
        send_message("hello", None, "stable-id", "alice", token="secret")
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert post.call_args.kwargs["json"]["user_message_id"] == "stable-id"


def test_failed_start_retries_same_request_id():
    import frontend_api

    sent = []

    def send(*args, **kwargs):
        sent.append(args)
        if len(sent) == 1:
            raise frontend_api.ChatApiError("Network error")
        return valid_response(usage=ME["usage"])

    with (
        patch("frontend_auth.current_account", return_value=ME),
        patch("frontend_api.send_message", side_effect=send),
    ):
        app = AppTest.from_file(APP)
        app.session_state["auth_token"] = "secret"
        app.run()
        app.chat_input[0].set_value("hello").run()
        app.button(key="retry-message").click().run()
    assert len(sent) == 2
    assert sent[0] == sent[1]


def test_usage_unavailable_does_not_invent_counter():
    from frontend_auth import AuthError

    with patch("frontend_auth.current_account", side_effect=AuthError("unavailable", 503)):
        app = AppTest.from_file(APP)
        app.session_state["auth_token"] = "secret"
        app.run()
        assert any("unavailable" in e.value.lower() for e in app.error)
        assert not app.chat_input


def test_signed_in_rating_sends_bearer_token():
    from tests.test_streamlit_app import assistant_message
    from tests.test_frontend_api import response_with

    def accepted(*args, **kwargs):
        return response_with({"accepted": True, "event_id": kwargs["json"]["rating_event_id"]}, 202)

    with (
        patch("frontend_auth.current_account", return_value=ME),
        patch("frontend_api.requests.post", side_effect=accepted) as post,
    ):
        app = AppTest.from_file(APP)
        app.session_state["auth_token"] = "secret"
        app.session_state["conversation_id"] = "conversation-1"
        app.session_state["messages"] = [assistant_message()]
        app.run()
        app.button(key="rating-down-assistant-1").click().run()
        assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}
        assert app.multiselect(key="feedback-reasons-assistant-1")


def test_expired_conversation_requires_explicit_empty_new_chat():
    from frontend_api import ChatApiError

    with (
        patch("frontend_auth.current_account", return_value=ME),
        patch("frontend_api.send_message", side_effect=ChatApiError("Expired", 410)),
    ):
        app = AppTest.from_file(APP)
        app.session_state["auth_token"] = "secret"
        app.session_state["conversation_id"] = "old"
        app.run()
        app.chat_input[0].set_value("hello").run()
        assert app.chat_input[0].disabled
        app.button(key="new-conversation").click().run()
        assert app.session_state["messages"] == []
        assert not app.chat_input[0].disabled
