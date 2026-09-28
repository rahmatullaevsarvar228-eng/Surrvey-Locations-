/**
 * AnketaQC — сервер доступа на Google Apps Script.
 *
 * Живёт внутри одной Google-таблицы («реестр»), которой владеет только
 * администратор. Администратор создаёт логины и указывает команду каждого
 * сотрудника. Команды сами подключают свои Google-таблицы с анкетами
 * (источники) к своим проектам — другие команды их не видят. Таблицы
 * остаются закрытыми. Подключить таблицу можно двумя способами:
 *  • через свой Google-аккаунт: руководитель один раз ставит себе личный
 *    коннектор (server/Connector.gs), и сервер читает таблицы через него —
 *    ничего никому расшаривать не нужно;
 *  • через аккаунт сервера: команда даёт доступ «Читатель» адресу сервера
 *    (или в таблице стоит «Все, у кого есть ссылка»).
 *
 * Установка — см. README («Сервер доступа»): вставить этот код в
 * Расширения → Apps Script, один раз запустить setup(), развернуть как
 * веб-приложение («Выполнять от: меня», «Доступ: все»).
 */

var SHEET_USERS = 'Пользователи';
var SHEET_SOURCES = 'Источники';
var SHEET_LOG = 'Журнал';
var USERS_HEADER = ['login', 'name', 'team', 'role', 'active', 'salt', 'hash', 'created', 'last_login'];
// via — чей личный коннектор читает таблицу (логин); пусто — аккаунт сервера
var SOURCES_HEADER = ['id', 'team', 'project', 'name', 'url', 'sheet', 'added_by', 'created', 'via'];
var SHEET_BRIDGES = 'Коннекторы';
var BRIDGES_HEADER = ['login', 'url', 'key', 'email', 'created'];
var LOG_HEADER = ['time', 'login', 'action', 'detail'];
var DECISIONS_SHEET = 'Решения ОТК';
var DECISIONS_HEADER = ['ID анкеты', 'Решение', 'Причина (система)', 'Комментарий', 'Кто решил', 'Когда'];
var DECISION_VALUES = ['Брак', 'Принять', 'На перезвон'];
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
    case 'me': return { user: publicUser_(me), server_email: serverEmail_(), bridge: publicBridge_(me) };
    case 'set_bridge': return withLock_(function () { return setBridge_(me, req); });
    case 'sources': return { sources: userSources_(me) };
    case 'add_source': return withLock_(function () { return addSource_(me, req); });
    case 'delete_source': return withLock_(function () { return deleteSource_(me, req.id); });
    case 'fetch': return fetchSource_(me, req.source_id, req.sheet);
    case 'set_decisions': return withLock_(function () { return setDecisions_(me, req); });
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
  return { token: makeToken_(login), user: publicUser_(user), sources: userSources_(user), server_email: serverEmail_(),
           bridge: publicBridge_(user) };
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
    login: login, name: String(req.name || ''), team: team, role: normRole_(req.role),
    active: 'да', salt: salt, hash: hashPassword_(password, salt), created: now_(), last_login: '',
  });
  log_(me.login, 'create_user', login);
  return { login: login, password: password };
}

