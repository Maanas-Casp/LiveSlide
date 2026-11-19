from liveslide_model.eval.cv import grouped_folds


def test_grouped_folds_never_split_a_block():
    groups = ["a"] * 4 + ["b"] * 4 + ["c"] * 4 + ["d"] * 4 + ["e"] * 4
    for train, test in grouped_folds(groups, 5):
        assert not (set(groups[i] for i in train) & set(groups[i] for i in test))
