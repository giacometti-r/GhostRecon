#!/bin/sh
set -eu

heads="$(alembic heads | grep -c '(head)' || true)"
if [ "$heads" -ne 1 ]; then
  echo "expected exactly one Alembic head, found $heads" >&2
  exit 1
fi

alembic upgrade head
alembic check
alembic upgrade head
