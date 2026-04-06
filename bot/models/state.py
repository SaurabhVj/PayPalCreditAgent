from enum import Enum


class FlowState(str, Enum):
    IDLE = "idle"
    GREETED = "greeted"
    SCORED = "scored"
    OFFERS_SHOWN = "offers_shown"
    SELECTED = "selected"
    CONFIRMED = "confirmed"
    APPROVED = "approved"
