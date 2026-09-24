/**
 * AnketaQC — сервер доступа на Google Apps Script.
 *
 * Живёт внутри одной Google-таблицы («реестр»), которой владеет только
 * администратор. Администратор создаёт логины и указывает команду каждого
 * сотрудника. Команды сами подключают свои Google-таблицы с анкетами
 * (источники) к своим проектам — другие команды их не видят. Таблицы
 * остаются закрытыми: команда даёт доступ «Читатель» аккаунту сервера, и
 * скрипт читает анкеты от его имени.
 *
 * Установка — см. README («Сервер доступа»): вставить этот код в
 * Расширения → Apps Script, один раз запустить setup(), развернуть как
 * веб-приложение («Выполнять от: меня», «Доступ: все»).
 */

var SHEET_USERS = 'Пользователи';
var SHEET_SOURCES = 'Источники';
var SHEET_LOG = 'Журнал';
var USERS_HEADER = ['login', 'name', 'team', 'role', 'active', 'salt', 'hash', 'created', 'last_login'];
var SOURCES_HEADER = ['id', 'team', 'project', 'name', 'url', 'sheet', 'added_by', 'created'];
var LOG_HEADER = ['time', 'login', 'action', 'detail'];
var TOKEN_HOURS = 12;
var HASH_ROUNDS = 500;
var MAX_FAILS = 8;          // неудачных входов подряд до паузы
var LOCK_SECONDS = 900;     // пауза после MAX_FAILS, сек

// ── HTTP ───────────────────────────────────────────────────────────────────
function doGet() {
  return out_({ ok: true, service: 'AnketaQC' });
}

function doPost(e) {
  var req;
  try {
    req = JSON.parse(e.postData.contents);
  } catch (err) {
    return out_({ error: 'Неверный запрос' });
  }
  try {
    return out_(handle_(req));
  } catch (err) {
    return out_({ error: String((err && err.message) || err) });
  }
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function handle_(req) {
  var action = req.action;
  if (action === 'ping') return { ok: true };
  if (action === 'login') return login_(req.login, req.password);

  var me = auth_(req.token);
  switch (action) {
    case 'me': return { user: publicUser_(me), server_email: serverEmail_() };
    case 'sources': return { sources: userSources_(me) };
    case 'add_source': return withLock_(function () { return addSource_(me, req); });
    case 'delete_source': return withLock_(function () { return deleteSource_(me, req.id); });
    case 'fetch': return fetchSource_(me, req.source_id);
    case 'change_password': return changePassword_(me, req.old_password, req.new_password);
  }
  if (me.role !== 'admin') throw new Error('Нужны права администратора');
  switch (action) {
    case 'list_users': return { users: readRows_(SHEET_USERS, USERS_HEADER).map(publicUser_) };
    case 'create_user': return withLock_(function () { return createUser_(me, req); });
    case 'update_user': return withLock_(function () { return updateUser_(me, req); });
    case 'reset_password': return withLock_(function () { return resetPassword_(me, req.login); });
    case 'delete_user': return withLock_(function () { return deleteUser_(me, req.login); });
    case 'log': return { log: readLog_(req.limit || 100) };
  }
  throw new Error('Неизвестное действие: ' + action);
}

// ── Вход и токены ──────────────────────────────────────────────────────────
function login_(login, password) {
  login = normLogin_(login);
  if (!login || !password) throw new Error('Введите логин и пароль');
  var cache = CacheService.getScriptCache();
  var failKey = 'fail:' + login;
  var fails = Number(cache.get(failKey) || 0);
  if (fails >= MAX_FAILS) throw new Error('Слишком много неудачных попыток. Подождите 15 минут.');

  var user = findUser_(login);
  if (!user || hashPassword_(String(password), user.salt) !== user.hash) {
    cache.put(failKey, String(fails + 1), LOCK_SECONDS);
    log_(login, 'login_failed', '');
    throw new Error('Неверный логин или пароль');
  }
  if (!isActive_(user)) {
    log_(login, 'login_blocked', '');
    throw new Error('Доступ закрыт администратором');
  }
  cache.remove(failKey);
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'last_login', now_());
  log_(login, 'login', '');
  return { token: makeToken_(login), user: publicUser_(user), sources: userSources_(user), server_email: serverEmail_() };
}

function makeToken_(login) {
  var exp = Date.now() + TOKEN_HOURS * 3600 * 1000;
  var payload = Utilities.base64EncodeWebSafe(JSON.stringify({ l: login, e: exp }));
  return payload + '.' + sign_(payload);
}

/** Проверяет токен и КАЖДЫЙ раз перечитывает пользователя из реестра —
 *  блокировка или удаление действуют сразу, а не после истечения токена. */
