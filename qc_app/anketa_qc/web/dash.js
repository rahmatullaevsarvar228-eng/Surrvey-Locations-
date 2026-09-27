/* Дашборды: графики, фильтры, карта GPS. Без внешних библиотек (кроме Leaflet
   для карты) — всё рисуется здесь, работает офлайн. Общие функции (h, fmt,
   table, go, S…) — из app.js. */
"use strict";

// ── Состояние анкеты с учётом решения руководителя ──────────────────────────
const ST = {
  brak: { label: "Брак", icon: "✕", cls: "st-brak" },
  warn: { label: "Проверить", icon: "!", cls: "st-warn" },
  ok: { label: "Норма", icon: "✓", cls: "st-ok" },
  tech: { label: "Тех. записи", icon: "▶", cls: "st-tech" },
};
function stateOf(a) {
  if (a.technical) return "tech";
  if (a.decision === "Брак") return "brak";
  if (a.decision === "Принять") return "ok";
  if (a.decision === "На перезвон") return "warn";
  return a.defect ? "brak" : a.warning ? "warn" : "ok";
}
const label = (code) => (S.result.labels || {})[code] || (code && code.startsWith("rule:") ? `Правило «${code.slice(5)}»` : code);

// ── Фильтры: одна строка над всеми графиками страницы ────────────────────────
const FKEYS = [["region", "Регион", "Все регионы"], ["city", "Город", "Все города"], ["inter", "Интервьюер", "Все интервьюеры"], ["date", "День", "Все дни"]];
function F() { return S.f || (S.f = {}); }
function matches(a, skip) {
  const f = F();
  return FKEYS.every(([k]) => k === skip || !f[k] || a[k] === f[k]);
}
function scoped() { return S.result.anketas.filter((a) => matches(a)); }
function setFilter(k, v, page) {
  F()[k] = v || null;
  // нижние фильтры, которые противоречат новому выбору, снимаем
  const order = FKEYS.map((x) => x[0]);
  for (const k2 of order.slice(order.indexOf(k) + 1)) {
    if (F()[k2] && !S.result.anketas.some((a) => matches(a, k2) && a[k2] === F()[k2])) F()[k2] = null;
  }
  go(page || S.page);
}
function filterBar(page) {
  const f = F();
  const box = h("div", { class: "filters" });
  for (const [k, name, all] of FKEYS) {
    const vals = [...new Set(S.result.anketas.filter((a) => matches(a, k)).map((a) => a[k]).filter((v) => v != null && v !== ""))]
      .sort((x, y) => String(x).localeCompare(String(y), "ru", { numeric: true }));
    const fmtVal = (v) => (k === "date" ? dayLabel(v) : v);
    box.append(h("label", { class: `fsel ${f[k] ? "on" : ""}` }, h("span", {}, name),
      select(vals.map((v) => [v, fmtVal(v)]), f[k] || "", (v) => setFilter(k, v, page), all)));
  }
  if (FKEYS.some(([k]) => f[k])) box.append(h("button", { class: "btn small ghost", onclick: () => { S.f = {}; go(page); } }, "Сбросить"));
  const n = scoped();
  box.append(h("span", { class: "spacer" }), h("span", { class: "muted small" },
    `${fmt(n.filter((a) => !a.technical).length)} анкет` + (n.some((a) => a.technical) ? ` + ${fmt(n.filter((a) => a.technical).length)} тех. записей` : "")));
  return box;
}
function dayLabel(d) {
  if (!d) return "—";
  const [y, m, dd] = d.split("-");
  return `${dd}.${m}`;
}

// ── Всплывающая подсказка (одна на всё приложение) ───────────────────────────
function tip(e, ...lines) {
  let t = $("#tip");
  if (!t) { t = h("div", { id: "tip", class: "tip" }); document.body.append(t); }
  t.replaceChildren(...lines.map((l) => (l instanceof Node ? l : h("div", {}, l))));
  t.hidden = false;
  const x = Math.min(e.clientX + 14, window.innerWidth - t.offsetWidth - 8);
  const y = Math.min(e.clientY + 14, window.innerHeight - t.offsetHeight - 8);
  t.style.left = `${x}px`; t.style.top = `${y}px`;
}
function untip() { const t = $("#tip"); if (t) t.hidden = true; }
function hoverable(el, lines) {
  el.addEventListener("pointermove", (e) => tip(e, ...lines()));
  el.addEventListener("pointerleave", untip);
  el.tabIndex = 0;
  el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); tip({ clientX: r.right, clientY: r.top }, ...lines()); });
  el.addEventListener("blur", untip);
  return el;
}
const tipVal = (v, name, color) => h("div", { class: "tip-row" }, color ? h("i", { class: `key ${color}` }) : null, h("b", {}, v), h("span", {}, name));

// ── Графики ─────────────────────────────────────────────────────────────────
// Горизонтальные полосы: категория слева, значение справа, полоса одного цвета.
function hbars(items, opts = {}) {
  const max = opts.max ?? Math.max(1, ...items.map((x) => x.value));
  const list = h("div", { class: `hbars ${opts.onClick ? "clickable" : ""}` });
  const shown = items.slice(0, opts.limit || 12);
  for (const it of shown) {
    const row = h("div", { class: `hbar ${it.active ? "active" : ""}`, onclick: opts.onClick ? () => opts.onClick(it) : null },
      h("div", { class: "hb-label", title: it.label }, it.label, it.sub ? h("span", { class: "hb-sub" }, it.sub) : null),
      h("div", { class: "hb-track" }, h("i", { class: it.color || opts.color || "c-blue", style: `width:${Math.max(0.8, it.value / max * 100)}%` })),
      h("div", { class: "hb-val" }, opts.fmtVal ? opts.fmtVal(it) : fmt(it.value)));
    if (it.tip) hoverable(row, it.tip);
    list.append(row);
  }
  if (items.length > shown.length) list.append(h("div", { class: "muted small hb-more" }, `и ещё ${items.length - shown.length}`));
  if (!items.length) list.append(h("div", { class: "empty small" }, opts.empty || "Нет данных"));
  return list;
}

// Полоса из частей (брак / проверить / норма) с зазорами 2px.
function stackBar(parts, total) {
  const bar = h("div", { class: "stack" });
  const t = total || parts.reduce((a, p) => a + p.value, 0) || 1;
  for (const p of parts) {
    if (!p.value) continue;
    bar.append(hoverable(h("i", { class: p.color, style: `flex:${p.value / t}` }),
      () => [tipVal(fmt(p.value), p.label, p.color), h("div", { class: "muted" }, `${fmt(p.value / t * 100, 1)}%`)]));
  }
  return bar;
}

function legend(items) {
  return h("div", { class: "legend" }, items.map(([cls, text]) => h("span", {}, h("i", { class: `sw ${cls}` }), text)));
}

// Столбцы по дням: брак / проверить / норма, общий масштаб, подсказка на столбце.
function dayColumns(anks, onPick) {
  const days = [...new Set(anks.map((a) => a.date).filter(Boolean))].sort();
  const box = h("div", { class: "cols-chart" });
  if (!days.length) return h("div", { class: "empty small" }, "Нет дат в анкетах");
  const data = days.map((d) => {
    const x = { d, brak: 0, warn: 0, ok: 0 };
    anks.forEach((a) => { if (a.date === d && !a.technical) x[stateOf(a)]++; });
    x.total = x.brak + x.warn + x.ok;
    return x;
  });
  const max = Math.max(1, ...data.map((x) => x.total));
  const step = niceStep(max);
  const top = Math.ceil(max / step) * step;
  const grid = h("div", { class: "cc-grid" });
  for (let v = 0; v <= top; v += step) grid.append(h("div", { class: "cc-line", style: `bottom:${v / top * 100}%` }, h("span", {}, fmt(v))));
  const bars = h("div", { class: "cc-bars" });
  for (const x of data) {
    const col = h("div", { class: `cc-col ${F().date === x.d ? "active" : ""}`, onclick: () => onPick && onPick(x.d) },
      h("div", { class: "cc-stack", style: `height:${x.total / top * 100}%` },
        ["ok", "warn", "brak"].map((k) => x[k] ? h("i", { class: `c-${k}`, style: `flex:${x[k]}` }) : null)),
      h("div", { class: "cc-x" }, dayLabel(x.d)));
    hoverable(col, () => [h("div", { class: "tip-h" }, dayLabel(x.d)), tipVal(fmt(x.brak), "брак", "c-brak"),
      tipVal(fmt(x.warn), "проверить", "c-warn"), tipVal(fmt(x.ok), "норма", "c-ok"), h("div", { class: "muted" }, `всего ${fmt(x.total)}`)]);
    bars.append(col);
  }
  box.append(grid, bars);
  return box;
}
function niceStep(max) {
  const raw = max / 4;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * p).find((s) => s >= raw) || p * 10;
}

