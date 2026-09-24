/* Интерфейс приложения. Без фреймворков и внешних библиотек — всё работает офлайн. */
"use strict";

const S = { state: null, result: null, history: null, page: "data", anketaFilter: "defect", lastRefresh: null };
const STATUS_LABEL = { RED: "Критично", YELLOW: "Внимание", GREEN: "Норма" };
const SEVERITY_OPTIONS = [["defect", "Брак"], ["warning", "Предупреждение"]];

// ── Утилиты ───────────────────────────────────────────────────────────────
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else if (k === "value" || (k in el && typeof v !== "string")) el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const fmt = (n, d = 0) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("ru-RU", { maximumFractionDigits: d, minimumFractionDigits: d }));
const pill = (status) => status ? h("span", { class: `pill ${status}` }, STATUS_LABEL[status] || status) : "";
const svg = (path) => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 20 20"); s.innerHTML = path; return s; };

async function call(method, url, body, isForm) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data.auth) {
    // сессия закончилась или администратор закрыл доступ
    showLogin(data.error);
    throw new Error(data.error || "Нужно войти");
  }
  if (!res.ok) throw new Error(data.error || `Ошибка ${res.status}`);
  return data;
}
const GET = (u) => call("GET", u);
const POST = (u, b) => call("POST", u, b);

let toastTimer;
function toast(msg, error) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), error ? 5200 : 2600);
}
function busy(on, text) {
  $("#busy").hidden = !on;
  if (text) $("#busyText").textContent = text;
}
async function guarded(fn, text) {
  busy(true, text);
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { busy(false); }
}

let saveTimer;
function saveConfigSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try { S.state = await POST("/api/config", { config: S.state.config }); renderSidebar(); scheduleAuto(); }
    catch (e) { toast(e.message, true); }
  }, 450);
}
const cfg = () => S.state.config;

// ── Таблица с поиском и сортировкой ─────────────────────────────────────────
function table(columns, rows, opts = {}) {
  let sortKey = opts.sortKey || null, asc = opts.asc ?? false, query = "";
  const tbody = h("tbody");
  const count = h("span", { class: "table-count" });
  const heads = columns.map((c) => {
    const th = h("th", { class: c.num ? "num" : "", onclick: () => {
      if (sortKey === c.key) asc = !asc; else { sortKey = c.key; asc = !c.num; }
      heads.forEach((x) => x.classList.remove("sorted", "asc"));
      th.classList.add("sorted"); if (asc) th.classList.add("asc");
      draw();
    } }, c.label);
    return th;
  });
  function draw() {
    let list = rows;
    if (query) {
      const q = query.toLowerCase();
      list = list.filter((r) => columns.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q)));
    }
    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      const val = col.sortVal || ((r) => r[sortKey]);
      list = [...list].sort((a, b) => {
        const x = val(a), y = val(b);
        if (x === y) return 0;
        if (x === null || x === undefined || x === "") return 1;
        if (y === null || y === undefined || y === "") return -1;
        const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "ru", { numeric: true });
        return asc ? r : -r;
      });
    }
    tbody.replaceChildren();
    const limit = opts.limit || 2000;
    for (const r of list.slice(0, limit)) {
      const tr = h("tr", { class: [opts.rowClass ? opts.rowClass(r) : "", opts.onClick ? "clickable" : ""].join(" "),
        onclick: opts.onClick ? () => opts.onClick(r) : null });
      for (const c of columns) {
        const v = c.render ? c.render(r) : (c.num && typeof r[c.key] === "number" ? fmt(r[c.key], c.digits ?? 0) : r[c.key]);
        tr.append(h("td", { class: [c.num ? "num" : "", c.wrap ? "wrap" : ""].join(" ") }, v ?? ""));
      }
      tbody.append(tr);
    }
    if (!list.length) tbody.append(h("tr", {}, h("td", { colspan: columns.length, class: "empty" }, opts.empty || "Ничего не найдено")));
    count.textContent = list.length > limit ? `Показано ${fmt(limit)} из ${fmt(list.length)}` : `${fmt(list.length)} строк`;
  }
  draw();
  const tools = h("div", { class: "table-tools" },
    opts.search === false ? null : h("input", { type: "search", placeholder: "Поиск", oninput: (e) => { query = e.target.value; draw(); } }),
    opts.tools || null, h("span", { class: "spacer" }), count);
  const wrap = h("div", { class: "table-wrap", style: opts.height ? `max-height:${opts.height}px` : null },
    h("table", {}, h("thead", {}, h("tr", {}, heads)), tbody));
  return h("div", {}, tools, wrap);
}

// ── Поля настроек ───────────────────────────────────────────────────────────
function select(options, value, onchange, placeholder) {
  const s = h("select", { onchange: (e) => onchange(e.target.value || null) });
  if (placeholder !== undefined) s.append(h("option", { value: "" }, placeholder));
  for (const o of options) {
    const [v, label] = Array.isArray(o) ? o : [o, o];
    s.append(h("option", { value: v, selected: v === value }, label));
  }
  if (value && !options.some((o) => (Array.isArray(o) ? o[0] : o) === value)) {
    s.append(h("option", { value, selected: true }, `${value} (нет в файле)`));
  }
  return s;
}
function number(obj, key, min, max, step = 1) {
  return h("input", { type: "number", min, max, step, value: obj[key],
    onchange: (e) => { const v = Number(e.target.value); if (!Number.isNaN(v)) { obj[key] = v; saveConfigSoon(); } } });
}
function toggle(obj, key, after) {
  return h("label", { class: "switch" },
    h("input", { type: "checkbox", checked: !!obj[key], onchange: (e) => { obj[key] = e.target.checked; saveConfigSoon(); after && after(); } }),
    h("span"));
}
function formRow(label, desc, control) {
  return h("div", { class: "form-row" },
    h("div", {}, h("div", { class: "label" }, label), desc ? h("div", { class: "desc" }, desc) : null),
    h("div", { class: "row" }, control));
}

function columnPicker(selected, onChange) {
  const cols = S.state.columns;
  let query = "";
  const chips = h("div", { class: "chips" });
  const list = h("div", { class: "picker-list" });
  function drawChips() {
    chips.replaceChildren(...(selected.length ? selected.map((c) => h("span", { class: "chip", title: c }, h("span", {}, c),
      h("button", { title: "Убрать", onclick: () => { selected.splice(selected.indexOf(c), 1); onChange(selected); drawAll(); } }, "×")))
      : [h("span", { class: "muted small" }, "Колонки не выбраны")]));
  }
  function drawList() {
    const q = query.toLowerCase();
    list.replaceChildren(...cols.filter((c) => !q || c.toLowerCase().includes(q)).slice(0, 400).map((c) =>
      h("label", {}, h("input", { type: "checkbox", checked: selected.includes(c), onchange: (e) => {
        if (e.target.checked) selected.push(c); else selected.splice(selected.indexOf(c), 1);
        selected.sort((a, b) => cols.indexOf(a) - cols.indexOf(b));
        onChange(selected); drawChips();
      } }), h("span", {}, c))));
  }
  function drawAll() { drawChips(); drawList(); }
  drawAll();
  return h("div", { class: "picker" },
    h("div", { class: "picker-top" }, h("input", { type: "search", placeholder: "Найти колонку…", oninput: (e) => { query = e.target.value; drawList(); } })),
    list, h("div", { style: "border-top:1px solid var(--line)" }, chips));
}

function needData() {
  return h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "Данные ещё не подключены"),
    "Загрузите Excel-файл или подключите Google Sheets на странице «Данные».",
    h("div", { style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => go("data") }, "Перейти к данным"))));
}

// ── Навигация ──────────────────────────────────────────────────────────────
const PAGES = {
  data: { title: "Данные", render: pageData },
  columns: { title: "Колонки", render: pageColumns },
  checks: { title: "Пороги проверок", render: pageChecks },
  open: { title: "Открытые вопросы", render: pageOpen },
  rules: { title: "Логические правила", render: pageRules },
  overview: { title: "Обзор", render: pageOverview },
  interviewers: { title: "Интервьюеры", render: pageInterviewers },
  anketas: { title: "Анкеты", render: pageAnketas },
  cities: { title: "Города", render: pageCities },
  answers: { title: "Ответы в открытых вопросах", render: pageAnswers },
  repetition: { title: "Повтор значения у интервьюера", render: pageRepetition },
  history: { title: "История интервьюеров по волнам", render: pageHistory },
  admin: { title: "Администрирование", render: pageAdmin },
  gps: { title: "GPS-контроль", render: pageGps },
  map: { title: "Карта GPS", render: pageMap },
};

function go(page) {
  S.page = page;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  $("#pageTitle").textContent = PAGES[page].title;
  const r = S.result && S.result.summary;
  $("#pageSub").textContent = r ? [r.source, r.sheet && `лист «${r.sheet}»`, r.period, `проверено ${r.processed_at}`].filter(Boolean).join("  ·  ")
    : (S.state.source ? `${S.state.source} · лист «${cfg().sheet}»` : "");
  const content = $("#content");
  const page_ = h("div", { class: "page" });
  content.replaceChildren(page_);
  content.scrollTop = 0;
  Promise.resolve(PAGES[page].render(page_)).catch((e) => toast(e.message, true));
}

