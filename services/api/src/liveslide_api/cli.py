from __future__ import annotations

import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from .db import Base, SessionLocal, engine
from .config import PHOTO_STORAGE_DIR
from .models import Cell, Event, Feature, Report, Road, Score, Settlement, User
from .security import hash_password
from .services.reports import perceptual_hash

DEV_PASSWORD = "liveslide-dev"


def seed():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        users = [
            ("officer@example.test", "officer", "Demo Officer"),
            ("volunteer@example.test", "volunteer", "Demo Volunteer"),
            ("admin@example.test", "admin", "Demo Admin"),
        ]
        user_rows = {}
        for email, role, name in users:
            user = session.query(User).filter_by(email=email).first()
            if not user:
                user = User(email=email, role=role, display_name=name,
                            password_hash=hash_password(DEV_PASSWORD))
                session.add(user)
                session.flush()
            user_rows[email] = user
        if session.query(Cell).first():
            session.commit()
            print("Seed data already exists; no rows added.")
            return

        rng = random.Random(26001)
        min_lon, min_lat, max_lon, max_lat = 91.6, 26.0, 91.9, 26.3
        width, height = (max_lon - min_lon) / 30, (max_lat - min_lat) / 30
        cells, scores = [], []
        now = datetime.now(timezone.utc)
        for row in range(30):
            for col in range(30):
                cell_id = f"AS-{row:04d}-{col:04d}"
                cell = Cell(cell_id=cell_id, state="AS", row=row, col=col,
                            min_lon=min_lon + col * width, min_lat=min_lat + row * height,
                            max_lon=min_lon + (col + 1) * width, max_lat=min_lat + (row + 1) * height,
                            elevation_m=100 + rng.random() * 1000, slope_deg=rng.random() * 40,
                            curvature=(rng.random() - .5) * 2, twi=rng.random() * 10, synthetic=True)
                cells.append(cell)
                rank = row * 30 + col
                threshold = ("IGNORE", 0.0, .30) if rank < 630 else ("WATCH", .30, .60) if rank < 810 else ("VERIFY", .60, .80) if rank < 873 else ("WARN", .80, .99)
                action, low, high = threshold
                scores.append(Score(cell_id=cell_id, ts=now - timedelta(minutes=rank),
                                    risk_p=rng.uniform(low, high), action=action,
                                    model_version="SYNTHETIC-v0", synthetic=True))
        session.bulk_save_objects(cells)
        session.bulk_save_objects(scores)
        session.commit()

        feature_rows = []
        for cell in cells:
            rain_history = [max(0, rng.gauss(12, 8)) for _ in range(90)]
            for index in range(90):
                def rolling(days):
                    return sum(rain_history[max(0, index - days + 1):index + 1])
                feature_rows.append(Feature(
                    cell_id=cell.cell_id, ts=date.today() - timedelta(days=89 - index),
                    rain_1d=rain_history[index], rain_3d=rolling(3), rain_7d=rolling(7),
                    rain_20d=rolling(20), soil_moisture=min(1, max(0, rng.random())),
                    source_version="SYNTHETIC-v0", synthetic=True))
        session.bulk_save_objects(feature_rows)
        session.commit()

        for index in range(12):
            lat = min_lat + rng.random() * (max_lat - min_lat)
            lon = min_lon + rng.random() * (max_lon - min_lon)
            cell = session.query(Cell).filter(Cell.min_lon <= lon, Cell.max_lon >= lon,
                                              Cell.min_lat <= lat, Cell.max_lat >= lat).first()
            session.add(Event(event_date=date.today() - timedelta(days=index * 31), latitude=lat,
                              longitude=lon, location_accuracy_m=500, source="SYNTHETIC",
                              trigger="rainfall", fatalities=0, cell_id=cell.cell_id if cell else None,
                              synthetic=True))
        for index in range(10):
            lon = min_lon + .02 + index * .025
            session.add(Road(name=f"SYNTHETIC Road {index + 1}", road_class="tertiary",
                             geometry={"type": "LineString", "coordinates": [[lon, 26.05], [lon + .01, 26.2]]},
                             synthetic=True))
        for index in range(8):
            session.add(Settlement(name=f"SYNTHETIC Settlement {index + 1}",
                                   population=100 + index * 40, latitude=26.03 + index * .03,
                                   longitude=91.62 + index * .03, synthetic=True))
        session.commit()

        image_dir = Path(PHOTO_STORAGE_DIR) / "2026" / "11"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / "SYNTHETIC-placeholder.jpg"
        Image.new("RGB", (32, 32), color=(190, 190, 190)).save(image_path, format="JPEG")
        volunteer = user_rows["volunteer@example.test"]
        for index in range(6):
            client_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"liveslide-synthetic-report-{index}"))
            if session.query(Report).filter_by(client_report_id=client_id).first():
                continue
            cell = cells[index]
            session.add(Report(
                client_report_id=client_id, user_id=volunteer.id, device_id="SYNTHETIC-device",
                photo_path=str(image_path), photo_sha256="synthetic-placeholder",
                phash=perceptual_hash(Image.open(image_path)),
                lat=(cell.min_lat + cell.max_lat) / 2, lon=(cell.min_lon + cell.max_lon) / 2,
                captured_at=now - timedelta(hours=index), received_at=now - timedelta(minutes=index),
                flags=["exif_missing"], cell_id=cell.cell_id, status="pending",
                note="SYNTHETIC demo report", synthetic=True))
        session.commit()
        print("Seeded 900 synthetic cells, 90 days of features, 12 events, 10 roads, 8 settlements and 6 reports.")
        print(f"Demo password: {DEV_PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if command == "seed":
        seed()
    else:
        raise SystemExit(f"Unknown command: {command}")
