from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ghostrecon.common.configuration import RuntimeProfile

PROHIBITED_SYNTHETIC_MARKERS = frozenset(
    {"demo", "synthetic_demo", "demo_inferred", "local_demo", "local-demo"}
)
GUARDED_LINEAGE_FIELDS = frozenset(
    {"provider", "geocode_provider", "calendar_provider", "adapter_type", "source"}
)


class SyntheticPersistenceError(ValueError):
    """Raised before synthetic provider or lineage markers reach a strict-profile database."""

    def __init__(self, model_name: str, field_name: str) -> None:
        self.model_name = model_name
        self.field_name = field_name
        super().__init__(
            f"synthetic provider or lineage marker rejected in {model_name}.{field_name}"
        )


def enable_synthetic_persistence_guard(session: Session, profile: RuntimeProfile) -> None:
    session.info["ghostrecon_profile"] = profile


@event.listens_for(Session, "before_flush")
def _reject_synthetic_lineage(session: Session, _context: object, _instances: object) -> None:
    profile = session.info.get("ghostrecon_profile")
    if profile not in {RuntimeProfile.STAGING, RuntimeProfile.PRODUCTION}:
        return
    for instance in (*session.new, *session.dirty):
        state = inspect(instance)
        is_new = instance in session.new
        for field_name in GUARDED_LINEAGE_FIELDS.intersection(state.mapper.attrs.keys()):
            attribute = state.attrs[field_name]
            if not is_new and not attribute.history.has_changes():
                continue
            value = attribute.value
            if isinstance(value, str) and value.strip().lower() in PROHIBITED_SYNTHETIC_MARKERS:
                raise SyntheticPersistenceError(type(instance).__name__, field_name)
