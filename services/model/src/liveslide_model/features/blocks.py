from __future__ import annotations

import math


def block_id(lat: float, lon: float, block_km: float) -> str:
    """Assign a stable approximate spatial block in local east/north kilometres."""
    if block_km <= 0:
        raise ValueError("block_km must be positive")
    north_km = lat * 111.32
    east_km = lon * 111.32 * math.cos(math.radians(lat))
    return f"{math.floor(north_km / block_km)}:{math.floor(east_km / block_km)}"
