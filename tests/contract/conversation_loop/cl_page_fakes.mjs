// Fakes for the conversation-loop page tests (slice tester). Built from the contract, not the code.
// conversation.js is loaded as the page loads it (vm context = the window), so attach(document, window) runs.
// The window has: a fake AudioContext (the analyser gives the level the test sets, as float and as byte
// waveforms of that RMS; decodeAudioData in promise and callback form; buffer sources fire `ended` on demand),
// a fake MediaRecorder (state "inactive" at once on stop(), then `dataavailable` and `stop` in tasks of their
// own, as a browser does), getUserMedia, fetch routed by the end of the URL, setInterval driven by the test
// (tick), performance.now = the test's clock, performance.mark recorded, location.reload counted.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"), "utf8");
const realSetTimeout = globalThis.setTimeout;

export const WEBM = "audio/webm;codecs=opus";
export const STOPPED = "Режим розмови зупинено — спробуйте ще раз.";

export async function flush(n = 60) {
  for (let i = 0; i < n; i++) await new Promise((r) => realSetTimeout(r, 0));
}

function element(id, tag = "div") {
  const attributes = {};
  const listeners = {};
  const el = {
    id,
    tagName: tag.toUpperCase(),
    value: "",
    textContent: "",
    className: "",
    attributes,
    listeners,
    children: [],
    stateLog: [],
    addEventListener(type, fn) {
      (listeners[type] ||= []).push(fn);
    },
    removeEventListener(type, fn) {
      listeners[type] = (listeners[type] || []).filter((f) => f !== fn);
    },
    appendChild(c) {
      el.children.push(c);
      c.parentNode = el;
      return c;
    },
    append(...cs) {
      for (const c of cs) el.appendChild(typeof c === "string" ? Object.assign(element(""), { textContent: c }) : c);
    },
    setAttribute(k, v) {
      if (k === "data-state") el.dataset.state = String(v);
      else if (k.startsWith("data-")) el.dataset[k.slice(5)] = String(v);
      else attributes[k] = String(v);
    },
    getAttribute(k) {
      if (k.startsWith("data-")) return el.dataset[k.slice(5)] ?? null;
      return k in attributes ? attributes[k] : null;
    },
    removeAttribute(k) {
      if (k.startsWith("data-")) delete el.dataset[k.slice(5)];
      else delete attributes[k];
    },
    hasAttribute(k) {
      return el.getAttribute(k) !== null;
    },
    toggleAttribute(k, force) {
      const on = force === undefined ? !el.hasAttribute(k) : force;
      if (on) el.setAttribute(k, "");
      else el.removeAttribute(k);
      return on;
    },
    querySelector: () => null,
  };
  for (const name of ["hidden", "disabled"]) {
    Object.defineProperty(el, name, {
      get: () => name in attributes,
      set: (v) => (v ? (attributes[name] = "") : delete attributes[name]),
    });
  }
  Object.defineProperty(el, "ariaPressed", {
    get: () => attributes["aria-pressed"] ?? null,
    set: (v) => (attributes["aria-pressed"] = String(v)),
  });
  Object.defineProperty(el, "className", {
    get: () => attributes.class ?? "",
    set: (v) => (attributes.class = String(v)),
  });
  el.classList = {
    add: (...cs) => (el.className = [...new Set([...el.className.split(/\s+/).filter(Boolean), ...cs])].join(" ")),
    remove: (...cs) => (el.className = el.className.split(/\s+/).filter((c) => c && !cs.includes(c)).join(" ")),
    contains: (c) => el.className.split(/\s+/).includes(c),
    toggle: (c, f) => {
      const on = f === undefined ? !el.classList.contains(c) : f;
      if (on) el.classList.add(c);
      else el.classList.remove(c);
      return on;
    },
  };
  el.dataset = new Proxy(
    {},
    {
      set(target, key, value) {
        target[key] = String(value);
        if (key === "state") el.stateLog.push(String(value));
        return true;
      },
    },
  );
  return el;
}

export function fire(el, type) {
  const ev = { type, preventDefault() {}, target: el, currentTarget: el };
  for (const fn of el.listeners[type] || []) fn(ev);
  if (typeof el["on" + type] === "function") el["on" + type](ev);
}

function emit(obj, type, ev) {
  for (const fn of (obj.listeners && obj.listeners[type]) || []) fn(ev);
  if (typeof obj["on" + type] === "function") obj["on" + type](ev);
}

export const json = (obj, status = 200) => () =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
export const fragment = (text, status) => () =>
  new Response(`<p class="error">${text}</p>`, { status, headers: { "content-type": "text/html; charset=utf-8" } });
