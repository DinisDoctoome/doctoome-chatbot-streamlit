from unittest.mock import Mock, patch

import pytest
import requests

from frontend_api import ChatApiError, send_message


def response_with(payload, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.raise_for_status.side_effect = (
        requests.HTTPError("bad response") if status_code >= 400 else None
    )
    response.json.return_value = payload
    return response


def valid_response(conversation_id="abc123"):
    return {
        "answer": False,
        "needs_followup": True,
        "response_type": "WAITING_FOR_LOCATION",
        "message": "Where would you like to search?",
        "state": "WAITING_FOR_LOCATION",
        "options": [],
        "url": None,
        "conversation_id": conversation_id,
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
