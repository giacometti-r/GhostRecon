from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import requirements_for, validate_configuration

EXIT_VALID = 0
EXIT_INVALID = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GhostRecon runtime configuration.")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def _settings_error(exc: ValidationError) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(item) for item in error.get("loc", ())) or "settings"
        issues.append(
            {
                "profile": "unknown",
                "service": "unknown",
                "setting_name": location,
                "error_code": "invalid_setting",
                "remediation": f"set a supported value for GHOSTRECON_{location.upper()}",
            }
        )
    return issues


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profile = "unknown"
    service = "unknown"
    checks: list[str] = []
    try:
        settings = Settings()
    except ValidationError as exc:
        issues = _settings_error(exc)
    else:
        profile = settings.profile.value
        service = settings.service_name.value
        checks = [item.check_name for item in requirements_for(settings.service_name)]
        issues = [issue.as_dict() for issue in validate_configuration(settings)]

    valid = not issues
    payload: dict[str, object] = {
        "status": "valid" if valid else "invalid",
        "profile": profile,
        "service": service,
        "checks": checks,
        "issues": issues,
    }
    if args.format == "json":
        print(json.dumps(payload, sort_keys=True))
    elif valid:
        print(f"configuration valid: profile={profile} service={service}")
    else:
        print("configuration invalid", file=sys.stderr)
        for issue in issues:
            print(
                f"{issue['setting_name']}: {issue['error_code']} - {issue['remediation']}",
                file=sys.stderr,
            )
    return EXIT_VALID if valid else EXIT_INVALID


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