function renderSidebar() {
  const sel = $("#projectSelect");
  sel.replaceChildren(...S.state.projects.map((p) => h("option", { value: p, selected: p === S.state.project }, p)));
  document.querySelectorAll("#nav a.needs-result").forEach((a) => a.classList.toggle("disabled", !S.result));
  $("#exportBtn").disabled = !S.result;
  $("#sideFoot").textContent = `Версия ${S.state.app.version}`;
  const u = S.state.user || {};
  document.body.classList.toggle("is-admin", u.role === "admin");
  $("#userBox").replaceChildren(
    h("div", { class: "who" }, u.name || u.login || ""),
    h("div", { class: "team" }, u.role === "admin" ? "Администратор" : (u.team ? `Команда: ${u.team}` : "")),
    h("div", { class: "row" },
      h("button", { class: "btn small", onclick: changePassword }, "Пароль"),
      h("button", { class: "btn small", onclick: logout }, "Выйти")));
}

async function refreshState() {
  S.state = await GET("/api/state");
  renderSidebar();
}

async function runChecks() {
  await guarded(async () => {
    clearTimeout(saveTimer);
    S.result = await POST("/api/run", { config: S.state.config });
    await refreshState();
    scheduleAuto();
    const s = S.result.summary;
    toast(`Проверено ${fmt(s.total)} анкет · брак ${fmt(s.defects)} (${fmt(s.defect_pct, 1)}%)`);
    go("overview");
  }, "Проверяю анкеты…");
}

async function exportReport(kind) {
  if (window.pywebview && window.pywebview.api) {
    const r = await window.pywebview.api.save_export(kind);
    if (r && r.error) toast(r.error, true);
    else if (r && r.path) toast(`Сохранено: ${r.path}`);
    return;
  }
  const a = h("a", { href: `/api/export/${kind}` });
  document.body.append(a); a.click(); a.remove();
}

// ── Страница «Данные» ───────────────────────────────────────────────────────
async function pageData(root) {
  const c = cfg();
  const fileInput = h("input", { type: "file", accept: ".xlsx,.xlsm,.xls", hidden: true, onchange: (e) => e.target.files[0] && upload(e.target.files[0]) });
  async function upload(file) {
    const fd = new FormData(); fd.append("file", file);
    await guarded(async () => { S.state = await call("POST", "/api/source/file", fd, true); S.result = null; renderSidebar(); go("data"); toast(`Файл «${file.name}» загружен`); }, "Читаю файл…");
  }
  const drop = h("div", { class: "drop", onclick: () => fileInput.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); },
    ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); e.dataTransfer.files[0] && upload(e.dataTransfer.files[0]); } },
    h("div", { class: "drop-icon" }, svg('<path d="M10 13V4m0 0L6.5 7.5M10 4l3.5 3.5"/><path d="M4 12.5v2A1.5 1.5 0 005.5 16h9a1.5 1.5 0 001.5-1.5v-2"/>')),
    h("b", {}, "Перетащите файл выгрузки сюда"),
    h("span", { class: "muted" }, "или нажмите, чтобы выбрать .xlsx на компьютере"), fileInput);

  root.append(teamSourcesCard());
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Или файл Excel"),
      h("p", { class: "hint" }, "Разовая проверка выгрузки с компьютера — без подключения таблицы."))), drop));

  if (!S.state.sheets.length) return;
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" },
      h("div", {}, h("h2", {}, "Лист с данными"), h("p", { class: "hint" }, `Источник: ${S.state.source}. В файлах часто есть вспомогательные листы (свод, Pivot) — выберите лист с анкетами.`)),
      select(S.state.sheets, c.sheet, async (v) => { await guarded(async () => { S.state = await POST("/api/sheet", { sheet: v }); S.result = null; renderSidebar(); go("data"); }); })),
    h("div", { id: "preview" }, h("div", { class: "muted" }, "Загружаю предпросмотр…"))));
  const pv = await GET("/api/preview");
  const cols = S.state.columns.slice(0, 14);
  $("#preview").replaceChildren(
    h("p", { class: "muted small" }, `${fmt(pv.total)} строк · ${fmt(S.state.columns.length)} колонок. Первые строки:`),
    table(cols.map((k) => ({ key: k, label: k.length > 32 ? k.slice(0, 30) + "…" : k })), pv.rows, { search: false, height: 320 }),
    h("div", { class: "row", style: "margin-top:16px" }, h("button", { class: "btn primary", onclick: () => go("columns") }, "Дальше: колонки →")));
}

// ── Страница «Колонки» ──────────────────────────────────────────────────────
function pageColumns(root) {
  if (!S.state.sheets.length) return root.append(needData());
  const c = cfg();
  for (const role of S.state.roles) {
    if (!c.mapping[role.key] && S.state.suggested[role.key]) c.mapping[role.key] = S.state.suggested[role.key];
  }
  saveConfigSoon();
  const rows = S.state.roles.map((role) => formRow(
    h("span", {}, role.label, role.required ? h("span", { class: "req" }, "*") : null),
    { phone: "Для поиска дубликатов и контроля пропусков телефона", name: "Для поиска дубликатов респондентов",
      id: "Если не выбрано — будет номер строки в Excel", device: "IMEI / идентификатор устройства",
      lat: "Для GPS-контроля. Если координаты в одной колонке «41.31 69.24 …» — выберите её здесь", lon: "Можно оставить пустым, если координаты в одной колонке" }[role.key] || null,
    select(S.state.columns, c.mapping[role.key], (v) => { c.mapping[role.key] = v; saveConfigSoon(); }, "— не выбрано —")));
  root.append(h("div", { class: "card" }, h("h2", {}, "Какая колонка за что отвечает"),
    h("p", { class: "hint" }, "Частые названия колонок подставлены автоматически — проверьте и при необходимости выберите вручную. * — обязательные поля."),
    h("div", { class: "form-list" }, rows)));
  root.append(h("div", { class: "card" }, h("h2", {}, "Признак завершённого интервью"),
    h("p", { class: "hint" }, "Колонки из конца анкеты (например ФИО или телефон респондента). Если хотя бы одна заполнена — интервью считается дошедшим до конца. Скринауты короткими быть обязаны, поэтому минимальная длительность и глубина зондажа проверяются только у завершённых. Не выбрано — все анкеты считаются завершёнными."),
    columnPicker(c.completed_cols, (v) => { c.completed_cols = v; saveConfigSoon(); })));
}

// ── Страница «Пороги проверок» ──────────────────────────────────────────────
function pageChecks(root) {
  const c = cfg(), t = c.thresholds, n = c.night, d = c.duplicates, st = c.status;
  const sev = (obj, key) => select(SEVERITY_OPTIONS, obj[key], (v) => { obj[key] = v; saveConfigSoon(); });
  root.append(h("div", { class: "card" }, h("h2", {}, "Время и устройство"),
    h("p", { class: "hint" }, "Технические признаки фальсификации — работают на выгрузке любого проекта."),
    h("div", { class: "form-list" },
      formRow("Минимальная длительность интервью", "Только для завершённых анкет", [number(t, "min_duration_min", 1, 120), h("span", { class: "unit" }, "мин")]),
      formRow("Максимальная длительность анкеты", "Дольше — скорее всего не закрыл форму вовремя", [number(t, "max_duration_min", 5, 600), h("span", { class: "unit" }, "мин")]),
      formRow("Минимальный интервал между анкетами", "И между стартами, и между концом предыдущей и началом следующей", [number(t, "min_interval_min", 0, 60, 0.5), h("span", { class: "unit" }, "мин")]),
      formRow("«Конвейер»: окно времени", "Сколько минут смотреть подряд на одном устройстве", [number(t, "mass_window_min", 1, 120), h("span", { class: "unit" }, "мин")]),
      formRow("«Конвейер»: анкет в окне", "Столько анкет и больше в окне — массовое штампование", [number(t, "mass_min_count", 2, 100), h("span", { class: "unit" }, "шт")]))),
  );
  const nightRows = h("div", {});
  const drawNight = () => nightRows.replaceChildren(...(n.enabled ? [
    formRow("Рабочее время с", null, [number(n, "work_start_hour", 0, 23), h("span", { class: "unit" }, "ч")]),
    formRow("Рабочее время до", "Анкеты, начатые вне этого окна, будут отмечены", [number(n, "work_end_hour", 1, 24), h("span", { class: "unit" }, "ч")]),
    formRow("Считать как", null, sev(n, "severity"))] : []));
  drawNight();
  root.append(h("div", { class: "grid-2" },
    h("div", { class: "card" }, h("h2", {}, "Время суток"), h("p", { class: "hint" }, "Анкеты глубокой ночью — частый признак заполнения «из дома». Время берётся местное, как в выгрузке."),
      h("div", { class: "form-list" }, formRow("Проверять время суток", null, toggle(n, "enabled", drawNight)), nightRows)),
    h("div", { class: "card" }, h("h2", {}, "Дубликаты респондентов"), h("p", { class: "hint" }, "Один человек прошёл опрос несколько раз за волну. Телефон сравнивается по последним 9 цифрам, ФИО — без учёта регистра и порядка слов (только имя + фамилия)."),
      h("div", { class: "form-list" },
        formRow("Тот же телефон", c.mapping.phone ? `Колонка: ${c.mapping.phone}` : "Колонка телефона не выбрана", sev(d, "phone_severity")),
        formRow("То же ФИО", c.mapping.name ? `Колонка: ${c.mapping.name}` : "Колонка ФИО не выбрана", sev(d, "name_severity"))))));
  root.append(h("div", { class: "grid-2" },
    h("div", { class: "card" }, h("h2", {}, "Города"), h("p", { class: "hint" }, "Если один человек сделал почти все анкеты города — это подозрительно."),
      h("div", { class: "form-list" },
        formRow("Макс. доля одного интервьюера в городе", null, [number(t, "max_share_city_pct", 10, 100), h("span", { class: "unit" }, "%")]),
        formRow("Минимум интервьюеров на город", null, [number(t, "min_inters_per_city", 1, 20), h("span", { class: "unit" }, "чел")]),
        formRow("Макс. доля анкет без телефона", "Среди завершённых, по городу", [number(t, "phone_missing_city_pct", 0, 100), h("span", { class: "unit" }, "%")]))),
    h("div", { class: "card" }, h("h2", {}, "Статус интервьюера"), h("p", { class: "hint" }, "Система раннего предупреждения — одна шкала для всех проверок."),
      h("div", { class: "form-list" },
        formRow(h("span", {}, pill("RED"), " от"), "Остановить, проверить данные, решить о замене", [number(st, "red_pct", 1, 100), h("span", { class: "unit" }, "% брака")]),
        formRow(h("span", {}, pill("YELLOW"), " от"), "Уведомить, провести инструктаж, усилить мониторинг", [number(st, "yellow_pct", 0, 100), h("span", { class: "unit" }, "% брака")]),
        formRow(h("span", {}, pill("GREEN")), "Всё, что ниже жёлтого порога", "")))));
}

