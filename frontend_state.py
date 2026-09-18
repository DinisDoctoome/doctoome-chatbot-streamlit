"""State transitions for chat history and analytics UX."""

from collections.abc import Callable, MutableMapping
from typing import Any
from uuid import uuid4

from frontend_api import AnalyticsApiError

State = MutableMapping[str, Any]
Sender = Callable[[dict[str, Any]], None]
IdFactory = Callable[[], str]


def new_event_id() -> str:
    return str(uuid4())


def initialize_state(state: State) -> None:
    state.setdefault("user_id", None)
    state.setdefault("ui_language", "en")
    state.setdefault("conversation_id", None)
    state.setdefault("messages", [])
    state.setdefault("pending_options", [])
    state.setdefault("ratings_by_message", {})
    state.setdefault("feedback_ui_state", {})
    state.setdefault("submitted_feedback_ids", set())
    state.setdefault("suggestion_ui_state", {})


def reset_conversation(state: State) -> None:
    state["conversation_id"] = None
    state["messages"] = []
    state["pending_options"] = []
    state["ratings_by_message"] = {}
    state["feedback_ui_state"] = {}
    state["submitted_feedback_ids"] = set()
    state["suggestion_ui_state"] = {}


def append_user_message(
    state: State, content: str, user_message_id: str, display_content: str | None = None
) -> None:
    state["messages"].append(
        {
            "role": "user",
            "content": display_content or content,
            "user_message_id": user_message_id,
            "turn_id": None,
        }
    )


def append_assistant_response(state: State, response: dict[str, Any]) -> None:
    turn_id = response.get("turn_id")
    for message in reversed(state["messages"]):
        if message["role"] == "user" and message.get("turn_id") is None:
            message["turn_id"] = turn_id
            break

    conversation_id = response.get("conversation_id") or state["conversation_id"]
    state["messages"].append(
        {
            "role": "assistant",
            "content": response["message"],
            "url": response["url"],
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "assistant_message_id": response.get("assistant_message_id"),
        }
    )
    if response.get("conversation_id") is not None:
        state["conversation_id"] = response["conversation_id"]
    state["pending_options"] = response["options"]


def rate_assistant(
    state: State,
    message: dict[str, Any],
    rating: str,
    sender: Sender,
    id_factory: IdFactory = new_event_id,
) -> bool:
    assistant_message_id = message.get("assistant_message_id")
    if assistant_message_id is None or rating not in {"up", "down"}:
        return False

    rating_state = state["ratings_by_message"].setdefault(assistant_message_id, {})
    if rating_state.get("rating") == rating and not rating_state.get("pending_event_id"):
        return False

    if rating_state.get("pending_rating") == rating and rating_state.get("pending_event_id"):
        event_id = rating_state["pending_event_id"]
    else:
        event_id = id_factory()
        rating_state["pending_event_id"] = event_id
        rating_state["pending_rating"] = rating

    payload = {
        "rating_event_id": event_id,
        "user_id": state["user_id"],
        "conversation_id": message.get("conversation_id"),
        "turn_id": message.get("turn_id"),
        "assistant_message_id": assistant_message_id,
        "rating": rating,
    }
    try:
        sender(payload)
    except AnalyticsApiError:
        rating_state["error"] = True
        return False

    rating_state["rating"] = rating
    rating_state["rating_event_id"] = event_id
    rating_state["error"] = False
    rating_state.pop("pending_event_id", None)
    rating_state.pop("pending_rating", None)
    if rating == "down":
        rating_state["latest_down_event_id"] = event_id
    return True


def submit_feedback_event(
    state: State,
    message: dict[str, Any],
    selected_reasons: list[str],
    feedback_text: str,
    sender: Sender,
    id_factory: IdFactory = new_event_id,
) -> bool:
    assistant_message_id = message.get("assistant_message_id")
    if assistant_message_id is None or (not selected_reasons and not feedback_text.strip()):
        return False

    rating_state = state["ratings_by_message"].get(assistant_message_id, {})
    rating_event_id = rating_state.get("latest_down_event_id")
    if rating_state.get("rating") != "down" or rating_event_id is None:
        return False

    feedback_state = state["feedback_ui_state"].setdefault(assistant_message_id, {})
    if feedback_state.get("submitted_rating_event_id") == rating_event_id:
        return False

    retrying_same_payload = (
        feedback_state.get("pending_rating_event_id") == rating_event_id
        and feedback_state.get("pending_reasons") == list(selected_reasons)
        and feedback_state.get("pending_text") == feedback_text
    )
    if retrying_same_payload:
        feedback_id = feedback_state["pending_feedback_id"]
    else:
        feedback_id = id_factory()
        feedback_state["pending_feedback_id"] = feedback_id
        feedback_state["pending_rating_event_id"] = rating_event_id
        feedback_state["pending_reasons"] = list(selected_reasons)
        feedback_state["pending_text"] = feedback_text

    payload = {
        "feedback_id": feedback_id,
        "rating_event_id": rating_event_id,
        "user_id": state["user_id"],
        "conversation_id": message.get("conversation_id"),
        "turn_id": message.get("turn_id"),
        "assistant_message_id": assistant_message_id,
        "selected_reasons": list(selected_reasons),
        "feedback_text": feedback_text,
    }
    try:
        sender(payload)
    except AnalyticsApiError:
        feedback_state["error"] = True
        return False

    feedback_state["error"] = False
    feedback_state["submitted_rating_event_id"] = rating_event_id
    feedback_state.pop("pending_feedback_id", None)
    feedback_state.pop("pending_rating_event_id", None)
    feedback_state.pop("pending_reasons", None)
    feedback_state.pop("pending_text", None)
    state["submitted_feedback_ids"].add(feedback_id)
    return True


def submit_suggestion_event(
    state: State,
    suggestion_text: str,
    sender: Sender,
    id_factory: IdFactory = new_event_id,
) -> bool:
    if not suggestion_text.strip():
        return False

    assistant_message_id = next(
        (
            message.get("assistant_message_id")
            for message in reversed(state["messages"])
            if message.get("role") == "assistant" and message.get("assistant_message_id")
        ),
        None,
    )
    suggestion_state = state["suggestion_ui_state"]
    if (
        suggestion_state.get("pending_text") == suggestion_text
        and suggestion_state.get("pending_suggestion_id")
    ):
        suggestion_id = suggestion_state["pending_suggestion_id"]
    else:
        suggestion_id = id_factory()
        suggestion_state["pending_suggestion_id"] = suggestion_id
        suggestion_state["pending_text"] = suggestion_text

    payload = {
        "suggestion_id": suggestion_id,
        "user_id": state["user_id"],
        "conversation_id": state["conversation_id"],
        "assistant_message_id": assistant_message_id,
        "suggestion_text": suggestion_text,
    }
    try:
        sender(payload)
    except AnalyticsApiError:
        suggestion_state["error"] = True
        suggestion_state["success"] = False
        return False

    suggestion_state.clear()
    suggestion_state["success"] = True
    return True