function auth_(token) {
  if (!token || String(token).indexOf('.') < 0) throw new Error('AUTH: нужно войти');
  var parts = String(token).split('.');
  if (sign_(parts[0]) !== parts[1]) throw new Error('AUTH: сессия недействительна, войдите снова');
  var data = JSON.parse(Utilities.newBlob(Utilities.base64DecodeWebSafe(parts[0])).getDataAsString());
  if (Date.now() > data.e) throw new Error('AUTH: сессия истекла, войдите снова');
  var user = findUser_(data.l);
  if (!user) throw new Error('AUTH: пользователь удалён');
  if (!isActive_(user)) throw new Error('AUTH: доступ закрыт администратором');
  return user;
}

function sign_(text) {
  return hex_(Utilities.computeHmacSha256Signature(text, secret_()));
}

function secret_() {
  var props = PropertiesService.getScriptProperties();
  var s = props.getProperty('TOKEN_SECRET');
  if (!s) {
    s = Utilities.getUuid() + Utilities.getUuid();
    props.setProperty('TOKEN_SECRET', s);
  }
  return s;
}

function hashPassword_(password, salt) {
  var data = salt + '|' + password;
  var digest;
  for (var i = 0; i < HASH_ROUNDS; i++) {
    digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, data, Utilities.Charset.UTF_8);
    data = hex_(digest) + salt;
  }
  return hex_(digest);
}

function newPassword_() {
  // без похожих символов (0/O, 1/l/I), чтобы пароль легко продиктовать
  var alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid() + Utilities.getUuid());
  var out = '';
  for (var i = 0; i < 10; i++) out += alphabet.charAt(((bytes[i] % 256) + 256) % 256 % alphabet.length);
  return out;
}

function changePassword_(me, oldPassword, newPassword) {
  if (hashPassword_(String(oldPassword || ''), me.salt) !== me.hash) throw new Error('Текущий пароль неверный');
  if (!newPassword || String(newPassword).length < 8) throw new Error('Новый пароль — минимум 8 символов');
  return withLock_(function () {
    var salt = Utilities.getUuid();
    setCell_(SHEET_USERS, USERS_HEADER, me._row, 'salt', salt);
    setCell_(SHEET_USERS, USERS_HEADER, me._row, 'hash', hashPassword_(String(newPassword), salt));
    log_(me.login, 'change_password', '');
    return { ok: true };
  });
}

// ── Пользователи (админ) ───────────────────────────────────────────────────
function createUser_(me, req) {
  var login = normLogin_(req.login);
  if (!/^[a-z0-9._-]{3,32}$/.test(login)) throw new Error('Логин: 3–32 символа, латиница, цифры, точка, дефис');
  if (findUser_(login)) throw new Error('Такой логин уже есть');
  var password = newPassword_();
  var salt = Utilities.getUuid();
  var team = String(req.team || '').trim();
  if (req.role !== 'admin' && !team) throw new Error('Укажите команду сотрудника');
  writeRow_(SHEET_USERS, USERS_HEADER, {
    login: login, name: String(req.name || ''), team: team, role: req.role === 'admin' ? 'admin' : 'user',
    active: 'да', salt: salt, hash: hashPassword_(password, salt), created: now_(), last_login: '',
  });
  log_(me.login, 'create_user', login);
  return { login: login, password: password };
}

function updateUser_(me, req) {
  var user = findUser_(req.login);
  if (!user) throw new Error('Пользователь не найден');
  if (user.login === me.login && (req.active === false || req.role === 'user')) {
    throw new Error('Нельзя заблокировать себя или снять с себя права администратора');
  }
  if (req.name !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'name', String(req.name));
  if (req.role !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'role', req.role === 'admin' ? 'admin' : 'user');
  if (req.active !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'active', req.active ? 'да' : 'нет');
  if (req.team !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'team', String(req.team).trim());
  log_(me.login, 'update_user', user.login);
  return { user: publicUser_(findUser_(user.login)) };
}

function resetPassword_(me, login) {
  var user = findUser_(login);
  if (!user) throw new Error('Пользователь не найден');
  var password = newPassword_();
  var salt = Utilities.getUuid();
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'salt', salt);
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'hash', hashPassword_(password, salt));
  log_(me.login, 'reset_password', user.login);
  return { login: user.login, password: password };
}

function deleteUser_(me, login) {
  var user = findUser_(login);
  if (!user) throw new Error('Пользователь не найден');
  if (user.login === me.login) throw new Error('Нельзя удалить самого себя');
  sheet_(SHEET_USERS, USERS_HEADER).deleteRow(user._row);
  log_(me.login, 'delete_user', user.login);
  return { ok: true };
}

function publicUser_(u) {
  return {
    login: String(u.login), name: String(u.name || ''), team: String(u.team || ''), role: u.role, active: isActive_(u),
    created: String(u.created || ''), last_login: String(u.last_login || ''),
  };
}