// ── Страница «Открытые вопросы» ─────────────────────────────────────────────
function pageOpen(root) {
  if (!S.state.sheets.length) return root.append(needData());
  const c = cfg(), p = c.probing, rep = c.repetition;
  const blocksBox = h("div", {});
  function drawBlocks() {
    blocksBox.replaceChildren(...p.blocks.map((b, i) => {
      const anchor = h("input", { type: "text", placeholder: "Текст вопроса, например «первым приходит»", style: "flex:1;min-width:220px" });
      const width = h("input", { type: "number", min: 1, max: 30, value: b.columns.length || 5 });
      return h("div", { class: "block-card" },
        h("div", { class: "block-head" },
          h("input", { type: "text", value: b.label, placeholder: "Название блока", oninput: (e) => { b.label = e.target.value; saveConfigSoon(); } }),
          h("span", { class: "muted small" }, "минимум ответов"), number(b, "min_n", 0, 30),
          h("button", { class: "btn small danger", onclick: () => { p.blocks.splice(i, 1); saveConfigSoon(); drawBlocks(); } }, "Удалить")),
        h("div", { class: "row", style: "margin-bottom:10px" }, anchor, h("span", { class: "muted small" }, "колонок подряд"), width,
          h("button", { class: "btn small", onclick: () => {
            const q = anchor.value.trim().toLowerCase();
            const idx = S.state.columns.findIndex((col) => col.toLowerCase().includes(q));
            if (!q || idx < 0) return toast("Колонка с таким текстом не найдена", true);
            b.columns = S.state.columns.slice(idx, idx + Number(width.value || 1));
            saveConfigSoon(); drawBlocks();
          } }, "Найти колонки")),
        columnPicker(b.columns, (v) => { b.columns = v; saveConfigSoon(); }));
    }));
    if (!p.blocks.length) blocksBox.append(h("div", { class: "empty" }, "Блоков пока нет — проверка глубины зондажа отключена."));
  }
  drawBlocks();
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Глубина зондажа"),
      h("p", { class: "hint" }, "Открытые вопросы без подсказки («Какой бренд первым приходит на ум?» + пробы «А ещё?»). Если респондент начал отвечать, интервьюер обязан переспросить нужное число раз. Выберите колонки вопроса и всех его проб.")),
      h("button", { class: "btn", onclick: () => { p.blocks.push({ label: `Блок ${p.blocks.length + 1}`, columns: [], min_n: 3 }); saveConfigSoon(); drawBlocks(); } }, "+ Блок")),
    blocksBox,
    h("div", { class: "form-list", style: "margin-top:6px" },
      formRow("Меньше минимума в анкете — это", null, select(SEVERITY_OPTIONS, p.severity, (v) => { p.severity = v; saveConfigSoon(); })),
      formRow("Интервьюер ниже медианы волны", "Среднее число ответов интервьюера меньше X% от медианы по волне", [number(p, "low_avg_pct", 0, 100), h("span", { class: "unit" }, "%"),
        select(SEVERITY_OPTIONS, p.low_avg_severity, (v) => { p.low_avg_severity = v; saveConfigSoon(); })]))));

  const lines = (arr) => arr.join("\n");
  const parseLines = (s) => s.split("\n").map((x) => x.trim()).filter(Boolean);
  root.append(h("div", { class: "card" }, h("h2", {}, "Ответы-заглушки"),
    h("p", { class: "hint" }, "«Не знаю», «999», «bilmayman» и т.п. не засчитываются как названный бренд. По одному на строку."),
    h("div", { class: "grid-2" },
      h("div", {}, h("div", { class: "form-group-title" }, "Точное совпадение"),
        h("textarea", { rows: 8, value: lines(p.invalid_exact), oninput: (e) => { p.invalid_exact = parseLines(e.target.value); saveConfigSoon(); } })),
      h("div", {}, h("div", { class: "form-group-title" }, "Содержит (любые варианты написания)"),
        h("textarea", { rows: 8, value: lines(p.invalid_substr), oninput: (e) => { p.invalid_substr = parseLines(e.target.value); saveConfigSoon(); } })))));

  const valuesText = rep.values.map((v) => v.variants && v.variants.length ? `${v.name}: ${v.variants.join(", ")}` : v.name).join("\n");
  const parseValues = (s) => parseLines(s).map((line) => {
    const [name, rest] = line.split(/:(.*)/s);
    return { name: name.trim(), variants: (rest || "").split(",").map((x) => x.trim()).filter(Boolean) };
  }).filter((v) => v.name);
  const repCols = h("div", {});
  const drawRepCols = () => repCols.replaceChildren(columnPicker(rep.columns, (v) => { rep.columns = v; saveConfigSoon(); }));
  drawRepCols();
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Повтор значения у интервьюера"),
      h("p", { class: "hint" }, "Если интервьюер подозрительно часто записывает одно и то же значение — вероятно, он не спрашивает, а вписывает сам. Подходит для любой категории: банки, лекарства, магазины, марки авто. Пока список значений пуст — проверка выключена."))),
    h("div", { class: "grid-2" },
      h("div", {}, h("div", { class: "form-group-title" }, "Известные значения проекта"),
        h("p", { class: "muted small", style: "margin:0 0 8px" }, "По одному на строку. Варианты написания — через двоеточие и запятые: ", h("span", { class: "kbd" }, "Uzum Bank: uzum, узум, uzumbank")),
        h("textarea", { rows: 10, value: valuesText, placeholder: "Uzum Bank: uzum, узум\nTBC Bank: tbc, тбс, твс\nPayme: пайми, пайме", oninput: (e) => { rep.values = parseValues(e.target.value); saveConfigSoon(); } })),
      h("div", {}, h("div", { class: "row", style: "justify-content:space-between" }, h("div", { class: "form-group-title" }, "Колонки с ответами"),
          h("button", { class: "btn small ghost", onclick: () => { rep.columns = [...new Set(p.blocks.flatMap((b) => b.columns))]; saveConfigSoon(); drawRepCols(); } }, "Взять из блоков зондажа")),
        repCols)),
    h("div", { class: "form-list", style: "margin-top:18px" },
      formRow(h("span", {}, pill("RED"), " сильный повтор"), "Доля самого частого значения и минимум ответов у интервьюера", [number(rep, "red_pct", 1, 100), h("span", { class: "unit" }, "%"), h("span", { class: "unit" }, "от"), number(rep, "red_min_n", 1, 1000), h("span", { class: "unit" }, "ответов")]),
      formRow(h("span", {}, pill("YELLOW"), " заметный повтор"), null, [number(rep, "yellow_pct", 1, 100), h("span", { class: "unit" }, "%"), h("span", { class: "unit" }, "от"), number(rep, "yellow_min_n", 1, 1000), h("span", { class: "unit" }, "ответов")]))));
}

