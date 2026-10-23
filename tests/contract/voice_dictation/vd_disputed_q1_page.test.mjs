// Disputed (Q1): the page side of the microphone — `attach` in conversation.js (I5, Seam 5's buttons, limitMs).
// The contract exports only createRecorder for `node --test` and says createRecorder calls
// `ui.insertText(json.text)` with the text as it came; the appending rule (I5) is then the page's ui. Reading
// taken (Q1): it is observed by loading conversation.js as the page does — in a browser-like global scope
// (window = globalThis, document, navigator.mediaDevices, MediaRecorder, fetch, setTimeout), where the script
// itself calls attach(document, window) — and clicking #mic. The field is the <textarea name="text"> of
// #reply-form. Not sealed until the slice planner answers Q1.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"), "utf8");
const WEBM = "audio/webm;codecs=opus";
const NOT_RECOGNIZED = "Не вдалося розпізнати — спробуйте ще раз.";
const RECORDING_WORDS = "Запис… натисніть ще раз, щоб зупинити";
const RECOGNIZING_WORDS = "Розпізнаю…";

const realSetTimeout = globalThis.setTimeout;
const tick = () => new Promise((r) => realSetTimeout(r, 0));
async function flush(n = 25) {
  for (let i = 0; i < n; i++) await tick();
}

function element(tag, id, doc) {
  const el = {
    tagName: tag.toUpperCase(),
    id,
    hidden: false,
    disabled: false,
    value: "",
    textContent: "",
    innerText: "",
    className: "",
    dataset: {},
    style: {},
    attributes: {},
    children: [],
    listeners: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    },
    removeEventListener(type, fn) {
      this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
    },
    setAttribute(k, v) {
      this.attributes[k] = String(v);
      if (k === "disabled" || k === "hidden") this[k] = true;
      else this[k] = String(v);
    },
    removeAttribute(k) {
      delete this.attributes[k];
      if (k === "disabled" || k === "hidden") this[k] = false;
    },
    toggleAttribute(k, force) {
      const on = force === undefined ? !this[k] : !!force;
      if (on) this.setAttribute(k, "");
      else this.removeAttribute(k);
      return on;
    },
    hasAttribute(k) {
      return k in this.attributes || ((k === "disabled" || k === "hidden") && this[k]);
    },
    getAttribute(k) {
      return k in this.attributes ? this.attributes[k] : null;
    },
    appendChild(c) {
      this.children.push(c);
      return c;
    },
    append(...cs) {
      this.children.push(...cs);
    },
    remove() {},
    focus() {},
    blur() {},
    dispatchEvent(ev) {
      fire(this, ev.type, ev);
      return true;
    },
    click() {
      fire(this, "click");
    },
    querySelector(sel) {
      return doc.querySelector(sel);
    },
    querySelectorAll() {
      return [];
    },
    closest() {
      return doc.byId["reply-form"];
    },
  };
  return el;
}

function fire(el, type, given) {
  const ev = given || {
    type,
    target: el,
    currentTarget: el,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {},
  };
  if (typeof el["on" + type] === "function") el["on" + type](ev);
  for (const fn of el.listeners[type] || []) fn(ev);
}

function makeDocument() {
  const doc = { byId: {} };
  const add = (tag, id) => (doc.byId[id] = element(tag, id, doc));
  const form = add("form", "reply-form");
  form.dataset.key = "draft:alice-1/t-0123456789ab";
  form.action = "/topics/alice-1/t-0123456789ab/reply";
  form.attributes.action = form.action;
  form.method = "post";
  const field = element("textarea", "", doc);
  field.name = "text";
  form.elements = { text: field, namedItem: (n) => (n === "text" ? field : null) };
  doc.field = field;
  for (const [tag, id] of [
    ["button", "send"],
    ["button", "mic"],
    ["button", "recognize"],
    ["span", "mic-state"],
    ["div", "live"],
    ["p", "error"],
  ]) {
    add(tag, id);
  }
  doc.byId.recognize.hidden = true;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    if (/textarea|name=["']?text/.test(sel)) return field;
    const m = /^#([\w-]+)$/.exec(sel.trim());
    if (m) return doc.byId[m[1]] || null;
    if (sel.trim() === "form") return form;
    return null;
  };
  doc.querySelectorAll = (sel) => {
    const one = doc.querySelector(sel);
    return one ? [one] : [];
  };
  doc.createElement = (tag) => element(tag, "", doc);
  doc.addEventListener = () => {};
  doc.readyState = "complete";
  doc.body = element("body", "", doc);
  return doc;
}

function fakeRecorderClass() {
  const instances = [];
  class FakeRecorder {
    static isTypeSupported(type) {
      return type === WEBM || type === "audio/mp4";
    }
    constructor(stream, options) {
      this.stream = stream;
      this.options = options;
      this.state = "inactive";
      this.mimeType = options && options.mimeType ? options.mimeType : "";
      this.listeners = {};
      this.ondataavailable = null;
      this.onstop = null;
      this.id = instances.length + 1;
      instances.push(this);
    }
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    }
    removeEventListener(type, fn) {
      this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
    }
    _emit(type, event) {
      if (typeof this["on" + type] === "function") this["on" + type](event);
      for (const fn of this.listeners[type] || []) fn(event);
    }
    start() {
      this.state = "recording";
    }
    stop() {
      if (this.state === "inactive") return;
      this.state = "inactive";
      realSetTimeout(() => {
        this._emit("dataavailable", { data: new Blob([`rec-${this.id}`], { type: this.mimeType }) });
        realSetTimeout(() => this._emit("stop", {}), 0);
      }, 0);
    }
  }
  return { FakeRecorder, instances };
}

