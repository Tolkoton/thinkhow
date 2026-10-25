// Task 206: «Надіслати» pressed while the microphone records stops the recording, the text goes into the field,
// and nothing is sent; only the next «Надіслати» sends. conversation.js is loaded as the page loads it.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.resolve(here, "../../src/thinkhow/web/static/conversation.js"), "utf8");
const realSetTimeout = globalThis.setTimeout;

async function flush(n = 25) {
  for (let i = 0; i < n; i++) await new Promise((r) => realSetTimeout(r, 0));
}

function element(id) {
  return {
    id,
    hidden: false,
    disabled: false,
    value: "",
    textContent: "",
    dataset: {},
    listeners: {},
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    },
    appendChild(c) {
      return c;
    },
  };
}

function fire(el, type) {
  const ev = { type, preventDefault() {} };
  for (const fn of el.listeners[type] || []) fn(ev);
}

class FakeRecorder {
  static isTypeSupported() {
    return true;
  }
  constructor() {
    this.state = "inactive";
    this.mimeType = "audio/webm;codecs=opus";
    this.listeners = {};
  }
  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }
  emit(type, event) {
    for (const fn of this.listeners[type] || []) fn(event);
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    realSetTimeout(() => {
      this.emit("dataavailable", { data: new Blob(["rec"], { type: this.mimeType }) });
      realSetTimeout(() => this.emit("stop", {}), 0);
    }, 0);
  }
}

// answers: a queue of () => Response | Promise<Response>, one per fetch
function loadPage(answers) {
  const byId = {};
  for (const id of ["reply-form", "send", "retry", "live", "error", "mic", "recognize", "mic-state"]) {
    byId[id] = element(id);
  }
  const field = element("");
  byId["reply-form"].dataset.key = "draft:alice-1/t-0123456789ab";
  byId["reply-form"].querySelector = () => field;
  byId.recognize.hidden = true;
  const calls = [];
  const win = {
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }) } },
    MediaRecorder: FakeRecorder,
    fetch: (url, init) => {
      calls.push({ url, init });
      const a = answers.shift();
      if (!a) throw new Error("fetch called more times than planned: " + url);
      return Promise.resolve().then(a);
    },
    setTimeout: (fn, ms) => (ms >= 1000 ? 1 : realSetTimeout(fn, ms)),
    clearTimeout() {},
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    location: { reload() {} },
    Blob,
    Response,
    TextDecoder,
    URLSearchParams,
  };
  win.window = win;
  win.document = { getElementById: (id) => byId[id] || null, createElement: () => element("") };
  vm.runInContext(SRC, vm.createContext(win));
  return { byId, field, calls };
}

const text = (t) => () =>
  new Response(JSON.stringify({ text: t }), { status: 200, headers: { "content-type": "application/json" } });
const stream = () =>
  new Response("event: saved\ndata: {}\n\nevent: answered\ndata: {}\n\n", {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
const replies = (p) => p.calls.filter((c) => c.url.endsWith("/reply"));

test("send while recording: stops, the text goes into the field, nothing is sent", async () => {
  const p = loadPage([text("світ"), stream]);
  p.field.value = "Привіт";
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(p.calls.length, 1, "only the recording was posted");
  assert.ok(p.calls[0].url.endsWith("/voice"), p.calls[0].url);
  assert.equal(p.field.value, "Привіт світ");
  assert.equal(replies(p).length, 0, "a reply was sent");
  assert.equal(p.byId.error.textContent, "");
  assert.equal(p.byId["mic-state"].textContent, "");
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replies(p).length, 1, "the next send did not send");
  assert.equal(replies(p)[0].init.body.get("text"), "Привіт світ");
});

test("send while recognizing: nothing is sent and the text is not lost", async () => {
  let release;
  const p = loadPage([() => new Promise((r) => (release = r)), stream]);
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId.mic, "click");
  await flush();
  assert.equal(p.byId["mic-state"].textContent, "Розпізнаю…");
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replies(p).length, 0, "an empty reply was sent while recognizing");
  release(text("світ")());
  await flush();
  assert.equal(p.field.value, "світ");
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replies(p)[0].init.body.get("text"), "світ");
});

test("send between stop and the recorder's stop event: nothing is sent", async () => {
  const p = loadPage([text("світ"), stream]);
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId.mic, "click");
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replies(p).length, 0, "a reply was sent before the text came");
  assert.equal(p.field.value, "світ");
});

test("send after a failed recognition sends what the field holds", async () => {
  const refused = () =>
    new Response('<p class="error">Не вдалося розпізнати — спробуйте ще раз.</p>', {
      status: 502,
      headers: { "content-type": "text/html" },
    });
  const p = loadPage([refused, stream]);
  p.field.value = "набране";
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replies(p).length, 1, "send stayed blocked after a refusal");
  assert.equal(replies(p)[0].init.body.get("text"), "набране");
});

// Task 207: the mic button is an icon; the state the words used to show is on the button itself.
test("the mic shows its state without words: recording, recognizing, idle", async () => {
  let release;
  const p = loadPage([() => new Promise((r) => (release = r))]);
  const mic = p.byId.mic;
  fire(mic, "click");
  await flush();
  assert.equal(mic.dataset.state, "recording");
  assert.equal(mic.ariaPressed, "true");
  fire(mic, "click");
  await flush();
  assert.equal(mic.dataset.state, "recognizing");
  assert.equal(mic.ariaPressed, "false");
  assert.equal(mic.disabled, true);
  release(text("світ")());
  await flush();
  assert.equal(mic.dataset.state, "");
  assert.equal(mic.disabled, false);
});

test("the mic leaves its recording state when recognition fails", async () => {
  const refused = () =>
    new Response('<p class="error">Не вдалося розпізнати — спробуйте ще раз.</p>', {
      status: 502,
      headers: { "content-type": "text/html" },
    });
  const p = loadPage([refused]);
  fire(p.byId.mic, "click");
  await flush();
  fire(p.byId.mic, "click");
  await flush();
  assert.equal(p.byId.mic.dataset.state, "");
  assert.equal(p.byId.recognize.hidden, false);
});
