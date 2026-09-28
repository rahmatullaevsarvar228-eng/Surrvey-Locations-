/**
 * AnketaQC — личный коннектор руководителя проекта.
 *
 * Ставится ОДИН раз в Google-аккаунте руководителя. Через него сервер
 * AnketaQC читает Google-таблицы с анкетами от имени руководителя: всё, что
 * руководитель сам видит в Google Sheets, можно подключить в программе по
 * ссылке — никому расшаривать таблицы не нужно. Решения ОТК коннектор пишет
 * на лист «Решения ОТК» тоже от имени руководителя.
 *
 * Установка (~5 минут):
 *  1. Откройте https://script.google.com под своей почтой → «Новый проект».
 *     Удалите пример кода, вставьте весь этот файл, сохраните.
 *  2. Вверху выберите функцию setup → «Выполнить» → разрешите доступ.
 *     Внизу, в журнале выполнения, появится «Ключ коннектора: …».
 *  3. «Развернуть» → «Новое развёртывание» → тип «Веб-приложение».
 *     «Выполнять от имени»: Я. «У кого есть доступ»: Все. → «Развернуть».
 *     Скопируйте ссылку …/exec.
 *  4. В AnketaQC: ⋯ → Источники данных → «Мой Google-аккаунт»: вставьте
 *     ссылку и ключ.
 *
 * Без ключа коннектор ничего не отдаёт. Новый ключ (если старый попал не в
 * те руки) — запустите newKey() и вставьте его в программу заново.
 */

var DECISIONS_SHEET = 'Решения ОТК';
var DECISIONS_HEADER = ['ID анкеты', 'Решение', 'Причина (система)', 'Комментарий', 'Кто решил', 'Когда'];

function setup() {
  var props = PropertiesService.getScriptProperties();
  var key = props.getProperty('KEY');
  if (!key) {
    key = newKey_();
    props.setProperty('KEY', key);
  }
  Logger.log('Ключ коннектора: ' + key);
  Logger.log('Аккаунт: ' + email_() + '. Теперь: Развернуть → Новое развёртывание → Веб-приложение.');
}

function newKey() {
  var key = newKey_();
  PropertiesService.getScriptProperties().setProperty('KEY', key);
  Logger.log('Старый ключ больше не работает. Вставьте в AnketaQC новый.');
  Logger.log('Новый ключ коннектора: ' + key);
}

function doGet() {
  return out_({ ok: true, service: 'AnketaQC-connector' });
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

function handle_(req) {
  var key = PropertiesService.getScriptProperties().getProperty('KEY');
  if (!key) throw new Error('Коннектор не настроен: в редакторе Apps Script запустите setup()');
  if (String(req.key || '') !== key) throw new Error('Неверный ключ коннектора');
  var label = String(req.label || 'таблица');
  switch (req.action) {
    case 'ping': return { ok: true, email: email_() };
    case 'check': {
      var ss = open_(req.url);
      var want = String(req.sheet || '').trim();
      if (want && !ss.getSheetByName(want)) throw new Error('В таблице нет листа «' + want + '»');
      return { ok: true };
    }
    case 'read': return readBook_(open_(req.url), String(req.sheet || '').trim(), label);
    case 'decide':
      return { decisions: writeDecisions_(open_(req.url), req.items || [], String(req.by || ''),
        'Аккаунт ' + email_() + ' не может записать решения в «' + label + '»: нужно право «Редактор» в этой таблице.') };
  }
  throw new Error('Неизвестное действие: ' + req.action);
}

function open_(url) {
  try {
    return SpreadsheetApp.openByUrl(String(url || ''));
  } catch (err) {
    throw new Error('Аккаунт ' + email_() + ' не видит эту таблицу. Откройте её в Google Sheets под этой почтой ' +
                    'или попросите владельца таблицы дать доступ.');
  }
}

function email_() {
  try { return Session.getEffectiveUser().getEmail(); } catch (err) { return ''; }
}

function newKey_() {
  return (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ── Ниже — те же функции, что в server/Code.gs ────────────────────────────
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
function now_() { return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss'); }