// Тепловая карта: строки × столбцы, один оттенок от светлого к тёмному.
function heatmap(rows, cols, value, opts = {}) {
  const max = Math.max(1, ...rows.flatMap((r) => cols.map((c) => value(r, c))));
  const grid = h("div", { class: "heat", style: `grid-template-columns: minmax(120px, 180px) repeat(${cols.length}, minmax(44px, 1fr))` });
  grid.append(h("div", { class: "heat-corner" }, opts.corner || ""));
  cols.forEach((c) => grid.append(h("div", { class: "heat-col", title: c.label }, c.short || c.label)));
  for (const r of rows) {
    grid.append(h("div", { class: "heat-row", title: r.label }, r.label));
    for (const c of cols) {
      const v = value(r, c);
      const step = v ? Math.min(6, 1 + Math.floor(v / max * 5.999)) : 0;
      const cell = h("div", { class: `heat-cell s${step}`, onclick: v && opts.onClick ? () => opts.onClick(r, c) : null }, v ? String(v) : "");
      hoverable(cell, () => [h("div", { class: "tip-h" }, r.label), tipVal(fmt(v), c.label)]);
      grid.append(cell);
    }
  }
  return h("div", { class: "heat-wrap" }, grid,
    h("div", { class: "heat-scale" }, h("span", {}, "меньше"), [1, 2, 3, 4, 5, 6].map((s) => h("i", { class: `heat-cell s${s}` })), h("span", {}, "больше")));
}

function tile(k, v, s, cls, onClick) {
  return h("div", { class: `stat ${cls || ""} ${onClick ? "clickable" : ""}`, onclick: onClick || null },
    h("div", { class: "k" }, k), h("div", { class: "v" }, v), s ? h("div", { class: "s" }, s) : null);
}
function card(title, hint, ...body) {
  return h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", {}, h("h2", {}, title), hint ? h("p", { class: "hint" }, hint) : null)), ...body);
}
const pct = (a, b) => (b ? a / b * 100 : 0);

// ── Сводные подсчёты по набору анкет ───────────────────────────────────────
function counts(anks) {
  const c = { brak: 0, warn: 0, ok: 0, tech: 0 };
  anks.forEach((a) => c[stateOf(a)]++);
  c.iv = c.brak + c.warn + c.ok;
  return c;
}
function groupBy(anks, key) {
  const m = new Map();
  for (const a of anks) {
    const k = typeof key === "function" ? key(a) : a[key];
    if (k == null || k === "") continue;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(a);
  }
  return m;
}
function levelOf(p) {
  const st = S.result.status_cfg;
  return p >= st.red_pct ? "RED" : p >= st.yellow_pct ? "YELLOW" : "GREEN";
}
// Причины брака: для каждой причины — сколько анкет (анкета считается один раз на причину).
function reasonCounts(anks, sev) {
  const m = new Map();
  for (const a of anks) {
    if (a.technical) continue;
    const seen = new Set();
    for (const [code, s] of a.issues) {
      if (s !== sev || seen.has(code)) continue;
      seen.add(code);
      m.set(code, (m.get(code) || 0) + 1);
    }
  }
  return [...m.entries()].sort((x, y) => y[1] - x[1]);
}
function blockCounts(anks, sev) {
  const m = new Map();
  for (const a of anks) {
    if (a.technical) continue;
    for (const b of new Set(a.issues.filter((i) => i[1] === sev).map((i) => i[2]))) m.set(b, (m.get(b) || 0) + 1);
  }
  return [...m.entries()].sort((x, y) => y[1] - x[1]);
}
function isBrak(a) { return stateOf(a) === "brak"; }

// ── Главная ─────────────────────────────────────────────────────────────────
function headline(anks) {
  const c = counts(anks);
  const p = pct(c.brak, c.iv);
  const st = S.result.status_cfg;
  const lvl = p >= st.yellow_pct ? "RED" : p >= st.yellow_pct / 2 ? "YELLOW" : "GREEN";
  const byCity = [...groupBy(anks.filter((a) => !a.technical), "city")].map(([k, v]) => [k, pct(v.filter(isBrak).length, v.length), v.length])
    .filter((x) => x[2] >= 5).sort((a, b) => b[1] - a[1]);
  const byInter = [...groupBy(anks.filter((a) => !a.technical), "inter")].map(([k, v]) => [k, pct(v.filter(isBrak).length, v.length)])
    .sort((a, b) => b[1] - a[1]);
  const top = reasonCounts(anks.filter(isBrak), "defect")[0];
  const title = { RED: "Много брака — нужно вмешаться", YELLOW: "Есть проблемы — стоит проверить", GREEN: "Поле идёт нормально" }[lvl];
  const parts = [`Брак ${fmt(p, 1)}% (${fmt(c.brak)} из ${fmt(c.iv)} анкет).`];
  if (c.brak && byCity.length && byCity[0][1] > 0) parts.push(`Больше всего — ${byCity[0][0]} (${fmt(byCity[0][1], 0)}%).`);
  if (top) parts.push(`Главная причина: «${label(top[0])}».`);
  const worst = byInter.filter((x) => levelOf(x[1]) === "RED").map((x) => x[0]);
  if (worst.length) parts.push(`В красной зоне: ${worst.slice(0, 4).join(", ")}${worst.length > 4 ? ` и ещё ${worst.length - 4}` : ""}.`);
  return h("div", { class: `hero ${lvl}` },
    h("div", { class: "hero-light" }, h("i", { class: "r" }), h("i", { class: "y" }), h("i", { class: "g" })),
    h("div", {}, h("div", { class: "hero-title" }, title), h("div", { class: "hero-text" }, parts.join(" "))));
}

