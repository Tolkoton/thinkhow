// Disputed (Q2): createController of conversation.js — the draft and the buttons (Seam 5).
// The contract names createController({fetch, storage, ui, key}) and the ui methods, not the controller's
// own methods. Reading taken (Q2): the controller has send(text) for «Надіслати» and retry() for
// «Спробуйте ще раз»; storage is localStorage-like (getItem/setItem/removeItem); the draft is stored either
// under `key` or under "draft:" + key (both accepted: KEY already starts with "draft:"); the reply URL ends
// with "/reply", the retry URL with "/retry". Completion is observed on the ui, not on a returned promise.
// Not sealed until the slice planner answers Q2.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createController } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const KEY = "draft:u1/t-0123456789ab";
const NAMES = [KEY, "draft:" + KEY];
const enc = (s) => new TextEncoder().encode(s);
const ev = (name, data) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

function fakeUi() {
  const calls = [];
  const ui = {};
  for (const m of ["disable", "enable", "appendDelta", "showRetry", "showError", "reload", "setDraft"]) {
    ui[m] = (...args) => calls.push([m, ...args]);
  }
  return { ui, calls, names: () => calls.map((c) => c[0]) };
}

function fakeStorage(preset) {
  const map = new Map();
  if (preset !== undefined) for (const n of NAMES) map.set(n, preset);
  const log = [];
  return {
    map,
    log,
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => {
      log.push(["set", k, v]);
      map.set(k, String(v));
    },
    removeItem: (k) => {
      log.push(["remove", k]);
      map.delete(k);
    },
    draft() {
      for (const n of NAMES) if (map.has(n)) return map.get(n);
      return null;
    },
  };
}

function streamOf(chunks, { fail = false } = {}) {
  let i = 0;
  return new ReadableStream({
    pull(c) {
      if (i < chunks.length) c.enqueue(chunks[i++]);
      else if (fail) c.error(new TypeError("network lost"));
      else c.close();
    },
  });
}

function bytewise(text) {
  const b = enc(text);
  const out = [];
  for (let i = 0; i < b.length; i++) out.push(b.slice(i, i + 1));
  return out;
}

const sse = (stream) =>
  new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
const html = (status, body) =>
  new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8" } });

function fakeFetch(respond, storage, uiCalls) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url: String(url), init: init || {}, draft: storage.draft(), uiBefore: uiCalls.map((c) => c[0]) });
    return respond();
  };
  return { fetch, calls };
}

async function until(cond, what, ms = 3000) {
  const end = Date.now() + ms;
  while (!cond()) {
    if (Date.now() > end) throw new Error(`timed out waiting for: ${what}`);
    await new Promise((r) => setTimeout(r, 5));
  }
}

function start(action) {
  Promise.resolve()
    .then(action)
    .catch(() => {});
}

test("controller: send keeps the draft, disables, POSTs to reply", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const f = fakeFetch(() => sse(streamOf([enc(ev("saved", { turn: 1 }) + ev("answered", { turn: 2 }))])), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Мій текст 🌍"));
  await until(() => names().includes("reload"), "reload");
  assert.equal(f.calls.length, 1);
  assert.ok(f.calls[0].url.endsWith("/reply"), f.calls[0].url);
  assert.equal(String(f.calls[0].init.method).toUpperCase(), "POST");
  assert.equal(f.calls[0].draft, "Мій текст 🌍", "the draft is in storage before the request");
  assert.ok(f.calls[0].uiBefore.includes("disable"), "buttons disabled before the request");
});

test("controller: saved removes the draft, deltas appended, answered reloads", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const body =
    ev("saved", { turn: 1 }) + ev("delta", { text: "Що " }) + ev("delta", { text: "сталося?\n😀" }) +
    ev("answered", { turn: 2 });
  const f = fakeFetch(() => sse(streamOf(bytewise(body))), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Текст"));
  await until(() => names().includes("reload"), "reload");
  assert.equal(storage.draft(), null);
  assert.deepStrictEqual(
    calls.filter((x) => x[0] === "appendDelta").map((x) => x[1]),
    ["Що ", "сталося?\n😀"],
  );
  assert.equal(names().filter((n) => n === "reload").length, 1);
});

test("controller: buttons stay disabled until the stream ends", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  let ctl;
  const stream = new ReadableStream({ start: (c) => (ctl = c) });
  const f = fakeFetch(() => sse(stream), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Текст"));
  await until(() => ctl !== undefined && f.calls.length === 1, "the request");
  ctl.enqueue(enc(ev("saved", { turn: 1 }) + ev("delta", { text: "почато" })));
  await until(() => names().includes("appendDelta"), "the delta");
  await new Promise((r) => setTimeout(r, 50));
  const lastDisable = names().lastIndexOf("disable");
  assert.ok(lastDisable >= 0);
  assert.ok(!names().slice(lastDisable).includes("enable"), "enabled before the stream ended");
  ctl.enqueue(enc(ev("failed", { reason: "Boom" })));
  ctl.close();
  await until(() => names().slice(lastDisable).includes("enable"), "enable after the end");
  assert.ok(names().includes("showRetry"));
});

