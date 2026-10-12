# ITTKI Nazorat

Настольное приложение для Windows: учёт, капитализация и контроль расходов на НИОКР (ITTKI)
одновременно по **BHMS 11 (2024)** и **IAS 38** (+ IAS 36). Программная часть магистерской диссертации
(Raxmatullayev S.N., ISFT). Техническое задание: [`docs/TZ_ITTKI_dastur.md`](docs/TZ_ITTKI_dastur.md).

Интерфейс на узбекском языке (латиница). Все строки лежат в `ittki/i18n/uz.py`, русский можно добавить
файлом `ru.py` с теми же ключами.

## Возможности

| Модуль ТЗ | Где в программе |
|---|---|
| M1 Реестр проектов, M2 Стадии | Loyihalar → Loyiha kartasi → Ma'lumot / Bosqichlar |
| M3 Критерии K1–K7 (версии, документы-доказательства) | вкладка Mezonlar |
| M4 Журнал затрат, импорт из Excel | вкладка Xarajatlar, шаблон `templates/xarajatlar_shablon.xlsx` |
| M5 Движок решений R0–R8 | `ittki/core/engine.py`, вкладка Qaror (IAS 38 \| BHMS 11) |
| M6 Проводки | `ittki/core/journal.py`, вкладка Provodkalar |
| M7 График амортизации | вкладка Amortizatsiya, Excel |
| M8 Сверка NAS ↔ IFRS | вкладка Solishtirma, Hisobotlar → Excel |
| M9 Примечание к отчётности | Hisobotlar → Word (.docx) |
| M10 Исключения E1–E10, отчёт для аудиторского комитета | `ittki/core/controls.py`, окно Nazorat, PDF/Excel |
| M11 Журнал аудита | окно Audit jurnali (удалить или изменить запись нельзя, это запрещено триггерами SQLite) |
| M12 Настройки (счета, пороги, категории) | окно Sozlamalar |

Проводки, графики и решения не хранятся в базе: движок пересчитывает их при каждом открытии.
Деньги хранятся только целыми числами (сум), даты имеют тип `datetime.date`, в интерфейсе формат `dd.mm.yyyy`.
Коды счетов задаются в настройках, значения по умолчанию взяты из таблицы M6. Счёт 9410 запрещён валидатором.

## Структура

```
ITTKI_Nazorat/
├── main.py                    точка входа (и для PyInstaller)
├── ITTKI_Nazorat.spec         сборка одного exe
├── requirements.txt
├── ittki/
│   ├── core/                  движок без UI: engine, journal (M6), controls (E1–E10), rules, defaults, appsettings
│   ├── db/                    SQLite: schema (миграции), repository (загрузка/сохранение + аудит)
│   ├── reports/               excel, word, pdf, excel_import
│   ├── ui/                    PySide6: main_window, pages, project_card, dialogs, widgets, style
│   ├── i18n/uz.py             все строки интерфейса
│   ├── services.py            связка репозиторий + движок + контроль для UI и отчётов
│   └── demo.py                4 условных проекта («Shartli misol»)
├── reference/                 исходные эталонные файлы (engine_reference.py и тесты), без изменений
├── tests/                     pytest
├── templates/                 xarajatlar_shablon.xlsx
├── tools/                     screenshots.py, samples.py, test_results.py
└── docs/                      ТЗ, algorithm.md, test_results.md, doubts.md, screenshots/, samples/
```

## Установка (Windows 10/11)

Нужен Python 3.11 или новее.

