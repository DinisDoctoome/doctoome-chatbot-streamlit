from collections import UserDict

import pytest

from frontend_api import AnalyticsApiError
from frontend_state import (
    append_assistant_response,
    append_user_message,
    initialize_state,
    rate_assistant,
    reset_conversation,
    submit_feedback_event,
    submit_suggestion_event,
)


class State(UserDict):
    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        if name == "data":
            super().__setattr__(name, value)
        else:
            self.data[name] = value


def assistant_message(**overrides):
    return {
        "role": "assistant",
        "content": "Choose an option.",
        "url": None,
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "assistant_message_id": "assistant-1",
        **overrides,
    }


def initialized_state(**overrides):
    state = State()
    initialize_state(state)
    state.update(overrides)
    return state


def test_initialize_state_adds_nullable_user_and_analytics_state():
    state = initialized_state()

    assert state.user_id is None
    assert state.ui_language == "en"
    assert state.ratings_by_message == {}
    assert state.feedback_ui_state == {}
    assert state.submitted_feedback_ids == set()


def test_chat_history_keeps_stable_user_and_assistant_metadata():
    state = initialized_state(conversation_id="conversation-1")
    append_user_message(state, "Paris", "user-1")

    append_assistant_response(
        state,
        {
            "message": "Choose an option.",
            "url": None,
            "options": [],
            "conversation_id": "conversation-1",
            "turn_id": "turn-1",
            "assistant_message_id": "assistant-1",
        },
    )

    assert state.messages[0] == {
        "role": "user",
        "content": "Paris",
        "user_message_id": "user-1",
        "turn_id": "turn-1",
    }
    assert state.messages[1] == assistant_message()


def test_missing_assistant_message_id_does_not_submit_rating():
    state = initialized_state()
    sent = []

    result = rate_assistant(
        state,
        assistant_message(assistant_message_id=None),
        "up",
        sent.append,
        lambda: "rating-1",
    )

    assert result is False
    assert sent == []
    assert state.ratings_by_message == {}


def test_up_rating_sends_once_and_rerun_does_not_duplicate():
    state = initialized_state()
    sent = []
    message = assistant_message()

    assert rate_assistant(state, message, "up", sent.append, lambda: "rating-1") is True
    assert rate_assistant(state, message, "up", sent.append, lambda: "rating-2") is False

    assert sent == [
        {
            "rating_event_id": "rating-1",
            "user_id": None,
            "conversation_id": "conversation-1",
            "turn_id": "turn-1",
            "assistant_message_id": "assistant-1",
            "rating": "up",
        }
    ]
    assert state.ratings_by_message["assistant-1"]["rating"] == "up"


def test_changing_up_to_down_sends_second_event_and_opens_feedback():
    state = initialized_state()
    sent = []
    ids = iter(["rating-1", "rating-2"])
    message = assistant_message()

    rate_assistant(state, message, "up", sent.append, lambda: next(ids))
    rate_assistant(state, message, "down", sent.append, lambda: next(ids))

    assert [event["rating"] for event in sent] == ["up", "down"]
    assert [event["rating_event_id"] for event in sent] == ["rating-1", "rating-2"]
    assert state.ratings_by_message["assistant-1"]["rating"] == "down"
    assert state.ratings_by_message["assistant-1"]["latest_down_event_id"] == "rating-2"


def test_failed_rating_keeps_chat_state_and_reuses_event_id_for_retry():
    state = initialized_state(conversation_id="conversation-1")
    attempts = []

    def fail_once(payload):
        attempts.append(payload)
        if len(attempts) == 1:
            raise AnalyticsApiError("failed")

    assert rate_assistant(
        state, assistant_message(), "down", fail_once, lambda: "rating-1"
    ) is False
    assert rate_assistant(
        state, assistant_message(), "down", fail_once, lambda: "rating-2"
    ) is True

    assert [attempt["rating_event_id"] for attempt in attempts] == ["rating-1", "rating-1"]
    assert state.conversation_id == "conversation-1"


def test_feedback_preserves_keys_text_and_down_rating_link():
    state = initialized_state()
    state.ratings_by_message["assistant-1"] = {
        "rating": "down",
        "latest_down_event_id": "rating-1",
    }
    sent = []

    result = submit_feedback_event(
        state,
        assistant_message(),
        ["wrong_result", "technical_problem"],
        "  More detail.  ",
        sent.append,
        lambda: "feedback-1",
    )

    assert result is True
    assert sent == [
        {
            "feedback_id": "feedback-1",
            "rating_event_id": "rating-1",
            "user_id": None,
            "conversation_id": "conversation-1",
            "turn_id": "turn-1",
            "assistant_message_id": "assistant-1",
            "selected_reasons": ["wrong_result", "technical_problem"],
            "feedback_text": "  More detail.  ",
        }
    ]
    assert "feedback-1" in state.submitted_feedback_ids


