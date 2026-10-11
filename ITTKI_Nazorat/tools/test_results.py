"""Generates docs/test_results.md: scenarios S1–S20 (TZ section 8) with ACTUAL engine results and the
pytest outcome of each scenario test.  Run:  python tools/test_results.py"""
import os
import platform
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date as d, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from ittki.core.engine import Cost, Settings, carrying_amount, evaluate, reconcile, schedule  # noqa: E402
from tests.test_engine import M, base_costs, proj, yes_all  # noqa: E402


def m(v):
    return f"{v:,}".replace(",", " ")


def mln(v):
    return f"{v / M:,.0f} млн".replace(",", " ") if v % M == 0 else m(v)


def has(r, code):
    return any(code in w for w in r["warnings"])


def both(p, s=Settings(), **kw):
    return evaluate(p, "IAS38", s, **kw), evaluate(p, "NAS11", s, **kw)


def scenarios():
    out = []

    def add(no, name, ias, nas, test):
        out.append((no, name, ias, nas, test))

    a, b = both(proj(development_start=None, available_for_use=None, assessments=[]))
    add("S1", "Только исследование", f"капит. {mln(a['capitalized'])} / расход {mln(a['expensed'])}",
        f"капит. {mln(b['capitalized'])} / расход {mln(b['expensed'])}", "test_s1_research_only")

    p = proj(); a, b = both(p); sa, sb = schedule(a, p), schedule(b, p)
    add("S2", "Базовый", f"капит. {mln(a['capitalized'])}, {a['amort_months']} мес., с {sa[0]['period_end']:%m.%Y}",
        f"капит. {mln(b['capitalized'])}, {b['amort_months']} мес., с {sb[0]['period_end']:%m.%Y}",
        "test_s2_base_and_amortization")
    r = reconcile(p, d(2025, 12, 31))
    add("S2", "Балансовая стоимость 31.12.2025",
        f"{m(r['IAS38_carrying'])} (= 550 млн − 12 × {m(550 * M // 96)})",
        f"{m(r['NAS11_carrying'])} (= 550 млн − 12 × {m(550 * M // 60)})", "test_s2_base_and_amortization")

    p = proj(available_for_use=d(2025, 1, 15)); a = evaluate(p, "IAS38")
    s0 = schedule(a, p)[0]["period_end"]
    add("S2b", "Акт 15.01.2025, `auto`", f"амортизация с {s0:%m.%Y}",
        f"амортизация с {schedule(evaluate(p, 'NAS11'), p)[0]['period_end']:%m.%Y}",
        "test_s2b_amortization_start_settings")

    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K4="no")]))
    add("S3", "K4 = Yo'q", mln(a["capitalized"]), mln(b["capitalized"]), "test_s3_no_future_benefit")
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K3="no")]))
    add("S4", "K3 = Yo'q", mln(a["capitalized"]), mln(b["capitalized"]), "test_s4_ability_criterion_difference")
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K5="noevidence")]))
    add("S5", "K5 = Ha без документа", f"{mln(a['capitalized'])} + {'E1' if has(a, 'E1') else '—'}",
        f"{mln(b['capitalized'])} + {'E1' if has(b, 'E1') else '—'}", "test_s5_yes_without_evidence")
    a, b = both(proj(phases_separable=False))
    add("S6", "Стадии не разделить", mln(a["capitalized"]), mln(b["capitalized"]),
        "test_s6_phases_not_separable")
    p = proj(available_for_use=None, abandoned_on=d(2025, 3, 1)); a, b = both(p)
    add("S7", "Прекращён 01.03.2025 до готовности", f"списание {mln(a['writeoff'])}",
        f"списание {mln(b['writeoff'])}", "test_s7_abandoned_before_ready")
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K1="expert"), yes_all(d(2024, 10, 1))]))
    add("S8", "K1 «Ekspert» 01.07, подтверждён 01.10.2024", f"{mln(a['capitalized'])} (критерии с {a['first_met_on']:%d.%m.%Y})",
        mln(b["capitalized"]), "test_s8_expert_then_confirmed")
    p = proj(available_for_use=None, impairment_test_dates=[])
    a, b = evaluate(p, "IAS38", as_of=d(2025, 1, 31)), evaluate(p, "NAS11", as_of=d(2025, 1, 31))
    add("S9", "Не готов, теста за 2024 нет, «сегодня» 31.01.2025", "E5" if has(a, "E5") else "нет E5",
        "E5" if has(b, "E5") else "нет E5", "test_s9_annual_impairment_test_ias_only")
    p = proj(impairment_event=(d(2025, 12, 31), 300 * M)); res = []
    for fw in ("IAS38", "NAS11"):
        sch = schedule(evaluate(p, fw), p)
        row = next(x for x in sch if x["impairment"])
        res.append(f"остаток после декабря {mln(row['closing'])}; амортизация + обесценение = "
                   f"{mln(sum(x['amortization'] + x['impairment'] for x in sch))}")
    add("S10", "Обесценение 31.12.2025 до 300 млн", res[0], res[1], "test_s10_impairment_after_ready")
    p = proj(assessments=[yes_all(d(2024, 7, 1)), yes_all(d(2024, 9, 1), K4="no")]); a, b = both(p)
    wd = b["nas_writeoff_rows"][0][0] if b["nas_writeoff_rows"] else None
    add("S11", "01.09.2024 новая оценка K4 = Yo'q",
        f"капит. {mln(a['capitalized'])}" + (" + предупреждение IAS 36" if has(a, "IAS 36") else ""),
        f"капит. {mln(b['capitalized'])}, списание {mln(b['nas_criteria_writeoff'])} "
        f"{wd:%d.%m.%Y}", "test_s11_criteria_revoked")
    p = proj(abandoned_on=d(2025, 7, 10)); res = []
    for fw, n in (("IAS38", 96), ("NAS11", 60)):
        r_ = evaluate(p, fw)
        res.append(f"{len(schedule(r_, p))} мес., списание {m(r_['writeoff'])} "
                   f"(= 550 млн − 6 × {m(550 * M // n)})")
    add("S12", "Прекращён 10.07.2025 после готовности", res[0], res[1], "test_s12_abandoned_after_ready")
    dec = {sc: both(proj(scope=sc)) for sc in ("mineral_exploration", "contract_for_customer")}
    add("S13", "Тип «geologik qidiruv» / «buyurtma asosida»",
        " / ".join(dec[s][0]["decision"] for s in dec), " / ".join(dec[s][1]["decision"] for s in dec),
        "test_s13_out_of_scope")
    p = proj(impairment_event=(d(2024, 12, 15), 400 * M)); res = []
    for fw in ("IAS38", "NAS11"):
        r_ = evaluate(p, fw)
        res.append(f"стоимость {mln(carrying_amount(r_, p, d(2024, 12, 31)))}, амортизируется "
                   f"{mln(sum(x['amortization'] for x in schedule(r_, p)))}")
    add("S14", "Обесценение 15.12.2024 до готовности, 400 млн", res[0], res[1],
        "test_s14_impairment_before_ready")
    extra = [Cost(d(2024, 11, 20), 10 * M, "legal_registration"), Cost(d(2024, 11, 21), 5 * M, "selling")]
    a, b = both(proj(costs=base_costs() + extra))
    add("S15", "+ регистрация права 10 млн, + расходы на продажу 5 млн", mln(a["capitalized"]),
        mln(b["capitalized"]), "test_s15_categories")
    a, b = both(proj(expected_net_benefit=400 * M))
    r8 = sum(x["amount"] for x in b["rows"] if x["reason"].startswith("R8"))
    add("S16", "Ожидаемая чистая выгода 400 млн",
        f"{mln(a['capitalized'])}" + (" + предупреждение IAS 36.12" if has(a, "IAS 36.12") else ""),
        f"{mln(b['capitalized'])} (п.13: {mln(r8)} в расход)", "test_s16_nas_benefit_limit")
    rej = []
    for kw in ({"amort_start": "tomorrow"}, {"nas_max_months": 72}):
        try:
            Settings(**kw); rej.append("принято")
        except AssertionError:
            rej.append("отклоняется")
    add("S17", "Неверная настройка (`amort_start`, срок > 60 мес.)", " / ".join(rej), " / ".join(rej),
        "test_s17_invalid_settings_rejected")
    costs = [Cost(d(2024, 7, 1), 10 * M, "salary"), Cost(d(2024, 4, 1), 7 * M, "salary"),
             Cost(d(2025, 1, 1), 9 * M, "salary")]
    res = []
    for fw in ("IAS38", "NAS11"):
        by = {(x["date"], x["amount"]): x["treatment"] for x in evaluate(proj(costs=costs), fw)["rows"]}
        t = {"capitalize": "капит.", "expense": "расход"}
        res.append(" / ".join(t[by[k]] for k in ((d(2024, 7, 1), 10 * M), (d(2024, 4, 1), 7 * M),
                                                  (d(2025, 1, 1), 9 * M))))
    add("S18", "Затрата в день оценки / в день начала разработки / в день акта", res[0], res[1],
        "test_s18_same_day_and_boundary_dates")
    a, b = both(proj(development_start=d(2024, 7, 1), costs=[Cost(d(2024, 7, 1), 10 * M, "salary")]))
    add("S18b", "Начало разработки = оценка = затрата (01.07.2024)", f"капит. {mln(a['capitalized'])}",
        f"капит. {mln(b['capitalized'])}", "test_s18b_development_start_day_is_development")
    a, b = both(proj(available_for_use=None, abandoned_on=d(2024, 10, 1)))
    add("S19", "Прекращён 01.10.2024; затрата 10.11.2024",
        f"капит. {mln(a['capitalized'])}, списание {mln(a['writeoff'])}",
        f"капит. {mln(b['capitalized'])}, списание {mln(b['writeoff'])}",
        "test_s19_costs_after_abandonment_expensed")
    a = evaluate(proj(impairment_test_dates=[d(2024, 12, 20)]), "IAS38", as_of=d(2026, 6, 30))
    add("S20", "Готов 01.01.2025, тест за 2024 есть, «сегодня» 30.06.2026", "E5" if has(a, "E5") else "E5 нет", "—",
        "test_s20_no_e5_after_asset_ready")
    return out