test("controller: failed shows retry and enables", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const body = ev("saved", { turn: 1 }) + ev("delta", { text: "Що" }) + ev("failed", { reason: "LlmUnavailable" });
  const f = fakeFetch(() => sse(streamOf([enc(body)])), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Текст"));
  await until(() => names().includes("showRetry") && names().includes("enable"), "showRetry and enable");
  assert.ok(names().lastIndexOf("enable") > names().lastIndexOf("disable"));
  assert.ok(!names().includes("reload"));
  assert.equal(storage.draft(), null, "saved came: the draft is gone");
});

test("controller: stream broken before saved keeps the draft", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const half = enc(ev("saved", { turn: 1 })).slice(0, 9);
  const f = fakeFetch(() => sse(streamOf([half], { fail: true })), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Мій текст"));
  await until(() => names().includes("showRetry") && names().includes("enable"), "showRetry and enable");
  assert.ok(names().lastIndexOf("enable") > names().lastIndexOf("disable"));
  assert.equal(storage.draft(), "Мій текст");
});

test("controller: fetch rejection keeps the draft", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  const c = createController({ fetch, storage, ui, key: KEY });
  start(() => c.send("Мій текст"));
  await until(() => names().includes("showRetry") && names().includes("enable"), "showRetry and enable");
  assert.ok(names().lastIndexOf("enable") > names().lastIndexOf("disable"));
  assert.equal(storage.draft(), "Мій текст");
});

test("controller: an HTML error response shows its text and keeps the draft", async () => {
  const cases = [
    [401, "Потрібно увійти через Google"],
    [409, "Спершу дочекайтеся відповіді або натисніть «Спробуйте ще раз»."],
    [200, "Запит не прийнято."],
  ];
  for (const [status, text] of cases) {
    const { ui, calls, names } = fakeUi();
    const storage = fakeStorage();
    const f = fakeFetch(() => html(status, `<p class="error">${text}</p>`), storage, calls);
    const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
    start(() => c.send("Мій текст"));
    await until(() => names().includes("showError") && names().includes("enable"), `showError (${status})`);
    assert.ok(names().lastIndexOf("enable") > names().lastIndexOf("disable"), String(status));
    const shown = calls.filter((x) => x[0] === "showError").map((x) => String(x[1]));
    assert.ok(shown.some((s) => s.includes(text)), `${status}: ${shown}`);
    assert.equal(storage.draft(), "Мій текст", String(status));
    assert.ok(!names().includes("reload"), String(status));
  }
});

test("controller: stream closed after saved without an end event", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const body = ev("saved", { turn: 1 }) + ev("delta", { text: "почато" });
  const f = fakeFetch(() => sse(streamOf([enc(body)])), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Мій текст"));
  await until(() => names().includes("showRetry") && names().includes("enable"), "showRetry and enable");
  assert.ok(names().lastIndexOf("enable") > names().lastIndexOf("disable"));
  assert.ok(!names().includes("reload"));
  assert.equal(storage.draft(), null, "saved came: the draft is gone");
});

test("controller: stream closed before saved keeps the draft", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage();
  const f = fakeFetch(() => sse(streamOf([])), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.send("Мій текст"));
  await until(() => names().includes("showRetry") && names().includes("enable"), "showRetry and enable");
  assert.equal(storage.draft(), "Мій текст");
});

test("controller: retry POSTs to retry and leaves the draft alone", async () => {
  const { ui, calls, names } = fakeUi();
  const storage = fakeStorage("стара чернетка");
  const body = ev("delta", { text: "Ще раз" }) + ev("answered", { turn: 2 });
  const f = fakeFetch(() => sse(streamOf([enc(body)])), storage, calls);
  const c = createController({ fetch: f.fetch, storage, ui, key: KEY });
  start(() => c.retry());
  await until(() => names().includes("reload"), "reload");
  assert.equal(f.calls.length, 1);
  assert.ok(f.calls[0].url.endsWith("/retry"), f.calls[0].url);
  assert.equal(String(f.calls[0].init.method).toUpperCase(), "POST");
  const sent = f.calls[0].init.body;
  if (sent instanceof FormData || sent instanceof URLSearchParams) assert.ok(!sent.has("text"));
  else assert.ok(sent === undefined || sent === null || !String(sent).includes("стара"), String(sent));
  assert.deepStrictEqual(storage.log, [], "retry does not touch the draft");
  for (const n of NAMES) assert.equal(storage.map.get(n), "стара чернетка");
  assert.deepStrictEqual(
    calls.filter((x) => x[0] === "appendDelta").map((x) => x[1]),
    ["Ще раз"],
  );
});

test("controller: on open the draft returns to the field", async () => {
  const { ui, calls } = fakeUi();
  const storage = fakeStorage("чернетка 🌍\nдругий рядок");
  const fetch = async () => {
    throw new Error("no request expected");
  };
  createController({ fetch, storage, ui, key: KEY });
  await until(() => calls.some((x) => x[0] === "setDraft"), "setDraft");
  assert.deepStrictEqual(
    calls.filter((x) => x[0] === "setDraft").map((x) => x[1]),
    ["чернетка 🌍\nдругий рядок"],
  );
});
