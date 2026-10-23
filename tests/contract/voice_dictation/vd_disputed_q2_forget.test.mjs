// Disputed (Q2): what «"останній запис» забувається» looks like from outside createRecorder.
// The contract says the recording is forgotten after a 200 with text, but not what recognize() does when
// nothing is held. Reading taken (Q2): it sends nothing — no POST at all. Not sealed until the slice planner
// answers Q2.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createRecorder } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const realSetTimeout = globalThis.setTimeout;
const tick = () => new Promise((r) => realSetTimeout(r, 0));
async function flush(n = 20) {
  for (let i = 0; i < n; i++) await tick();
}

class FakeRecorder {
  static isTypeSupported() {
    return true;
  }
  constructor(stream, options) {
    this.state = "inactive";
    this.mimeType = options && options.mimeType ? options.mimeType : "";
    this.ondataavailable = null;
    this.onstop = null;
    this.listeners = {};
  }
  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }
  removeEventListener() {}
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
      this._emit("dataavailable", { data: new Blob(["rec"], { type: this.mimeType }) });
      realSetTimeout(() => this._emit("stop", {}), 0);
    }, 0);
  }
}

test("Q2: after a 200 with text the recording is forgotten — recognize() posts nothing", async () => {
  const calls = [];
  const ui = new Proxy({}, { get: (_, n) => (typeof n === "string" && n !== "then" ? () => {} : undefined) });
  const tracks = [{ stop() {} }];
  const rec = createRecorder({
    media: { getUserMedia: async () => ({ getTracks: () => tracks }) },
    Recorder: FakeRecorder,
    fetch: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ text: "світ" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
    ui,
    url: "/topics/alice-1/t-0123456789ab/voice",
    limitMs: 5000,
    setTimeout: () => 1,
    clearTimeout: () => {},
  });
  await rec.start();
  await flush();
  rec.stop();
  await flush();
  assert.equal(calls.length, 1);
  try {
    await rec.recognize();
  } catch {
    // nothing held: refusing is allowed, sending is not
  }
  await flush();
  assert.equal(calls.length, 1);
});
