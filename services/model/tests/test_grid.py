from liveslide_model.features.grid import make_grid


def test_grid_ids_count_from_southwest():
    grid = make_grid("AS", (91.6, 26.0, 91.62, 26.02), cell_km=1)
    assert grid.iloc[0].cell_id == "AS-0000-0000"
    assert grid.iloc[0].row == 0
    assert grid.iloc[0].col == 0
    assert grid.iloc[-1].row >= grid.iloc[0].row
    assert grid.iloc[-1].col >= grid.iloc[0].col
