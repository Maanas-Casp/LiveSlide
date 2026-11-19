from liveslide_model.eval.bootstrap import block_bootstrap
from liveslide_model.eval.metrics import binary_metrics


def test_bootstrap_returns_intervals_from_whole_blocks():
    labels = [1, 0, 1, 0, 1, 0]
    scores = [.9, .1, .8, .2, .7, .3]
    groups = ["a", "a", "b", "b", "c", "c"]
    intervals = block_bootstrap(labels, scores, groups, binary_metrics, n_resamples=30, seed=4)
    assert intervals["brier"][0] <= intervals["brier"][1]
    assert len(intervals["brier"]) == 2
