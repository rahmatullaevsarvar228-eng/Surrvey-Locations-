// Прогон server/Code.gs вне Google: имитация сервисов Apps Script в памяти.
// Запуск: node tests/gas_harness.js  (из папки qc_app). Код выхода 0 — всё прошло.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const crypto = require("crypto");
const assert = require("assert");

const signed = (buf) => Array.from(buf).map((b) => (b > 127 ? b - 256 : b));
const unsigned = (arr) => Buffer.from(arr.map((b) => (b + 256) % 256));

class Sheet {
  constructor(name, rows) { this.name = name; this.rows = rows || []; }
  getName() { return this.name; }
  appendRow(r) { if (this.readonly) throw new Error("нет прав на запись"); this.rows.push(r.slice()); }
  setFrozenRows() {}
  getLastRow() { return this.rows.length; }
  getLastColumn() { return Math.max(0, ...this.rows.map((r) => r.length)); }
  deleteRow(i) { this.rows.splice(i - 1, 1); }
  getDataRange() {
    const w = Math.max(0, ...this.rows.map((r) => r.length));
    return { getValues: () => this.rows.map((r) => Array.from({ length: w }, (_, j) => (r[j] === undefined ? "" : r[j]))) };
  }
  getRange(row, col, nr, nc) {
    if (this.readonly) throw new Error("нет прав на запись");
    if (typeof row === "string") return { setNumberFormat() {} };
    return {
      setValue: (v) => { while (this.rows.length < row) this.rows.push([]); this.rows[row - 1][col - 1] = v; },
      setValues: (vals) => { while (this.rows.length < row) this.rows.push([]); vals[0].forEach((v, j) => { this.rows[row - 1][col - 1 + j] = v; }); },
      getValues: () => this.rows.slice(row - 1, row - 1 + (nr || 1)).map((r) => r.slice(col - 1, col - 1 + (nc || 1))),
    };
  }
}
class Book {
  constructor(sheets) { this.sheets = sheets || []; }
  getSheetByName(n) { return this.sheets.find((s) => s.name === n) || null; }
  insertSheet(n) { if (this.readonly) throw new Error("нет прав на запись"); const s = new Sheet(n); this.sheets.push(s); return s; }
  getSheets() { return this.sheets; }
  getSpreadsheetTimeZone() { return "Asia/Tashkent"; }
}

// Веб-приложения по адресу (личные коннекторы руководителей): url → doPost
const WEB = {};

function makeEnv(standalone = false, file = "Code.gs", email = "server@example.com") {
  const registry = new Book();
  const created = [];
  const external = {};
  const props = {};
  const cache = {};
  const logs = [];
  const fmt = (d, tz, pattern) => {
    const t = new Date(d.getTime() + 5 * 3600 * 1000);   // Asia/Tashkent = UTC+5
    const p = (n) => String(n).padStart(2, "0");
    return pattern.replace("yyyy", t.getUTCFullYear()).replace("MM", p(t.getUTCMonth() + 1)).replace("dd", p(t.getUTCDate()))
      .replace("HH", p(t.getUTCHours())).replace("mm", p(t.getUTCMinutes())).replace("ss", p(t.getUTCSeconds())).replace(/'/g, "");
  };
  const ctx = {
    SpreadsheetApp: {
      getActiveSpreadsheet: () => (standalone ? null : registry),
      openById: (id) => { if (id !== "REG") throw new Error("нет"); return registry; },
      create: (name) => { created.push(name); return Object.assign(registry, { getId: () => "REG", getUrl: () => "https://docs.google.com/spreadsheets/d/REG" }); },
      openByUrl: (url) => { const id = (url.match(/\/d\/([^/]+)/) || [])[1]; if (!external[id]) throw new Error("нет доступа"); return external[id]; },
    },
    Utilities: {
      DigestAlgorithm: { SHA_256: "sha256" }, Charset: { UTF_8: "utf8" },
      computeDigest: (alg, s) => signed(crypto.createHash("sha256").update(String(s), "utf8").digest()),
      computeHmacSha256Signature: (v, k) => signed(crypto.createHmac("sha256", k).update(v, "utf8").digest()),
      base64EncodeWebSafe: (s) => Buffer.from(s, "utf8").toString("base64").replace(/\+/g, "-").replace(/\//g, "_"),
      base64DecodeWebSafe: (s) => signed(Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64")),
      newBlob: (bytes) => ({ getDataAsString: () => unsigned(bytes).toString("utf8") }),
      getUuid: () => crypto.randomUUID(),
      formatDate: fmt,
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => props[k] || null, setProperty: (k, v) => { props[k] = v; } }) },
    CacheService: { getScriptCache: () => ({ get: (k) => cache[k] || null, put: (k, v) => { cache[k] = v; }, remove: (k) => { delete cache[k]; } }) },
    LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
    ContentService: { MimeType: { JSON: "json" }, createTextOutput: (t) => ({ setMimeType: () => ({ text: t }) }) },
    Logger: { log: (m) => logs.push(m) },
    Session: { getScriptTimeZone: () => "Asia/Tashkent", getEffectiveUser: () => ({ getEmail: () => email }) },
    UrlFetchApp: {
      fetch: (url, opt) => {
        if (!WEB[url]) throw new Error("Address unavailable: " + url);
        // как Apps Script: JSON уходит строкой и приходит строкой
        const text = WEB[url](String(opt.payload));
        return { getContentText: () => text };
      },
    },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "server", file), "utf8"), ctx);
  const call = (body) => JSON.parse(ctx.doPost({ postData: { contents: JSON.stringify(body) } }).text);
  return { ctx, registry, external, logs, call, cache, created };
}

