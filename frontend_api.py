"""Small HTTP client for the deployed Doctoome chatbot API."""

import os
from typing import Any

import requests


DEFAULT_API_URL = "https://wp3xsfphbp.eu-west-3.awsapprunner.com/chat"
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


def api_url() -> str:
    return os.getenv("DOCTOOME_CHAT_API_URL", DEFAULT_API_URL)


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

    return payload


def send_message(message: str, conversation_id: str | None) -> dict[str, Any]:
    payload: dict[str, str] = {"message": message}
    if conversation_id is not None:
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
