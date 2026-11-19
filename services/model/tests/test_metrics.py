import pytest

from liveslide_model.eval.metrics import binary_metrics


def test_metrics_hand_calculation():
    # y=[1,1,0,0], predicted=[1,0,1,0]: H=1, M=1, F=1, C=1; POD=.5, FAR=.5, CSI=1/3, HSS=0.
    result = binary_metrics([1, 1, 0, 0], [.9, .1, .8, .2], threshold=.5)
    assert result["pod"] == pytest.approx(.5)
    assert result["far"] == pytest.approx(.5)
    assert result["csi"] == pytest.approx(1 / 3)
    assert result["hss"] == pytest.approx(0)
    assert result["brier"] == pytest.approx(.375)
    assert result["pr_auc"] is not None
    assert result["ece"] == pytest.approx(.5)


def test_metrics_null_for_undefined_ratio():
    result = binary_metrics([0, 0], [.1, .2])
    assert result["pod"] is None
    assert result["far"] is None