/** Личный коннектор (server/Connector.gs) в Google-аккаунте руководителя,
 *  развёрнутый по адресу url. Таблицы — те, что видит сам руководитель. */
function makeConnector(url, email) {
  const env = makeEnv(true, "Connector.gs", email);
  env.ctx.setup();
  env.key = env.logs.join("\n").match(/Ключ коннектора: (\S+)/)[1];
  WEB[url] = (body) => env.ctx.doPost({ postData: { contents: body } }).text;
  return env;
}

module.exports = { makeEnv, makeConnector, Book, Sheet, WEB };
if (require.main !== module) return;

// ── Сценарий ───────────────────────────────────────────────────────────────
const env = makeEnv();
const { call } = env;

env.ctx.setup();
const adminPass = env.logs.join("\n").match(/Пароль: (\S+)/)[1];
env.ctx.setup();   // повторный запуск ничего не ломает и второго админа не создаёт
assert.strictEqual(env.registry.getSheetByName("Пользователи").rows.length, 2);

assert.match(call({ action: "login", login: "admin", password: "wrong" }).error, /Неверный/);
const adm = call({ action: "login", login: "ADMIN ", password: adminPass });
assert.ok(adm.token, JSON.stringify(adm));
assert.strictEqual(adm.user.role, "admin");
const T = adm.token;

// две команды, у каждой свои таблицы
env.external["AAA"] = new Book([new Sheet("data", [
  ["start", "deviceid", "Город"],
  [new Date(Date.UTC(2025, 8, 15, 21, 30)), "d1", "Ташкент"],   // 02:30 по Ташкенту
  ["", "", ""],
])]);
env.external["BBB"] = new Book([new Sheet("Лист1", [["start", "deviceid"], ["2025-09-16T10:00:00", "d2"]])]);

assert.match(call({ action: "create_user", token: T, login: "Ы!", team: "A" }).error, /Логин/);
assert.match(call({ action: "create_user", token: T, login: "noteam" }).error, /команду/);
const created = call({ action: "create_user", token: T, login: "ali", name: "Али", team: "Uzum" });
assert.strictEqual(created.password.length, 10);
assert.match(call({ action: "create_user", token: T, login: "ali", team: "Uzum" }).error, /уже есть/);
const other = call({ action: "create_user", token: T, login: "bek", team: "Kapital" });

const u = call({ action: "login", login: "ali", password: created.password });
assert.ok(u.token);
assert.strictEqual(u.server_email, "server@example.com");
assert.deepStrictEqual(u.sources, []);