export const sse = (events) => () =>
  new Response(events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join(""), {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
export const reply = (...deltas) =>
  sse([["saved", {}], ...deltas.map((t) => ["delta", { text: t }]), ["answered", {}]]);
const mp3 = () =>
  new Response(new Uint8Array([0xff, 0xf3, 1, 2, 3]), { status: 200, headers: { "content-type": "audio/mpeg" } });

export function loadPage({ voice = "yes", audio = true, media = true, supported = [WEBM, "audio/mp4"] } = {}) {
  const p = {
    level: 0,
    clock: { t: 1000 },
    ctxs: [],
    recorders: [],
    gum: [],
    streams: [],
    intervals: [],
    marks: [],
    reloads: 0,
    calls: [],
    voice: [],
    reply: [],
    speak: [],
    retry: [],
    denyMic: false,
    decodeFails: false,
  };
  const byId = {};
  for (const id of ["reply-form", "send", "retry", "live", "error", "mic", "recognize", "mic-state", "talk"]) {
    byId[id] = element(id, id === "reply-form" ? "form" : id === "live" ? "div" : "button");
  }
  const field = element("", "textarea");
  const form = byId["reply-form"];
  form.dataset.key = "draft:alice-1/t-0123456789ab";
  form.dataset.voice = voice;
  form.querySelector = (sel) => (sel === "textarea" || sel === "[name=text]" || sel === 'textarea[name="text"]' ? field : null);
  byId.retry.hidden = true;
  byId.recognize.hidden = true;
  byId.talk.hidden = true;
  byId.talk.ariaPressed = "false";
  byId.talk.stateLog.length = 0;
  p.byId = byId;
  p.field = field;
  p.talk = byId.talk;

  class FakeAudioContext {
    constructor() {
      p.ctxs.push(this);
      this.state = "suspended";
      this.resumed = 0;
      this.closed = false;
      this.destination = { kind: "destination" };
      this.currentTime = 0;
      this.sources = [];
      this.analysers = [];
      this.streamSources = [];
    }
    resume() {
      this.resumed++;
      this.state = "running";
      return Promise.resolve();
    }
    close() {
      this.closed = true;
      this.state = "closed";
      return Promise.resolve();
    }
    createMediaStreamSource(stream) {
      const node = {
        stream,
        connected: [],
        connect(x) {
          this.connected.push(x);
          return x;
        },
        disconnect() {},
      };
      this.streamSources.push(node);
      return node;
    }
    createAnalyser() {
      const a = {
        fftSize: 2048,
        get frequencyBinCount() {
          return this.fftSize / 2;
        },
        connect: (x) => x,
        disconnect() {},
        getFloatTimeDomainData(arr) {
          for (let i = 0; i < arr.length; i++) arr[i] = (i % 2 ? -1 : 1) * p.level;
        },
        getByteTimeDomainData(arr) {
          for (let i = 0; i < arr.length; i++) {
            arr[i] = Math.max(0, Math.min(255, Math.round(128 + (i % 2 ? -1 : 1) * p.level * 128)));
          }
        },
      };
      this.analysers.push(a);
      return a;
    }
    createGain() {
      return { gain: { value: 1 }, connect: (x) => x, disconnect() {} };
    }
    decodeAudioData(buf, ok, err) {
      const fails = p.decodeFails;
      const result = fails
        ? Promise.reject(new DOMException("Unable to decode audio data", "EncodingError"))
        : Promise.resolve({ duration: 1, length: 24000, sampleRate: 24000, numberOfChannels: 1 });
      result.then(
        (b) => ok && ok(b),
        (e) => err && err(e),
      );
      if (ok || err) result.catch(() => {});
      return result;
    }
    createBufferSource() {
      const ctx = this;
      const src = {
        buffer: null,
        connected: [],
        listeners: {},
        onended: null,
        started: false,
        stopped: false,
        ended: false,
        startedAt: null,
        connect(x) {
          this.connected.push(x);
          return x;
        },
        disconnect() {},
        addEventListener(type, fn) {
          (this.listeners[type] ||= []).push(fn);
        },
        removeEventListener() {},
        start() {
          this.started = true;
          this.startedAt = p.clock.t;
        },
        stop() {
          this.stopped = true;
        },
      };
      ctx.sources.push(src);
      return src;
    }
  }

  class FakeRecorder {
    static isTypeSupported(type) {
      return supported.includes(type);
    }
    constructor(stream, options) {
      p.recorders.push(this);
      this.stream = stream;
      this.options = options || {};
      this.mimeType = this.options.mimeType || "";
      this.state = "inactive";
      this.listeners = {};
      this.ondataavailable = null;
      this.onstop = null;
      this.startCalls = 0;
    }
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    }
    removeEventListener() {}
    start() {
      this.startCalls++;
      this.state = "recording";
    }
    stop() {
      if (this.state === "inactive") return;
      this.state = "inactive";
      realSetTimeout(() => {
        emit(this, "dataavailable", { data: new Blob(["rec"], { type: this.mimeType }) });
        realSetTimeout(() => emit(this, "stop", {}), 0);
      }, 0);
    }
  }

  const navigator = {};
  if (media) {
    navigator.mediaDevices = {
      getUserMedia: async (constraints) => {
        p.gum.push(constraints);
        if (p.denyMic) throw new DOMException("Permission denied", "NotAllowedError");
        const track = { kind: "audio", stopped: false, stop() {
          this.stopped = true;
        } };
        const stream = { tracks: [track], getTracks: () => [track], getAudioTracks: () => [track] };
        p.streams.push(stream);
        return stream;
      },
    };
  }

  let nextId = 1;
  const win = {
    navigator,
    MediaRecorder: FakeRecorder,
    fetch: (url, init = {}) => {
      p.calls.push({ url: String(url), init });
      const u = String(url);
      const queue = u.endsWith("/voice")
        ? p.voice
        : u.endsWith("/speak")
          ? p.speak
          : u.endsWith("/reply")
            ? p.reply
            : u.endsWith("/retry")
              ? p.retry
              : null;
      if (u.endsWith("/speak") && p.speak.length === 0) return Promise.resolve().then(mp3);
      const a = queue && queue.shift();
      if (!a) return Promise.reject(new Error("fetch not planned by the test: " + u));
      return Promise.resolve().then(a);
    },
    setTimeout: (fn, ms) => (ms >= 1000 ? nextId++ : realSetTimeout(fn, ms)),
    clearTimeout() {},
    setInterval: (fn, ms) => {
      const id = 1000 + nextId++;
      p.intervals.push({ id, fn, ms, cleared: false });
      return id;
    },
    clearInterval: (id) => {
      for (const i of p.intervals) if (i.id === id) i.cleared = true;
    },
    performance: {
      now: () => p.clock.t,
      mark: (name, options) => {
        p.marks.push({ name, startTime: options ? options.startTime : undefined });
        return { name, startTime: options ? options.startTime : p.clock.t };
      },
    },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    location: {
      reload() {
        p.reloads++;
      },
    },
    console,
    Blob,
    Response,
    Headers,
    FormData,
    ReadableStream,
    TextDecoder,
    TextEncoder,
    URLSearchParams,
    DOMException,
    Float32Array,
    Uint8Array,
    queueMicrotask,
  };
  if (audio) win.AudioContext = FakeAudioContext;
  win.window = win;
  win.document = {
    getElementById: (id) => byId[id] || null,
    createElement: (tag) => element("", tag),
    querySelector: (sel) => {
      const m = /^#([\w-]+)(?:\[data-([\w-]+)="([^"]*)"\])?$/.exec(sel);
      if (!m) return null;
      const el = byId[m[1]];
      if (!el) return null;
      if (m[2] && el.dataset[m[2]] !== m[3]) return null;
      return el;
    },
  };
  vm.runInContext(SRC, vm.createContext(win));
  return p;
}

// the interval of the page, driven by the test: each tick moves the clock by 50 ms and gives one frame
export function tick(p, level, n = 1) {
  for (let i = 0; i < n; i++) {
    p.clock.t += 50;
    p.level = level;
    for (const iv of p.intervals) if (!iv.cleared) iv.fn();
  }
  return p.clock.t;
}

export const calibrate = (p) => tick(p, 0.01, 8); // 400 ms of a quiet room
export const loud = (p) => tick(p, 0.3, 8); // 400 ms of speech; returns the t of its last frame
export const silence = (p) => tick(p, 0.01, 36); // 1800 ms of quiet

// one utterance from the start of listening; returns the t of its last frame with speech
export async function utter(p) {
  calibrate(p);
  const last = loud(p);
  silence(p);
  await flush();
  return last;
}

export function state(p) {
  return p.talk.dataset.state ?? "";
}

export const voiceCalls = (p) => p.calls.filter((c) => c.url.endsWith("/voice"));
export const replyCalls = (p) => p.calls.filter((c) => c.url.endsWith("/reply"));
export const speakCalls = (p) => p.calls.filter((c) => c.url.endsWith("/speak"));
export const retryCalls = (p) => p.calls.filter((c) => c.url.endsWith("/retry"));

export function formText(init, name = "text") {
  const b = init.body;
  if (typeof b === "string") return new URLSearchParams(b).get(name);
  return b.get(name);
}

export function contentType(init) {
  const h = init.headers || {};
  if (h instanceof Headers) return h.get("content-type");
  for (const k of Object.keys(h)) if (k.toLowerCase() === "content-type") return h[k];
  return null;
}

export const sources = (p) => p.ctxs.flatMap((c) => c.sources);
export const playing = (p) => sources(p).filter((s) => s.started && !s.ended && !s.stopped);

// the sound of the sentence now playing ends
export async function endAudio(p) {
  const s = playing(p)[0];
  if (!s) throw new Error("no sound is playing");
  s.ended = true;
  emit(s, "ended", { type: "ended", target: s });
  await flush();
}

// let every queued sentence play to its end (at most `max`)
export async function playAll(p, max = 60) {
  for (let i = 0; i < max && playing(p).length > 0; i++) await endAudio(p);
}

export const live = (p) => p.byId.live.children.map((c) => ({ cls: c.className, text: c.textContent }));
export const recording = (p) => p.recorders.filter((r) => r.state === "recording");

export async function tapTalk(p) {
  fire(p.talk, "click");
  await flush();
}