// ── Страница «Логические правила» ───────────────────────────────────────────
function pageRules(root) {
  if (!S.state.sheets.length) return root.append(needData());
  const c = cfg();
  const ops = Object.entries(S.state.rule_ops);
  const box = h("div", {});
  function valueInput(rule, key, op) {
    if (op === "empty" || op === "not_empty") return null;
    return h("input", { type: "text", placeholder: "значение", value: rule[key] ?? "", oninput: (e) => { rule[key] = e.target.value; saveConfigSoon(); } });
  }
  function draw() {
    box.replaceChildren(...c.rules.map((r, i) => h("div", { class: "rule" },
      h("div", { class: "rule-num" }, i + 1),
      h("div", {},
        h("div", { class: "rule-line" },
          h("input", { type: "text", value: r.name || "", placeholder: "Название правила", style: "flex:1;min-width:220px;font-weight:550", oninput: (e) => { r.name = e.target.value; saveConfigSoon(); } }),
          select(SEVERITY_OPTIONS, r.severity || "defect", (v) => { r.severity = v; saveConfigSoon(); }),
          h("button", { class: "btn small danger", onclick: () => { c.rules.splice(i, 1); saveConfigSoon(); draw(); } }, "Удалить")),
        h("div", { class: "rule-line" }, h("span", { class: "kw" }, "Если"),
          select(S.state.columns, r.if_col, (v) => { r.if_col = v; saveConfigSoon(); draw(); }, "— всегда (для всех анкет) —"),
          r.if_col ? select(ops, r.if_op, (v) => { r.if_op = v; saveConfigSoon(); draw(); }) : null,
          r.if_col ? valueInput(r, "if_val", r.if_op) : null),
        h("div", { class: "rule-line" }, h("span", { class: "kw" }, "то"),
          select(S.state.columns, r.then_col, (v) => { r.then_col = v; saveConfigSoon(); }, "— выберите колонку —"),
          select(ops, r.then_op, (v) => { r.then_op = v; saveConfigSoon(); draw(); }),
          valueInput(r, "then_val", r.then_op))))));
    if (!c.rules.length) box.append(h("div", { class: "empty" }, h("b", {}, "Правил пока нет"), "Например: если «Возраст» меньше 18, то «Доход» не больше 0."));
  }
  draw();
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Правила согласованности ответов"),
      h("p", { class: "hint" }, "У каждого проекта своя анкета — поэтому правила задаются здесь, а не в коде. Анкета нарушает правило, если условие «если» выполнено, а «то» — нет. Если число в ячейке не удалось прочитать, правило к анкете не применяется.")),
      h("button", { class: "btn", onclick: () => { c.rules.push({ name: "", if_col: null, if_op: "<", if_val: "", then_col: null, then_op: "<=", then_val: "", severity: "defect" }); saveConfigSoon(); draw(); } }, "+ Правило")),
    box));
}

// ── Результаты ──────────────────────────────────────────────────────────────
function noResult(root) {
  root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "Проверка ещё не запускалась"),
    "Подключите данные, сопоставьте колонки и нажмите «Проверить».")));
}

function reasonsTable(rows, base) {
  return table([
    { key: "Причина", label: "Причина", wrap: true },
    { key: "Анкет", label: "Анкет", num: true },
    { key: "%", label: base, num: true, render: (r) => h("div", { class: "bar-cell" }, h("div", { class: "bar" }, h("i", { style: `width:${Math.min(100, r["%"])}%` })), h("span", {}, `${fmt(r["%"], 1)}%`)) },
  ], rows, { search: false, sortKey: "Анкет", empty: "Ничего не найдено" });
}

function pageOverview(root) {
  if (!S.result) return noResult(root);
  const R = S.result, s = R.summary, sc = s.status_counts, ninter = sc.RED + sc.YELLOW + sc.GREEN || 1;
  if (s.dropped) root.append(h("div", { class: "notice warn" }, `Пропущено ${fmt(s.dropped)} строк без Device ID/интервьюера или без города.`));
  if (R.rule_errors.length) root.append(h("div", { class: "notice bad" }, h("div", {}, h("b", {}, "Некоторые правила не проверены: "), R.rule_errors.join("; "))));
  root.append(h("div", { class: "stats" },
    h("div", { class: "stat" }, h("div", { class: "k" }, "Всего анкет"), h("div", { class: "v" }, fmt(s.total)), h("div", { class: "s" }, s.period || "")),
    h("div", { class: "stat red" }, h("div", { class: "k" }, "Брак"), h("div", { class: "v" }, fmt(s.defects)), h("div", { class: "s" }, `${fmt(s.defect_pct, 1)}% от всех`)),
    h("div", { class: "stat yellow" }, h("div", { class: "k" }, "С предупреждениями"), h("div", { class: "v" }, fmt(s.warnings)), h("div", { class: "s" }, "не считаются браком")),
    h("div", { class: "stat" }, h("div", { class: "k" }, "Интервьюеров"), h("div", { class: "v" }, fmt(s.interviewers)), h("div", { class: "s" }, `${fmt(s.cities)} городов`))));

  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Статус интервьюеров"), h("p", { class: "hint" }, "По доле брака в их анкетах.")),
      h("button", { class: "btn small", onclick: () => go("interviewers") }, "Подробнее →")),
    h("div", { class: "status-bar" }, h("div", { class: "r", style: `width:${sc.RED / ninter * 100}%` }), h("div", { class: "y", style: `width:${sc.YELLOW / ninter * 100}%` }), h("div", { class: "g", style: `width:${sc.GREEN / ninter * 100}%` })),
    h("div", { class: "legend-row" }, ["RED", "YELLOW", "GREEN"].map((k) => h("span", {}, pill(k), " ", h("b", {}, fmt(sc[k])), h("span", { class: "muted" }, " чел."))))));

  root.append(h("div", { class: "grid-2" },
    h("div", { class: "card" }, h("h2", {}, "Причины брака"), h("p", { class: "hint" }, "Одна анкета может иметь несколько причин."), reasonsTable(R.defect_reasons, "% брака")),
    h("div", { class: "card" }, h("h2", {}, "Предупреждения"), h("p", { class: "hint" }, "Сигналы для ручной проверки — сами по себе не брак."), reasonsTable(R.warning_reasons, "% анкет"))));

  root.append(h("div", { class: "card" }, h("h2", {}, "Проблемы по городам"),
    R.city_issues.length ? h("ul", { class: "issue-list" }, R.city_issues.map((x) => h("li", {}, pill(x.level), h("span", { class: "city" }, x.city), h("span", {}, x.text))))
      : h("div", { class: "notice ok" }, "По городам всё в норме.")));

  const waveInput = h("input", { type: "text", placeholder: "Например: Волна 3 — сентябрь", style: "flex:1;max-width:380px" });
  root.append(h("div", { class: "card" }, h("h2", {}, "Сохранить волну в историю"),
    h("p", { class: "hint" }, "Итоги по интервьюерам сохранятся на этом компьютере — так видно, кто уже несколько волн подряд в жёлтой или красной зоне. Повторное сохранение с тем же названием перезапишет волну."),
    h("div", { class: "row" }, waveInput, h("button", { class: "btn primary", onclick: async () => {
      await guarded(async () => { S.history = await POST("/api/history/save", { wave: waveInput.value }); toast("Волна сохранена"); go("history"); });
    } }, "Сохранить"))));
}

function pageInterviewers(root) {
  if (!S.result) return noResult(root);
  const R = S.result;
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Интервьюеры"), h("p", { class: "hint" }, "Отсортированы по доле брака. Нажмите на строку, чтобы увидеть его анкеты с браком.")),
      h("button", { class: "btn small", onclick: () => exportReport("interviewers") }, "Excel")),
    table([
      { key: "Статус", label: "Статус", render: (r) => pill(r["Статус"]), sortVal: (r) => ({ RED: 3, YELLOW: 2, GREEN: 1 })[r["Статус"]] },
      { key: "Интервьюер", label: "Интервьюер" }, { key: "Город", label: "Город" },
      { key: "Анкет", label: "Анкет", num: true }, { key: "Брак", label: "Брак", num: true },
      { key: "% брака", label: "% брака", num: true, digits: 1 },
      { key: "Предупреждений", label: "Предупр.", num: true },
      { key: "Повтор значения", label: "Повтор значения", render: (r) => r["Повтор значения"] ? h("span", {}, r["Повтор: статус"] !== "GREEN" ? h("span", { class: `dot ${r["Повтор: статус"]}` }) : null, " ", r["Повтор значения"]) : "" },
      { key: "Главные причины брака", label: "Главные причины брака", wrap: true },
    ], R.interviewers, { rowClass: (r) => `row-${r["Статус"]}`, onClick: (r) => showInterviewer(r["Интервьюер"]) })));
  root.append(h("div", { class: "card" }, h("h2", {}, "Система раннего предупреждения"),
    h("ul", { class: "issue-list" }, R.legend.map((l) => h("li", {}, h("span", { style: "min-width:110px" }, pill(l.code)), h("b", { style: "min-width:170px" }, l.desc), h("span", { class: "muted" }, l.actions))))));
}

