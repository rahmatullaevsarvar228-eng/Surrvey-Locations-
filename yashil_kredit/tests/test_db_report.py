from greencredit.calc import Sozlamalar, hisobla, namuna_kiritma
from greencredit.db import Baza
from greencredit.report import pasport_yarat


def test_baza_saqlash_olish_ochirish(tmp_path):
    b = Baza(tmp_path / "t.db")
    k = namuna_kiritma()
    hid = b.saqlash(k, 84, "A")
    assert b.olish(hid) == k
    k.korxona = "Yangi nom"
    assert b.saqlash(k, 80, "A", hisob_id=hid) == hid
    assert [r["korxona"] for r in b.royxat()] == ["Yangi nom"]
    b.ochirish(hid)
    assert b.royxat() == []
    b.yopish()


def test_sozlamalar_saqlanadi(tmp_path):
    b = Baza(tmp_path / "t.db")
    assert b.sozlamalar() == Sozlamalar()
    b.sozlamalarni_saqlash(Sozlamalar(yashil_foiz=10.0))
    b.yopish()
    assert Baza(tmp_path / "t.db").sozlamalar().yashil_foiz == 10.0


def test_pasport_pdf(tmp_path):
    k, s = namuna_kiritma(), Sozlamalar()
    yol = pasport_yarat(tmp_path / "p.pdf", k, hisobla(k, s), s, 1)
    data = yol.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 3000
