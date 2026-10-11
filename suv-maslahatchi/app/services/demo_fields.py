"""
Uyushma paneli uchun NAMUNA (SINTETIK) dalalar — haqiqiy fermerlar emas.
Faqat dala sozlamalari sun’iy; ob-havo — keshdagi haqiqiy arxiv. Ekranda «Namuna (sintetik)» belgisi bilan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SampleField:
    id: str
    crop: str
    soil: str
    method: str
    area_ha: float
    planting_shift: int          # kesh ekish sanasiga nisbatan, kun
    last_irrigation_ago: int     # demo kunidan necha kun oldin sug‘orilgan

    def planting(self, base: date) -> date:
        return base + timedelta(days=self.planting_shift)


# Turli tuproq/usul/ekish sanasi kombinatsiyasi — talab egri chizig‘i tekis bo‘lmasligi uchun.
SAMPLE_FIELDS: tuple[SampleField, ...] = (
    SampleField("N-01", "paxta", "orta", "egat", 12.0, 0, 3),
    SampleField("N-02", "paxta", "yengil", "egat", 8.0, -5, 6),
    SampleField("N-03", "paxta", "ogir", "egat", 15.0, 5, 9),
    SampleField("N-04", "paxta", "orta", "tomchi", 4.0, 0, 1),
    SampleField("N-05", "paxta", "orta", "egat", 20.0, -10, 11),
    SampleField("N-06", "paxta", "yengil", "yomgir", 6.0, 3, 4),
    SampleField("N-07", "paxta", "ogir", "egat", 10.0, 8, 7),
    SampleField("N-08", "paxta", "orta", "egat", 9.0, -3, 13),
)
