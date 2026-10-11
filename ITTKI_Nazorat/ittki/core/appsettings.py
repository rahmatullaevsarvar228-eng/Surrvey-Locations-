"""M12. All program settings in one object (engine, account codes, control thresholds, general)."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import engine
from .controls import ControlSettings
from .defaults import DEFAULT_ACCOUNTS, DEFAULT_CONTROLS, DEFAULT_GENERAL
from .journal import Accounts


@dataclass
class AppSettings:
    engine: engine.Settings = field(default_factory=engine.Settings)
    accounts: Accounts = field(default_factory=Accounts)
    controls: ControlSettings = field(default_factory=ControlSettings)
    organization: str = DEFAULT_GENERAL["organization"]
    language: str = DEFAULT_GENERAL["language"]

    # ---- flat key/value form used by the `settings` table
    def to_flat(self) -> dict:
        d = {"organization": self.organization, "language": self.language,
             "amort_start": self.engine.amort_start, "nas_max_months": self.engine.nas_max_months}
        for fw in engine.FRAMEWORKS:
            d[f"categories.{fw}"] = sorted(self.engine.categories(fw))
        for k in DEFAULT_ACCOUNTS:
            d[f"account.{k}"] = getattr(self.accounts, k)
        for k, v in self.accounts.source.items():
            d[f"source.{k}"] = v
        for k in DEFAULT_CONTROLS:
            d[f"control.{k}"] = getattr(self.controls, k)
        return d

    @classmethod
    def from_flat(cls, d: dict) -> "AppSettings":
        """Raises AssertionError / ValueError on invalid values (S17)."""
        base = cls().to_flat()
        base.update(d)
        d = base
        included = {fw: set(d[f"categories.{fw}"]) for fw in engine.FRAMEWORKS}
        if included == {fw: set(engine.INCLUDED[fw]) for fw in engine.FRAMEWORKS}:
            included = None
        eng = engine.Settings(amort_start=d["amort_start"], nas_max_months=d["nas_max_months"], included=included)
        acc = Accounts(**{k: d[f"account.{k}"] for k in DEFAULT_ACCOUNTS},
                       source={c: d[f"source.{c}"] for c in sorted(engine.ALL_CATEGORIES)})
        ctl = ControlSettings(**{k: d[f"control.{k}"] for k in DEFAULT_CONTROLS})
        return cls(eng, acc, ctl, d["organization"], d["language"])
