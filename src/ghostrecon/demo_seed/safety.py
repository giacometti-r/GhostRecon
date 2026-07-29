from ghostrecon.common.config import Settings


class DemoSeedSafetyError(RuntimeError):
    """Raised when demo seed is requested in a non-local environment."""


def assert_demo_seed_allowed(settings: Settings) -> None:
    if settings.profile.value == "local":
        return
    raise DemoSeedSafetyError("refusing to seed demo data outside the local profile")
