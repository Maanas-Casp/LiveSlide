from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Cell(Base):
    __tablename__ = "cells"
    cell_id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(String, index=True)
    row: Mapped[int] = mapped_column(Integer)
    col: Mapped[int] = mapped_column(Integer)
    min_lon: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    slope_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    curvature: Mapped[float | None] = mapped_column(Float, nullable=True)
    twi: Mapped[float | None] = mapped_column(Float, nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Feature(Base):
    __tablename__ = "cell_features"
    __table_args__ = (UniqueConstraint("cell_id", "ts", name="uq_feature_cell_day"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    cell_id: Mapped[str] = mapped_column(ForeignKey("cells.cell_id"), index=True)
    ts: Mapped[date] = mapped_column(Date, index=True)
    rain_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_version: Mapped[str] = mapped_column(String, default="unknown")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Score(Base):
    __tablename__ = "cell_scores"
    __table_args__ = (UniqueConstraint("cell_id", "ts", "model_version", name="uq_score_cell_time_model"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    cell_id: Mapped[str] = mapped_column(ForeignKey("cells.cell_id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    risk_p: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Event(Base):
    __tablename__ = "landslide_events"
    __table_args__ = (UniqueConstraint("event_date", "latitude", "longitude", "source", name="uq_event_natural"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String)
    trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    fatalities: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cell_id: Mapped[str | None] = mapped_column(ForeignKey("cells.cell_id"), nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Road(Base):
    __tablename__ = "roads"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    road_class: Mapped[str] = mapped_column(String)
    geometry: Mapped[dict] = mapped_column(JSON)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Settlement(Base):
    __tablename__ = "settlements"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    client_report_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_path: Mapped[str] = mapped_column(String)
    photo_sha256: Mapped[str] = mapped_column(String)
    phash: Mapped[str] = mapped_column(String)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    exif_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exif_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    exif_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_mismatch_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    cell_id: Mapped[str | None] = mapped_column(ForeignKey("cells.cell_id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verifier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Review(Base):
    __tablename__ = "report_reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String, index=True)
    facts: Mapped[dict] = mapped_column(JSON)
    texts: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    entity: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String)
    row_hash: Mapped[str] = mapped_column(String)