function pageOverview(root) {
  if (!S.result) return noResult(root);
  const R = S.result, s = R.summary;
  const anks = scoped();
  const c = counts(anks);
  root.append(filterBar("overview"));
  if (R.rule_errors.length) root.append(h("div", { class: "notice bad" }, h("div", {}, h("b", {}, "Некоторые правила не проверены: "), R.rule_errors.join("; "))));
  root.append(headline(anks));
  root.append(reconciliation());

  const rv = s.review, q = R.quotas || {};
  const todo = anks.filter((a) => (a.defect || a.warning) && !a.decision && !a.technical).length;
  root.append(h("div", { class: "stats" },
    tile("Анкет", fmt(c.iv), c.tech ? `+ ${fmt(c.tech)} тех. записей (видео/фото)` : s.period || ""),
    tile("Брак", fmt(c.brak), `${fmt(pct(c.brak, c.iv), 1)}% анкет`, "red", () => go("defects")),
    tile("Проверить", fmt(c.warn), "сигналы, не брак сами по себе", "yellow", () => { S.reviewFilter = "warn"; go("review"); }),
    tile("Норма", fmt(c.ok), `${fmt(pct(c.ok, c.iv), 1)}% анкет`, "green"),
    rv.enabled ? tile("Ждут решения", fmt(todo), "руководителя проекта", "", () => { S.reviewFilter = "todo"; go("review"); }) : null,
    q.enabled ? tile("План выполнен", `${fmt(q.summary.pct)}%`, `план ${fmt(q.summary.plan)} · добрать ${fmt(q.summary.left)}${q.summary.over ? ` · перебор ${fmt(q.summary.over)}` : ""}`, "", () => go("quotas")) : null));

  root.append(h("div", { class: "grid-2 wide-left" },
    card("Анкеты по дням", "Нажмите на день — все графики покажут только его.",
      legend([["c-brak", "Брак"], ["c-warn", "Проверить"], ["c-ok", "Норма"]]),
      dayColumns(scoped().filter((a) => matches(a, "date")), (d) => setFilter("date", F().date === d ? null : d, "overview"))),
    lastDayCard()));

  root.append(h("div", { class: "grid-2" },
    card("Главные причины брака", "Сколько анкет с каждой причиной. У анкеты может быть несколько причин. Нажмите — подробности.",
      hbars(reasonCounts(anks.filter(isBrak), "defect").map(([code, n]) => ({ label: label(code), value: n, code,
        tip: () => [tipVal(fmt(n), "анкет с браком"), h("div", { class: "muted" }, `${fmt(pct(n, c.brak), 0)}% всего брака`)] })),
      { color: "c-brak", limit: 7, onClick: (it) => { S.defReason = it.code; go("defects"); }, empty: "Брака нет" })),
    card("Интервьюеры в зоне риска", "С наибольшей долей брака. Нажмите — откроется карточка интервьюера.",
      riskList(anks))));

  const cities = [...groupBy(anks.filter((a) => !a.technical), "city")].map(([city, v]) => {
    const cc = counts(v);
    return { label: city, sub: v[0].region !== city ? v[0].region : "", value: pct(cc.brak, cc.iv), n: cc.iv, cc, active: F().city === city };
  }).sort((a, b) => b.value - a.value);
  root.append(h("div", { class: "grid-2" },
    card("Брак по городам", "Доля брака среди анкет города. Нажмите на город, чтобы отфильтровать.",
      cityBars(cities)),
    card("Отчёты и история", "Отчёт Word строится по выбранным фильтрам. Волна сохраняет итоги по интервьюерам на этом компьютере — видно, кто несколько волн подряд в красной или жёлтой зоне.",
      h("div", { class: "row", style: "flex-wrap:wrap;margin-bottom:14px" },
        h("button", { class: "btn primary", onclick: () => exportReport("word") }, "Отчёт Word"),
        h("button", { class: "btn", onclick: () => exportReport("client") }, "Для заказчика (Excel)"),
        h("button", { class: "btn", onclick: () => exportReport("clean") }, "Чистая база"),
        h("button", { class: "btn", onclick: () => exportReport("full") }, "Полный Excel")),
      saveWave())));
}
// Последний день: кто работал, кто выполнил норму, кто нет.
function lastDayCard() {
  const { norm, days, rows } = dailyData(S.result.anketas.filter((a) => matches(a, "date")));
  if (!days.length) return card("Последний день", null, h("div", { class: "empty small" }, "Нет дат"));
  const day = F().date && days.includes(F().date) ? F().date : days[days.length - 1];
  const k = days.indexOf(day);
  const cs = rows.map((r) => r.cells[k]);
  const worked = cs.filter((c) => c.n).length, off = rows.length - worked;
  const low = cs.filter((c) => c.st === "low").length, good = cs.filter((c) => c.st === "good").length;
  return card(`День ${dayLabel(day)}`, "Кто работал и выполнил ли дневную норму. Подробно — во вкладке «По дням».",
    h("div", { class: "day-sum" },
      h("div", {}, h("div", { class: "ds-v" }, `${worked}/${rows.length}`), h("div", { class: "muted small" }, "работали")),
      norm ? h("div", {}, h("div", { class: "ds-v t-okx" }, good), h("div", { class: "muted small" }, `выполнили норму (${norm})`)) : null,
      norm ? h("div", {}, h("div", { class: "ds-v t-warnx" }, low), h("div", { class: "muted small" }, "ниже нормы")) : null,
      h("div", {}, h("div", { class: `ds-v ${off ? "t-brak" : ""}` }, off), h("div", { class: "muted small" }, "не работали"))),
    stackBar([{ value: good || (norm ? 0 : worked), color: "c-ok", label: norm ? "выполнили норму" : "работали" },
      { value: low, color: "c-warn", label: "ниже нормы" }, { value: off, color: "c-brak", label: "не работали" }], rows.length),
    h("div", { class: "row", style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => go("daily") }, "Открыть «По дням» →"),
      norm ? null : h("span", { class: "muted small" }, "Норма в день не задана")));
}

function cityBars(cities) {
  return hbars(cities.map((x) => ({ ...x, tip: () => [h("div", { class: "tip-h" }, x.label),
    tipVal(fmt(x.cc.brak), "брак", "c-brak"), tipVal(fmt(x.cc.warn), "проверить", "c-warn"), tipVal(fmt(x.cc.ok), "норма", "c-ok")] })),
  { color: "c-brak", max: 100, limit: 10, fmtVal: (it) => `${fmt(it.value, 0)}% · ${fmt(it.n)}`,
    onClick: (it) => setFilter("city", F().city === it.label ? null : it.label, S.page) });
}
function riskList(anks) {
  const rows = [...groupBy(anks.filter((a) => !a.technical), "inter")].map(([inter, v]) => {
    const cc = counts(v);
    const p = pct(cc.brak, cc.iv);
    const top = reasonCounts(v.filter(isBrak), "defect")[0];
    return { inter, p, cc, lvl: levelOf(p), city: v[0].city, top: top ? label(top[0]) : "" };
  }).filter((r) => r.cc.brak).sort((a, b) => b.p - a.p).slice(0, 8);
  if (!rows.length) return h("div", { class: "notice ok" }, "Брака у интервьюеров нет.");
  return h("div", { class: "risk-list" }, rows.map((r) => h("div", { class: "risk-row clickable", onclick: () => showInterviewer(r.inter) },
    pill(r.lvl), h("div", { class: "rl-name" }, h("b", {}, r.inter), h("span", { class: "muted small" }, ` · ${r.city}`),
      r.top ? h("div", { class: "muted small" }, r.top) : null),
    h("div", { class: "rl-bar" }, stackBar([{ value: r.cc.brak, color: "c-brak", label: "брак" }, { value: r.cc.warn, color: "c-warn", label: "проверить" },
      { value: r.cc.ok, color: "c-ok", label: "норма" }])),
    h("div", { class: "rl-val" }, `${fmt(r.p, 0)}%`))));
}
function saveWave() {
  const waveInput = h("input", { type: "text", placeholder: "Например: Волна 3 — сентябрь", style: "flex:1" });
  return h("div", { class: "row" }, waveInput, h("button", { class: "btn primary", onclick: async () => {
    await guarded(async () => { S.history = await POST("/api/history/save", { wave: waveInput.value }); toast("Волна сохранена"); go("history"); });
  } }, "Сохранить"));
}

