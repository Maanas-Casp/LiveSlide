import pytest

from liveslide_model.baselines.threshold import exceeds_threshold, fit_intensity_duration, rainfall_events


def test_threshold_fits_known_power_law():
    duration = [1, 2, 3, 4, 5, 6]
    intensity = [10 / (d ** 0.5) for d in duration]
    result = fit_intensity_duration(intensity, duration, quantile=.5)
    assert result["a"] == pytest.approx(10, rel=.02)
    assert result["b"] == pytest.approx(.5, rel=.02)
    assert result["events_used"] == 6
    assert exceeds_threshold(20, 1, result)


def test_rainfall_event_allows_one_dry_day_and_counts_elapsed_duration():
    import pandas as pd

    daily = pd.DataFrame({"cell_id": ["a"] * 4,
                          "ts": pd.date_range("2024-01-01", periods=4, tz="UTC"),
                          "rain_mm": [5, 0, 7, 0]})
    events = rainfall_events(daily, rain_cutoff_mm=1)
    assert len(events) == 1
    assert events.iloc[0].duration_days == 3
    assert events.iloc[0].intensity_mm_day == pytest.approx(4)