// команда сама подключает таблицу; сервер без доступа подсказывает, кому дать «Читатель»
assert.match(call({ action: "add_source", token: u.token, name: "X", url: "https://docs.google.com/spreadsheets/d/ZZZ/edit" }).error, /server@example.com/);
assert.match(call({ action: "add_source", token: u.token, name: "X", url: "https://docs.google.com/spreadsheets/d/AAA/edit", sheet: "нет" }).error, /нет листа/);
const s1 = call({ action: "add_source", token: u.token, name: "Ташкент", project: "Uzum сентябрь", url: "https://docs.google.com/spreadsheets/d/AAA/edit", sheet: "data" }).source;
assert.strictEqual(s1.team, "Uzum");
assert.strictEqual(s1.project, "Uzum сентябрь");

const b = call({ action: "login", login: "bek", password: other.password });
const s2 = call({ action: "add_source", token: b.token, name: "Самарканд", url: "https://docs.google.com/spreadsheets/d/BBB/edit" }).source;

// каждая команда видит только своё
assert.deepStrictEqual(call({ action: "sources", token: u.token }).sources.map((x) => x.name), ["Ташкент"]);
assert.deepStrictEqual(call({ action: "sources", token: b.token }).sources.map((x) => x.name), ["Самарканд"]);
assert.strictEqual(call({ action: "sources", token: T }).sources.length, 2, "админ видит все");

env.external["AAA"].sheets.push(new Sheet("Мониторинг", [["ID", "Брак"], ["5001", 1]]));
const f = call({ action: "fetch", token: u.token, source_id: s1.id });
assert.deepStrictEqual(f.columns, ["start", "deviceid", "Город"]);
assert.deepStrictEqual(f.sheets, ["data", "Мониторинг"], "список листов для выбора в программе");
assert.strictEqual(f.sheet, "data");
const f2 = call({ action: "fetch", token: u.token, source_id: s1.id, sheet: "Мониторинг" });
assert.deepStrictEqual(f2.columns, ["ID", "Брак"], "другой лист по выбору в программе");
assert.match(call({ action: "fetch", token: u.token, source_id: s1.id, sheet: "нет" }).error, /нет листа «нет»/);
assert.strictEqual(f.rows.length, 1, "пустые хвостовые строки отброшены");
assert.strictEqual(f.rows[0][0], "2025-09-16T02:30:00", "дата в местном времени таблицы");
assert.match(call({ action: "fetch", token: u.token, source_id: s2.id }).error, /Нет доступа/);
assert.match(call({ action: "delete_source", token: u.token, id: s2.id }).error, /другой команды/);
assert.match(call({ action: "list_users", token: u.token }).error, /администратора/);

// таблицу закрыли от сервера — понятная ошибка
delete env.external["AAA"];
assert.match(call({ action: "fetch", token: u.token, source_id: s1.id }).error, /потерял доступ/);

// блокировка действует сразу, даже с ещё живым токеном
call({ action: "update_user", token: T, login: "ali", active: false });
assert.match(call({ action: "sources", token: u.token }).error, /^AUTH: доступ закрыт/);
assert.match(call({ action: "login", login: "ali", password: created.password }).error, /закрыт/);
call({ action: "update_user", token: T, login: "ali", active: true });
// перевод в другую команду меняет видимые источники
call({ action: "update_user", token: T, login: "ali", team: "Kapital" });
assert.deepStrictEqual(call({ action: "sources", token: u.token }).sources.map((x) => x.name), ["Самарканд"]);

// сброс пароля: старый больше не подходит
const reset = call({ action: "reset_password", token: T, login: "ali" });
assert.match(call({ action: "login", login: "ali", password: created.password }).error, /Неверный/);
assert.ok(call({ action: "login", login: "ali", password: reset.password }).token);

// смена пароля самим пользователем
const u2 = call({ action: "login", login: "ali", password: reset.password });
assert.match(call({ action: "change_password", token: u2.token, old_password: "x", new_password: "12345678" }).error, /неверный/);
assert.ok(call({ action: "change_password", token: u2.token, old_password: reset.password, new_password: "новый-пароль-1" }).ok);
assert.ok(call({ action: "login", login: "ali", password: "новый-пароль-1" }).token);

