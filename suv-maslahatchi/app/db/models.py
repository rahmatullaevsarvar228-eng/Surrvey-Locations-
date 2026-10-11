"""SQLAlchemy 2 modellari: foydalanuvchilar, dalalar, sug‘orish yozuvlari."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)        # Telegram user id
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    active_field_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    fields: Mapped[list[FieldRow]] = relationship(back_populates="user", cascade="all, delete-orphan")


class FieldRow(Base):
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    crop: Mapped[str] = mapped_column(String(16))
    soil: Mapped[str] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(16))
    planting: Mapped[date] = mapped_column(Date)
    area_ha: Mapped[float] = mapped_column(Float, default=1.0)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    eff: Mapped[float | None] = mapped_column(Float, nullable=True)
    place: Mapped[str | None] = mapped_column(String(64), nullable=True)   # viloyat nomi yoki None (GPS)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="fields")
    events: Mapped[list[IrrigationEvent]] = relationship(back_populates="field",
                                                         cascade="all, delete-orphan")


class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    field: Mapped[FieldRow] = relationship(back_populates="events")