function showInterviewer(inter) {
  const rows = S.result.anketas.filter((a) => a.inter === inter && (a.defect || a.warning));
  openModal(`Интервьюер ${inter}`, table(anketaColumns(), rows, { search: false, height: 460, rowClass: (r) => r.defect ? "row-RED" : "row-YELLOW" }));
}

function anketaColumns() {
  return [
    { key: "id", label: "ID анкеты" }, { key: "city", label: "Город" }, { key: "inter", label: "Интервьюер" },
    { key: "start", label: "Старт", sortVal: (r) => r.start && r.start.split(/[. :]/).reverse().join("") },
    { key: "duration", label: "Мин", num: true, digits: 1 },
    { key: "reasons", label: "Причина брака", wrap: true },
    { key: "warnings", label: "Предупреждения", wrap: true },
  ];
}

function pageAnketas(root) {
  if (!S.result) return noResult(root);
  const all = S.result.anketas;
  const filters = { defect: ["Брак", (a) => a.defect], warning: ["Предупреждения", (a) => a.warning && !a.defect], all: ["Все", () => true] };
  const seg = h("div", { class: "segmented" }, Object.entries(filters).map(([k, [label, fn]]) =>
    h("button", { class: S.anketaFilter === k ? "on" : "", onclick: () => { S.anketaFilter = k; go("anketas"); } }, `${label} · ${fmt(all.filter(fn).length)}`)));
  const rows = all.filter(filters[S.anketaFilter][1]);
  root.append(h("div", { class: "card" },
    table([...anketaColumns().slice(0, 3), { key: "device", label: "Device ID" }, ...anketaColumns().slice(3)], rows,
      { tools: seg, rowClass: (r) => r.defect ? "row-RED" : r.warning ? "row-YELLOW" : "", height: 640 })));
}

function pageCities(root) {
  if (!S.result) return noResult(root);
  const R = S.result;
  if (R.city_issues.length) root.append(h("div", { class: "card" }, h("h2", {}, "Проблемы по городам"),
    h("ul", { class: "issue-list" }, R.city_issues.map((x) => h("li", {}, pill(x.level), h("span", { class: "city" }, x.city), h("span", {}, x.text))))));
  root.append(h("div", { class: "card" }, h("h2", {}, "Города"),
    table([
      { key: "Статус", label: "Статус", render: (r) => pill(r["Статус"]) },
      { key: "Город", label: "Город" }, { key: "Анкет", label: "Анкет", num: true },
      { key: "Интервьюеров", label: "Интервьюеров", num: true }, { key: "Брак", label: "Брак", num: true },
      { key: "% брака", label: "% брака", num: true, digits: 1 },
    ], R.cities, { sortKey: "% брака", rowClass: (r) => `row-${r["Статус"]}` })));
}

function pageAnswers(root) {
  if (!S.result) return noResult(root);
  const rows = S.result.answers;
  if (!rows.length) {
    root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "Открытые вопросы не настроены"),
      "Укажите колонки на странице «Открытые вопросы» — здесь появятся все уникальные ответы.",
      h("div", { style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => go("open") }, "Настроить")))));
    return;
  }
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Все уникальные ответы — 100%, без фильтрации"),
      h("p", { class: "hint" }, "Каждый текст, который встретился в выбранных колонках, со статусом: засчитан, из списка значений, не из списка или отсечён как «не знаю». Нажмите на ответ, чтобы увидеть, кто именно его написал.")),
      h("button", { class: "btn small", onclick: () => exportReport("answers") }, "Excel")),
    table([
      { key: "Ответ", label: "Ответ" }, { key: "Раз", label: "Раз", num: true },
      { key: "Интервьюеров", label: "Интервьюеров", num: true },
      { key: "Статус", label: "Статус" }, { key: "Значение из списка", label: "Значение из списка" },
    ], rows, { onClick: showWho, height: 640 })));
}

async function showWho(r) {
  const who = await GET(`/api/answers/who?answer=${encodeURIComponent(r["Ответ"])}`);
  openModal(`«${r["Ответ"]}» — ${fmt(who.length)} раз`, table([
    { key: "ID анкеты", label: "ID анкеты" }, { key: "Город", label: "Город" },
    { key: "Интервьюер", label: "Интервьюер" }, { key: "Вопрос", label: "Вопрос / колонка", wrap: true },
  ], who, { height: 460 }));
}

function pageRepetition(root) {
  if (!S.result) return noResult(root);
  const rep = S.result.repetition;
  if (!rep.enabled) {
    root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "Проверка выключена"),
      "Чтобы включить, задайте список известных значений проекта и колонки с ответами на странице «Открытые вопросы».",
      h("div", { style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => go("open") }, "Настроить")))));
    return;
  }
  const c = cfg().repetition;
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Кто повторяет одно и то же значение"),
      h("p", { class: "hint" }, `Самое частое значение у каждого интервьюера и его доля среди всех его ответов (разные написания объединены). Сильный повтор — от ${c.red_pct}% при ${c.red_min_n}+ ответах, заметный — от ${c.yellow_pct}% при ${c.yellow_min_n}+. Отсортировано по городу, чтобы сравнить с коллегами.`)),
      h("button", { class: "btn small", onclick: () => exportReport("repetition") }, "Excel")),
    table([
      { key: "Статус", label: "Статус", render: (r) => pill(r["Статус"]), sortVal: (r) => ({ RED: 3, YELLOW: 2, GREEN: 1 })[r["Статус"]] },
      { key: "Город", label: "Город" }, { key: "Интервьюер", label: "Интервьюер" },
      { key: "Ответов", label: "Ответов", num: true }, { key: "Самое частое значение", label: "Самое частое значение" },
      { key: "Повторов", label: "Повторов", num: true }, { key: "% повтора", label: "% повтора", num: true, digits: 1 },
    ], rep.rows, { rowClass: (r) => `row-${r["Статус"]}` })));
}

// ── История ─────────────────────────────────────────────────────────────────
async function pageHistory(root) {
  S.history = await GET("/api/history");
  const H = S.history;
  if (!H.waves.length) {
    root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "В истории пока нет волн"),
      "После проверки нажмите «Сохранить волну» на странице «Обзор». История хранится в файле на этом компьютере и привязана к проекту.")));
    return;
  }
  const hot = H.rows.filter((r) => r["Подряд в зоне риска"] >= 2);
  if (hot.length) root.append(h("div", { class: "notice bad" }, h("div", {}, h("b", {}, `${hot.length} интервьюер(ов) ${hot.length === 1 ? "" : ""}несколько волн подряд в жёлтой/красной зоне: `),
    hot.slice(0, 12).map((r) => `${r["Интервьюер"]} (${r["Подряд в зоне риска"]})`).join(", "))));
  const waveNames = H.waves.map((w) => w.wave);
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Накопительный рейтинг"),
      h("p", { class: "hint" }, "Статус в каждой волне слева направо (от старых к новым). «Подряд» — сколько последних волн интервьюер не выходит из жёлтой/красной зоны.")),
      h("button", { class: "btn small", onclick: () => exportReport("history") }, "Excel")),
    table([
      { key: "Интервьюер", label: "Интервьюер" }, { key: "Город", label: "Город" },
      { key: "waves", label: "Волны", render: (r) => h("div", { class: "history-dots" }, waveNames.map((w) => {
        const x = r.waves[w];
        return x ? h("span", { class: `dot ${x.status}`, title: `${w}: ${STATUS_LABEL[x.status]} · ${x.pct}% брака · ${x.n} анкет` })
          : h("span", { class: "dot", style: "background:var(--fill)", title: `${w}: не работал` });
      })), sortVal: (r) => Object.keys(r.waves).length },
      { key: "Подряд в зоне риска", label: "Подряд", num: true, render: (r) => h("span", { class: `streak ${r["Подряд в зоне риска"] >= 2 ? "hot" : ""}` }, r["Подряд в зоне риска"] || "—") },
      { key: "Худший статус", label: "Худший", render: (r) => pill(r["Худший статус"]) },
      { key: "Волн", label: "Волн", num: true }, { key: "Анкет всего", label: "Анкет", num: true },
      { key: "Брак всего", label: "Брак", num: true }, { key: "% брака (накоп.)", label: "% брака", num: true, digits: 1 },
    ], H.rows, { sortKey: "Подряд в зоне риска", rowClass: (r) => r["Подряд в зоне риска"] ? `row-${r["Худший статус"]}` : "" })));
  root.append(h("div", { class: "card" }, h("h2", {}, "Волны"),
    table([
      { key: "wave", label: "Волна" }, { key: "period", label: "Период данных" }, { key: "saved_at", label: "Сохранено" },
      { key: "n_total", label: "Анкет", num: true }, { key: "n_defect", label: "Брак", num: true },
      { key: "del", label: "", render: (w) => h("button", { class: "btn small danger", onclick: async (e) => {
        e.stopPropagation();
        if (!confirm(`Удалить волну «${w.wave}» из истории?`)) return;
        await guarded(async () => { await POST("/api/history/delete", { wave: w.wave }); go("history"); });
      } }, "Удалить") },
    ], H.waves, { search: false })));
}


