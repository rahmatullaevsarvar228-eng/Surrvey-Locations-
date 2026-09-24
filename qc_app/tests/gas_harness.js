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
  appendRow(r) { if (this.readonly) throw new Error("нет прав на запись"); this.rows.push(r.slice()); }
  setFrozenRows() {}
  getLastRow() { return this.rows.length; }
  deleteRow(i) { this.rows.splice(i - 1, 1); }
  getDataRange() {
    const w = Math.max(0, ...this.rows.map((r) => r.length));
    return { getValues: () => this.rows.map((r) => Array.from({ length: w }, (_, j) => (r[j] === undefined ? "" : r[j]))) };
  }
  getRange(row, col, nr, nc) {
    if (this.readonly) throw new Error("нет прав на запись");
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

function makeEnv(standalone = false) {
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
    Session: { getScriptTimeZone: () => "Asia/Tashkent", getEffectiveUser: () => ({ getEmail: () => "server@example.com" }) },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "server", "Code.gs"), "utf8"), ctx);
  const call = (body) => JSON.parse(ctx.doPost({ postData: { contents: JSON.stringify(body) } }).text);
  return { ctx, registry, external, logs, call, cache, created };
}

module.exports = { makeEnv, Book, Sheet };
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

const f = call({ action: "fetch", token: u.token, source_id: s1.id });
assert.deepStrictEqual(f.columns, ["start", "deviceid", "Город"]);
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

console.log("gas_harness: OK");
