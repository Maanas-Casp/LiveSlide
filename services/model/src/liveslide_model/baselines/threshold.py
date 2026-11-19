from __future__ import annotations

import numpy as np
import statsmodels.api as sm


def fit_intensity_duration(intensity, duration, quantile: float = 0.05) -> dict:
    intensity = np.asarray(intensity, dtype=float)
    duration = np.asarray(duration, dtype=float)
    valid = (intensity > 0) & (duration > 0) & np.isfinite(intensity) & np.isfinite(duration)
    if valid.sum() < 3:
        raise ValueError("At least three positive finite rainfall events are required")
    x = np.log(duration[valid])
    y = np.log(intensity[valid])
    fit = sm.QuantReg(y, sm.add_constant(x)).fit(q=quantile)
    return {"a": float(np.exp(fit.params[0])), "b": float(-fit.params[1]),
            "events_used": int(valid.sum()), "quantile": quantile}


def rainfall_events(daily, rain_cutoff_mm: float = 1.0):
    """Group rain days; at most one dry day may occur inside an event."""
    import pandas as pd

    frame = daily.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values(["cell_id", "ts"])
    output = []
    for cell_id, rows in frame.groupby("cell_id"):
        active = []
        dry_gap = 0
        for row in rows.to_dict("records"):
            if float(row["rain_mm"]) >= rain_cutoff_mm:
                if active and dry_gap > 1:
                    output.append(_summarize(cell_id, active))
                    active = []
                active.append(row)
                dry_gap = 0
            elif active:
                dry_gap += 1
                if dry_gap > 1:
                    output.append(_summarize(cell_id, active))
                    active = []
                    dry_gap = 0
        if active:
            output.append(_summarize(cell_id, active))
    return pd.DataFrame(output, columns=["cell_id", "start", "end", "duration_days", "intensity_mm_day"])


def _summarize(cell_id, rows):
    duration_days = (rows[-1]["ts"] - rows[0]["ts"]).days + 1
    return {"cell_id": cell_id, "start": rows[0]["ts"], "end": rows[-1]["ts"],
            "duration_days": duration_days,
            "intensity_mm_day": sum(float(row["rain_mm"]) for row in rows) / duration_days}


def exceeds_threshold(intensity_mm_day: float, duration_days: float, fit: dict) -> bool:
    if intensity_mm_day < 0 or duration_days <= 0:
        raise ValueError("Intensity must be non-negative and duration must be positive")
    threshold = fit["a"] * duration_days ** (-fit["b"])
    return intensity_mm_day > threshold
