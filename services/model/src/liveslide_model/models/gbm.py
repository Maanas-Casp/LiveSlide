from __future__ import annotations

import numpy as np


def build_model(version: str, seed: int = 26001, positives: int | None = None,
                negatives: int | None = None):
    """Create the configured LightGBM model; v0 and v1 select features in the caller."""
    from lightgbm import LGBMClassifier

    if version not in {"v0", "v1"}:
        raise ValueError("version must be 'v0' or 'v1'")
    weight = negatives / positives if positives and negatives else 1.0
    return LGBMClassifier(
        objective="binary", random_state=seed, scale_pos_weight=weight,
        n_estimators=200, learning_rate=0.05, num_leaves=15, verbosity=-1,
    )


def tune_model(model, features, labels, groups):
    """Tune a small parameter grid using grouped folds from the training data only."""
    from sklearn.model_selection import GridSearchCV, GroupKFold

    groups = np.asarray(groups)
    folds = min(3, len(np.unique(groups)))
    if folds < 2:
        model.fit(features, labels)
        return model, {"tuning": "skipped: fewer than two training blocks"}
    cv_splits = []
    for train_idx, valid_idx in GroupKFold(n_splits=folds).split(features, labels, groups):
        if len(np.unique(np.asarray(labels)[train_idx])) == 2 and len(np.unique(np.asarray(labels)[valid_idx])) == 2:
            cv_splits.append((train_idx, valid_idx))
    if not cv_splits:
        model.fit(features, labels)
        return model, {"tuning": "skipped: grouped folds lack both classes"}
    search = GridSearchCV(
        model,
        {"n_estimators": [100, 200], "num_leaves": [7, 15]},
        scoring="average_precision",
        cv=cv_splits,
        n_jobs=1,
        refit=True,
    )
    search.fit(features, labels)
    return search.best_estimator_, {"best_params": search.best_params_,
                                    "best_grouped_cv_score": float(search.best_score_),
                                    "inner_folds": folds}
