from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from frontend_api import AnalyticsApiError


APP_PATH = Path(__file__).parents[1] / "streamlit_app.py"


def assistant_message(message_id="assistant-1", **overrides):
    return {
        "role": "assistant",
        "content": "Choose an option.",
        "url": None,
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "assistant_message_id": message_id,
        **overrides,
    }


def app_with_messages(messages):
    app = AppTest.from_file(APP_PATH, default_timeout=5)
    app.session_state["messages"] = messages
    app.session_state["conversation_id"] = "conversation-1"
    return app.run()


def test_each_identified_assistant_message_has_rating_controls_but_user_does_not():
    app = app_with_messages(
        [
            {"role": "user", "content": "Paris", "user_message_id": "user-1"},
            assistant_message("assistant-1"),
            assistant_message("assistant-2"),
        ]
    )

    rating_buttons = [button for button in app.button if button.key and button.key.startswith("rating-")]
    assert [(button.label, button.key) for button in rating_buttons] == [
        ("👍", "rating-up-assistant-1"),
        ("👎", "rating-down-assistant-1"),
        ("👍", "rating-up-assistant-2"),
        ("👎", "rating-down-assistant-2"),
    ]


def test_legacy_assistant_without_stable_id_has_no_rating_controls():
    app = app_with_messages([assistant_message(None)])

    assert not [button for button in app.button if button.key and button.key.startswith("rating-")]


def test_down_rating_opens_feedback_and_sends_one_event():
    sent = []
    with patch("frontend_api.send_rating", side_effect=sent.append):
        app = app_with_messages([assistant_message()])
        app.button(key="rating-down-assistant-1").click().run()

    assert len(sent) == 1
    assert sent[0]["rating"] == "down"
    assert app.multiselect(key="feedback-reasons-assistant-1")
    assert app.text_area(key="feedback-text-assistant-1")


def test_rerun_does_not_resend_rating_and_changing_rating_sends_second_event():
    sent = []
    with patch("frontend_api.send_rating", side_effect=sent.append):
        app = app_with_messages([assistant_message()])
        app.button(key="rating-up-assistant-1").click().run()
        app.run()
        app.button(key="rating-down-assistant-1").click().run()

    assert [event["rating"] for event in sent] == ["up", "down"]
    assert sent[0]["rating_event_id"] != sent[1]["rating_event_id"]


def test_feedback_ui_sends_stable_reason_keys_and_verbatim_text():
    ratings = []
    feedback = []
    with (
        patch("frontend_api.send_rating", side_effect=ratings.append),
        patch("frontend_api.send_feedback", side_effect=feedback.append),
    ):
        app = app_with_messages([assistant_message()])
        app.button(key="rating-down-assistant-1").click().run()
        app.multiselect(key="feedback-reasons-assistant-1").set_value(
            ["Wrong result", "Technical problem"]
        )
        app.text_area(key="feedback-text-assistant-1").set_value("  More detail.  ")
        app.button(key="feedback-submit-assistant-1").click().run()

    assert feedback[0]["selected_reasons"] == ["wrong_result", "technical_problem"]
    assert feedback[0]["feedback_text"] == "  More detail.  "
    assert feedback[0]["rating_event_id"] == ratings[0]["rating_event_id"]


def test_suggestion_box_is_always_available_and_includes_current_context():
    sent = []
    with patch("frontend_api.send_suggestion", side_effect=sent.append):
        app = app_with_messages([assistant_message()])
        assert app.sidebar.expander[0].label == "Have a suggestion?"
        app.text_area(key="suggestion-text").set_value("Add appointment filters.")
        app.button(key="suggestion-submit").click().run()

    assert sent[0]["conversation_id"] == "conversation-1"
    assert sent[0]["assistant_message_id"] == "assistant-1"


def test_french_selector_translates_frontend_analytics_ui_only():
    with patch("frontend_api.send_rating", side_effect=lambda payload: None):
        app = app_with_messages([assistant_message()])
        app.sidebar.radio[0].set_value("Français").run()
        app.button(key="rating-down-assistant-1").click().run()

    assert app.sidebar.expander[0].label == "Une suggestion ?"
    assert app.multiselect(key="feedback-reasons-assistant-1").options == [
        "Il a mal compris ma demande",
        "Résultat incorrect",
        "Fonctionnalité ou filtre manquant",
        "Trop de questions",
        "Problème technique",
        "Autre",
    ]
    assert app.chat_message[0].text[0].value == "Choose an option."


def test_new_conversation_clears_feedback_state_but_preserves_language():
    app = AppTest.from_file(APP_PATH, default_timeout=5)
    app.session_state["ui_language"] = "fr"
    app.session_state["messages"] = [assistant_message()]
    app.session_state["ratings_by_message"] = {"assistant-1": {"rating": "down"}}
    app.session_state["feedback_ui_state"] = {"assistant-1": {"error": True}}
    app.run()

    app.button(key="new-conversation").click().run()

    assert app.session_state["ui_language"] == "fr"
    assert app.session_state["messages"] == []
    assert app.session_state["ratings_by_message"] == {}
    assert app.session_state["feedback_ui_state"] == {}


def test_rating_failure_shows_local_error_and_keeps_chat_usable():
    with patch(
        "frontend_api.send_rating", side_effect=AnalyticsApiError("temporary failure")
    ):
        app = app_with_messages([assistant_message()])
        app.button(key="rating-up-assistant-1").click().run()

    assert app.error[0].value == "We couldn't save your rating. Please try again."
    assert app.chat_input[0].placeholder == "Message the chatbot"
    assert app.session_state["conversation_id"] == "conversation-1"


def test_existing_url_and_current_option_rendering_remain_available():
    app = AppTest.from_file(APP_PATH, default_timeout=5)
    app.session_state["messages"] = [
        assistant_message(url="https://www.doctoome.com/s/example")
    ]
    app.session_state["pending_options"] = [
        {"number": 2, "label": "A practitioner", "offices": ["Paris — 75001"]}
    ]
    app.run()

    assert any("https://www.doctoome.com/s/example" in item.value for item in app.markdown)
    assert app.button(key="option-2").label == "A practitioner\nParis — 75001"


def test_current_option_click_posts_number_once_and_removes_stale_options():
    calls = []

    def chat_response(message, conversation_id, user_message_id, user_id):
        calls.append((message, conversation_id, user_message_id, user_id))
        return {
            "answer": True,
            "needs_followup": False,
            "response_type": "SEARCH_RESOLVED",
            "message": "Open the result.",
            "state": "IDLE",
            "options": [],
            "url": "https://www.doctoome.com/s/example",
            "conversation_id": "conversation-1",
        }

    with patch("frontend_api.send_message", side_effect=chat_response):
        app = AppTest.from_file(APP_PATH, default_timeout=5)
        app.session_state["conversation_id"] = "conversation-1"
        app.session_state["pending_options"] = [
            {"number": 2, "label": "A practitioner", "offices": []}
        ]
        app.run()
        app.button(key="option-2").click().run()

    assert len(calls) == 1
    assert calls[0][0:2] == ("2", "conversation-1")
    assert calls[0][3] is None
    assert app.session_state["pending_options"] == []
    assert not [button for button in app.button if button.key == "option-2"]
