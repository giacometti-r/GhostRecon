#!/usr/bin/env python3
"""Generate checked Sprint 25b operation and RLS inventories."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from ghostrecon.security.operations import OPERATIONS
from ghostrecon.service_apps import routers as _routers  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "generated"


def _migration(name: str):
    path = ROOT / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render() -> dict[Path, str]:
    operation_rows = OPERATIONS.matrix()
    schema = _migration("0016_security_completion_schema.py")
    rls_rows = [
        {
            "table": table,
            "classification": "protected",
            "enable_revision": "0018_enable_grouped_rls",
            "force_revision": "0019_force_grouped_rls",
            "crud_policies": ["select", "insert", "update", "delete"],
        }
        for table in sorted(schema.PROTECTED)
    ] + [
        {
            "table": table,
            "classification": "explicit_exclusion",
            "enable_revision": None,
            "force_revision": None,
            "crud_policies": [],
        }
        for table in sorted(schema.EXCLUDED)
    ]
    operation_md = [
        "# Generated operation matrix",
        "",
        "| Operation | Owner | Authentication | Permission | Assurance | RLS | CSRF | Rate |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for row in operation_rows:
        operation_md.append(
            f"| {row['operation_id']} | {row['owner']} | {row['authentication']} | "
            f"{row['permission'] or '-'} | {row['assurance'] or '-'} | "
            f"{row['rls']} | {row['csrf']} | {row['rate_class']} |"
        )
    rls_md = [
        "# Generated RLS matrix",
        "",
        "| Table | Classification | Enable | Force | CRUD policies |",
        "|---|---|---|---|---|",
    ]
    for row in rls_rows:
        rls_md.append(
            f"| {row['table']} | {row['classification']} | "
            f"{row['enable_revision'] or '-'} | {row['force_revision'] or '-'} | "
            f"{', '.join(row['crud_policies']) or '-'} |"
        )
    return {
        OUTPUT / "operation-matrix.json": json.dumps(operation_rows, indent=2) + "\n",
        OUTPUT / "operation-matrix.md": "\n".join(operation_md) + "\n",
        OUTPUT / "rls-matrix.json": json.dumps(rls_rows, indent=2) + "\n",
        OUTPUT / "rls-matrix.md": "\n".join(rls_md) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    stale: list[str] = []
    for path, content in _render().items():
        if check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(content)
    if stale:
        raise SystemExit("stale security matrices: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
