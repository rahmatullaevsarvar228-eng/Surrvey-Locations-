"""Ma’lumotlar bazasi bilan ishlash (sinxron SQLAlchemy; bot handlerlarida qisqa tranzaksiyalar)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from engine.suv_engine import Field

from .models import Base, FieldRow, IrrigationEvent, User


class Repo:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)
        self._sm = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sm() as s, s.begin():
            yield s

    # ---------------------------------------------------------------- users
    def ensure_user(self, uid: int, lang: str = "uz") -> User:
        with self.session() as s:
            u = s.get(User, uid)
            if u is None:
                u = User(id=uid, lang=lang)
                s.add(u)
            return u

    def set_lang(self, uid: int, lang: str) -> None:
        with self.session() as s:
            u = s.get(User, uid) or User(id=uid)
            u.lang = lang
            s.add(u)

    def lang(self, uid: int) -> str:
        with self.session() as s:
            u = s.get(User, uid)
            return u.lang if u else "uz"

    # ---------------------------------------------------------------- fields
    def add_field(self, uid: int, fld: Field, last_irrigation: date | None, place: str | None = None) -> int:
        """Yangi dala qo‘shadi va uni faol qiladi."""
        self.ensure_user(uid)
        with self.session() as s:
            row = FieldRow(user_id=uid, crop=fld.crop, soil=fld.soil, method=fld.method,
                           planting=fld.planting, area_ha=fld.area_ha, lat=fld.lat, lon=fld.lon,
                           eff=fld.eff, place=place)
            s.add(row)
            s.flush()
            if last_irrigation:
                s.add(IrrigationEvent(field_id=row.id, date=last_irrigation))
            u = s.get(User, uid)
            assert u is not None
            u.active_field_id = row.id
            return row.id

    def fields_of(self, uid: int) -> list[FieldRow]:
        with self.session() as s:
            return list(s.scalars(select(FieldRow).where(FieldRow.user_id == uid).order_by(FieldRow.id)))

    def set_active(self, uid: int, field_id: int) -> bool:
        with self.session() as s:
            row = s.get(FieldRow, field_id)
            u = s.get(User, uid)
            if row is None or u is None or row.user_id != uid:
                return False
            u.active_field_id = field_id
            return True

    def current_field(self, uid: int) -> FieldRow | None:
        """Faol dala; belgilanmagan bo‘lsa — eng so‘nggisi."""
        with self.session() as s:
            u = s.get(User, uid)
            if u is not None and u.active_field_id is not None:
                row = s.get(FieldRow, u.active_field_id)
                if row is not None and row.user_id == uid:
                    return row
            return s.scalars(select(FieldRow).where(FieldRow.user_id == uid)
                             .order_by(FieldRow.id.desc()).limit(1)).first()

    def all_fields(self) -> list[FieldRow]:
        with self.session() as s:
            return list(s.scalars(select(FieldRow)))

    # ---------------------------------------------------------------- irrigation
    def add_irrigation(self, field_id: int, day: date, m3: float | None = None) -> None:
        with self.session() as s:
            s.add(IrrigationEvent(field_id=field_id, date=day, m3=m3))

    def last_irrigation(self, field_id: int) -> date | None:
        with self.session() as s:
            return s.scalar(select(func.max(IrrigationEvent.date))
                            .where(IrrigationEvent.field_id == field_id))

    def stats(self) -> tuple[int, int, int]:
        with self.session() as s:
            return (s.scalar(select(func.count()).select_from(User)) or 0,
                    s.scalar(select(func.count()).select_from(FieldRow)) or 0,
                    s.scalar(select(func.count()).select_from(IrrigationEvent)) or 0)


def to_engine(row: FieldRow) -> Field:
    return Field(crop=row.crop, soil=row.soil, method=row.method, planting=row.planting,
                 area_ha=row.area_ha, lat=row.lat, lon=row.lon, eff=row.eff)
