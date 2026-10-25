"""Shared helpers for the dashboard pages.

Note: ``dashboard.lib.maps`` imports streamlit and is NOT re-exported here, so
``from dashboard.lib import config, data`` works without the demo group.
"""

from dashboard.lib import config, data  # noqa: F401

__all__ = ["config", "data"]
