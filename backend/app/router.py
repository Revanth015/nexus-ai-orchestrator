"""Compatibility facade for the current dynamic worker router."""

from .worker_router import route_task

__all__ = ["route_task"]