// ── Брак: где и почему ──────────────────────────────────────────────────────
function pageDefects(root) {
  if (!S.result) return noResult(root);
  root.append(filterBar("defects"));
  const anks = scoped();
  const sev = S.defSev || "defect";
  const pool = anks.filter((a) => !a.technical && (sev === "defect" ? isBrak(a) : stateOf(a) === "warn"));
  const reason = S.defReason && pool.some((a) => a.issues.some((i) => i[0] === S.defReason && i[1] === sev)) ? S.defReason : null;
  const sel = reason ? pool.filter((a) => a.issues.some((i) => i[0] === reason && i[1] === sev)) : pool;
  const c = counts(anks);

  root.append(h("div", { class: "row", style: "margin-bottom:14px" },
    h("div", { class: "segmented" },
      h("button", { class: sev === "defect" ? "on" : "", onclick: () => { S.defSev = "defect"; S.defReason = null; go("defects"); } }, `Брак · ${fmt(c.brak)}`),
      h("button", { class: sev === "warning" ? "on" : "", onclick: () => { S.defSev = "warning"; S.defReason = null; go("defects"); } }, `Проверить · ${fmt(c.warn)}`)),
    reason ? h("span", { class: "chip-on" }, "Причина: ", h("b", {}, label(reason)), h("button", { title: "Снять", onclick: () => { S.defReason = null; go("defects"); } }, "×")) : null,
    h("span", { class: "spacer" }),
    h("span", { class: "muted small" }, sev === "defect" ? "С учётом решений руководителя: «Принять» убирает из брака, «Брак» добавляет." : "Сигналы для ручной проверки — сами по себе не брак.")));

  const inters = new Set(sel.map((a) => a.inter));
  const cities = new Set(sel.map((a) => a.city));
  root.append(h("div", { class: "stats" },
    tile(sev === "defect" ? "Анкет с браком" : "Анкет «проверить»", fmt(sel.length), `${fmt(pct(sel.length, c.iv), 1)}% всех анкет`, sev === "defect" ? "red" : "yellow"),
    tile("Интервьюеров", fmt(inters.size), `из ${fmt(new Set(anks.map((a) => a.inter)).size)}`),
    tile("Городов", fmt(cities.size), `из ${fmt(new Set(anks.map((a) => a.city)).size)}`),
    tile("Средний риск", fmt(sel.length ? sel.reduce((x, a) => x + a.risk, 0) / sel.length : 0), "балл 0–100 по сигналам")));

  const color = sev === "defect" ? "c-brak" : "c-warn";
  const reasons = reasonCounts(pool, sev);
  root.append(h("div", { class: "grid-2" },
    card("Почему", "Причины по числу анкет. Нажмите на причину — всё ниже покажет только её.",
      hbars(reasons.map(([code, n]) => ({ label: label(code), value: n, code, active: code === reason })),
        { color, limit: 14, onClick: (it) => { S.defReason = reason === it.code ? null : it.code; go("defects"); }, empty: "Нет анкет" })),
    card("В каком блоке анкеты", "Где именно ошибка: блок вопросов анкеты или служебная область.",
      hbars(blockCounts(sel, sev).map(([b, n]) => ({ label: b, value: n })), { color, limit: 14, empty: "Нет анкет" }))));

  const regions = [...groupBy(anks.filter((a) => !a.technical), "region")].map(([rg, v]) => {
    const n = v.filter((a) => sel.includes(a)).length;
    return { label: rg, value: pct(n, v.length), n, total: v.length };
  }).filter((x) => x.n).sort((a, b) => b.value - a.value);
  const cityRows = [...groupBy(anks.filter((a) => !a.technical), "city")].map(([city, v]) => {
    const n = v.filter((a) => sel.includes(a)).length;
    return { label: city, sub: v[0].region !== city ? v[0].region : "", value: pct(n, v.length), n, total: v.length, active: F().city === city };
  }).filter((x) => x.n).sort((a, b) => b.value - a.value);
  const fv = (it) => `${fmt(it.value, 0)}% · ${fmt(it.n)} из ${fmt(it.total)}`;
  root.append(h("div", { class: "grid-2" },
    card("Где: регионы", "Доля таких анкет среди всех анкет региона.",
      hbars(regions, { color, max: 100, fmtVal: fv, onClick: (it) => setFilter("region", F().region === it.label ? null : it.label, "defects") })),
    card("Где: города", "Нажмите на город — отфильтровать.",
      hbars(cityRows, { color, max: 100, fmtVal: fv, onClick: (it) => setFilter("city", F().city === it.label ? null : it.label, "defects") }))));

  // кто × почему
  const topInters = [...groupBy(sel, "inter")].sort((a, b) => b[1].length - a[1].length).slice(0, 15);
  const topReasons = reasons.slice(0, 8).map(([code]) => ({ code, label: label(code), short: shortLabel(label(code)) }));
  const cellCount = (r, col) => r.list.filter((a) => a.issues.some((i) => i[0] === col.code && i[1] === sev)).length;
  root.append(card("Кто и почему", "Интервьюеры с наибольшим числом таких анкет × причины. Чем темнее клетка, тем больше анкет. Нажмите на клетку — список анкет.",
    topInters.length ? heatmap(topInters.map(([inter, list]) => ({ label: `${inter} · ${list[0].city}`, inter, list })), topReasons, cellCount,
      { corner: "Интервьюер", onClick: (r, col) => showList(`${r.inter}: ${col.label}`, r.list.filter((a) => a.issues.some((i) => i[0] === col.code && i[1] === sev))) })
      : h("div", { class: "empty small" }, "Нет анкет")));

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const byHour = hours.map((hh) => sel.filter((a) => a.hour === hh).length);
  root.append(h("div", { class: "grid-2 wide-left" },
    card("На карте", "Каждая точка — анкета. Нажмите на точку, чтобы увидеть, почему она отмечена.", miniMap(sel, color)),
    card("Когда: час начала анкеты", "По местному времени выгрузки.", hourBars(byHour, color))));

  root.append(card("Анкеты", "Паспорт каждой анкеты: что, кто, где, когда и в каком блоке. Нажмите на строку — подробности и исходная строка из таблицы.",
    passportTable(sel, sev, reason)));
}
function shortLabel(s) { return s.length > 22 ? s.slice(0, 20) + "…" : s; }
function hourBars(byHour, color) {
  const max = Math.max(1, ...byHour);
  const box = h("div", { class: "hours" });
  byHour.forEach((n, hh) => box.append(hoverable(h("div", { class: "hr" },
    h("div", { class: "hr-bar" }, h("i", { class: color, style: `height:${n / max * 100}%` })),
    h("div", { class: "hr-x" }, hh % 3 === 0 ? String(hh) : "")), () => [h("div", { class: "tip-h" }, `${hh}:00–${hh}:59`), tipVal(fmt(n), "анкет")])));
  return box;
}
function passportTable(list, sev, reason) {
  const rows = list.map((a) => {
    const iss = a.issues.filter((i) => i[1] === sev && (!reason || i[0] === reason));
    const main = iss.find((i) => i[0] === a.primary) || iss[0] || [];
    return { ...a, why: main[3] || "", what: main[4] || "", block: [...new Set(iss.map((i) => i[2]))].join(", "), more: Math.max(0, iss.length - 1) };
  });
  return table([
    { key: "risk", label: "Риск", num: true, render: (r) => riskTag(r.risk) },
    { key: "id", label: "ID" }, { key: "region", label: "Регион" }, { key: "city", label: "Город" }, { key: "inter", label: "Интервьюер" },
    { key: "start", label: "Когда", sortVal: (r) => r.start && r.start.split(/[. :]/).reverse().join("") },
    { key: "block", label: "Блок", wrap: true },
    { key: "why", label: "Почему", wrap: true, render: (r) => h("div", {}, h("b", {}, r.why), r.more ? h("span", { class: "muted small" }, ` +${r.more}`) : null, h("div", { class: "muted small" }, r.what)) },
    { key: "decision", label: "Решение", render: (r) => decisionTag(r.decision) },
  ], rows, { sortKey: "risk", height: 560, onClick: (r) => openAnketa(r.pos) });
}
function showList(title, list) {
  openModal(title, passportTable(list, list.some(isBrak) ? "defect" : "warning"), true);
}

