// Contract tests of voice-dictation, Seam 5 and I4: createRecorder of conversation.js (slice tester).
// Written from the contract, not the code. The fake Recorder behaves as a browser does (W3C): stop() sets
// state = "inactive" at once and delivers `dataavailable` and then `stop` AFTER returning, each in a task of
// its own. The ui is a recorder of calls: any method the controller calls is accepted and remembered.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createRecorder } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const URL_ = "/topics/alice-1/t-0123456789ab/voice";
const LIMIT = 5000;
const WEBM = "audio/webm;codecs=opus";
const NETWORK = "Не вдалося надіслати запис — спробуйте ще раз; якщо не вийде, увійдіть знову в новій вкладці.";
const SILENT = "Не почули слів — спробуйте ще раз.";
const DENIED = "Немає доступу до мікрофона.";
const NOT_RECOGNIZED = "Не вдалося розпізнати — спробуйте ще раз.";
const NOT_ACCEPTED = "Запис не прийнято — спробуйте записати ще раз.";
const FIRST_CHOOSE = "Спершу оберіть мову (сторінка «Мова»).";

const realSetTimeout = globalThis.setTimeout;
const tick = () => new Promise((r) => realSetTimeout(r, 0));
async function flush(n = 20) {
  for (let i = 0; i < n; i++) await tick();
}

function fakeUi() {
  const calls = [];
  const ui = new Proxy(
    {},
    {
      get(_, name) {
        if (typeof name !== "string" || name === "then") return undefined;
        return (...args) => calls.push([name, ...args]);
      },
    },
  );
  return { ui, calls, names: () => calls.map((c) => c[0]) };
}

function fakeRecorderClass({ supported = [WEBM, "audio/mp4"], browserType = "" } = {}) {
  const instances = [];
  class FakeRecorder {
    static isTypeSupported(type) {
      return supported.includes(type);
    }
    constructor(stream, options) {
      this.stream = stream;
      this.options = options;
      this.state = "inactive";
      this.mimeType = options && options.mimeType ? options.mimeType : browserType;
      this.listeners = {};
      this.ondataavailable = null;
      this.onstop = null;
      this.stopCalls = 0;
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
      this.stopCalls += 1;
      if (this.state === "inactive") return;
      this.state = "inactive";
      realSetTimeout(() => {
        this._emit("dataavailable", { data: new Blob([`rec-${this.id}-a`], { type: this.mimeType }) });
        realSetTimeout(() => {
          this._emit("dataavailable", { data: new Blob([`|rec-${this.id}-b`], { type: this.mimeType }) });
          realSetTimeout(() => this._emit("stop", {}), 0);
        }, 0);
      }, 0);
    }
  }
  return { Recorder: FakeRecorder, instances };
}

function fakeMedia({ deny = false } = {}) {
  const media = { requests: [], streams: [] };
  media.getUserMedia = async (constraints) => {
    media.requests.push(constraints);
    if (deny) throw new DOMException("Permission denied", "NotAllowedError");
    const tracks = [{ stopped: 0, stop() { this.stopped += 1; } }];
    const stream = { tracks, getTracks: () => tracks, getAudioTracks: () => tracks };
    media.streams.push(stream);
    return stream;
  };
  return media;
}

function fakeTimers() {
  const timers = { set: [], cleared: [] };
  let next = 1;
  timers.setTimeout = (fn, ms) => {
    const id = next++;
    timers.set.push({ id, fn, ms });
    return id;
  };
  timers.clearTimeout = (id) => timers.cleared.push(id);
  timers.fire = (ms) => {
    const t = timers.set.find((x) => x.ms === ms && !timers.cleared.includes(x.id));
    assert.ok(t, `no live timer of ${ms} ms`);
    t.fn();
  };
  return timers;
}

const json = (status, obj) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
const fragment = (status, text) =>
  new Response(`<p class="error">${text}</p>`, { status, headers: { "content-type": "text/html; charset=utf-8" } });
const loginPage = () =>
  new Response("<!doctype html><html><head><title>Sign in</title></head><body><form>Google</form></body></html>", {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
  });

// A queue of answers; "net" rejects as fetch does on a network failure; a function gives a pending promise.
function fakeFetch(answers) {
  const calls = [];
  const fetch = (url, init) => {
    calls.push({ url, init });
    const a = answers.shift();
    if (a === undefined) throw new Error("fetch called more times than planned");
    if (a === "net") return Promise.reject(new TypeError("Failed to fetch"));
    if (typeof a === "function") return a();
    return Promise.resolve(a());
  };
  return { fetch, calls };
}

async function bodyOf(call) {
  return await call.init.body.text();
}
const typeOf = (call) => new Headers(call.init.headers).get("content-type");

function setup({ answers = [], supported, browserType, deny } = {}) {
  const u = fakeUi();
  const { Recorder, instances } = fakeRecorderClass({ supported, browserType });
  const media = fakeMedia({ deny });
  const timers = fakeTimers();
  const f = fakeFetch(answers);
  const rec = createRecorder({
    media,
    Recorder,
    fetch: f.fetch,
    ui: u.ui,
    url: URL_,
    limitMs: LIMIT,
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
  });
  return { rec, u, instances, media, timers, f };
}

