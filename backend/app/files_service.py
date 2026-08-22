"""Compatibility wrapper for the mission execution file reader.

The file storage implementation lives in file_store.py.  Older execution
imports use files_service.read_file, so keep that interface stable while
using the canonical file store implementation.
"""

from .file_store import read_file

__all__ = ["read_file"]