// подделанный токен
const forged = Buffer.from(JSON.stringify({ l: "admin", e: Date.now() + 1e9 })).toString("base64") + "." + "00";
assert.match(call({ action: "list_users", token: forged }).error, /^AUTH/);
assert.match(call({ action: "list_users" }).error, /^AUTH/);

// нельзя заблокировать или удалить себя
assert.match(call({ action: "update_user", token: T, login: "admin", active: false }).error, /себя/);
assert.match(call({ action: "delete_user", token: T, login: "admin" }).error, /себя/);

// перебор паролей: пауза после 8 ошибок
for (let i = 0; i < 8; i++) call({ action: "login", login: "ali", password: "bad" });
assert.match(call({ action: "login", login: "ali", password: "новый-пароль-1" }).error, /Слишком много/);

// удаление
assert.ok(call({ action: "delete_user", token: T, login: "ali" }).ok);
assert.match(call({ action: "fetch", token: u.token, source_id: s1.id }).error, /удалён/);
assert.ok(call({ action: "delete_source", token: b.token, id: s2.id }).ok);
assert.strictEqual(call({ action: "sources", token: T }).sources.length, 1);
assert.ok(call({ action: "log", token: T, limit: 5 }).log.length === 5);
assert.match(call({ action: "nope", token: T }).error, /Неизвестное/);

// проект Apps Script, созданный отдельно от таблицы: реестр создаётся один раз
const solo = makeEnv(true);
solo.ctx.setup();
solo.ctx.setup();
assert.deepStrictEqual(solo.created, ["AnketaQC — сервер"]);
const soloPass = solo.logs.join("\n").match(/Пароль: (\S+)/)[1];
assert.ok(solo.call({ action: "login", login: "admin", password: soloPass }).token);

// забытый пароль администратора: сброс из редактора
const r = makeEnv();
r.ctx.setup();
const oldPass = r.logs.join("\n").match(/Пароль: (\S+)/)[1];
r.ctx.resetAdminPassword();
const newPass = r.logs.join("\n").match(/Новый пароль администратора. Логин: admin   Пароль: (\S+)/)[1];
assert.notStrictEqual(oldPass, newPass);
assert.match(r.call({ action: "login", login: "admin", password: oldPass }).error, /Неверный/);
assert.ok(r.call({ action: "login", login: "admin", password: newPass }).token);

// решения ОТК: только руководитель, запись в лист «Решения ОТК» таблицы источника
{
  const e = makeEnv();
  e.ctx.setup();
  const pw = e.logs.join("\n").match(/Пароль: (\S+)/)[1];
  const A = e.call({ action: "login", login: "admin", password: pw }).token;
  e.external["DDD"] = new Book([new Sheet("data", [["_id", "x"], [1, "a"], [2, "b"]])]);
  const lead = e.call({ action: "create_user", token: A, login: "boss", team: "T", role: "lead" });
  const usr = e.call({ action: "create_user", token: A, login: "sup", team: "T" });
  const L = e.call({ action: "login", login: "boss", password: lead.password }).token;
  const U = e.call({ action: "login", login: "sup", password: usr.password }).token;
  const src = e.call({ action: "add_source", token: L, name: "Поток", url: "https://docs.google.com/spreadsheets/d/DDD/edit" }).source;
  assert.match(e.call({ action: "set_decisions", token: U, source_id: src.id, items: [{ id: "1", decision: "Брак" }] }).error, /руководитель/);
  assert.match(e.call({ action: "set_decisions", token: L, source_id: src.id, items: [{ id: "1", decision: "Плохо" }] }).error, /Неизвестное/);
  // нет прав редактора — понятная подсказка
  e.external["DDD"].readonly = true;
  assert.match(e.call({ action: "set_decisions", token: L, source_id: src.id, items: [{ id: "1", decision: "Брак" }] }).error, /Редактор/);
  e.external["DDD"].readonly = false;
  let r = e.call({ action: "set_decisions", token: L, source_id: src.id, items: [
    { id: "1", decision: "Брак", reason: "длилась 3 мин", comment: "не дозвонились" }, { id: "2", decision: "На перезвон" }] });
  assert.strictEqual(r.decisions.length, 2);
  r = e.call({ action: "set_decisions", token: L, source_id: src.id, items: [{ id: "2", decision: "Принять" }, { id: "1", decision: "" }] });
  assert.deepStrictEqual(r.decisions.map((d) => [d.id, d.decision, d.by]), [["2", "Принять", "boss"]]);
  const f = e.call({ action: "fetch", token: U, source_id: src.id });
  assert.strictEqual(f.rows.length, 2, "лист решений не смешивается с анкетами");
  assert.deepStrictEqual(f.decisions.map((d) => d.decision), ["Принять"]);
  assert.strictEqual(e.external["DDD"].getSheets()[0].name, "data");
}