async function record(s) {
  await s.rec.start();
  await flush();
  s.rec.stop();
  await flush();
}

test("start: audio only, the first supported type, 64 kbit/s, ui.recording", async () => {
  for (const [supported, expected] of [
    [[WEBM, "audio/mp4"], WEBM],
    [["audio/mp4"], "audio/mp4"],
  ]) {
    const s = setup({ supported });
    await s.rec.start();
    await flush();
    assert.deepEqual(s.media.requests, [{ audio: true }]);
    assert.equal(s.instances.length, 1);
    const r = s.instances[0];
    assert.equal(r.stream, s.media.streams[0]);
    assert.equal(r.options.mimeType, expected);
    assert.equal(r.options.audioBitsPerSecond, 64000);
    assert.equal(r.state, "recording");
    assert.ok(s.u.names().includes("recording"));
  }
  const none = setup({ supported: [], browserType: "audio/ogg" });
  await none.rec.start();
  await flush();
  const r = none.instances[0];
  assert.ok(!r.options || !r.options.mimeType, `mimeType given though none is supported: ${r.options && r.options.mimeType}`);
  assert.equal(r.options.audioBitsPerSecond, 64000);
  assert.equal(r.state, "recording");
});

test("stop: the Blob is gathered after the stop event and posted with its type", async () => {
  const s = setup({ answers: [() => json(200, { text: "світ" })] });
  await s.rec.start();
  await flush();
  s.rec.stop();
  assert.equal(s.f.calls.length, 0, "posted inside stop(), before the recorder's stop event");
  await flush();
  assert.equal(s.instances[0].stopCalls, 1);
  assert.equal(s.f.calls.length, 1);
  const call = s.f.calls[0];
  assert.equal(call.url, URL_);
  assert.equal(call.init.method, "POST");
  assert.equal(await bodyOf(call), "rec-1-a|rec-1-b");
  assert.equal(call.init.body.type, WEBM);
  assert.equal(typeOf(call), WEBM);
  assert.ok(s.media.streams[0].tracks.every((t) => t.stopped >= 1), "the stream's tracks were not stopped");
  const names = s.u.names();
  assert.ok(names.includes("recognizing"));
});

test("stop: an empty recorder.mimeType gives a Blob of type audio/webm", async () => {
  const s = setup({ supported: [], browserType: "", answers: [() => json(200, { text: "світ" })] });
  await record(s);
  assert.equal(s.f.calls.length, 1);
  assert.equal(s.f.calls[0].init.body.type, "audio/webm");
  assert.equal(typeOf(s.f.calls[0]), "audio/webm");
});

test("limit: start sets a limitMs timer, the button's stop clears it", async () => {
  const s = setup({ answers: [() => json(200, { text: "світ" })] });
  await s.rec.start();
  await flush();
  const t = s.timers.set.find((x) => x.ms === LIMIT);
  assert.ok(t, "no timer of limitMs");
  s.rec.stop();
  await flush();
  assert.ok(s.timers.cleared.includes(t.id), "the limitMs timer was not cleared");
});

test("limit: the timer stops by itself; a press after it gives one recorder.stop and one POST", async () => {
  const s = setup({ answers: [() => json(200, { text: "світ" })] });
  await s.rec.start();
  await flush();
  s.timers.fire(LIMIT);
  await flush();
  assert.equal(s.instances[0].stopCalls, 1);
  assert.equal(s.f.calls.length, 1);
  s.rec.stop();
  await flush();
  assert.equal(s.instances[0].stopCalls, 1);
  assert.equal(s.f.calls.length, 1);
});

test("denied: the microphone refused shows its message and leaves the state as before", async () => {
  const s = setup({ deny: true });
  await s.rec.start();
  await flush();
  assert.deepEqual(
    s.u.calls.filter((c) => c[0] === "showError"),
    [["showError", DENIED]],
  );
  assert.ok(!s.u.names().includes("recording"));
  assert.equal(s.instances.length, 0);
  s.rec.stop();
  await flush();
  assert.equal(s.f.calls.length, 0);
});

test("200 with text: insertText(text), then idle", async () => {
  const s = setup({ answers: [() => json(200, { text: "світ" })] });
  await record(s);
  const inserts = s.u.calls.filter((c) => c[0] === "insertText");
  assert.deepEqual(inserts, [["insertText", "світ"]]);
  const names = s.u.names();
  assert.ok(names.lastIndexOf("idle") > names.indexOf("insertText"), names.join(","));
});