EXPECTED = {   # TZ section 8, verbatim
    "S1": ("0 / расход 940 млн", "то же"),
    "S2": ("капит. 550 млн, 96 мес., с января 2025", "550 млн, 60 мес."),
    "S2#": ("550 млн − 12 × 5 729 166", "550 млн − 12 × 9 166 666"),
    "S2b": ("амортизация с февраля", "то же"),
    "S3": ("0", "0"), "S4": ("0", "550 млн"), "S5": ("0 + E1", "0 + E1"), "S6": ("0", "0"),
    "S7": ("списание 550 млн", "то же"), "S8": ("250 млн", "250 млн"), "S9": ("E5", "нет E5"),
    "S10": ("остаток после декабря 300 млн; амортизация + обесценение = 550 млн", "то же событие"),
    "S11": ("капит. 300 млн + предупреждение IAS 36", "капит. 300 млн и списание 300 млн 01.09.2024"),
    "S12": ("6 мес. амортизации, списание остатка 550 млн − 6 × 5 729 166", "6 мес., списание 550 млн − 6 × 9 166 666"),
    "S13": ("STANDART QO'LLANILMAYDI", "то же"),
    "S14": ("стоимость 400 млн, амортизируется 400 млн", "то же"),
    "S15": ("560 млн", "560 млн"),
    "S16": ("550 млн + предупреждение IAS 36.12", "400 млн (п.13: 150 млн из ноябрьской затраты в расход)"),
    "S17": ("отклоняется", "отклоняется"), "S18": ("капит. / расход / расход", "то же"),
    "S18b": ("капит. 10 млн", "то же"), "S19": ("капит. 300 млн (ноябрь — в расход), списание 300 млн", "то же"),
    "S20": ("E5 нет", "—"),
}