// ── Google-таблицы команды ──────────────────────────────────────────────────
function teamSourcesCard() {
  const c = cfg();
  const all = S.state.remote_sources || [];
  const chosen = new Set(c.remote_sources || []);
  const list = h("div", { class: "src-list" });
  const drawList = () => list.replaceChildren(...(all.length ? all.map((src) => h("label", { class: "src" },
    h("input", { type: "checkbox", checked: chosen.has(src.id), onchange: (e) => { e.target.checked ? chosen.add(src.id) : chosen.delete(src.id); } }),
    h("div", {}, h("div", {}, h("b", {}, src.name), " ", src.project ? h("span", { class: "tag" }, src.project) : null,
      S.state.user.role === "admin" && src.team ? [" ", h("span", { class: "tag" }, `команда ${src.team}`)] : null),
      h("div", { class: "meta" }, [src.sheet ? `лист «${src.sheet}»` : "первый лист", src.added_by && `добавил ${src.added_by}`].filter(Boolean).join(" · "))),
    h("button", { class: "btn small danger", onclick: async (e) => {
      e.preventDefault();
      if (!confirm(`Отключить таблицу «${src.name}» от команды? Сами анкеты в Google Sheets не удалятся.`)) return;
      await guarded(async () => { S.state.remote_sources = await POST("/api/remote/sources/delete", { id: src.id }); await refreshState(); go("data"); });
    } }, "Отключить")))
    : [h("div", { class: "empty" }, h("b", {}, "Таблиц пока нет"), "Добавьте ссылку на Google-таблицу, куда поступают анкеты вашего проекта.")]));
  drawList();

  async function load(thenRun) {
    const ids = all.filter((x) => chosen.has(x.id)).map((x) => x.id);
    await guarded(async () => {
      S.state = await POST("/api/source/remote", { ids });
      S.result = null; renderSidebar();
      toast("Анкеты загружены из Google Sheets");
    }, "Загружаю анкеты из Google Sheets…");
    if (thenRun && S.state.sheets.length) await runChecks(); else go("data");
  }

  const name = h("input", { type: "text", placeholder: "Например: Ташкент — сентябрь", style: "flex:1;min-width:200px" });
  const url = h("input", { type: "url", placeholder: "https://docs.google.com/spreadsheets/d/…", style: "flex:2;min-width:260px" });
  const sheet = h("input", { type: "text", placeholder: "Лист (необязательно)", style: "width:170px" });
  const email = S.state.server_email;
  const addForm = h("div", { class: "block-card", style: "margin-top:16px" },
    h("div", { class: "form-group-title", style: "margin-top:0" }, "Подключить ещё таблицу"),
    h("ol", { class: "small muted", style: "margin:0 0 12px;padding-left:18px;line-height:1.7" },
      h("li", {}, "Откройте Google-таблицу с анкетами → «Настройки доступа»."),
      h("li", {}, "Добавьте ", email ? h("span", { class: "kbd" }, email) : "адрес сервера (его знает администратор)", " с правом «Читатель»."),
      h("li", {}, "Вставьте ссылку на таблицу сюда и нажмите «Подключить».")),
    h("div", { class: "row" }, name, url, sheet,
      h("button", { class: "btn", onclick: async () => {
        await guarded(async () => {
          S.state.remote_sources = await POST("/api/remote/sources/add", { name: name.value, url: url.value, sheet: sheet.value });
          const added = S.state.remote_sources.find((x) => x.name === name.value.trim());
          if (added) { c.remote_sources = [...new Set([...(c.remote_sources || []), added.id])]; saveConfigSoon(); }
          toast("Таблица подключена"); go("data");
        }, "Проверяю доступ к таблице…");
      } }, "Подключить")));

  const freq = select([["0", "выключено"], ["5", "каждые 5 минут"], ["10", "каждые 10 минут"], ["15", "каждые 15 минут"], ["30", "каждые 30 минут"], ["60", "каждый час"]],
    String(c.auto_refresh_min ?? 15), (v) => { c.auto_refresh_min = Number(v); saveConfigSoon(); scheduleAuto(); go("data"); });
  const live = autoActive() ? h("span", { class: "live" }, S.lastRefresh ? `последнее обновление в ${S.lastRefresh}` : "включено")
    : h("span", { class: "live off" }, (c.remote_sources || []).length ? "выключено" : "отметьте таблицы и нажмите «Загрузить»");

  return h("div", { class: "card" },
    h("div", { class: "card-head" },
      h("div", {}, h("h2", {}, "Google-таблицы команды"),
        h("p", { class: "hint" }, "Таблицы, куда поступают анкеты. Отметьте нужные для этого проекта — они объединятся в одну выгрузку с колонкой «Источник». Таблицы видит только ваша команда.")),
      h("button", { class: "btn small ghost", onclick: async () => { await guarded(async () => { S.state.remote_sources = await GET("/api/remote/sources"); go("data"); }); } }, "Обновить список")),
    list,
    all.length ? h("div", { class: "row", style: "margin-top:14px" },
      h("button", { class: "btn", onclick: () => load(false) }, "Загрузить"),
      h("button", { class: "btn primary", onclick: () => load(true) }, svg('<path d="M6.5 4.5v11l9-5.5z"/>'), "Загрузить и проверить")) : null,
    h("div", { class: "form-list", style: "margin-top:16px" },
      formRow("Автоматическая проверка", "Приложение само забирает новые анкеты из отмеченных таблиц и перепроверяет всё, пока открыто", h("div", { class: "row" }, live, freq))),
    addForm);
}

// ── Автообновление ─────────────────────────────────────────────────────────
let autoTimer = null;
function autoActive() {
  const c = cfg();
  return c.auto_refresh_min > 0 && (c.remote_sources || []).length > 0;
}
function scheduleAuto() {
  clearInterval(autoTimer);
  if (!autoActive()) return;
  autoTimer = setInterval(autoRefresh, cfg().auto_refresh_min * 60 * 1000);
}
async function autoRefresh() {
  if (!$("#busy").hidden || !$("#loginScreen").hidden) return;
  try {
    const r = await POST("/api/refresh");
    S.result = r;
    S.lastRefresh = r.refresh.at;
    renderSidebar();
    if (r.refresh.new) {
      toast(`Новых анкет: ${fmt(r.refresh.new)}` + (r.refresh.new_defects ? ` · из них с браком: ${fmt(r.refresh.new_defects)}` : ""), r.refresh.new_defects > 0);
    }
    if ($("#modal").hidden && !["columns", "checks", "open", "rules", "admin", "gps", "map"].includes(S.page)) go(S.page);
  } catch (e) { /* ошибку покажет следующая ручная проверка; вход — через showLogin */ }
}

// ── Вход и выход ───────────────────────────────────────────────────────────
function showLogin(message) {
  clearInterval(autoTimer);
  const scr = $("#loginScreen");
  scr.hidden = false;
  const err = $("#loginError");
  err.hidden = !message;
  err.textContent = message || "";
  setTimeout(() => ($("#loginName").value ? $("#loginPass") : $("#loginName")).focus(), 50);
}

async function prepareLogin() {
  const a = await GET("/api/auth");
  $("#loginServer").value = a.server_url || "";
  $("#serverBox").open = !a.server_url;
  $("#loginName").value = a.last_login || "";
  $("#loginFoot").textContent = `Версия ${a.app.version} · пароль выдаёт администратор`;
  return a;
}

async function logout() {
  await POST("/api/auth/logout");
  S.result = null;
  await prepareLogin();
  $("#loginPass").value = "";
  showLogin();
}

function changePassword() {
  const oldP = h("input", { type: "password", autocomplete: "current-password" });
  const newP = h("input", { type: "password", autocomplete: "new-password" });
  const err = h("div", { class: "notice bad", hidden: true });
  openModal("Сменить пароль", h("div", { style: "display:flex;flex-direction:column;gap:12px;max-width:360px" }, err,
    h("label", { class: "field" }, h("span", {}, "Текущий пароль"), oldP),
    h("label", { class: "field" }, h("span", {}, "Новый пароль (минимум 8 символов)"), newP),
    h("button", { class: "btn primary", onclick: async () => {
      try { await POST("/api/auth/password", { old_password: oldP.value, new_password: newP.value }); closeModal(); toast("Пароль изменён"); }
      catch (e) { err.hidden = false; err.textContent = e.message; }
    } }, "Сохранить")));
}

// ── Администрирование ───────────────────────────────────────────────────────
function showPassword(login, password, title) {
  openModal(title, h("div", {},
    h("p", { class: "hint" }, `Передайте сотруднику логин и пароль. Пароль показывается один раз — после закрытия окна его не восстановить, только сбросить.`),
    h("div", { class: "form-list" }, formRow("Логин", null, h("b", {}, login))),
    h("div", { class: "password-box" }, password),
    h("div", { class: "row" },
      h("button", { class: "btn primary", onclick: async () => {
        try { await navigator.clipboard.writeText(`Логин: ${login}\nПароль: ${password}`); toast("Скопировано"); } catch (e) { toast("Выделите пароль и скопируйте вручную", true); }
      } }, "Скопировать логин и пароль"),
      h("button", { class: "btn", onclick: closeModal }, "Готово"))));
}

