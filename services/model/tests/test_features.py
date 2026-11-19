import pandas as pd
import pytest

from liveslide_model.features.build import assert_no_future_features, build_daily_features


def test_feature_builder_uses_only_present_and_past_days():
    daily = pd.DataFrame({"cell_id": ["a"] * 4, "ts": pd.date_range("2024-01-01", periods=4),
                          "rain_mm": [1, 2, 3, 4]})
    result = build_daily_features(daily)
    assert result["rain_3d"].iloc[2:].tolist() == [6, 9]
    audit = result.assign(source_max_ts=result["ts"])
    assert_no_future_features(audit)
    audit.loc[2, "source_max_ts"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="leakage"):
        assert_no_future_features(audit)


def test_feature_builder_rejects_missing_days():
    daily = pd.DataFrame({"cell_id": ["a", "a"],
                          "ts": pd.to_datetime(["2024-01-01", "2024-01-03"], utc=True),
                          "rain_mm": [1, 2]})
    with pytest.raises(ValueError, match="consecutive day"):
        build_daily_features(daily)