function updateUser_(me, req) {
  var user = findUser_(req.login);
  if (!user) throw new Error('Пользователь не найден');
  if (user.login === me.login && (req.active === false || (req.role !== undefined && req.role !== 'admin'))) {
    throw new Error('Нельзя заблокировать себя или снять с себя права администратора');
  }
  if (req.name !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'name', String(req.name));
  if (req.role !== undefined) setCell_(SHEET_USERS, USERS_HEADER, user._row, 'role', normRole_(req.role));
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
  var sheetName = String(req.sheet || '').trim();
  var via = '';
  if (req.via === 'bridge') {
    var b = findBridge_(me.login);
    if (!b) throw new Error('Сначала подключите свой Google-аккаунт (личный коннектор)');
    callBridge_(b, { action: 'check', url: url, sheet: sheetName, label: name });
    via = me.login;
  } else {
    var ss;
    try {
      ss = SpreadsheetApp.openByUrl(url);
    } catch (err) {
      throw new Error('Сервер не видит эту таблицу. Подключите её через свой Google-аккаунт или в Google Sheets ' +
                      'нажмите «Настройки доступа» и добавьте ' + serverEmail_() + ' как «Читатель».');
    }
    if (sheetName && !ss.getSheetByName(sheetName)) throw new Error('В таблице нет листа «' + sheetName + '»');
  }
  var src = {
    id: 's' + Utilities.getUuid().slice(0, 8), team: team, project: String(req.project || '').trim(),
    name: name, url: url, sheet: sheetName, added_by: me.login, created: now_(), via: via,
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
    via: String(s.via || ''),
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

function findSource_(me, sourceId) {
  var all = readRows_(SHEET_SOURCES, SOURCES_HEADER);
  for (var i = 0; i < all.length; i++) {
    if (String(all[i].id) !== String(sourceId)) continue;
    if (!canUse_(me, all[i])) throw new Error('Нет доступа к источнику «' + all[i].name + '»');
    return all[i];
  }
  throw new Error('Источник не найден');
}

/** Коннектор, через который читается источник (или null — аккаунт сервера). */
function sourceBridge_(src) {
  if (!String(src.via || '')) return null;
  var b = findBridge_(src.via);
  if (!b) throw new Error('Таблица «' + src.name + '» подключена через Google-аккаунт ' + src.via +
                          ', но его коннектор отключён. Подключите коннектор снова или переподключите таблицу.');
  return b;
}

function fetchSource_(me, sourceId, sheetOverride) {
  var src = findSource_(me, sourceId);
  // Лист можно выбрать в программе (в таблице их бывает много); иначе —
  // указанный при подключении или первый.
  var want = String(sheetOverride || src.sheet || '').trim();
  var bridge = sourceBridge_(src);
  var book;
  if (bridge) {
    book = callBridge_(bridge, { action: 'read', url: src.url, sheet: want, label: src.name });
  } else {
    var ss;
    try {
      ss = SpreadsheetApp.openByUrl(src.url);
    } catch (err) {
      throw new Error('Сервер потерял доступ к таблице «' + src.name + '». Снова добавьте ' + serverEmail_() +
                      ' как «Читатель» или подключите таблицу через свой Google-аккаунт.');
    }
    book = readBook_(ss, want, src.name);
  }
  log_(me.login, 'fetch', src.name + ' (' + book.rows.length + ' строк)');
  return { id: String(src.id), name: String(src.name), columns: book.columns, rows: book.rows,
           decisions: book.decisions, sheets: book.sheets, sheet: book.sheet };
}

// ── Личный коннектор руководителя (server/Connector.gs) ───────────────────
/** Руководитель ставит коннектор в своём Google-аккаунте и один раз
 *  вставляет в программу его ссылку и ключ. Сервер читает таблицы через
 *  коннектор — доступ к ним есть у самого руководителя, расшаривать ничего
 *  не нужно. */
function findBridge_(login) {
  login = normLogin_(login);
  var rows = readRows_(SHEET_BRIDGES, BRIDGES_HEADER);
  for (var i = 0; i < rows.length; i++) if (normLogin_(rows[i].login) === login) return rows[i];
  return null;
}

function publicBridge_(user) {
  var b = findBridge_(user.login);
  return b ? { email: String(b.email || ''), url: String(b.url), created: String(b.created || '') } : null;
}

function callBridge_(bridge, body) {
  body.key = String(bridge.key);
  var resp;
  try {
    resp = UrlFetchApp.fetch(String(bridge.url), {
      method: 'post', contentType: 'application/json', payload: JSON.stringify(body),
      muteHttpExceptions: true, followRedirects: true,
    });
  } catch (err) {
    throw new Error('Нет связи с коннектором: ' + ((err && err.message) || err));
  }
  var data;
  try {
    data = JSON.parse(resp.getContentText());
  } catch (err) {
    throw new Error('Коннектор ответил не то, что ожидалось. Проверьте ссылку (…/exec) и что при развёртывании ' +
                    'выбрано «Выполнять от имени: Я», «У кого есть доступ: Все».');
  }
  if (data && data.error) throw new Error(String(data.error));
  return data;
}

function setBridge_(me, req) {
  var url = String(req.url || '').trim();
  var key = String(req.key || '').trim();
  var old = findBridge_(me.login);
  if (!url) {
    if (old) sheet_(SHEET_BRIDGES, BRIDGES_HEADER).deleteRow(old._row);
    log_(me.login, 'set_bridge', 'отключён');
    return { bridge: null };
  }
  if (!/^https:\/\/script\.google\.com\/(a\/[^/]+\/)?macros\/s\/[A-Za-z0-9_-]+\/exec/.test(url)) {
    throw new Error('Нужна ссылка веб-приложения коннектора вида https://script.google.com/macros/s/…/exec');
  }
  if (!key) throw new Error('Введите ключ коннектора (он в журнале выполнения после запуска setup)');
  var info = callBridge_({ url: url, key: key }, { action: 'ping' });
  var row = { login: me.login, url: url, key: key, email: String(info.email || ''), created: now_() };
  if (old) {
    BRIDGES_HEADER.forEach(function (k) { setCell_(SHEET_BRIDGES, BRIDGES_HEADER, old._row, k, row[k]); });
  } else {
    writeRow_(SHEET_BRIDGES, BRIDGES_HEADER, row);
  }
  log_(me.login, 'set_bridge', row.email);
  return { bridge: publicBridge_(me) };
}

// ── Чтение таблицы и решения ОТК ──────────────────────────────────────────
// readBook_, readDecisions_, writeDecisions_ и now_ одинаковы здесь и в
// server/Connector.gs (тест сверяет): коннектор делает то же самое, только
// от имени руководителя.
function readBook_(ss, want, label) {
  var tabs = ss.getSheets().map(function (x) { return x.getName(); })
    .filter(function (n) { return n !== DECISIONS_SHEET; });
  var sh = want ? ss.getSheetByName(want) : ss.getSheets()[0];
  if (!sh) throw new Error('В источнике «' + label + '» нет листа «' + want + '»');
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
  return { columns: values[0] || [], rows: values.slice(1), decisions: readDecisions_(ss, tz), sheets: tabs,
           sheet: sh.getName() };
}

// ── Решения ОТК (пишутся в ту же Google-таблицу, на отдельный лист) ────────
function normRole_(role) {
  return role === 'admin' ? 'admin' : role === 'lead' ? 'lead' : 'user';
}

function readDecisions_(ss, tz) {
  var sh = ss.getSheetByName(DECISIONS_SHEET);
  if (!sh) return [];
  var values = sh.getDataRange().getValues();
  var out = [];
  for (var r = 1; r < values.length; r++) {
    var id = String(values[r][0]).trim();
    if (!id) continue;
    var at = values[r][5];
    if (Object.prototype.toString.call(at) === '[object Date]') at = Utilities.formatDate(at, tz, 'yyyy-MM-dd HH:mm');
    out.push({ id: id, decision: String(values[r][1]), reason: String(values[r][2]), comment: String(values[r][3]),
               by: String(values[r][4]), at: String(at) });
  }
  return out;
}

/** Решения ставит только руководитель проекта (или администратор). Одна
 *  строка на анкету: повторное решение перезаписывает прежнее, пустое —
 *  удаляет. Нужны права «Редактор» у аккаунта, который пишет в таблицу. */
function setDecisions_(me, req) {
  if (me.role !== 'lead' && me.role !== 'admin') throw new Error('Решения по анкетам ставит только руководитель проекта');
  var src = findSource_(me, req.source_id);
  var items = req.items || [];
  for (var k = 0; k < items.length; k++) {
    var d = String(items[k].decision || '');
    if (d && DECISION_VALUES.indexOf(d) < 0) throw new Error('Неизвестное решение: ' + d);
    if (!String(items[k].id || '').trim()) throw new Error('У анкеты нет ID');
  }
  var bridge = sourceBridge_(src);
  var decisions;
  if (bridge) {
    decisions = callBridge_(bridge, { action: 'decide', url: src.url, items: items, by: me.login, label: src.name }).decisions;
  } else {
    decisions = writeDecisions_(SpreadsheetApp.openByUrl(src.url), items, me.login,
      'Сервер не может записать решения в «' + src.name + '». Дайте ' + serverEmail_() +
      ' право «Редактор» в настройках доступа этой таблицы.');
  }
  log_(me.login, 'set_decisions', src.name + ': ' + items.length + ' анкет');
  return { decisions: decisions };
}

function writeDecisions_(ss, items, by, noRights) {
  var sh = ss.getSheetByName(DECISIONS_SHEET);
  try {
    if (!sh) {
      sh = ss.insertSheet(DECISIONS_SHEET);
      sh.getRange('A:A').setNumberFormat('@');   // ID как текст — не терять ведущие нули
      sh.appendRow(DECISIONS_HEADER);
      sh.setFrozenRows(1);
    }
  } catch (err) {
    throw new Error(noRights);
  }
  var values = sh.getDataRange().getValues();
  var rowOf = {};
  for (var r = 1; r < values.length; r++) rowOf[String(values[r][0]).trim()] = r + 1;
  var toDelete = [];
  var stamp = now_();
  try {
    items.forEach(function (it) {
      var id = String(it.id).trim();
      var row = [id, String(it.decision || ''), String(it.reason || ''), String(it.comment || ''), by, stamp];
      if (!it.decision) {
        if (rowOf[id]) toDelete.push(rowOf[id]);
      } else if (rowOf[id]) {
        sh.getRange(rowOf[id], 1, 1, row.length).setValues([row]);
      } else {
        sh.appendRow(row);
        rowOf[id] = sh.getLastRow();
      }
    });
    toDelete.sort(function (a, b) { return b - a; }).forEach(function (r) { sh.deleteRow(r); });
  } catch (err) {
    throw new Error(noRights);
  }
  return readDecisions_(ss, ss.getSpreadsheetTimeZone());
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
  } else {
    // новые колонки после обновления кода дописываются справа
    for (var j = sh.getLastColumn(); j < header.length; j++) sh.getRange(1, j + 1).setValue(header[j]);
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
  sheet_(SHEET_BRIDGES, BRIDGES_HEADER);
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
