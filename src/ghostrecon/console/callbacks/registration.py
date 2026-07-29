from typing import Any

from ghostrecon.common.config import Settings

from .action import register_action_callbacks
from .event import register_event_callbacks
from .incident import register_incident_callbacks
from .navigation import register_navigation_callbacks
from .review import register_review_callbacks
from .sequence import register_sequence_callbacks


def register_callbacks(dash_app: Any, settings: Settings) -> None:
    register_navigation_callbacks(dash_app, settings)
    register_action_callbacks(dash_app, settings)
    register_event_callbacks(dash_app, settings)
    register_incident_callbacks(dash_app, settings)
    register_review_callbacks(dash_app, settings)
    register_sequence_callbacks(dash_app, settings)