async function pageAdmin(root) {
  if ((S.state.user || {}).role !== "admin") return root.append(h("div", { class: "card" }, h("div", { class: "empty" }, "Раздел только для администратора.")));
  const [{ users }, { log }] = await Promise.all([POST("/api/admin/list_users", {}), POST("/api/admin/log", { limit: 80 })]);
  const teams = [...new Set(users.map((u) => u.team).filter(Boolean))].sort();
  const act = (action, body, msg) => guarded(async () => { const r = await POST(`/api/admin/${action}`, body); if (msg) toast(msg); return r; });

  const login = h("input", { type: "text", placeholder: "логин латиницей, напр. ali.k", style: "width:210px" });
  const name = h("input", { type: "text", placeholder: "Имя и фамилия", style: "flex:1;min-width:180px" });
  const team = h("input", { type: "text", placeholder: "Команда / проект", list: "teamsList", style: "width:200px" });
  const role = select([["user", "Сотрудник"], ["admin", "Администратор"]], "user", () => {});
  root.append(h("div", { class: "card" },
    h("h2", {}, "Новый сотрудник"),
    h("p", { class: "hint" }, "Пароль создаётся автоматически и показывается один раз. Команда определяет, какие Google-таблицы увидит сотрудник: у каждой команды свои."),
    h("datalist", { id: "teamsList" }, teams.map((t) => h("option", { value: t }))),
    h("div", { class: "row" }, login, name, team, role,
      h("button", { class: "btn primary", onclick: async () => {
        const r = await act("create_user", { login: login.value, name: name.value, team: team.value, role: role.value });
        if (r && r.password) { showPassword(r.login, r.password, "Сотрудник создан"); go("admin"); }
      } }, "Создать"))));

  root.append(h("div", { class: "card" },
    h("h2", {}, "Сотрудники"),
    h("p", { class: "hint" }, "Выключите доступ — и программа у человека перестанет работать при следующем же обращении к серверу, даже если она сейчас открыта."),
    table([
      { key: "active", label: "Доступ", render: (u) => h("label", { class: "switch" },
        h("input", { type: "checkbox", checked: u.active, disabled: u.login === S.state.user.login, onchange: async (e) => {
          const r = await act("update_user", { login: u.login, active: e.target.checked }, e.target.checked ? "Доступ открыт" : "Доступ закрыт");
          if (!r) e.target.checked = !e.target.checked;
        } }), h("span")), sortVal: (u) => (u.active ? 1 : 0) },
      { key: "login", label: "Логин" }, { key: "name", label: "Имя" },
      { key: "team", label: "Команда", render: (u) => u.role === "admin" ? h("span", { class: "tag" }, "все команды") : h("span", {}, u.team || "—", " ",
        h("button", { class: "btn small ghost", onclick: async () => {
          const t = prompt(`Команда для ${u.login}`, u.team || "");
          if (t !== null && await act("update_user", { login: u.login, team: t }, "Команда изменена")) go("admin");
        } }, "изменить")) },
      { key: "role", label: "Роль", render: (u) => u.role === "admin" ? h("span", { class: "pill plain neutral" }, "Администратор") : "Сотрудник" },
      { key: "last_login", label: "Последний вход" },
      { key: "actions", label: "", render: (u) => h("div", { class: "row" },
        h("button", { class: "btn small", onclick: async () => {
          if (!confirm(`Сбросить пароль ${u.login}? Старый перестанет работать.`)) return;
          const r = await act("reset_password", { login: u.login });
          if (r && r.password) showPassword(r.login, r.password, "Новый пароль");
        } }, "Сбросить пароль"),
        u.login === S.state.user.login ? null : h("button", { class: "btn small danger", onclick: async () => {
          if (!confirm(`Удалить ${u.login}? Вход по этому логину станет невозможен.`)) return;
          if (await act("delete_user", { login: u.login }, "Удалён")) go("admin");
        } }, "Удалить")) },
    ], users, { rowClass: (u) => (u.active ? "" : "row-RED") })));

  root.append(h("div", { class: "card" }, h("h2", {}, "Журнал"),
    h("p", { class: "hint" }, "Входы, неудачные попытки, подключение таблиц и действия администратора. Полный журнал — на листе «Журнал» в таблице сервера."),
    table([{ key: "time", label: "Время" }, { key: "login", label: "Логин" },
      { key: "action", label: "Действие", render: (x) => ({ login: "вход", login_failed: "неверный пароль", login_blocked: "вход заблокирован",
        fetch: "загрузка анкет", add_source: "подключил таблицу", delete_source: "отключил таблицу", create_user: "создал сотрудника",
        update_user: "изменил сотрудника", reset_password: "сбросил пароль", delete_user: "удалил сотрудника", change_password: "сменил пароль" })[x.action] || x.action },
      { key: "detail", label: "Подробности", wrap: true }], log, { height: 420 })));
}

// ── GPS: настройки ──────────────────────────────────────────────────────────
function pageGps(root) {
  const c = cfg(), g = c.geo;
  const sev = (key) => select(SEVERITY_OPTIONS, g[key], (v) => { g[key] = v; saveConfigSoon(); });
  const plan = g.plan || {};
  const cities = Object.keys(plan);
  const nPoints = cities.reduce((a, k) => a + ((plan[k] || {}).points || []).length, 0);
  const mapped = c.mapping.lat;

  if (!mapped) {
    root.append(h("div", { class: "notice warn" }, h("div", {}, "Не выбрана колонка с координатами. На странице ",
      h("a", { href: "#", onclick: (e) => { e.preventDefault(); go("columns"); } }, "«Колонки»"),
      " укажите «GPS: широта» и «GPS: долгота» (в Kobo обычно …_latitude и …_longitude). Если координаты в одной колонке «41.31 69.24 …», выберите её как широту, а долготу оставьте пустой.")));
  }

  root.append(h("div", { class: "card" }, h("h2", {}, "Что проверяется"),
    h("p", { class: "hint" }, "GPS показывает, где интервьюер был в момент анкеты. Проверки срабатывают, когда в выгрузке есть координаты."),
    h("div", { class: "form-list" },
      formRow("Далеко от точки опроса", "Анкета дальше заданного расстояния от ближайшей плановой точки своего города",
        [number(g, "max_dist_km", 0.1, 100, 0.1), h("span", { class: "unit" }, "км"), sev("far_severity")]),
      formRow("Скопление анкет", "Сколько анкет интервьюера допустимо в одном месте (радиус ниже)",
        [number(g, "max_per_point", 1, 1000), h("span", { class: "unit" }, "анкет"), sev("cluster_severity")]),
      formRow("Радиус «одного места»", "Анкеты ближе этого считаются одной точкой",
        [number(g, "min_sep_km", 0.05, 20, 0.05), h("span", { class: "unit" }, "км")]),
      formRow("Одинаковые координаты", "Столько анкет интервьюера с координатами, совпадающими до метра, — похоже на копирование или подмену GPS",
        [number(g, "same_point_min", 2, 100), h("span", { class: "unit" }, "анкет"), sev("same_severity")]),
      formRow("Нет координат", "GPS не записался в анкете", sev("no_gps_severity")))));

  const fileInput = h("input", { type: "file", accept: ".xlsx", hidden: true, onchange: async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    await guarded(async () => { g.plan = await call("POST", "/api/geo/plan/parse", fd, true); saveConfigSoon(); toast("План точек загружен"); go("gps"); });
  } });
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "План точек опроса"),
      h("p", { class: "hint" }, nPoints ? `${cities.length} городов, ${nPoints} точек. Анкеты из городов, которых нет в плане, по расстоянию не проверяются (скопления и одинаковые координаты — проверяются).`
        : "План не задан — проверяются только скопления, одинаковые координаты и отсутствие GPS.")),
      h("div", { class: "row" },
        h("button", { class: "btn", onclick: async () => { await guarded(async () => { g.plan = await GET("/api/geo/default-plan"); saveConfigSoon(); toast("Встроенный план загружен"); go("gps"); }); } }, "Встроенный план (14 городов)"),
        h("button", { class: "btn", onclick: () => fileInput.click() }, "Из Excel…"), fileInput,
        nPoints ? h("button", { class: "btn danger", onclick: () => { if (confirm("Очистить план точек?")) { g.plan = {}; saveConfigSoon(); go("gps"); } } }, "Очистить") : null)),
    h("p", { class: "muted small" }, "Excel для плана: колонки «Город», «Широта», «Долгота» и необязательная «Название»."),
    nPoints ? table([{ key: "city", label: "Город" }, { key: "n", label: "Точек", num: true },
      { key: "names", label: "Точки", wrap: true }],
      cities.map((k) => ({ city: k, n: plan[k].points.length, names: plan[k].points.map((p, i) => p.street_ru || `Точка ${i + 1}`).join(" · ") })),
      { search: false, height: 360 }) : null));
}