function isActive_(u) {
  var v = String(u.active).toLowerCase();
  return v === 'да' || v === 'true' || v === '1' || v === 'yes';
}

function findUser_(login) {
  login = normLogin_(login);
  var rows = readRows_(SHEET_USERS, USERS_HEADER);
  for (var i = 0; i < rows.length; i++) if (normLogin_(rows[i].login) === login) return rows[i];
  return null;
}

// ── Источники анкет (подключает сама команда) ─────────────────────────────
/** Источник принадлежит команде: видят и меняют его только её сотрудники
 *  (администратор — все). */
function canUse_(user, src) {
  return user.role === 'admin' || (String(user.team || '') !== '' && String(src.team) === String(user.team));
}

function addSource_(me, req) {
  var url = String(req.url || '').trim();
  if (!/\/spreadsheets\/d\/[A-Za-z0-9_-]+/.test(url)) throw new Error('Нужна ссылка на Google-таблицу');
  var name = String(req.name || '').trim();
  if (!name) throw new Error('Введите название источника');
  var team = me.role === 'admin' && req.team ? String(req.team).trim() : String(me.team || '').trim();
  if (!team) throw new Error('Вам не назначена команда — обратитесь к администратору');
  var ss;
  try {
    ss = SpreadsheetApp.openByUrl(url);
  } catch (err) {
    throw new Error('Сервер не видит эту таблицу. В Google Sheets нажмите «Настройки доступа» и добавьте ' +
                    serverEmail_() + ' как «Читатель».');
  }
  var sheetName = String(req.sheet || '').trim();
  if (sheetName && !ss.getSheetByName(sheetName)) throw new Error('В таблице нет листа «' + sheetName + '»');
  var src = {
    id: 's' + Utilities.getUuid().slice(0, 8), team: team, project: String(req.project || '').trim(),
    name: name, url: url, sheet: sheetName, added_by: me.login, created: now_(),
  };
  writeRow_(SHEET_SOURCES, SOURCES_HEADER, src);
  log_(me.login, 'add_source', team + ' / ' + name);
  return { source: publicSource_(src) };
}

function deleteSource_(me, id) {
  var rows = readRows_(SHEET_SOURCES, SOURCES_HEADER);
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].id) === String(id)) {
      if (!canUse_(me, rows[i])) throw new Error('Это источник другой команды');
      sheet_(SHEET_SOURCES, SOURCES_HEADER).deleteRow(rows[i]._row);
      log_(me.login, 'delete_source', rows[i].team + ' / ' + rows[i].name);
      return { ok: true };
    }
  }
  throw new Error('Источник не найден');
}

function publicSource_(s) {
  return {
    id: String(s.id), team: String(s.team || ''), project: String(s.project || ''), name: String(s.name),
    url: String(s.url), sheet: String(s.sheet || ''), added_by: String(s.added_by || ''), created: String(s.created || ''),
  };
}

function userSources_(user) {
  return readRows_(SHEET_SOURCES, SOURCES_HEADER)
    .filter(function (s) { return canUse_(user, s); })
    .map(publicSource_);
}

/** Адрес Google-аккаунта, от имени которого работает сервер: ему команды
 *  дают доступ «Читатель» к своим таблицам. */
function serverEmail_() {
  try { return Session.getEffectiveUser().getEmail(); } catch (err) { return ''; }
}

function fetchSource_(me, sourceId) {
  var src = null;
  var all = readRows_(SHEET_SOURCES, SOURCES_HEADER);
  for (var i = 0; i < all.length; i++) if (String(all[i].id) === String(sourceId)) src = all[i];
  if (!src) throw new Error('Источник не найден');
  if (!canUse_(me, src)) throw new Error('Нет доступа к источнику «' + src.name + '»');
  var ss;
  try {
    ss = SpreadsheetApp.openByUrl(src.url);
  } catch (err) {
    throw new Error('Сервер потерял доступ к таблице «' + src.name + '». Снова добавьте ' + serverEmail_() +
                    ' как «Читатель».');
  }
  var sh = src.sheet ? ss.getSheetByName(src.sheet) : ss.getSheets()[0];
  if (!sh) throw new Error('В источнике «' + src.name + '» нет листа «' + src.sheet + '»');
  var tz = ss.getSpreadsheetTimeZone();
  var values = sh.getDataRange().getValues();
  // Даты — строкой в часовом поясе таблицы (местное время), а не в UTC:
  // иначе сдвинутся проверки времени суток.
  for (var r = 0; r < values.length; r++) {
    for (var c = 0; c < values[r].length; c++) {
      var v = values[r][c];
      if (Object.prototype.toString.call(v) === '[object Date]') values[r][c] = Utilities.formatDate(v, tz, "yyyy-MM-dd'T'HH:mm:ss");
    }
  }
  while (values.length > 1 && values[values.length - 1].join('') === '') values.pop();
  log_(me.login, 'fetch', src.name + ' (' + Math.max(values.length - 1, 0) + ' строк)');
  return { id: String(src.id), name: String(src.name), columns: values[0] || [], rows: values.slice(1) };
}