// личный коннектор: руководитель подключает свои таблицы через свою почту,
// аккаунту сервера доступ к ним не нужен
{
  const e = makeEnv();
  e.ctx.setup();
  const pw = e.logs.join("\n").match(/Пароль: (\S+)/)[1];
  const A = e.call({ action: "login", login: "admin", password: pw }).token;
  const lead = e.call({ action: "create_user", token: A, login: "dilnoza", team: "Bank", role: "lead" });
  const sup = e.call({ action: "create_user", token: A, login: "sup2", team: "Bank" });
  const alien = e.call({ action: "create_user", token: A, login: "alien", team: "Other", role: "lead" });
  const L = e.call({ action: "login", login: "dilnoza", password: lead.password });
  const U = e.call({ action: "login", login: "sup2", password: sup.password }).token;
  const X = e.call({ action: "login", login: "alien", password: alien.password }).token;
  assert.strictEqual(L.bridge, null);

  const url = "https://script.google.com/macros/s/LEADBRIDGE/exec";
  const con = makeConnector(url, "dilnoza@gmail.com");
  con.external["KOBO"] = new Book([new Sheet("Kobo", [["_id", "start"], [7, new Date(Date.UTC(2025, 9, 1, 5, 0))]]),
    new Sheet("ТЗ", [["_id"], [8]])]);
  assert.ok(!e.external["KOBO"], "у сервера доступа к таблице нет");

  // без коннектора — подсказка про оба способа
  assert.match(e.call({ action: "add_source", token: L.token, name: "Bank", url: "https://docs.google.com/spreadsheets/d/KOBO/edit" }).error,
    /свой Google-аккаунт/);
  assert.match(e.call({ action: "add_source", token: L.token, name: "Bank", via: "bridge", url: "https://docs.google.com/spreadsheets/d/KOBO/edit" }).error,
    /Сначала подключите/);
  assert.match(e.call({ action: "set_bridge", token: L.token, url: "https://example.com/x", key: con.key }).error, /script\.google\.com/);
  assert.match(e.call({ action: "set_bridge", token: L.token, url, key: "wrong" }).error, /Неверный ключ/);
  assert.match(e.call({ action: "set_bridge", token: L.token, url: "https://script.google.com/macros/s/NOPE/exec", key: "k" }).error, /Нет связи/);
  const sb = e.call({ action: "set_bridge", token: L.token, url, key: con.key });
  assert.strictEqual(sb.bridge.email, "dilnoza@gmail.com");
  assert.ok(!("key" in sb.bridge), "ключ программе не отдаётся");
  assert.strictEqual(e.call({ action: "me", token: L.token }).bridge.email, "dilnoza@gmail.com");

  assert.match(e.call({ action: "add_source", token: L.token, name: "Bank", via: "bridge", url: "https://docs.google.com/spreadsheets/d/NOPE/edit" }).error,
    /dilnoza@gmail\.com не видит/);
  assert.match(e.call({ action: "add_source", token: L.token, name: "Bank", via: "bridge", sheet: "нет", url: "https://docs.google.com/spreadsheets/d/KOBO/edit" }).error,
    /нет листа/);
  const src = e.call({ action: "add_source", token: L.token, name: "Bank", via: "bridge", url: "https://docs.google.com/spreadsheets/d/KOBO/edit" }).source;
  assert.strictEqual(src.via, "dilnoza");

  // читает и сотрудник команды — через коннектор руководителя
  const f = e.call({ action: "fetch", token: U, source_id: src.id });
  assert.deepStrictEqual(f.columns, ["_id", "start"]);
  assert.deepStrictEqual(f.sheets, ["Kobo", "ТЗ"]);
  assert.strictEqual(f.rows[0][1], "2025-10-01T10:00:00", "дата в местном времени и через коннектор");
  assert.deepStrictEqual(e.call({ action: "fetch", token: U, source_id: src.id, sheet: "ТЗ" }).columns, ["_id"]);
  assert.match(e.call({ action: "fetch", token: X, source_id: src.id }).error, /Нет доступа/, "другая команда не видит");

  // решения пишутся в таблицу руководителя от его имени
  const d = e.call({ action: "set_decisions", token: L.token, source_id: src.id, items: [{ id: "7", decision: "Брак", reason: "3 мин" }] });
  assert.deepStrictEqual(d.decisions.map((x) => [x.id, x.decision, x.by]), [["7", "Брак", "dilnoza"]]);
  assert.strictEqual(con.external["KOBO"].getSheetByName("Решения ОТК").rows.length, 2);
  assert.match(e.call({ action: "set_decisions", token: U, source_id: src.id, items: [{ id: "7", decision: "Брак" }] }).error, /руководитель/);
  con.external["KOBO"].readonly = true;
  con.external["KOBO"].getSheetByName("Решения ОТК").readonly = true;
  assert.match(e.call({ action: "set_decisions", token: L.token, source_id: src.id, items: [{ id: "8", decision: "Брак" }] }).error,
    /dilnoza@gmail\.com не может записать/);

  // новый ключ: старый перестаёт работать, программа просит обновить
  con.ctx.newKey();
  assert.match(e.call({ action: "fetch", token: U, source_id: src.id }).error, /Неверный ключ/);
  const key2 = con.logs.join("\n").match(/Новый ключ коннектора: (\S+)/)[1];
  e.call({ action: "set_bridge", token: L.token, url, key: key2 });
  const f3 = e.call({ action: "fetch", token: U, source_id: src.id });
  assert.strictEqual(f3.rows && f3.rows.length, 1, JSON.stringify(f3));
  assert.strictEqual(e.registry.getSheetByName("Коннекторы").rows.length, 2, "одна строка на руководителя");

  // отключили коннектор — понятная ошибка
  assert.strictEqual(e.call({ action: "set_bridge", token: L.token, url: "" }).bridge, null);
  assert.match(e.call({ action: "fetch", token: U, source_id: src.id }).error, /коннектор отключён/);

  // коннектор без ключа ничего не отдаёт
  assert.match(JSON.parse(WEB[url](JSON.stringify({ action: "read", url: "https://docs.google.com/spreadsheets/d/KOBO/edit" }))).error, /Неверный ключ/);
  assert.strictEqual(JSON.parse(con.ctx.doGet().text).service, "AnketaQC-connector");

  // общие функции в Code.gs и Connector.gs одинаковы
  for (const name of ["readBook_", "readDecisions_", "writeDecisions_", "now_"]) {
    assert.strictEqual(con.ctx[name].toString(), e.ctx[name].toString(), name + " разошлись между Code.gs и Connector.gs");
  }
}

// реестр от старой версии: колонка via дописывается, старые источники работают
{
  const e = makeEnv();
  e.registry.sheets.push(new Sheet("Источники", [["id", "team", "project", "name", "url", "sheet", "added_by", "created"],
    ["s1", "T", "", "Старая", "https://docs.google.com/spreadsheets/d/OLD/edit", "", "admin", ""]]));
  e.external["OLD"] = new Book([new Sheet("data", [["a"], [1]])]);
  e.ctx.setup();
  const pw = e.logs.join("\n").match(/Пароль: (\S+)/)[1];
  const A = e.call({ action: "login", login: "admin", password: pw }).token;
  assert.strictEqual(e.registry.getSheetByName("Источники").rows[0][8], "via");
  assert.strictEqual(e.call({ action: "fetch", token: A, source_id: "s1" }).rows.length, 1);
  const s2 = e.call({ action: "add_source", token: A, team: "T", name: "Новая", url: "https://docs.google.com/spreadsheets/d/OLD/edit" }).source;
  assert.strictEqual(s2.via, "");
  assert.strictEqual(e.call({ action: "sources", token: A }).sources.length, 2);
}

console.log("gas_harness: OK");
