# Liveslide evaluation protocol

Status: draft for mentor review. This protocol must be reviewed and committed before any model is trained or evaluated. Values marked provisional are defaults for the first real-data run, not validated scientific choices.

## Prediction unit and label

The unit of prediction is one 1 km grid cell on one day. The prediction time is the end of that day in UTC. The target is whether at least one recorded landslide occurs during the following 3 days, with its reported point inside the cell or no more than 1,000 m from the cell boundary. The 3-day window is a provisional short-lead warning horizon. The 1,000 m buffer is provisional and reflects the uncertainty common in regional landslide inventories; sensitivity analysis should compare smaller buffers when event-location accuracy supports it.

Events without usable coordinates or dates cannot define labels. Keep the event source and reported location accuracy with every retained event. Do not treat unrecorded events as confirmed negatives.

Inventory extraction must include a spatial halo at least as wide as the label buffer and a temporal lookahead at least as long as the label window. Otherwise, events just outside the study bbox or after the final feature date would be missed when assigning labels.

## Negative sampling

Candidate negatives are cell-days with no inventory event in the 3-day target window and no event within 3 days before the prediction time. Sample at most 10 negative cell-days per positive cell-day, stratified by calendar month. This ratio is provisional and must be reported with every result.

Case-control sampling changes the observed event prevalence. Precision and false-alarm estimates on the sampled table are not operational estimates. Report the sample ratio and sampled prevalence; estimate operational false-alarm rates only after reweighting to a documented population prevalence or evaluating against an unsampled time-and-space population.

## Splits

Use spatial blocks of 20 km, provisionally. Run five-fold grouped cross-validation by `block_id`; no block may occur in both train and test in a fold. Also run a temporal holdout: train on all configured seasons before the final monsoon season and test on that final season. Do not tune hyperparameters against either test fold or temporal holdout. Any tuning uses grouped folds formed only from the training portion.

The study region and date range are not yet confirmed. The configuration must supply them before real-data evaluation. Synthetic fixtures are for software checks only and must never be reported as research results.

## Metrics

For hits `H`, misses `M`, false alarms `F`, and correct negatives `C`:

- Probability of detection (POD) = `H / (H + M)`.
- False alarm ratio (FAR) = `F / (H + F)`.
- Critical success index (CSI) = `H / (H + M + F)`.
- Heidke skill score (HSS) = `2(HC - MF) / ((H + M)(M + C) + (H + F)(F + C))`.
- PR-AUC is average precision over ranked predictions.
- Brier score is the mean squared error between predicted probability and binary label.
- Expected calibration error (ECE) uses 10 equal-width probability bins; each bin contributes its sample fraction times the absolute difference between mean confidence and event frequency.

For undefined denominators, report `null` rather than silently substituting zero. State the positive class and probability threshold used for threshold-based metrics.

## Uncertainty

Use 1,000 bootstrap resamples of whole spatial blocks to calculate 95% percentile confidence intervals. For temporal holdout, resample spatial blocks from the holdout season. Preserve all rows within each selected block. If too few blocks or events make an interval unreliable, report that limitation rather than switching to row-level resampling.

## Draft cost matrix

Draft only; mentor approval is required before it affects decisions. A missed event has a much higher cost than a false alert, and a verification request costs less than either. No numeric costs are fixed in this protocol yet.

## Baselines and comparisons

Compare: (1) rainfall intensity-duration threshold, (2) the NASA LHASA product when matching data are available, (3) gradient boosting with dynamic features only (`v0`), and (4) gradient boosting with dynamic and static features (`v1`). Use the same region, event inventory, label window, split definitions, and evaluation rows for every comparable method. If LHASA is unavailable, report it as unavailable and state why; do not fabricate a score.

The intensity-duration baseline groups rain days above a configured cutoff into rainfall events, allowing at most one dry day between rain days. Fit `log(I) = log(a) - b log(D)` by 5th-quantile regression using only training data. Report `a`, `b`, the cutoff, the number of qualifying events, and the fit split. Alarm when observed event intensity exceeds the fitted lower-bound curve.

## Leakage and prohibited practices

Features for a prediction at time `t` may use only observations available at or before `t`. The feature builder must check this condition. Never use random row splits, tune on test blocks, report synthetic results as research results, or compare methods with different label windows. Record any later change to labels, buffers, windows, or exclusions here with its date and reason before rerunning the evaluation.

## Reproducibility record

Every run records the configuration, random seed, source-data hash, code commit, package versions, split identifiers, and output metrics. The first model run must happen only after this protocol has been committed and reviewed. Model artifacts and metrics must retain that record.
