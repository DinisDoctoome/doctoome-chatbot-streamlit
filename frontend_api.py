"""Small HTTP client for the deployed Doctoome chatbot API."""

import os
from typing import Any

import requests


DEFAULT_API_URL = "https://wp3xsfphbp.eu-west-3.awsapprunner.com/chat"
DEFAULT_API_BASE_URL = "https://wp3xsfphbp.eu-west-3.awsapprunner.com"
REQUEST_TIMEOUT_SECONDS = 30
REQUIRED_FIELDS = {
    "answer",
    "needs_followup",
    "response_type",
    "message",
    "state",
    "options",
    "url",
    "conversation_id",
}


class ChatApiError(Exception):
    """A user-safe error raised when the chatbot API cannot be used."""


class AnalyticsApiError(Exception):
    """A user-safe error raised when an analytics event cannot be accepted."""


def api_url() -> str:
    return os.getenv("DOCTOOME_CHAT_API_URL", DEFAULT_API_URL)


def analytics_api_base_url() -> str:
    return os.getenv("DOCTOOME_ANALYTICS_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


def extended_chat_contract_enabled() -> bool:
    return os.getenv("CHAT_EXTENDED_CONTRACT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _validate_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not REQUIRED_FIELDS.issubset(payload):
        raise ChatApiError("The chatbot service returned an unexpected response.")

    if not isinstance(payload["message"], str) or not isinstance(payload["options"], list):
        raise ChatApiError("The chatbot service returned an unexpected response.")

    for option in payload["options"]:
        if not isinstance(option, dict):
            raise ChatApiError("The chatbot service returned an unexpected response.")
        if not isinstance(option.get("number"), int) or not isinstance(
            option.get("label"), str
        ):
            raise ChatApiError("The chatbot service returned an unexpected response.")
        if not isinstance(option.get("offices", []), list) or not all(
            isinstance(office, str) for office in option.get("offices", [])
        ):
            raise ChatApiError("The chatbot service returned an unexpected response.")

    if payload["url"] is not None and not isinstance(payload["url"], str):
        raise ChatApiError("The chatbot service returned an unexpected response.")

    if payload["conversation_id"] is not None and not isinstance(
        payload["conversation_id"], str
    ):
        raise ChatApiError("The chatbot service returned an unexpected response.")

    for optional_id in ("turn_id", "assistant_message_id"):
        if optional_id in payload and payload[optional_id] is not None and not isinstance(
            payload[optional_id], str
        ):
            raise ChatApiError("The chatbot service returned an unexpected response.")

    return payload


def send_message(
    message: str,
    conversation_id: str | None,
    user_message_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message}
    if extended_chat_contract_enabled():
        payload["conversation_id"] = conversation_id
        payload["user_message_id"] = user_message_id
        payload["user_id"] = user_id
    elif conversation_id is not None:
        payload["conversation_id"] = conversation_id

    try:
        response = requests.post(
            api_url(), json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return _validate_response(response.json())
    except (requests.RequestException, ValueError, ChatApiError) as exc:
        if isinstance(exc, ChatApiError):
            raise
        raise ChatApiError("I couldn't reach the chatbot service. Please try again.") from exc


def _send_analytics_event(path: str, payload: dict[str, Any], id_field: str) -> None:
    try:
        response = requests.post(
            analytics_api_base_url() + path,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 202:
            raise AnalyticsApiError("The analytics service did not accept the event.")
        result = response.json()
        if (
            not isinstance(result, dict)
            or result.get("accepted") is not True
            or result.get("event_id") != payload[id_field]
        ):
            raise AnalyticsApiError("The analytics service returned an unexpected response.")
    except (requests.RequestException, ValueError, AnalyticsApiError) as exc:
        if isinstance(exc, AnalyticsApiError):
            raise
        raise AnalyticsApiError("The analytics service is unavailable. Please try again.") from exc


def send_rating(payload: dict[str, Any]) -> None:
    _send_analytics_event("/analytics/ratings", payload, "rating_event_id")


def send_feedback(payload: dict[str, Any]) -> None:
    _send_analytics_event("/analytics/feedback", payload, "feedback_id")


def send_suggestion(payload: dict[str, Any]) -> None:
    _send_analytics_event("/analytics/suggestions", payload, "suggestion_id")