test("502: the fragment's text, offerRecognize; recognize() sends the same recording; then 200", async () => {
  const s = setup({ answers: [() => fragment(502, NOT_RECOGNIZED), () => json(200, { text: "світ" })] });
  await record(s);
  assert.deepEqual(
    s.u.calls.filter((c) => c[0] === "showError"),
    [["showError", NOT_RECOGNIZED]],
  );
  assert.ok(s.u.names().includes("offerRecognize"));
  assert.ok(!s.u.names().includes("insertText"));
  s.rec.recognize();
  await flush();
  assert.equal(s.f.calls.length, 2);
  assert.equal(await bodyOf(s.f.calls[1]), await bodyOf(s.f.calls[0]));
  assert.equal(typeOf(s.f.calls[1]), WEBM);
  assert.deepEqual(
    s.u.calls.filter((c) => c[0] === "insertText"),
    [["insertText", "світ"]],
  );
});

test("200 with empty text: «Не почули слів», offerRecognize, the recording stays", async () => {
  const s = setup({ answers: [() => json(200, { text: "" }), () => json(200, { text: "світ" })] });
  await record(s);
  assert.deepEqual(
    s.u.calls.filter((c) => c[0] === "showError"),
    [["showError", SILENT]],
  );
  assert.ok(s.u.names().includes("offerRecognize"));
  assert.ok(!s.u.names().includes("insertText"));
  s.rec.recognize();
  await flush();
  assert.equal(await bodyOf(s.f.calls[1]), "rec-1-a|rec-1-b");
});

test("network error and a 200 page that is not JSON: the network message, offerRecognize", async () => {
  for (const answer of ["net", () => loginPage(), () => new Response("Service Unavailable", { status: 503 })]) {
    const s = setup({ answers: [answer] });
    await record(s);
    assert.deepEqual(
      s.u.calls.filter((c) => c[0] === "showError"),
      [["showError", NETWORK]],
    );
    assert.ok(s.u.names().includes("offerRecognize"));
    assert.ok(!s.u.names().includes("insertText"));
  }
});

test("in flight: ui.recognizing is the last call until the answer; every answer is followed by more", async () => {
  for (const answer of [
    () => json(200, { text: "світ" }),
    () => fragment(502, NOT_RECOGNIZED),
    () => fragment(400, NOT_ACCEPTED),
    () => json(200, { text: "" }),
    "net",
  ]) {
    let release;
    const pending = () =>
      new Promise((resolve, reject) => {
        release = () => (answer === "net" ? reject(new TypeError("Failed to fetch")) : resolve(answer()));
      });
    const s = setup({ answers: [pending] });
    await record(s);
    assert.equal(s.f.calls.length, 1);
    const names = s.u.names();
    assert.equal(names[names.length - 1], "recognizing", names.join(","));
    release();
    await flush();
    const after = s.u.names();
    assert.ok(after.length > names.length && after.slice(names.length).some((n) => n === "idle" || n === "offerRecognize"));
  }
});

test("after a refusal a new recording replaces the held one", async () => {
  const s = setup({
    answers: [() => fragment(502, NOT_RECOGNIZED), () => fragment(502, NOT_RECOGNIZED), () => json(200, { text: "світ" })],
  });
  await record(s);
  assert.equal(await bodyOf(s.f.calls[0]), "rec-1-a|rec-1-b");
  await record(s);
  assert.equal(s.instances.length, 2);
  assert.equal(await bodyOf(s.f.calls[1]), "rec-2-a|rec-2-b");
  s.rec.recognize();
  await flush();
  assert.equal(await bodyOf(s.f.calls[2]), "rec-2-a|rec-2-b");
});

test("I4: the same recording is sent after any refusal, in any order and any number of times", async () => {
  const refusals = {
    400: () => fragment(400, NOT_ACCEPTED),
    409: () => fragment(409, FIRST_CHOOSE),
    502: () => fragment(502, NOT_RECOGNIZED),
    net: "net",
    page: () => loginPage(),
    empty: () => json(200, { text: "" }),
  };
  const sequences = [
    ["400", "409", "502", "net", "page", "empty"],
    ["empty", "page", "net", "502", "409", "400"],
    ["502", "502", "502"],
    ["net", "empty", "net", "empty"],
    ["page"],
    [],
  ];
  for (const seq of sequences) {
    const answers = seq.map((k) => refusals[k]);
    answers.push(() => json(200, { text: "світ" }));
    const s = setup({ answers });
    await record(s);
    for (let i = 0; i < seq.length; i++) {
      const names = s.u.names();
      assert.equal(names[names.length - 1] === "recognizing", false, `${seq}: stuck on recognizing after ${seq[i]}`);
      assert.ok(names.lastIndexOf("offerRecognize") > names.lastIndexOf("recognizing"), `${seq}: no offer after ${seq[i]}`);
      assert.ok(!names.includes("insertText"), `${seq}: text inserted after ${seq[i]}`);
      s.rec.recognize();
      await flush();
    }
    assert.equal(s.f.calls.length, seq.length + 1, String(seq));
    for (const call of s.f.calls) {
      assert.equal(await bodyOf(call), "rec-1-a|rec-1-b", String(seq));
      assert.equal(typeOf(call), WEBM);
    }
    assert.deepEqual(
      s.u.calls.filter((c) => c[0] === "insertText"),
      [["insertText", "світ"]],
      String(seq),
    );
  }
});