// ── Интервьюеры ─────────────────────────────────────────────────────────────
function pageInterviewers(root) {
  if (!S.result) return noResult(root);
  root.append(filterBar("interviewers"));
  const anks = scoped();
  const rows = [...groupBy(anks, "inter")].map(([inter, v]) => {
    const cc = counts(v);
    const p = pct(cc.brak, cc.iv);
    const top = reasonCounts(v.filter(isBrak), "defect").slice(0, 2).map(([code, n]) => `${label(code)} ×${n}`).join(", ");
    return { "Интервьюер": inter, "Город": v[0].city, "Регион": v[0].region, "Анкет": cc.iv, "Тех.": cc.tech, "Брак": cc.brak,
      "Проверить": cc.warn, "% брака": Math.round(p * 10) / 10, "Статус": levelOf(p), cc,
      "Риск": v.length ? Math.round(v.reduce((x, a) => x + a.risk, 0) / v.length) : 0, "Главные причины": top };
  });
  const sc = { RED: 0, YELLOW: 0, GREEN: 0 };
  rows.forEach((r) => sc[r["Статус"]]++);
  const st = S.result.status_cfg;
  root.append(h("div", { class: "stats" },
    tile("Интервьюеров", fmt(rows.length), `${fmt(new Set(anks.map((a) => a.city)).size)} городов`),
    tile("🔴 Критично", fmt(sc.RED), `брак от ${st.red_pct}% — остановить, проверить`, "red"),
    tile("🟡 Внимание", fmt(sc.YELLOW), `брак ${st.yellow_pct}–${st.red_pct}% — инструктаж`, "yellow"),
    tile("🟢 Норма", fmt(sc.GREEN), `брак до ${st.yellow_pct}%`, "green")));
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Все интервьюеры"),
      h("p", { class: "hint" }, "Полоса — состав его анкет: брак, проверить, норма. Нажмите на строку — карточка интервьюера: причины, дни, маршрут, анкеты.")),
      h("button", { class: "btn small", onclick: () => exportReport("interviewers") }, "Excel")),
    legend([["c-brak", "Брак"], ["c-warn", "Проверить"], ["c-ok", "Норма"]]),
    table([
      { key: "Статус", label: "Статус", render: (r) => pill(r["Статус"]), sortVal: (r) => ({ RED: 3, YELLOW: 2, GREEN: 1 })[r["Статус"]] },
      { key: "Интервьюер", label: "Интервьюер" }, { key: "Город", label: "Город" },
      { key: "Анкет", label: "Анкет", num: true },
      { key: "bar", label: "Состав анкет", sortVal: (r) => r["% брака"], render: (r) => h("div", { class: "cell-stack" },
        stackBar([{ value: r.cc.brak, color: "c-brak", label: "брак" }, { value: r.cc.warn, color: "c-warn", label: "проверить" }, { value: r.cc.ok, color: "c-ok", label: "норма" }])) },
      { key: "% брака", label: "% брака", num: true, digits: 1 },
      { key: "Риск", label: "Риск", num: true, render: (r) => riskTag(r["Риск"]) },
      { key: "Главные причины", label: "Главные причины брака", wrap: true },
    ], rows, { sortKey: "% брака", rowClass: (r) => `row-${r["Статус"]}`, onClick: (r) => showInterviewer(r["Интервьюер"]) })));
  root.append(h("div", { class: "card" }, h("h2", {}, "Что делать по статусу"),
    h("ul", { class: "issue-list" }, S.result.legend.map((l) => h("li", {}, h("span", { style: "min-width:110px" }, pill(l.code)), h("b", { style: "min-width:170px" }, l.desc), h("span", { class: "muted" }, l.actions))))));
}

function showInterviewer(inter) {
  const all = S.result.anketas.filter((a) => a.inter === inter);
  const cc = counts(all);
  const p = pct(cc.brak, cc.iv);
  const body = h("div", {},
    h("div", { class: "stats" },
      tile("Статус", pill(levelOf(p)), `${fmt(p, 1)}% брака`),
      tile("Анкет", fmt(cc.iv), cc.tech ? `+ ${fmt(cc.tech)} тех. записей` : [...new Set(all.map((a) => a.city))].join(", ")),
      tile("Брак", fmt(cc.brak), "", "red"), tile("Проверить", fmt(cc.warn), "", "yellow")),
    h("div", { class: "grid-2" },
      card("Почему брак", null, hbars(reasonCounts(all.filter(isBrak), "defect").map(([code, n]) => ({ label: label(code), value: n })), { color: "c-brak", empty: "Брака нет" })),
      card("По дням", null, legend([["c-brak", "Брак"], ["c-warn", "Проверить"], ["c-ok", "Норма"]]), dayColumns(all))),
    all.some((a) => a.lat != null) ? card("Маршрут", "Анкеты по времени; линия — порядок в течение дня.", miniMap(all, null, true)) : null,
    card("Анкеты", null, passportTable(all.filter((a) => a.defect || a.warning || a.decision), "defect")));
  openModal(`Интервьюер ${inter}`, body, true);
}

