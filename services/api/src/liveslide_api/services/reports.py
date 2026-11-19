from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ExifTags
from sqlalchemy.orm import Session

from ..config import PHOTO_STORAGE_DIR
from ..models import Cell, Report

MAX_BYTES = 10 * 1024 * 1024


class UploadProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def _dms(value):
    return sum(float(part) / (60 ** index) for index, part in enumerate(value))


def _exif_data(image: Image.Image):
    exif = image.getexif()
    exif_time = None
    raw_time = exif.get(36867) or exif.get(306)
    if raw_time:
        try:
            exif_time = datetime.strptime(str(raw_time), "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    latitude = longitude = None
    try:
        raw_gps = exif.get_ifd(34853)
        gps = {ExifTags.GPSTAGS.get(key, key): value for key, value in raw_gps.items()}
        latitude = _dms(gps["GPSLatitude"]) * (-1 if gps.get("GPSLatitudeRef") == "S" else 1)
        longitude = _dms(gps["GPSLongitude"]) * (-1 if gps.get("GPSLongitudeRef") == "W" else 1)
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    return exif_time, latitude, longitude


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1, math.sqrt(a)))


def _cell_for_point(db: Session, lat: float, lon: float):
    return db.query(Cell).filter(Cell.min_lon <= lon, Cell.max_lon >= lon,
                                 Cell.min_lat <= lat, Cell.max_lat >= lat).first()


def perceptual_hash(image: Image.Image) -> str:
    try:
        import imagehash
        return str(imagehash.phash(image))
    except ImportError:
        import math
        pixels = list(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS).getdata())
        coefficients = []
        for v in range(8):
            for u in range(8):
                total = 0.0
                for y in range(32):
                    cy = math.cos(math.pi * (2 * y + 1) * v / 64)
                    for x in range(32):
                        total += pixels[y * 32 + x] * math.cos(math.pi * (2 * x + 1) * u / 64) * cy
                coefficients.append(total)
        median = sorted(coefficients[1:])[len(coefficients[1:]) // 2]
        return f"{sum((1 << index) for index, value in enumerate(coefficients) if value > median):016x}"


def create_report(db: Session, *, user_id: str, client_report_id: str, device_id: str | None,
                  lat: float | None, lon: float | None, location_name: str | None,
                  captured_at: datetime, note: str | None,
                  content: bytes, content_type: str):
    existing = db.query(Report).filter(Report.client_report_id == client_report_id).first()
    if existing:
        return existing, False
    location_name = location_name.strip() if location_name else None
    if (lat is None) != (lon is None):
        raise UploadProblem(422, "incomplete_coordinates", "Provide both coordinates or leave both empty")
    if lat is None and not location_name:
        raise UploadProblem(422, "location_required", "Add a place name or use your device location")
    if len(content) > MAX_BYTES:
        raise UploadProblem(413, "file_too_large", "Photo must be 10 MB or smaller")
    if content_type not in {"image/jpeg", "image/png"}:
        raise UploadProblem(415, "unsupported_media_type", "Only JPEG and PNG photos are accepted")
    if not (content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG\r\n\x1a\n")):
        raise UploadProblem(415, "invalid_image", "Photo bytes are not a valid JPEG or PNG")
    import io
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
        image = Image.open(io.BytesIO(content))
    except Exception as exc:
        raise UploadProblem(415, "invalid_image", "Photo could not be decoded") from exc
    exif_time, exif_lat, exif_lon = _exif_data(image)
    flags = []
    gps_distance = None
    if lat is None:
        flags.append("location_pending")
    if not image.getexif():
        flags.append("exif_missing")
    if exif_lat is not None and exif_lon is not None and lat is not None and lon is not None:
        gps_distance = haversine_m(exif_lat, exif_lon, lat, lon)
        if gps_distance > 500:
            flags.append("gps_mismatch")
    if exif_time and abs((exif_time - captured_at).total_seconds()) > 600:
        flags.append("exif_time_mismatch")
    photo_hash = hashlib.sha256(content).hexdigest()
    photo_phash = perceptual_hash(image)
    for other in db.query(Report.phash).all():
        try:
            if (int(other[0], 16) ^ int(photo_phash, 16)).bit_count() <= 5:
                flags.append("duplicate_photo")
                break
        except (TypeError, ValueError):
            continue
    cell = _cell_for_point(db, lat, lon) if lat is not None and lon is not None else None
    if lat is not None and lon is not None and not cell:
        flags.append("outside_grid")
    now = datetime.now(timezone.utc)
    path = Path(PHOTO_STORAGE_DIR) / now.strftime("%Y") / now.strftime("%m") / f"{uuid.uuid4()}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="JPEG", quality=90, exif=b"")
    # The verifier is intentionally a no-op until the later verification milestone.
    report = Report(client_report_id=client_report_id, user_id=user_id, device_id=device_id,
                    photo_path=str(path), photo_sha256=photo_hash, phash=photo_phash,
                    lat=lat, lon=lon, location_name=location_name,
                    captured_at=captured_at, received_at=now,
                    exif_time=exif_time, exif_lat=exif_lat, exif_lon=exif_lon,
                    gps_mismatch_m=gps_distance, flags=sorted(set(flags)),
                    cell_id=cell.cell_id if cell else None, status="pending", note=note,
                    verifier_score=None)
    db.add(report)
    return report, True