```bat
cd ITTKI_Nazorat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск

```bat
venv\Scripts\activate
python main.py
```

При запуске программа спрашивает ФИО и роль. Оценки критериев и смену стадий сохраняет только **Loyiha rahbari**;
затраты, импорт, обесценение, настройки и отчёты — только **Buxgalter**; **Ichki auditor** только просматривает.
Попытка действия без прав показывает сообщение на узбекском и записывается в журнал аудита (права —
`ittki/db/permissions.py`).

База данных: `%APPDATA%\ITTKI_Nazorat\ittki_nazorat.sqlite3`. Схема создаётся автоматически при первом запуске.
Другой файл базы можно указать через переменную `ITTKI_DB`. Резервная копия делается кнопкой
**Zaxira nusxa** на главной странице.

Демо-данные загружает кнопка **Demo ma'lumotlarni yuklash** на главной странице.

## Тесты

```bat
venv\Scripts\activate
python -m pytest -q
```

Что проверяют тесты:

* `test_engine.py`: 22 эталонных сценария S1–S20 (ожидаемые числа не менялись);
* `test_invariants.py`: инварианты на 9 000 случайных проектов × 2 стандарта × 3 настройки;
* `test_equivalence.py`: перенесённый движок даёт точно те же результаты, что `reference/engine_reference.py`;
* `test_journal.py`: проводки M6, остатки на 0830+0490+0590 всегда равны балансовой стоимости движка;
* `test_controls.py`: каждое правило E1–E10 (положительный и отрицательный случай);
* `test_db.py`: схема, миграция, аудит, неизменяемость журналов, S2 → сохранить → загрузить → тот же результат;
* `test_ui.py`: окна и вкладки (offscreen), правило «Ha» только с документом или как черновик (E1);
* `test_reports.py`: Excel/Word/PDF, импорт шаблона, тождество движения остатков;
* `test_permissions.py`: права ролей (каждое действие × каждая роль), отказ пишется в журнал аудита, пустое
  поле «Kutilayotgan sof iqtisodiy naf» не превращается в 0, порог E9 = 1 000 000 сум;
* `test_demo.py`, `test_performance.py`: демо-данные; 1 000 затрат пересчитываются быстрее чем за 1 с.

На Linux без дисплея перед запуском тестов задайте `QT_QPA_PLATFORM=offscreen`.

## Сборка exe

```bat
venv\Scripts\activate
pyinstaller --clean --noconfirm ITTKI_Nazorat.spec
```

Результат: `dist\ITTKI_Nazorat.exe` (один файл, без консоли). Чтобы проверить exe без Python, скопируйте его
в любую папку и запустите самотест:

```bat
set PATH=C:\Windows\System32;C:\Windows
ITTKI_Nazorat.exe --selftest C:\Temp\selftest.txt
type C:\Temp\selftest.txt
```

Самотест загружает демо-данные во временную базу, считает оба стандарта и открывает все окна. Код возврата 0
означает успех.

То же самое автоматически делает GitHub Actions: workflow `.github/workflows/ittki-windows.yml` на `windows-latest`
прогоняет тесты, собирает exe, запускает его с PATH без Python и выкладывает `ITTKI_Nazorat.exe` как artifact
`ITTKI_Nazorat-windows`.

## Материалы для диссертации

```bat
python tools\screenshots.py      :: docs\screenshots\*.png (QWidget.grab(), демо-данные, дата 11.10.2026)
python tools\samples.py          :: docs\samples\ (примечание .docx, PDF для аудиторского комитета, Excel)
python tools\test_results.py     :: docs\test_results.md (сценарии S1–S20 с фактическими числами из pytest)
```

* [`docs/algorithm.md`](docs/algorithm.md): блок-схема движка (Mermaid) и таблица K1–K7 ↔ IAS 38 ↔ BHMS 11;
* [`docs/test_results.md`](docs/test_results.md): результаты сценариев;
* [`docs/Instruktsiya_ITTKI_Nazorat.pdf`](docs/Instruktsiya_ITTKI_Nazorat.pdf): инструкция пользователя на русском (собирается `python tools\manual.py`);
* [`docs/doubts.md`](docs/doubts.md): места, где трактовка ТЗ требует решения автора или научного руководителя.

## Ограничения v1 (из ТЗ, раздел 10)

Программа не ведёт полный бухгалтерский учёт и не рассчитывает налоги. Не поддерживаются: неопределённый срок
полезного использования, амортизация по объёму выпуска, капитализация затрат по займам и автоматическое
восстановление списаний. На проект допускается одно событие обесценения, как в движке. Все демо-проекты
условные: реальных данных AGMK по НИОКР нет.