def test_failed_feedback_preserves_chat_and_reuses_feedback_id():
    state = initialized_state(conversation_id="conversation-1")
    state.ratings_by_message["assistant-1"] = {
        "rating": "down",
        "latest_down_event_id": "rating-1",
    }
    attempts = []

    def fail_once(payload):
        attempts.append(payload)
        if len(attempts) == 1:
            raise AnalyticsApiError("failed")

    assert submit_feedback_event(
        state,
        assistant_message(),
        ["wrong_result"],
        "Details",
        fail_once,
        lambda: "feedback-1",
    ) is False
    assert submit_feedback_event(
        state,
        assistant_message(),
        ["wrong_result"],
        "Details",
        fail_once,
        lambda: "feedback-2",
    ) is True

    assert [attempt["feedback_id"] for attempt in attempts] == ["feedback-1", "feedback-1"]
    assert state.conversation_id == "conversation-1"


def test_editing_failed_feedback_creates_a_new_feedback_id():
    state = initialized_state()
    state.ratings_by_message["assistant-1"] = {
        "rating": "down",
        "latest_down_event_id": "rating-1",
    }
    attempts = []

    def always_fail(payload):
        attempts.append(payload)
        raise AnalyticsApiError("failed")

    submit_feedback_event(
        state,
        assistant_message(),
        ["wrong_result"],
        "First detail",
        always_fail,
        lambda: "feedback-1",
    )
    submit_feedback_event(
        state,
        assistant_message(),
        ["technical_problem"],
        "Edited detail",
        always_fail,
        lambda: "feedback-2",
    )

    assert [attempt["feedback_id"] for attempt in attempts] == ["feedback-1", "feedback-2"]


@pytest.mark.parametrize("reasons,text", [([], ""), ([], "   ")])
def test_feedback_requires_a_reason_or_text(reasons, text):
    state = initialized_state()
    state.ratings_by_message["assistant-1"] = {
        "rating": "down",
        "latest_down_event_id": "rating-1",
    }

    assert (
        submit_feedback_event(
            state,
            assistant_message(),
            reasons,
            text,
            lambda payload: None,
            lambda: "feedback-1",
        )
        is False
    )


def test_suggestion_uses_current_conversation_and_latest_assistant_id():
    state = initialized_state(
        conversation_id="conversation-1", messages=[assistant_message()]
    )
    sent = []

    result = submit_suggestion_event(
        state,
        "Add appointment filters.",
        sent.append,
        lambda: "suggestion-1",
    )

    assert result is True
    assert sent == [
        {
            "suggestion_id": "suggestion-1",
            "user_id": None,
            "conversation_id": "conversation-1",
            "assistant_message_id": "assistant-1",
            "suggestion_text": "Add appointment filters.",
        }
    ]


def test_suggestion_allows_null_assistant_message_id():
    state = initialized_state(conversation_id=None, messages=[])
    sent = []

    submit_suggestion_event(state, "A suggestion", sent.append, lambda: "suggestion-1")

    assert sent[0]["conversation_id"] is None
    assert sent[0]["assistant_message_id"] is None


def test_failed_suggestion_preserves_chat_and_reuses_suggestion_id():
    state = initialized_state(conversation_id="conversation-1")
    attempts = []

    def fail_once(payload):
        attempts.append(payload)
        if len(attempts) == 1:
            raise AnalyticsApiError("failed")

    assert submit_suggestion_event(
        state, "A suggestion", fail_once, lambda: "suggestion-1"
    ) is False
    assert submit_suggestion_event(
        state, "A suggestion", fail_once, lambda: "suggestion-2"
    ) is True

    assert [attempt["suggestion_id"] for attempt in attempts] == [
        "suggestion-1",
        "suggestion-1",
    ]
    assert state.conversation_id == "conversation-1"


def test_new_conversation_clears_chat_feedback_but_preserves_language_and_user():
    state = initialized_state(
        user_id=None,
        ui_language="fr",
        conversation_id="conversation-1",
        messages=[assistant_message()],
        pending_options=[{"number": 1}],
        ratings_by_message={"assistant-1": {"rating": "down"}},
        feedback_ui_state={"assistant-1": {"submitted": True}},
        submitted_feedback_ids={"feedback-1"},
    )

    reset_conversation(state)

    assert state.conversation_id is None
    assert state.messages == []
    assert state.pending_options == []
    assert state.ratings_by_message == {}
    assert state.feedback_ui_state == {}
    assert state.submitted_feedback_ids == set()
    assert state.ui_language == "fr"
    assert state.user_id is None