// ── Карта GPS ───────────────────────────────────────────────────────────────
const MAP_COLORS = { brak: "#d03b3b", warn: "#e89a00", ok: "#0ca30c", tech: "#6d5fd6" };
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
let maps = [];
function freshMap(box, opts) {
  maps = maps.filter((m) => document.body.contains(m.getContainer()) || (m.remove(), false));
  const m = L.map(box, { zoomControl: true, preferCanvas: true, ...opts });
  L.tileLayer(TILE_URL, { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(m);
  maps.push(m);
  return m;
}
function esc(t) { return String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function popupHtml(a) {
  const st = stateOf(a);
  const iss = a.issues.map((i) => `<li><b>${esc(i[3])}</b> <span class="muted">· ${esc(i[2])}</span><br>${esc(i[4])}</li>`).join("");
  return `<div class="pop"><div class="pop-h"><span class="st ${ST[st].cls}">${ST[st].icon}</span> Анкета ${esc(a.id)}</div>` +
    `<div>${esc(a.inter)} · ${esc(a.city)} · ${esc(a.start || "")}</div>` +
    (a.point ? `<div class="muted">точка «${esc(a.point)}», ${a.dist != null ? esc(a.dist) + " км" : ""}</div>` : "") +
    (iss ? `<ul>${iss}</ul>` : `<div class="muted">замечаний нет</div>`) +
    `<a href="#" data-pos="${a.pos}" class="pop-open">Открыть анкету →</a></div>`;
}
function bindPopupOpen(m) {
  m.on("popupopen", (e) => {
    const link = e.popup.getElement().querySelector(".pop-open");
    if (link) link.onclick = (ev) => { ev.preventDefault(); openAnketa(Number(link.dataset.pos)); };
  });
}
function dot(a, color) {
  return L.circleMarker([a.lat, a.lon], { radius: 5, color: "#fff", weight: 1.5, fillColor: color || MAP_COLORS[stateOf(a)], fillOpacity: 0.95 })
    .bindPopup(popupHtml(a), { maxWidth: 340 });
}
// Небольшая карта для других страниц: только точки (и маршрут для одного интервьюера).
function miniMap(list, color, route) {
  const box = h("div", { class: "map small" });
  const pts = list.filter((a) => a.lat != null);
  if (!window.L || !pts.length) { box.append(h("div", { class: "empty small" }, pts.length ? "Карта не загрузилась" : "Нет координат")); return box; }
  requestAnimationFrame(() => {
    if (!document.body.contains(box)) return;
    const m = freshMap(box);
    bindPopupOpen(m);
    if (route) drawRoutes(m, pts);
    pts.forEach((a) => dot(a, color && MAP_COLORS[color.replace("c-", "")]).addTo(m));
    m.fitBounds(pts.map((a) => [a.lat, a.lon]), { padding: [24, 24], maxZoom: 15 });
  });
  return box;
}
function drawRoutes(m, pts) {
  const byDay = groupBy([...pts].filter((a) => a.date).sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start)), "date");
  for (const list of byDay.values()) {
    L.polyline(list.sort((a, b) => a.start.localeCompare(b.start)).map((a) => [a.lat, a.lon]), { color: "#4a3aa7", weight: 2, opacity: 0.75, dashArray: "4 6" }).addTo(m);
  }
}

function pageMap(root) {
  if (!S.result) return noResult(root);
  const g = S.result.geo || {};
  if (!g.enabled) {
    root.append(h("div", { class: "card" }, h("div", { class: "empty" }, h("b", {}, "GPS-контроль не включён"),
      "Выберите колонки с координатами в «Настройке проверки → Колонки» и запустите проверку.",
      h("div", { style: "margin-top:14px" }, h("button", { class: "btn", onclick: () => openSetup("columns") }, "Настроить")))));
    return;
  }
  root.append(filterBar("map"));
  const anks = scoped();
  const gps = anks.filter((a) => a.lat != null);
  const has = (code) => (a) => a.issues.some((i) => i[0] === code);
  const n = (code) => anks.filter(has(code)).length;
  const lay = S.mapLayers || (S.mapLayers = { plan: true, dots: true, heat: false, route: true });
  const setLayer = (k) => { lay[k] = !lay[k]; draw(); };

  const pick = (code) => { S.mapOnly = S.mapOnly === code ? null : code; go("map"); };
  const only = S.mapOnly;
  root.append(h("div", { class: "stats" },
    tile("С координатами", fmt(gps.length), anks.length - gps.length ? `без GPS: ${fmt(anks.length - gps.length)}` : "у всех есть GPS", only === "no_gps" ? "active" : "", () => pick("no_gps")),
    tile("Не в своём городе", fmt(n("geo_city")), "координаты за чертой города из анкеты", `red ${only === "geo_city" ? "active" : ""}`, () => pick("geo_city")),
    tile("Далеко от точки", fmt(n("geo_far")), `дальше радиуса точки (${g.max_dist_km} км)`, `yellow ${only === "geo_far" ? "active" : ""}`, () => pick("geo_far")),
    tile("«Телепорт»", fmt(n("geo_jump")), `быстрее ${g.max_speed_kmh} км/ч между анкетами`, `yellow ${only === "geo_jump" ? "active" : ""}`, () => pick("geo_jump")),
    tile("Одинаковые координаты", fmt(n("geo_same")), "копирование или подмена GPS", `yellow ${only === "geo_same" ? "active" : ""}`, () => pick("geo_same")),
    tile("Скопления", fmt(n("geo_cluster")), `больше ${g.max_per_point} анкет в одном месте`, only === "geo_cluster" ? "active" : "", () => pick("geo_cluster"))));
  if (only) root.append(h("div", { class: "notice info" }, h("div", { style: "flex:1" }, "На карте только: ", h("b", {}, label(only))),
    h("button", { class: "btn small", onclick: () => pick(only) }, "Показать все")));

  // список городов слева: анкет, брак, вне города
  const cityStats = [...groupBy(anks.filter((a) => !a.technical), "city")].map(([city, v]) => ({
    city, region: v[0].region, n: v.length, brak: v.filter(isBrak).length, out: v.filter(has("geo_city")).length,
    far: v.filter(has("geo_far")).length, pts: v.filter((a) => a.lat != null) })).sort((a, b) => b.n - a.n);
  const side = h("div", { class: "map-side" },
    h("div", { class: "ms-head" }, "Города"),
    cityStats.map((c) => h("div", { class: `ms-city ${F().city === c.city ? "on" : ""}`, onclick: () => setFilter("city", F().city === c.city ? null : c.city, "map") },
      h("div", { class: "ms-name" }, h("b", {}, c.city), h("span", { class: "muted small" }, c.region !== c.city ? c.region : "")),
      h("div", { class: "ms-nums" }, h("span", { title: "анкет" }, fmt(c.n)),
        c.brak ? h("span", { class: "t-brak", title: "брак" }, `✕ ${fmt(c.brak)}`) : null,
        c.out ? h("span", { class: "t-out", title: "не в своём городе" }, `⌖ ${fmt(c.out)}`) : null),
      stackBar([{ value: c.brak, color: "c-brak", label: "брак" }, { value: c.n - c.brak, color: "c-okpale", label: "без брака" }]))));

  const box = h("div", { class: "map big" });
  const toggles = h("div", { class: "map-tools" },
    ...[["plan", "Плановые точки"], ["dots", "Анкеты"], ["heat", "Плотность"], ["route", "Маршрут интервьюера"]].map(([k, t]) =>
      h("label", { class: `mt ${lay[k] ? "on" : ""}` }, h("input", { type: "checkbox", checked: lay[k], onchange: (e) => { setLayer(k); e.target.parentElement.classList.toggle("on", lay[k]); } }), t)));
  const mapLegend = h("div", { class: "map-legend" },
    ...["brak", "warn", "ok", "tech"].map((k) => h("span", {}, h("i", { style: `background:${MAP_COLORS[k]}` }), ST[k].label)),
    h("span", {}, h("i", { class: "ring" }), "плановая точка: размер — сколько анкет, цвет — выполнение квоты"),
    h("span", {}, h("i", { class: "bubble" }), "при отдалении — города: размер — анкет, цвет — доля брака"));
  root.append(h("div", { class: "card map-card" }, h("div", { class: "map-layout" }, side, h("div", { class: "map-main" }, toggles, box, mapLegend))));

  // таблица точек: план / факт
  const planRows = pointRows(anks, g);
  if (planRows.length) {
    root.append(card("Плановые точки: где нужно было и сколько сделано",
      "Факт — анкеты в радиусе точки. Нажмите на строку — карта приблизится к точке.",
      table([
        { key: "st", label: "", render: (r) => h("span", { class: `dot ${r.st}`, title: r.stLabel }), sortVal: (r) => ({ RED: 3, YELLOW: 2, GREEN: 1 })[r.st] },
        { key: "Город", label: "Город" }, { key: "Точка", label: "Точка", wrap: true },
        { key: "Квота", label: "План", num: true, render: (r) => r["Квота"] ?? "—" },
        { key: "Факт", label: "Факт", num: true },
        { key: "bar", label: "Выполнение", sortVal: (r) => r.pct ?? -1, render: (r) => r["Квота"] ? h("div", { class: "bar-cell" }, h("div", { class: "bar" }, h("i", { class: r.st === "RED" ? "c-serious" : "c-ok", style: `width:${Math.min(100, r.pct)}%` })), h("span", {}, `${fmt(r.pct)}%`)) : "" },
        { key: "Брак", label: "Брак", num: true }, { key: "Интервьюеров", label: "Интервьюеров", num: true },
      ], planRows, { sortKey: "Факт", height: 420, onClick: (r) => { const m = maps[maps.length - 1]; if (m && document.body.contains(m.getContainer())) { m.setView([r.lat, r.lon], 15); box.scrollIntoView({ behavior: "smooth", block: "center" }); } } })));
  }
  const bad = anks.filter((a) => a.issues.some((i) => i[2] === "GPS и место опроса" && i[0] !== "no_gps"));
  root.append(card("Анкеты с нарушениями GPS", "Не в своём городе, далеко от точки, «телепорт», одинаковые координаты, скопления.",
    table([
      { key: "id", label: "ID" }, { key: "city", label: "Город" }, { key: "inter", label: "Интервьюер" }, { key: "start", label: "Когда" },
      { key: "why", label: "Что не так", wrap: true, render: (a) => h("div", {}, a.issues.filter((i) => i[2] === "GPS и место опроса").map((i) => h("div", {}, h("b", {}, i[3]), " — ", i[4]))) },
    ], bad, { height: 420, onClick: (a) => openAnketa(a.pos), empty: "Нарушений GPS нет" })));

  if (!window.L) { box.append(h("div", { class: "empty" }, "Карта не загрузилась")); return; }
  const m = freshMap(box);
  bindPopupOpen(m);
  const layers = { plan: L.layerGroup(), dots: L.layerGroup(), heat: L.layerGroup(), route: L.layerGroup(), cities: L.layerGroup() };
  Object.values(layers).forEach((l) => l.addTo(m));
  const visible = gps.filter((a) => !only || a.issues.some((i) => i[0] === only));

  function draw() {
    Object.values(layers).forEach((l) => l.clearLayers());
    const zoom = m.getZoom();
    const far = zoom < 10;
    if (far) {
      // обзор страны: пузырь на город — размер = анкет, цвет = доля брака
      for (const c of cityStats) {
        if (!c.pts.length) continue;
        const lat = c.pts.reduce((x, a) => x + a.lat, 0) / c.pts.length, lon = c.pts.reduce((x, a) => x + a.lon, 0) / c.pts.length;
        const p = pct(c.brak, c.n), lvl = levelOf(p);
        L.circleMarker([lat, lon], { radius: 8 + Math.sqrt(c.n) * 1.6, color: "#fff", weight: 2,
          fillColor: { RED: MAP_COLORS.brak, YELLOW: MAP_COLORS.warn, GREEN: MAP_COLORS.ok }[lvl], fillOpacity: 0.75 })
          .bindTooltip(`<b>${esc(c.city)}</b><br>${fmt(c.n)} анкет · брак ${fmt(p, 0)}%${c.out ? `<br>не в городе: ${c.out}` : ""}`)
          .on("click", () => m.setView([lat, lon], 12)).addTo(layers.cities);
      }
      return;
    }
    if (lay.heat) drawHeat(layers.heat, visible);
    if (lay.plan) drawPlan(layers.plan, planRows, g);
    if (lay.route && F().inter) drawRoutes(layers.route, visible);
    if (lay.dots) visible.forEach((a) => dot(a).addTo(layers.dots));
  }
  m.on("zoomend", draw);
  const bounds = visible.map((a) => [a.lat, a.lon]);
  requestAnimationFrame(() => {
    m.invalidateSize();
    if (bounds.length) m.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 }); else m.setView([41.3, 64.5], 6);
    draw();
  });
}

