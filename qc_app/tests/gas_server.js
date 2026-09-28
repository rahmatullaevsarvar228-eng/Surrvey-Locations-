// Локальный «Apps Script» для разработки интерфейса: настоящий server/Code.gs
// в имитации сервисов Google, доступный по HTTP.
// node tests/gas_server.js <порт> <tables.json>
// tables.json: {"<ID таблицы>": {"<лист>": [[заголовки], [строка], ...]}}
"use strict";
const http = require("http");
const fs = require("fs");
const { makeEnv, Book, Sheet } = require("./gas_harness");

const port = Number(process.argv[2] || 8799);
const env = makeEnv();
if (process.argv[3]) {
  const tables = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
  for (const [id, sheets] of Object.entries(tables)) {
    env.external[id] = new Book(Object.entries(sheets).map(([name, rows]) => new Sheet(name, rows)));
  }
}
env.ctx.setup();
console.log(env.logs.join("\n"));
http.createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    const out = req.method === "POST" ? env.ctx.doPost({ postData: { contents: body } }) : env.ctx.doGet();
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(out.text);
  });
}).listen(port, "127.0.0.1", () => console.log(`gas_server on ${port}`));