// answers: a queue of () => Response | Promise<Response>
function loadPage(answers) {
  const doc = makeDocument();
  const { FakeRecorder, instances } = fakeRecorderClass();
  const fetchCalls = [];
  const timers = [];
  const tracks = [{ stop() {} }];
  const win = {
    document: doc,
    navigator: {
      mediaDevices: { getUserMedia: async () => ({ getTracks: () => tracks, getAudioTracks: () => tracks }) },
    },
    MediaRecorder: FakeRecorder,
    fetch: (url, init) => {
      fetchCalls.push({ url, init });
      const a = answers.shift();
      if (!a) throw new Error("fetch called more times than planned");
      return Promise.resolve().then(a);
    },
    setTimeout: (fn, ms, ...args) => {
      timers.push(ms);
      if (ms >= 1000) return 1000 + timers.length;
      return realSetTimeout(fn, ms, ...args);
    },
    clearTimeout: (id) => {
      if (typeof id !== "number" || id <= 1000) clearTimeout(id);
    },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    location: { pathname: "/topics/alice-1/t-0123456789ab", href: "http://x/topics/alice-1/t-0123456789ab", reload() {} },
    addEventListener() {},
    console,
    Blob,
    Response,
    Headers,
    TextDecoder,
    TextEncoder,
    ReadableStream,
    DOMException,
    queueMicrotask,
    Promise,
    JSON,
    Error,
    TypeError,
  };
  win.window = win;
  win.self = win;
  const ctx = vm.createContext(win);
  vm.runInContext(SRC, ctx);
  return { doc, win, instances, fetchCalls, timers };
}

const ok = (text) => () =>
  new Response(JSON.stringify({ text }), { status: 200, headers: { "content-type": "application/json" } });
const fragment502 = () =>
  new Response(`<p class="error">${NOT_RECOGNIZED}</p>`, {
    status: 502,
    headers: { "content-type": "text/html; charset=utf-8" },
  });

async function speak(p) {
  fire(p.doc.byId.mic, "click");
  await flush();
  fire(p.doc.byId.mic, "click");
  await flush();
}

test("I5: the text is only appended to the field", async () => {
  const cases = [
    ["", "світ", "світ"],
    ["Привіт", "світ", "Привіт світ"],
    ["Привіт ", "світ", "Привіт світ"],
    ["рядок\n", "світ", "рядок\nсвіт"],
    ["Хочу", "нову роботу, зарплата і друзів.", "Хочу нову роботу, зарплата і друзів."],
    ["  два пробіли  ", "x", "  два пробіли  x"],
  ];
  for (const [before, text, after] of cases) {
    const p = loadPage([ok(text)]);
    p.doc.field.value = before;
    await speak(p);
    assert.equal(p.fetchCalls.length, 1, `no POST for ${JSON.stringify(before)}`);
    assert.equal(p.doc.field.value, after, JSON.stringify([before, text]));
    assert.ok(p.doc.field.value.startsWith(before));
  }
  // a refusal first, then the text: still appended once to what the person typed
  const p = loadPage([fragment502, ok("світ")]);
  p.doc.field.value = "Привіт";
  await speak(p);
  assert.equal(p.doc.field.value, "Привіт");
  fire(p.doc.byId.recognize, "click");
  await flush();
  assert.equal(p.doc.field.value, "Привіт світ");
});

test("page: the recorder's limit is 14.5 minutes", async () => {
  const p = loadPage([ok("світ")]);
  fire(p.doc.byId.mic, "click");
  await flush();
  assert.ok(p.timers.includes(870000), `timers set: ${p.timers.join(",")}`);
});

test("page: #mic and #recognize are disabled while the request is in flight, enabled after", async () => {
  let release;
  const pending = () =>
    new Promise((resolve) => {
      release = resolve;
    });
  const p = loadPage([() => pending(), () => pending()]);
  await speak(p);
  assert.equal(p.fetchCalls.length, 1);
  assert.equal(p.doc.byId.mic.disabled, true, "#mic enabled while in flight");
  assert.equal(p.doc.byId.recognize.disabled, true, "#recognize enabled while in flight");
  release(fragment502());
  await flush();
  assert.equal(p.doc.byId.mic.disabled, false, "#mic still disabled after a refusal");
  assert.equal(p.doc.byId.recognize.disabled, false, "#recognize still disabled after a refusal");
  assert.equal(p.doc.byId.recognize.hidden, false, "#recognize not offered after a refusal");
  fire(p.doc.byId.recognize, "click");
  await flush();
  assert.equal(p.fetchCalls.length, 2);
  assert.equal(p.doc.byId.mic.disabled, true);
  assert.equal(p.doc.byId.recognize.disabled, true);
  release(ok("світ")());
  await flush();
  assert.equal(p.doc.byId.mic.disabled, false, "#mic still disabled after the text");
});

test("page: #mic-state says what is happening", async () => {
  let release;
  const p = loadPage([
    () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  ]);
  fire(p.doc.byId.mic, "click");
  await flush();
  assert.equal(p.doc.byId["mic-state"].textContent, RECORDING_WORDS);
  fire(p.doc.byId.mic, "click");
  await flush();
  assert.equal(p.doc.byId["mic-state"].textContent, RECOGNIZING_WORDS);
  release(ok("світ")());
  await flush();
});
