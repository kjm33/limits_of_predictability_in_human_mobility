"""Map rendering helpers.

`st.scatter_map` existed in streamlit 1.45-1.4x but was removed upstream; newer
streamlits ship the pydeck-based `st.map` with the same data-first interface.
This wrapper picks whichever element the installed version provides and filters
kwargs to its signature, so pages run unchanged on any streamlit >= 1.40.
"""

from __future__ import annotations

import inspect

import pandas as pd
import streamlit as st


def scatter_map(
    data: pd.DataFrame,
    *,
    lat: str = "lat",
    lon: str = "lon",
    color: str | None = None,
    size: str | None = None,
    zoom: float | None = None,
) -> None:
    """Scatter points on a tiled map; no-op with a caption for empty frames."""
    if data is None or len(data) == 0:
        st.caption("No points to map.")
        return
    fn = getattr(st, "scatter_map", None) or st.map
    kwargs: dict = {
        "latitude": lat,
        "longitude": lon,
        "use_container_width": True,
        "height": 420,
    }
    if color is not None:
        kwargs["color"] = color
    if size is not None:
        kwargs["size"] = size
    if zoom is not None and "zoom" in inspect.signature(fn).parameters:
        kwargs["zoom"] = zoom
    kwargs = {k: v for k, v in kwargs.items() if k in inspect.signature(fn).parameters}
    fn(data, **kwargs)