// ── GPS: карта ──────────────────────────────────────────────────────────────
let leafletMap = null;
function pageMap(root) {
  if (!S.result) return noResult(root);
  const g = S.result.geo || {};
  if (!g.enabled) {
    root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "GPS-контроль не включён"),
      "Выберите колонки с координатами на странице «Колонки» и запустите проверку.",
      h("div", { style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => go("gps") }, "Настроить GPS")))));
    return;
  }
  root.append(h("div", { class: "stats" },
    h("div", { class: "stat" }, h("div", { class: "k" }, "Анкет с GPS"), h("div", { class: "v" }, fmt(g.with_gps)), h("div", { class: "s" }, g.without_gps ? `без GPS: ${fmt(g.without_gps)}` : "у всех есть координаты")),
    h("div", { class: "stat red" }, h("div", { class: "k" }, "Далеко от точки"), h("div", { class: "v" }, fmt(g.far)), h("div", { class: "s" }, `дальше ${g.max_dist_km} км`)),
    h("div", { class: "stat yellow" }, h("div", { class: "k" }, "Скоплений сверх лимита"), h("div", { class: "v" }, fmt(g.clusters_over)), h("div", { class: "s" }, `больше ${g.max_per_point} анкет в одном месте`)),
    h("div", { class: "stat red" }, h("div", { class: "k" }, "Одинаковые координаты"), h("div", { class: "v" }, fmt(g.same)), h("div", { class: "s" }, "анкет — копирование/подмена GPS"))));
  if (g.unmatched_cities.length) root.append(h("div", { class: "notice warn" }, `Нет в плане точек: ${g.unmatched_cities.join(", ")} — расстояние для этих городов не проверяется.`));

  const cities = [...new Set(g.points.map((p) => p.city))].sort((a, b) => String(a).localeCompare(String(b), "ru"));
  const inters = (city) => [...new Set(g.points.filter((p) => p.city === city).map((p) => p.inter))].sort();
  S.mapCity = cities.includes(S.mapCity) ? S.mapCity : cities[0];
  S.mapInter = S.mapInter || "";
  const box = h("div", { class: "map" });
  const controls = h("div", { class: "row", style: "margin-bottom:12px" },
    select(cities, S.mapCity, (v) => { S.mapCity = v; S.mapInter = ""; go("map"); }),
    select(inters(S.mapCity), S.mapInter, (v) => { S.mapInter = v || ""; draw(); }, "Все интервьюеры"),
    h("span", { class: "spacer" }),
    h("span", { class: "muted small" }, "Нажмите на точку — увидите анкету"));
  root.append(h("div", { class: "card" }, controls, box,
    h("div", { class: "map-legend" },
      h("span", {}, h("i", { style: "background:#0A84FF" }), "плановая точка и допустимый радиус"),
      h("span", {}, h("i", { style: "background:#34C759" }), "анкета в норме"),
      h("span", {}, h("i", { style: "background:#FF9F0A" }), "в скоплении"),
      h("span", {}, h("i", { style: "background:#E0352B" }), "далеко от точки / одинаковые координаты"))));

  if (leafletMap) { leafletMap.remove(); leafletMap = null; }
  if (!window.L) { box.replaceChildren(h("div", { class: "empty" }, "Карта не загрузилась.")); return; }
  leafletMap = L.map(box, { zoomControl: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(leafletMap);
  const layer = L.layerGroup().addTo(leafletMap);

  function draw() {
    layer.clearLayers();
    const bounds = [];
    const planPts = ((g.plan[S.mapCity] || Object.entries(g.plan).find(([k]) => k.toLowerCase() === String(S.mapCity).toLowerCase())?.[1] || {}).points) || [];
    planPts.forEach((p, i) => {
      L.circle([p.lat, p.lon], { radius: g.max_dist_km * 1000, color: "#0A84FF", weight: 1, fillOpacity: 0.04 }).addTo(layer);
      L.circleMarker([p.lat, p.lon], { radius: 7, color: "#fff", weight: 2, fillColor: "#0A84FF", fillOpacity: 1 })
        .bindTooltip(p.street_ru || `Точка ${i + 1}`).addTo(layer);
      bounds.push([p.lat, p.lon]);
    });
    g.points.filter((p) => p.city === S.mapCity && (!S.mapInter || p.inter === S.mapInter)).forEach((p) => {
      const bad = p.far || p.same;
      const color = bad ? "#E0352B" : p.cluster ? "#FF9F0A" : "#34C759";
      const why = [p.far && `далеко: ${p.dist} км от «${p.point}»`, p.cluster && "в скоплении", p.same && "одинаковые координаты"].filter(Boolean).join(", ");
      L.circleMarker([p.lat, p.lon], { radius: 5, color: "#fff", weight: 1, fillColor: color, fillOpacity: 0.9 })
        .bindPopup(`<b>${p.inter}</b> · анкета ${p.id}<br>${p.dist != null ? `до точки ${p.dist} км` : "город не в плане"}${why ? `<br><span style="color:${color}">${why}</span>` : ""}`)
        .addTo(layer);
      bounds.push([p.lat, p.lon]);
    });
    if (bounds.length) leafletMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    else leafletMap.setView([41.3, 69.24], 11);
  }
  draw();
  setTimeout(() => { if (leafletMap) { leafletMap.invalidateSize(); draw(); } }, 60);

  root.append(h("div", { class: "card" }, h("h2", {}, "Скопления анкет"),
    h("p", { class: "hint" }, `Где каждый интервьюер реально стоял: анкеты ближе ${g.min_sep_km} км объединены в одну точку. Больше ${g.max_per_point} анкет в одном месте — подозрительно.`),
    table([{ key: "Статус", label: "Статус", render: (r) => pill(r["Статус"]) },
      { key: "Город", label: "Город" }, { key: "Интервьюер", label: "Интервьюер" }, { key: "Точка", label: "Точка" },
      { key: "Анкет", label: "Анкет", num: true }, { key: "Лимит", label: "Лимит", num: true }],
      g.clusters, { sortKey: "Анкет", rowClass: (r) => `row-${r["Статус"]}`, height: 420 })));
  const flagged = g.points.filter((p) => p.far || p.same);
  root.append(h("div", { class: "card" }, h("h2", {}, "Анкеты не на месте"),
    table([{ key: "id", label: "ID анкеты" }, { key: "city", label: "Город" }, { key: "inter", label: "Интервьюер" },
      { key: "dist", label: "До точки, км", num: true, digits: 2 }, { key: "point", label: "Ближайшая точка" },
      { key: "why", label: "Причина", render: (p) => [p.far && "далеко от точки", p.same && "одинаковые координаты"].filter(Boolean).join(", ") }],
      flagged, { sortKey: "dist", rowClass: () => "row-RED", height: 420, empty: "Все анкеты у плановых точек" })));
}

// ── Модальное окно ──────────────────────────────────────────────────────────
function openModal(title, body) {
  $("#modalTitle").textContent = title;
  $("#modalBody").replaceChildren(body);
  $("#modal").hidden = false;
}
function closeModal() { $("#modal").hidden = true; }

// ── Старт ───────────────────────────────────────────────────────────────────
async function enterApp() {
  $("#loginScreen").hidden = true;
  await refreshState();
  S.result = null;
  if (S.state.has_result) { try { S.result = await GET("/api/result"); } catch (e) { /* нет результата */ } }
  renderSidebar();
  scheduleAuto();
  go(S.result ? "overview" : "data");
}

async function init() {
  document.querySelectorAll("#nav a").forEach((a) => a.addEventListener("click", () => go(a.dataset.page)));
  $("#runBtn").addEventListener("click", runChecks);
  $("#exportBtn").addEventListener("click", () => exportReport("full"));
  $("#modalClose").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  $("#projectSelect").addEventListener("change", async (e) => {
    await guarded(async () => { S.state = await POST("/api/project/open", { name: e.target.value }); S.result = null; renderSidebar(); scheduleAuto(); go("data"); });
  });
  $("#newProjectBtn").addEventListener("click", async () => {
    const name = prompt("Название нового проекта (например: Uzum Bank — сентябрь)");
    if (!name) return;
    await guarded(async () => { S.state = await POST("/api/project/open", { name }); S.result = null; renderSidebar(); scheduleAuto(); go("data"); toast(`Проект «${name}» создан`); });
  });
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#loginBtn");
    btn.disabled = true; btn.textContent = "Вхожу…";
    try {
      await POST("/api/auth/login", { server_url: $("#loginServer").value, login: $("#loginName").value, password: $("#loginPass").value });
      $("#loginPass").value = "";
      await enterApp();
    } catch (err) {
      if ($("#loginScreen").hidden) return;
      $("#loginError").hidden = false; $("#loginError").textContent = err.message;
      if (/адрес|сервер|https/i.test(err.message)) $("#serverBox").open = true;
    } finally { btn.disabled = false; btn.textContent = "Войти"; }
  });
  const a = await prepareLogin();
  if (a.logged_in) await enterApp(); else showLogin();
}
init().catch((e) => toast(e.message, true));