function pointRows(anks, g) {
  const stats = g.point_stats || [];
  const f = F();
  return stats.filter((p) => (!f.city || String(p["Город"]).toLowerCase() === String(f.city).toLowerCase())).map((p) => {
    const city = String(p["Город"]).toLowerCase();
    const here = anks.filter((a) => !a.technical && String(a.city).toLowerCase() === city && a.point === p["Точка"] && a.dist != null && a.dist <= p["Радиус, км"]);
    const fact = here.length, quota = p["Квота"];
    const pc = quota ? fact / quota * 100 : null;
    const st = quota == null ? (fact ? "GREEN" : "YELLOW") : fact > quota ? "RED" : fact >= quota ? "GREEN" : "YELLOW";
    return { ...p, "Факт": fact, "Брак": here.filter(isBrak).length, "Интервьюеров": new Set(here.map((a) => a.inter)).size, pct: pc, st,
      stLabel: { RED: "квота превышена", GREEN: quota ? "квота выполнена" : "анкеты есть", YELLOW: fact ? "добирать" : "анкет нет" }[st] };
  });
}
function drawPlan(layer, rows, g) {
  const maxFact = Math.max(1, ...rows.map((r) => r["Факт"]));
  for (const r of rows) {
    const color = { RED: "#ec835a", GREEN: "#0ca30c", YELLOW: r["Факт"] ? "#e89a00" : "#8a8a8e" }[r.st];
    L.circle([r.lat, r.lon], { radius: (r["Радиус, км"] || g.max_dist_km) * 1000, color: "#2a78d6", weight: 1, fillOpacity: 0.04, interactive: false }).addTo(layer);
    L.circleMarker([r.lat, r.lon], { radius: 7 + 13 * Math.sqrt(r["Факт"] / maxFact), color: "#fff", weight: 2.5, fillColor: color, fillOpacity: 0.85 })
      .bindTooltip(`<b>${esc(r["Точка"])}</b><br>${esc(r["Город"])}<br>план: ${r["Квота"] ?? "—"} · факт: ${r["Факт"]}${r["Брак"] ? ` · брак: ${r["Брак"]}` : ""}<br>интервьюеров: ${r["Интервьюеров"]} · радиус ${r["Радиус, км"]} км`)
      .addTo(layer);
  }
}
// Плотность: анкеты по квадратам ~400 м, один оттенок от светлого к тёмному.
function drawHeat(layer, pts) {
  const cell = 0.004;
  const m = new Map();
  pts.forEach((a) => { const k = `${Math.floor(a.lat / cell)}|${Math.floor(a.lon / cell)}`; m.set(k, (m.get(k) || 0) + 1); });
  const max = Math.max(1, ...m.values());
  const ramp = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"];
  for (const [k, v] of m) {
    const [i, j] = k.split("|").map(Number);
    L.rectangle([[i * cell, j * cell], [(i + 1) * cell, (j + 1) * cell]], { stroke: false, fillColor: ramp[Math.min(5, Math.floor(v / max * 5.999))], fillOpacity: 0.55 })
      .bindTooltip(`${v} анкет в квадрате ~400 м`).addTo(layer);
  }
}

// ── По дням: норма и кто не работал ─────────────────────────────────────────
function dailyData(anks) {
  const d = cfg().daily || (cfg().daily = { min: 0, team: [] });
  const norm = Number(d.min) || 0;
  const iv = anks.filter((a) => !a.technical && a.date);
  const days = [...new Set(iv.map((a) => a.date))].sort();
  const f = F();
  const team = (d.team || []).map((x) => String(x).trim()).filter(Boolean);
  const inters = [...new Set([...iv.map((a) => a.inter), ...(!f.city && !f.region && !f.inter ? team : [])])]
    .filter(Boolean).sort((x, y) => String(x).localeCompare(String(y), "ru", { numeric: true }));
  const by = new Map();
  for (const a of iv) {
    const k = `${a.inter}|${a.date}`;
    const x = by.get(k) || { n: 0, brak: 0, list: [] };
    x.n++; if (isBrak(a)) x.brak++; x.list.push(a);
    by.set(k, x);
  }
  const rows = inters.map((inter) => {
    const cells = days.map((day) => {
      const x = by.get(`${inter}|${day}`) || { n: 0, brak: 0, list: [] };
      const ok = x.n - x.brak;
      return { ...x, ok, day, st: x.n === 0 ? "off" : norm && ok < norm ? "low" : "good" };
    });
    const worked = cells.filter((c) => c.n).length;
    const ok = cells.reduce((s, c) => s + c.ok, 0);
    const city = (iv.find((a) => a.inter === inter) || {}).city || "—";
    return { inter, city, cells, worked, off: days.length - worked, low: cells.filter((c) => c.st === "low").length,
      ok, brak: cells.reduce((s, c) => s + c.brak, 0), avg: worked ? ok / worked : 0 };
  });
  return { norm, days, rows };
}

