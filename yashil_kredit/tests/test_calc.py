import pytest

from greencredit.calc import (Kiritma, KiritmaXatosi, Sozlamalar, annuitet_oylik, green_score,
                              hisobla, mln, namuna_kiritma, pul, raqam_oqi, tekshir)


def oddiy_kiritma(**kw) -> Kiritma:
    asos = dict(korxona="Test", elektr_oylik=[1000.0] * 12, gaz_oylik=[0.0] * 12,
                elektr_tarif=1000.0, investitsiya=12_000_000.0, quyosh_quvvati=4.0)
    asos.update(kw)
    return Kiritma(**asos)


def tekis() -> Sozlamalar:
    return Sozlamalar(quyosh_unumdorligi=1500, panel_degradatsiyasi=0, tarif_osishi=0,
                      elektr_co2=0.5, tahlil_muddati=10)


def test_quyosh_tejash_va_oqlash():
    # 4 kVt * 1500 = 6000 kVt·soat < 12000 iste'mol -> 6 mln so'm/yil, 12 mln investitsiya -> 2 yil
    n = hisobla(oddiy_kiritma(), tekis())
    assert n.yillik_tejash == pytest.approx(6_000_000)
    assert n.oqlash_muddati == pytest.approx(2.0)
    assert n.jami_tejash == pytest.approx(60_000_000)
    assert n.roi_foiz == pytest.approx(400)
    assert n.co2_yillik_t == pytest.approx(3.0)
    assert n.co2_ulush_foiz == pytest.approx(50)


def test_ortiqcha_quyosh_hisobga_olinmaydi():
    n = hisobla(oddiy_kiritma(quyosh_quvvati=100.0), tekis())
    assert n.elektr_tejash == pytest.approx(12_000)


def test_tejash_foizlari_qoshiladi():
    k = oddiy_kiritma(quyosh_quvvati=0.0, elektr_tejash_foiz=25.0, gaz_oylik=[100.0] * 12,
                      gaz_tarif=2000.0, gaz_tejash_foiz=50.0)
    n = hisobla(k, tekis())
    # elektr: 12000 * 25% = 3000 kVt·soat; gaz: 1200 * 50% = 600 m³
    assert n.elektr_tejash == pytest.approx(3000)
    assert n.gaz_tejash == pytest.approx(600)
    assert n.yillik_tejash == pytest.approx(3000 * 1000 + 600 * 2000)


def test_tarif_osishi_oqlashni_qisqartiradi():
    s = tekis()
    asl = hisobla(oddiy_kiritma(investitsiya=40_000_000.0), s).oqlash_muddati
    s.tarif_osishi = 10
    yangi = hisobla(oddiy_kiritma(investitsiya=40_000_000.0), s).oqlash_muddati
    assert yangi < asl


def test_oqlanmaydigan_loyiha():
    n = hisobla(oddiy_kiritma(investitsiya=1e12), tekis())
    assert n.oqlash_muddati is None
    assert n.score.oqlash_ball == 0


def test_annuitet():
    assert annuitet_oylik(1_200_000, 0, 1) == pytest.approx(100_000)
    # 1 mln, 12% yillik, 1 yil -> taxminan 88 849 so'm
    assert annuitet_oylik(1_000_000, 12, 1) == pytest.approx(88_848.79, abs=0.01)


def test_yashil_kredit_arzonroq():
    n = hisobla(namuna_kiritma(), Sozlamalar())
    assert n.kredit.yashil_oylik < n.kredit.oddiy_oylik
    assert n.kredit.yutuq > 0


def test_green_score_chegaralar():
    assert green_score(50, 3, 50).ball == 100
    assert green_score(50, 3, 50).daraja == "A"
    assert green_score(0, None, 0).ball == 0
    assert green_score(0, None, 0).daraja == "D"
    assert green_score(25, 6.5, 25).ball == 50


def test_tekshir_xatolar():
    assert tekshir(namuna_kiritma()) == []
    k = Kiritma()
    xatolar = tekshir(k)
    assert any("Korxona" in x for x in xatolar)
    with pytest.raises(KiritmaXatosi):
        hisobla(k)


def test_namuna_taqdimotga_yaqin():
    n = hisobla(namuna_kiritma(), Sozlamalar())
    assert n.investitsiya == 150_000_000
    assert 2.5 < n.oqlash_muddati < 3.5


@pytest.mark.parametrize("matn, kutilgan", [
    ("150 000 000", 150_000_000), ("1 234,5", 1234.5), ("1234.5", 1234.5),
    ("1,234.5", 1234.5), ("", 0.0), (" 7 200", 7200),
])
def test_raqam_oqi(matn, kutilgan):
    assert raqam_oqi(matn) == pytest.approx(kutilgan)


def test_raqam_oqi_xato():
    with pytest.raises(ValueError):
        raqam_oqi("abc")


def test_formatlash():
    assert pul(150_000_000) == "150 000 000"
    assert mln(150_000_000) == "150 mln"
    assert mln(49_410_000) == "49,4 mln"
    assert mln(1_500_000_000) == "1,5 mlrd"
