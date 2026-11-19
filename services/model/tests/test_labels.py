import pandas as pd

from liveslide_model.features.build import label_cell_days
from liveslide_model.ingest.inventory import read_inventory


def test_labels_future_event_and_excludes_near_event_negatives():
    cells = pd.DataFrame([{"cell_id": "AS-0000-0000", "min_lon": 0.0, "min_lat": 0.0,
                           "max_lon": 0.01, "max_lat": 0.01}])
    features = pd.DataFrame({"cell_id": ["AS-0000-0000"] * 5,
                             "ts": pd.date_range("2024-01-01", periods=5, tz="UTC")})
    events = pd.DataFrame({"event_date": ["2024-01-03"], "latitude": [0.005], "longitude": [0.005]})
    result = label_cell_days(features, cells, events, buffer_m=0, window_days=2,
                             negative_ratio=10, seed=1)
    positive_dates = set(result.loc[result.label == 1, "ts"].dt.day)
    assert positive_dates == {1, 2}
    assert not (result.label == 0).any()


def test_inventory_keeps_spatial_and_temporal_label_halo(tmp_path):
    path = tmp_path / "inventory.csv"
    pd.DataFrame({"event_date": ["2024-01-04"], "latitude": [0.015],
                  "longitude": [0.005], "source": ["GLC"]}).to_csv(path, index=False)
    events, counts = read_inventory(str(path), (0, 0, .01, .01), "2024-01-01", "2024-01-01",
                                    spatial_buffer_m=600, temporal_lookahead_days=3)
    assert len(events) == 1
    assert pd.isna(events.iloc[0].location_accuracy_m)
    assert counts["retained"] == 1
