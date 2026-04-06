"""In-memory session manager for demo. SQLite can be added later."""

from bot.models.state import FlowState


_sessions: dict[int, dict] = {}


def get_session(user_id: int) -> dict:
    if user_id not in _sessions:
        _sessions[user_id] = {
            "state": FlowState.IDLE,
            "selected_offer": None,
            "messages": [],
        }
    return _sessions[user_id]


def set_state(user_id: int, state: FlowState):
    get_session(user_id)["state"] = state


def get_state(user_id: int) -> FlowState:
    return get_session(user_id)["state"]


def set_selected_offer(user_id: int, offer_index: int):
    get_session(user_id)["selected_offer"] = offer_index


def get_selected_offer(user_id: int) -> int | None:
    return get_session(user_id)["selected_offer"]


def reset_session(user_id: int):
    _sessions[user_id] = {
        "state": FlowState.IDLE,
        "selected_offer": None,
        "messages": [],
    }