def run_pytest():
    xml = Path(tempfile.mkdtemp()) / "junit.xml"
    rc = pytest.main(["-q", "-p", "no:cacheprovider", f"--junitxml={xml}", str(ROOT / "tests")])
    status, total, failed, seconds = {}, 0, 0, 0.0
    root = ET.parse(xml).getroot()
    for suite in root.iter("testsuite"):
        seconds += float(suite.get("time", 0))
    for tc in root.iter("testcase"):
        total += 1
        bad = tc.find("failure") is not None or tc.find("error") is not None
        failed += bad
        status[(tc.get("classname").split(".")[-1], tc.get("name"))] = "FAIL" if bad else (
            "SKIP" if tc.find("skipped") is not None else "PASS")
    return rc, status, total, failed, seconds


def main():
    rc, status, total, failed, seconds = run_pytest()
    rows = scenarios()
    seen = {}
    lines = [
        "# Результаты тест-сценариев S1–S20",
        "",
        f"Сгенерировано `tools/test_results.py` {datetime.now():%d.%m.%Y %H:%M}; Python {platform.python_version()}, "
        f"{platform.system()}. Фактические значения посчитаны движком `ittki/core/engine.py`, статус взят из прогона "
        "pytest. Базовый проект и сценарии взяты из раздела 8 ТЗ (`tests/test_engine.py`).",
        "",
        f"**pytest: {total - failed} из {total} тестов прошли, {failed} упало ({seconds:.1f} с).**",
        "",
        "| № | Сценарий | Ожидается по ТЗ: IAS 38 | Факт: IAS 38 | Ожидается по ТЗ: BHMS 11 | Факт: BHMS 11 | pytest |",
        "|---|---|---|---|---|---|---|",
    ]
    for no, name, ias, nas, test in rows:
        key = no + ("#" if no in seen else "")
        seen[no] = True
        e_ias, e_nas = EXPECTED[key]
        st = status.get(("test_engine", test), "?")
        lines.append(f"| {no} | {name} | {e_ias} | {ias} | {e_nas} | {nas} | {'✅' if st == 'PASS' else '❌'} {st} |")
    inv = status.get(("test_invariants", "test_invariants"), "?")
    eq = status.get(("test_equivalence", "test_engine_equals_reference"), "?")
    lines += [
        "",
        "## Инварианты и эквивалентность",
        "",
        "| Проверка | Объём | pytest |",
        "|---|---|---|",
        f"| Инварианты раздела 8 (капитализировано + расходы = все затраты; сумма строк решения; предел п.13; "
        f"строки графика; закрытие в 0; списание ≤ капитализации; балансовая стоимость в [0; капитализация] и не "
        f"растёт после готовности; срок BHMS 11 ≤ 60 мес.) | 9 000 случайных проектов × 2 стандарта × 3 настройки "
        f"| {inv} |",
        f"| Перенесённый движок = эталон `reference/engine_reference.py` (решения, графики, балансовая стоимость, "
        f"сверка) | 2 000 случайных проектов × 2 стандарта × 3 настройки | {eq} |",
        f"| Проводки: 0830 + 0490 + 0590 = балансовая стоимость движка на любую дату | 1 500 проектов × 2 × 3 | "
        f"{status.get(('test_journal', 'test_journal_invariants_random'), '?')} |",
        f"| Движение остатков (примечание M9): начало + капитализация − амортизация − обесценение − списания = "
        f"конец | 800 проектов × 2 стандарта × 3 года | "
        f"{status.get(('test_reports', 'test_movement_rollforward_identity_random'), '?')} |",
        "",
        "## Все тесты по модулям",
        "",
        "| Модуль | Тестов | Прошли |",
        "|---|---|---|",
    ]
    mods = {}
    for (mod, _), st in status.items():
        t, p = mods.get(mod, (0, 0))
        mods[mod] = (t + 1, p + (st == "PASS"))
    for mod in sorted(mods):
        lines.append(f"| `tests/{mod}.py` | {mods[mod][0]} | {mods[mod][1]} |")
    lines.append(f"| **Итого** | **{total}** | **{total - failed}** |")
    (ROOT / "docs" / "test_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"docs/test_results.md: {total - failed}/{total} passed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
