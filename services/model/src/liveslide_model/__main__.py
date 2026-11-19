from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .config import load_config
from .features.build import build_daily_features, label_cell_days
from .features.grid import make_grid
from .ingest.manifest import write_manifest
from .publish.api_client import publish_batches


def _synthetic_rows(config):
    rng = np.random.default_rng(config["random_seed"])
    grid = make_grid(config["state_code"], tuple(config["bbox"]), config["grid_size_km"])
    rows = []
    for index, cell in grid.iterrows():
        position = (index + 0.5) / len(grid)
        if position < .70:
            action, lower, upper = "IGNORE", 0.0, 0.30
        elif position < .90:
            action, lower, upper = "WATCH", 0.30, 0.60
        elif position < .97:
            action, lower, upper = "VERIFY", 0.60, 0.80
        else:
            action, lower, upper = "WARN", 0.80, 1.0
        risk = float(rng.uniform(lower, upper))
        rows.append({"cell_id": cell.cell_id, "risk_p": risk, "action": action,
                     "model_version": "SYNTHETIC-v0", "synthetic": True})
    return rows


def main():
    parser = argparse.ArgumentParser(prog="liveslide_model")
    parser.add_argument("command", choices=["features", "baselines", "train", "evaluate", "publish", "ingest"])
    parser.add_argument("--config", default="configs/region.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true", help="send real scores to the Liveslide API")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "features":
        if config.get("synthetic", False):
            raise SystemExit("Refusing to create research features with synthetic region configuration")
        root = Path(__file__).resolve().parents[4]
        processed = root / "data/processed"
        daily = __import__("pandas").read_parquet(processed / "daily_rain.parquet")
        cells = __import__("pandas").read_parquet(processed / "cells.parquet")
        events = __import__("pandas").read_parquet(processed / "events.parquet")
        daily_features = build_daily_features(daily)
        frame = label_cell_days(daily_features, cells, events,
                                buffer_m=config["label_buffer_m"],
                                window_days=config["label_window_days"],
                                negative_ratio=config["negative_sampling_ratio"],
                                seed=config["random_seed"])
        if {"latitude", "longitude"} <= set(cells):
            from .features.blocks import block_id
            centres = cells.set_index("cell_id")[["latitude", "longitude"]]
            frame = frame.join(centres, on="cell_id")
            terrain_columns = [name for name in ("elevation_m", "slope_deg", "curvature", "twi")
                               if name in cells]
            if terrain_columns:
                terrain = cells.set_index("cell_id")[terrain_columns]
                frame = frame.join(terrain, on="cell_id")
            frame["block_id"] = [block_id(lat, lon, config["spatial_block_km"])
                                 for lat, lon in zip(frame.latitude, frame.longitude)]
        else:
            raise SystemExit("cells.parquet must include centroid latitude and longitude")
        from .features.build import write_feature_parquet
        source_files = [processed / "daily_rain.parquet", processed / "events.parquet"]
        version_hash = write_feature_parquet(frame, processed / "features.parquet", source_files, config)
        write_manifest(processed / "features.parquet", source="derived cell-day features",
                       version="1", start_date=config["start_date"], end_date=config["end_date"])
        print(f"Wrote {len(frame)} cell-day rows; data version {version_hash}")
    elif args.command in {"baselines", "train", "evaluate"}:
        from .eval.readiness import require_committed_protocol
        require_committed_protocol()
        root = Path(__file__).resolve().parents[4]
        frame = __import__("pandas").read_parquet(root / "data/processed/features.parquet")
        if args.command == "evaluate":
            from .eval.report import evaluate_table, print_metrics_table
            payload = evaluate_table(frame, config, output_root=root / "services/model/results",
                                    config_path=args.config)
            print_metrics_table(payload)
        elif args.command == "train":
            from .eval.report import DYNAMIC_FEATURES, STATIC_FEATURES
            from .models.gbm import build_model, tune_model
            for version, features in (("v0", DYNAMIC_FEATURES),
                                      ("v1", DYNAMIC_FEATURES + STATIC_FEATURES)):
                selected = [column for column in features if column in frame]
                if version == "v1" and len(selected) == len(DYNAMIC_FEATURES):
                    continue
                labels = frame.label.astype(int)
                model = build_model(version, config["random_seed"], int(labels.sum()), int((labels == 0).sum()))
                model, tuning = tune_model(model, frame[selected], labels, frame["block_id"])
                root_model = root / "services/model/results/models"
                root_model.mkdir(parents=True, exist_ok=True)
                import joblib
                from .eval.report import _git_commit, _sha256
                joblib.dump({"model": model, "version": version, "features": selected,
                             "config": config, "seed": config["random_seed"],
                             "data_hash": _sha256(root / "data/processed/features.parquet"),
                             "git_commit": _git_commit(), "tuning": tuning},
                            root_model / f"{version}.joblib")
                print(f"Saved {version} to {root_model}")
        else:
            print("Threshold baseline: use rainfall_events and fit_intensity_duration on training data.")
            print("LHASA baseline: see the explicit unavailable stub in ingest/lhasa.py.")
    elif args.command == "publish":
        if args.dry_run == args.live:
            raise SystemExit("Choose exactly one of --dry-run or --live")
        if args.dry_run:
            if not config.get("synthetic", False):
                raise SystemExit("Dry-run publishing uses only the clearly labelled synthetic fixture")
            rows = _synthetic_rows(config)
        else:
            if config.get("synthetic", True) or not config.get("real_data_enabled", False):
                raise SystemExit("Refusing to publish scores from a SYNTHETIC or unconfirmed region")
            from .eval.readiness import require_committed_protocol
            require_committed_protocol()
            import joblib
            root = Path(__file__).resolve().parents[4]
            bundle_path = root / "services/model/results/models/v1.joblib"
            feature_path = root / "data/processed/features.parquet"
            if not bundle_path.is_file() or not feature_path.is_file():
                raise SystemExit("Train a real model and build real features before live publishing")
            bundle = joblib.load(bundle_path)
            features = __import__("pandas").read_parquet(feature_path)
            latest = features.sort_values("ts").groupby("cell_id", as_index=False).tail(1)
            risk = bundle["model"].predict_proba(latest[bundle["features"]])[:, 1]
            rows = []
            for cell_id, timestamp, probability in zip(latest.cell_id, latest.ts, risk):
                action = "IGNORE" if probability < .30 else "WATCH" if probability < .60 else "VERIFY" if probability < .80 else "WARN"
                rows.append({"cell_id": cell_id, "ts": timestamp.isoformat(), "risk_p": float(probability),
                             "action": action, "model_version": bundle["version"], "synthetic": False})
        count = publish_batches("scores", rows, dry_run=args.dry_run,
                                output_dir=Path("results") / "SYNTHETIC-dry-run")
        print(json.dumps({"rows": count, "dry_run": args.dry_run,
                          "synthetic": bool(config.get("synthetic", False))}, indent=2))
    elif args.command == "ingest":
        if config.get("synthetic", True) or not config.get("real_data_enabled", False):
            raise SystemExit("Ingestion is disabled for the SYNTHETIC fixture. Confirm a real region first.")
        root = Path(__file__).resolve().parents[4]
        raw_root = root / "data/raw"
        processed = root / "data/processed"
        inventory_path = Path(config.get("inventory_file", raw_root / "inventory/events.csv"))
        if not inventory_path.is_absolute():
            inventory_path = root / inventory_path
        if not inventory_path.is_file():
            raise SystemExit(f"Place a licensed inventory CSV at {inventory_path} before ingestion")
        import pandas as pd
        from .ingest.dem import ingest as ingest_dem
        from .ingest.imerg import ingest as ingest_imerg
        from .ingest.inventory import read_inventory, write_events_geojson
        from .ingest.osm import ingest as ingest_osm
        from .ingest.smap import ingest as ingest_smap
        grid = make_grid(config["state_code"], tuple(config["bbox"]), config["grid_size_km"])
        processed.mkdir(parents=True, exist_ok=True)
        grid.to_parquet(processed / "cells.parquet", index=False)
        rainfall = ingest_imerg(config, grid, raw_root)
        moisture = ingest_smap(config, grid, raw_root)
        rainfall["ts"] = pd.to_datetime(rainfall["ts"], utc=True).dt.floor("D")
        moisture["ts"] = pd.to_datetime(moisture["ts"], utc=True).dt.floor("D")
        daily = rainfall.merge(moisture, on=["cell_id", "ts"], how="outer", validate="one_to_one")
        expected_dates = pd.date_range(config["start_date"], config["end_date"], freq="D", tz="UTC")
        complete_index = pd.MultiIndex.from_product(
            [grid.cell_id, expected_dates], names=["cell_id", "ts"]
        )
        daily = (daily.set_index(["cell_id", "ts"]).reindex(complete_index)
                 .reset_index().sort_values(["cell_id", "ts"]))
        missing_counts = daily[["rain_mm", "soil_moisture"]].isna().sum().to_dict()
        daily.to_parquet(processed / "daily_rain.parquet", index=False)
        write_manifest(processed / "daily_rain.parquet", source="IMERG and SMAP daily cell samples",
                       version=f"{config['imerg_version']}+{config['smap_version']}",
                       start_date=config["start_date"], end_date=config["end_date"],
                       metadata={"spatial_sampling": "nearest source pixel at cell centroid",
                                 "soil_moisture_aggregation": "mean of available 3-hourly samples by UTC day",
                                 "missing_values": missing_counts})
        terrain = ingest_dem(config, grid, raw_root, processed)
        grid = grid.merge(terrain, on="cell_id", how="left", validate="one_to_one")
        grid.to_parquet(processed / "cells.parquet", index=False)
        events, counts = read_inventory(
            str(inventory_path), tuple(config["bbox"]), config["start_date"], config["end_date"],
            spatial_buffer_m=config["label_buffer_m"],
            temporal_lookahead_days=config["label_window_days"],
        )
        events.to_parquet(processed / "events.parquet", index=False)
        write_events_geojson(events, processed / "events.geojson")
        write_manifest(processed / "events.parquet", source="licensed landslide inventory CSV",
                       version="input file", start_date=config["start_date"], end_date=config["end_date"],
                       metadata={"inventory_path": str(inventory_path), "retention_counts": counts,
                                 "license_review": "per-record review required"})
        ingest_osm(config, processed)
        (processed / "data_quality.json").write_text(
            json.dumps({"missing_daily_values": missing_counts, "inventory": counts}, indent=2),
            encoding="utf-8")
        print(json.dumps({"cells": len(grid), "daily_rows": len(daily), "events": counts,
                          "missing_daily_values": missing_counts}, indent=2))


if __name__ == "__main__":
    main()
