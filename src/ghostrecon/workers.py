"""Compatibility import for the consolidated, signed worker task registry."""

from ghostrecon.worker_runtime import celery_app

__all__ = ["celery_app"]
