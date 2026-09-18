from unittest.mock import Mock, patch

import pytest
import requests

from frontend_api import (
    AnalyticsApiError,
    ChatApiError,
    send_feedback,
    send_message,
    send_rating,
    send_suggestion,
)


def response_with(payload, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.raise_for_status.side_effect = (
        requests.HTTPError("bad response") if status_code >= 400 else None
    )
    response.json.return_value = payload
    return response


def valid_response(conversation_id="abc123", **extra):
    return {
        "answer": False,
        "needs_followup": True,
        "response_type": "WAITING_FOR_LOCATION",
        "message": "Where would you like to search?",
        "state": "WAITING_FOR_LOCATION",
        "options": [],
        "url": None,
        "conversation_id": conversation_id,
        **extra,
    }


@patch("frontend_api.requests.post")
def test_first_message_omits_conversation_id(mock_post):
    mock_post.return_value = response_with(valid_response())

    result = send_message("find a psychologist", None)

    assert result["conversation_id"] == "abc123"
    assert mock_post.call_args.kwargs["json"] == {"message": "find a psychologist"}


@patch("frontend_api.requests.post")
def test_followup_sends_returned_conversation_id(mock_post):
    mock_post.return_value = response_with(valid_response())

    send_message("Paris", "abc123")

    assert mock_post.call_args.kwargs["json"] == {
        "message": "Paris",
        "conversation_id": "abc123",
    }


@patch("frontend_api.requests.post")
def test_legacy_contract_omits_analytics_fields_by_default(mock_post, monkeypatch):
    monkeypatch.delenv("CHAT_EXTENDED_CONTRACT_ENABLED", raising=False)
    mock_post.return_value = response_with(valid_response())

    send_message("Paris", "abc123", "user-message-1", None)

    assert mock_post.call_args.kwargs["json"] == {
        "message": "Paris",
        "conversation_id": "abc123",
    }


@patch("frontend_api.requests.post")
def test_extended_contract_sends_user_message_id_and_nullable_user_id(mock_post, monkeypatch):
    monkeypatch.setenv("CHAT_EXTENDED_CONTRACT_ENABLED", "true")
    mock_post.return_value = response_with(valid_response())

    send_message("Paris", "abc123", "user-message-1", None)

    assert mock_post.call_args.kwargs["json"] == {
        "message": "Paris",
        "conversation_id": "abc123",
        "user_message_id": "user-message-1",
        "user_id": None,
    }


@patch("frontend_api.requests.post")
def test_extended_first_message_sends_nullable_conversation_id(mock_post, monkeypatch):
    monkeypatch.setenv("CHAT_EXTENDED_CONTRACT_ENABLED", "true")
    mock_post.return_value = response_with(valid_response())

    send_message("find a psychologist", None, "user-message-1", None)

    assert mock_post.call_args.kwargs["json"] == {
        "message": "find a psychologist",
        "conversation_id": None,
        "user_message_id": "user-message-1",
        "user_id": None,
    }


@patch("frontend_api.requests.post")
def test_optional_analytics_response_ids_are_preserved(mock_post):
    mock_post.return_value = response_with(
        valid_response(turn_id="turn-1", assistant_message_id="assistant-1")
    )

    result = send_message("Paris", "abc123")

    assert result["turn_id"] == "turn-1"
    assert result["assistant_message_id"] == "assistant-1"


@pytest.mark.parametrize(
    "side_effect",
    [requests.ConnectionError(), requests.Timeout(), requests.HTTPError()],
)
@patch("frontend_api.requests.post")
def test_transport_failures_raise_frontend_error_without_state_mutation(mock_post, side_effect):
    mock_post.side_effect = side_effect

    with pytest.raises(ChatApiError):
        send_message("Paris", "abc123")


@pytest.mark.parametrize("payload", [{}, {"message": "missing fields"}, {"options": []}])
@patch("frontend_api.requests.post")
def test_invalid_response_shape_raises_frontend_error(mock_post, payload):
    mock_post.return_value = response_with(payload)

    with pytest.raises(ChatApiError):
        send_message("search", None)


@patch("frontend_api.requests.post")
def test_invalid_option_shape_raises_frontend_error(mock_post):
    payload = valid_response()
    payload["options"] = [{"number": "2", "label": "A practitioner"}]
    mock_post.return_value = response_with(payload)

    with pytest.raises(ChatApiError):
        send_message("search", None)


@pytest.mark.parametrize(
    "sender,event_id,payload,path",
    [
        (
            send_rating,
            "rating-1",
            {
                "rating_event_id": "rating-1",
                "user_id": None,
                "conversation_id": "conversation-1",
                "turn_id": "turn-1",
                "assistant_message_id": "assistant-1",
                "rating": "up",
            },
            "/analytics/ratings",
        ),
        (
            send_feedback,
            "feedback-1",
            {
                "feedback_id": "feedback-1",
                "rating_event_id": "rating-1",
                "user_id": None,
                "conversation_id": "conversation-1",
                "turn_id": None,
                "assistant_message_id": "assistant-1",
                "selected_reasons": ["wrong_result", "technical_problem"],
                "feedback_text": "  Keep this verbatim.  ",
            },
            "/analytics/feedback",
        ),
        (
            send_suggestion,
            "suggestion-1",
            {
                "suggestion_id": "suggestion-1",
                "user_id": None,
                "conversation_id": None,
                "assistant_message_id": None,
                "suggestion_text": "Please add filters.",
            },
            "/analytics/suggestions",
        ),
    ],
)
@patch("frontend_api.requests.post")
def test_analytics_clients_post_exact_payload_and_accept_202(
    mock_post, monkeypatch, sender, event_id, payload, path
):
    monkeypatch.setenv("DOCTOOME_ANALYTICS_API_BASE_URL", "https://analytics.example")
    mock_post.return_value = response_with(
        {"accepted": True, "event_id": event_id}, status_code=202
    )

    sender(payload)

    assert mock_post.call_args.args == ("https://analytics.example" + path,)
    assert mock_post.call_args.kwargs["json"] == payload


@patch("frontend_api.requests.post")
def test_analytics_client_rejects_non_202_response(mock_post):
    mock_post.return_value = response_with(
        {"accepted": True, "event_id": "rating-1"}, status_code=200
    )

    with pytest.raises(AnalyticsApiError):
        send_rating(
            {
                "rating_event_id": "rating-1",
                "user_id": None,
                "conversation_id": "conversation-1",
                "turn_id": None,
                "assistant_message_id": "assistant-1",
                "rating": "up",
            }
        )