function pageDaily(root) {
  if (!S.result) return noResult(root);
  root.append(filterBar("daily"));
  const d = cfg().daily || (cfg().daily = { min: 0, team: [] });
  const data = dailyData(S.result.anketas.filter((a) => matches(a, "date")));
  const { norm, days, rows } = data;
  if (!days.length) return root.append(h("div", { class: "card" }, h("div", { class: "empty" }, "В анкетах нет дат.")));
  const day = F().date && days.includes(F().date) ? F().date : days[days.length - 1];
  const k = days.indexOf(day);
  const lead = document.body.classList.contains("is-lead");

  // норма — прямо здесь, одним полем
  const normInput = h("input", { type: "number", min: 0, max: 100, value: norm || "", placeholder: "—", class: "norm-input", disabled: !lead,
    onchange: (e) => {
      const v = Math.max(0, Math.round(Number(e.target.value) || 0));
      if (v === (Number(d.min) || 0)) return;
      d.min = v; saveConfigSoon(); setTimeout(() => go("daily"));   // перерисовка — после события, не внутри него
    } });
  root.append(h("div", { class: "norm-bar" },
    h("div", {}, h("b", {}, "Норма в день: "), normInput, h("span", {}, " засчитанных анкет на интервьюера")),
    h("div", { class: "muted small" }, norm ? "Засчитанная — без брака (с учётом решений руководителя). Технические записи не считаются."
      : "Норма не задана — впишите число (например 5, 6 или 7), и программа покажет, кто её не выполнил.")));

  // выбранный день
  const cs = rows.map((r) => ({ r, c: r.cells[k] }));
  const worked = cs.filter((x) => x.c.n);
  const off = cs.filter((x) => !x.c.n);
  const low = cs.filter((x) => x.c.st === "low");
  const good = cs.filter((x) => x.c.st === "good");
  root.append(h("div", { class: "day-pick" }, h("span", { class: "muted small" }, "День:"),
    days.map((x) => h("button", { class: `day-chip ${x === day ? "on" : ""}`, onclick: () => setFilter("date", x, "daily") }, dayLabel(x)))));
  root.append(h("div", { class: "stats" },
    tile(`Работали ${dayLabel(day)}`, `${fmt(worked.length)} из ${fmt(rows.length)}`, "интервьюеров прислали анкеты"),
    norm ? tile("Выполнили норму", fmt(good.length), `${norm}+ засчитанных анкет`, "green") : null,
    norm ? tile("Ниже нормы", fmt(low.length), `меньше ${norm} засчитанных`, "yellow") : null,
    tile("Не работали", fmt(off.length), "ни одной анкеты за день", off.length ? "red" : ""),
    tile("Засчитано", fmt(cs.reduce((s, x) => s + x.c.ok, 0)), `брак: ${fmt(cs.reduce((s, x) => s + x.c.brak, 0))}`)));
  const names = (list, extra) => list.length ? list.map((x) => h("span", { class: "name-chip", onclick: () => showInterviewer(x.r.inter) }, x.r.inter, extra ? h("b", {}, extra(x)) : null))
    : [h("span", { class: "muted" }, "нет")];
  root.append(h("div", { class: "grid-2" },
    card(`Не работали ${dayLabel(day)}`, "Интервьюеры проекта, от которых за этот день не пришло ни одной анкеты.", h("div", { class: "names" }, names(off))),
    card(`Ниже нормы ${dayLabel(day)}`, norm ? `Засчитано меньше ${norm} анкет. В скобках — засчитано / брак.` : "Задайте норму выше.",
      h("div", { class: "names" }, norm ? names(low, (x) => ` ${x.c.ok}${x.c.brak ? ` / ✕${x.c.brak}` : ""}`) : [h("span", { class: "muted" }, "—")]))));

  // матрица: интервьюер × день
  const head = h("tr", {}, h("th", { class: "sticky" }, "Интервьюер"), h("th", {}, "Город"),
    days.map((x) => h("th", { class: `num dcol ${x === day ? "on" : ""}`, onclick: () => setFilter("date", x, "daily"), title: "Выбрать день" }, dayLabel(x))),
    h("th", { class: "num" }, "Дней"), h("th", { class: "num" }, "Не работал"), norm ? h("th", { class: "num" }, "Ниже нормы") : null,
    h("th", { class: "num" }, "Засчитано"), h("th", { class: "num" }, "Брак"), h("th", { class: "num" }, "В день"));
  const body = h("tbody", {}, rows.map((r) => h("tr", {},
    h("td", { class: "sticky" }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); showInterviewer(r.inter); } }, r.inter)),
    h("td", { class: "muted" }, r.city),
    r.cells.map((c) => {
      const cell = h("td", { class: `num dcell ${c.st} ${c.day === day ? "on" : ""}`, onclick: c.n ? () => showList(`${r.inter} · ${dayLabel(c.day)}`, c.list) : null },
        c.n ? String(c.ok) : "—", c.brak ? h("sup", {}, `✕${c.brak}`) : null);
      hoverable(cell, () => [h("div", { class: "tip-h" }, `${r.inter} · ${dayLabel(c.day)}`),
        c.n ? tipVal(fmt(c.ok), "засчитано") : h("div", {}, "не работал"), c.brak ? tipVal(fmt(c.brak), "брак", "c-brak") : null,
        norm && c.n ? h("div", { class: "muted" }, c.ok >= norm ? "норма выполнена" : `до нормы не хватает ${norm - c.ok}`) : null]);
      return cell;
    }),
    h("td", { class: "num" }, r.worked), h("td", { class: `num ${r.off ? "t-bad" : ""}` }, r.off || "—"),
    norm ? h("td", { class: `num ${r.low ? "t-warn" : ""}` }, r.low || "—") : null,
    h("td", { class: "num" }, fmt(r.ok)), h("td", { class: "num" }, r.brak || "—"), h("td", { class: "num" }, fmt(r.avg, 1)))));
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", {}, h("h2", {}, "Интервьюеры по дням"),
      h("p", { class: "hint" }, "В клетке — засчитанные анкеты за день, маленькая цифра ✕ — брак. Зелёная — норма выполнена, жёлтая — ниже нормы, красная — не работал. Нажмите на клетку — анкеты за этот день."))),
    legend([["dl-good", "норма выполнена"], ["dl-low", "ниже нормы"], ["dl-off", "не работал"]]),
    h("div", { class: "table-wrap daily-wrap" }, h("table", { class: "daily" }, h("thead", {}, head), body))));

  // команда: чтобы видеть и тех, кто ни разу ничего не прислал
  if (lead) {
    const ta = h("textarea", { rows: 3, placeholder: "Inter 01, Inter 02, Inter 03…", value: (d.team || []).join(", ") });
    root.append(h("details", { class: "card fold" }, h("summary", {}, "Список команды (необязательно)"),
      h("p", { class: "hint" }, "Коды интервьюеров через запятую. Нужно, чтобы видеть и тех, кто за весь период не прислал ни одной анкеты — иначе программа знает только тех, кто что-то прислал."),
      ta, h("div", { class: "row", style: "margin-top:10px" }, h("button", { class: "btn", onclick: () => {
        d.team = ta.value.split(/[,;\n]/).map((x) => x.trim()).filter(Boolean); saveConfigSoon(); go("daily");
      } }, "Сохранить список"))));
  }
}

// ── Сверка: как получились цифры ───────────────────────────────────────────
function reconciliation() {
  const s = S.result.summary;
  const c = counts(S.result.anketas);
  const ti = s.technical_info;
  const parts = [
    ["строк в таблице", s.source_rows],
    s.dropped ? ["пропущено (нет города или интервьюера)", -s.dropped] : null,
    c.tech ? ["технические записи (видео/фото)", -c.tech] : null,
  ].filter(Boolean);
  const ok = c.brak + c.warn + c.ok === c.iv && s.source_rows - s.dropped - c.tech === c.iv;
  return h("div", { class: `recon ${ok ? "" : "bad"}` },
    h("b", {}, ok ? "✓ Сверка: " : "⚠ Сверка не сходится: "),
    parts.map(([t, n], i) => h("span", {}, i ? (n < 0 ? " − " : " + ") : "", h("b", {}, fmt(Math.abs(n))), ` ${t}`)),
    " = ", h("b", {}, fmt(c.iv)), " анкет = ",
    h("span", { class: "t-brak" }, fmt(c.brak)), " брак + ", h("span", { class: "t-warnx" }, fmt(c.warn)), " проверить + ",
    h("span", { class: "t-okx" }, fmt(c.ok)), " норма.",
    ti ? h("span", { class: "muted" }, ` Технические записи ${ti.auto ? "найдены автоматически" : "заданы"} по колонке «${ti.col}».`) : null);
}