// ── Журнал ─────────────────────────────────────────────────────────────────
function log_(login, action, detail) {
  try {
    sheet_(SHEET_LOG, LOG_HEADER).appendRow([now_(), login, action, detail]);
  } catch (err) { /* журнал не должен ломать основной запрос */ }
}

function readLog_(limit) {
  var sh = sheet_(SHEET_LOG, LOG_HEADER);
  var last = sh.getLastRow();
  if (last < 2) return [];
  var n = Math.min(limit, last - 1);
  return sh.getRange(last - n + 1, 1, n, LOG_HEADER.length).getValues().reverse().map(function (r) {
    return { time: String(r[0]), login: String(r[1]), action: String(r[2]), detail: String(r[3]) };
  });
}

// ── Таблицы реестра ────────────────────────────────────────────────────────
/** Таблица-реестр. Если скрипт создан из таблицы (Расширения → Apps Script) —
 *  это она. Если проект создан отдельно — setup() сам создаёт таблицу
 *  «AnketaQC — сервер» в вашем Google Диске и запоминает её. */
function registry_() {
  var active = SpreadsheetApp.getActiveSpreadsheet();
  if (active) return active;
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('REGISTRY_ID');
  if (id) return SpreadsheetApp.openById(id);
  var book = SpreadsheetApp.create('AnketaQC — сервер');
  props.setProperty('REGISTRY_ID', book.getId());
  Logger.log('Создана таблица-реестр: ' + book.getUrl());
  return book;
}

function sheet_(name, header) {
  var book = registry_();
  var sh = book.getSheetByName(name);
  if (!sh) {
    sh = book.insertSheet(name);
    sh.appendRow(header);
    sh.setFrozenRows(1);
  }
  return sh;
}

function readRows_(name, header) {
  var values = sheet_(name, header).getDataRange().getValues();
  var head = values[0];
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    if (String(values[i][0]) === '') continue;
    var o = { _row: i + 1 };
    for (var j = 0; j < head.length; j++) o[head[j]] = values[i][j];
    rows.push(o);
  }
  return rows;
}

function writeRow_(name, header, obj) {
  sheet_(name, header).appendRow(header.map(function (k) { return obj[k] === undefined ? '' : obj[k]; }));
}

function setCell_(name, header, row, key, value) {
  sheet_(name, header).getRange(row, header.indexOf(key) + 1).setValue(value);
}

function withLock_(fn) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try { return fn(); } finally { lock.releaseLock(); }
}

function normLogin_(v) { return String(v || '').trim().toLowerCase(); }
function now_() { return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss'); }
function hex_(bytes) {
  return bytes.map(function (b) { return ('0' + ((b + 256) % 256).toString(16)).slice(-2); }).join('');
}

// ── Первичная настройка (запустить один раз из редактора) ──────────────────
function setup() {
  sheet_(SHEET_USERS, USERS_HEADER);
  sheet_(SHEET_SOURCES, SOURCES_HEADER);
  sheet_(SHEET_LOG, LOG_HEADER);
  secret_();
  var admins = readRows_(SHEET_USERS, USERS_HEADER).filter(function (u) { return u.role === 'admin'; });
  if (admins.length) {
    Logger.log('Администратор уже есть: ' + admins[0].login + '. Ничего не меняю.');
    return;
  }
  var password = newPassword_();
  var salt = Utilities.getUuid();
  writeRow_(SHEET_USERS, USERS_HEADER, {
    login: 'admin', name: 'Администратор', team: '', role: 'admin', active: 'да', salt: salt,
    hash: hashPassword_(password, salt), created: now_(), last_login: '',
  });
  Logger.log('Создан администратор. Логин: admin   Пароль: ' + password + '   — сохраните его.');
}

/** Забыли пароль администратора — запустите эту функцию из редактора:
 *  новый пароль появится в журнале выполнения. */
function resetAdminPassword() {
  var user = findUser_('admin');
  if (!user) {
    Logger.log('Пользователя admin нет — запустите setup().');
    return;
  }
  var password = newPassword_();
  var salt = Utilities.getUuid();
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'salt', salt);
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'hash', hashPassword_(password, salt));
  setCell_(SHEET_USERS, USERS_HEADER, user._row, 'active', 'да');
  CacheService.getScriptCache().remove('fail:admin');
  log_('admin', 'reset_password', 'из редактора Apps Script');
  Logger.log('Новый пароль администратора. Логин: admin   Пароль: ' + password);
}
