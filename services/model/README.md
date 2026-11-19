# Liveslide model pipeline

Python package for source-data ingestion, cell-day feature building, baselines, grouped evaluation, and score publishing. It targets Python 3.11. Install from this directory with `pip install -e '.[dev,geo,nasa]'` when those optional capabilities are needed.

The checked-in region config is a **SYNTHETIC software fixture**, not a research region. The actual study region, dates, mentor-approved label protocol, contracts, and data access must be confirmed before real ingestion. The LHASA Version 1.1 archive ends in 2020, so it may not overlap a later study period.

The evaluation protocol must be committed before the first model run. Synthetic data are for offline software checks only; never include synthetic results in research findings.

Terrain processing uses bilinear reprojection to a local UTM CRS at 30 m, Horn's 3x3 gradient for slope, a Laplacian of elevation for total curvature, and D8 downslope accumulation for a topographic wetness index. These derivatives are initial choices and should be reviewed against the study area's terrain and raster edge effects before research use.
