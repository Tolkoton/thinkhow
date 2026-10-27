// Fakes for the conversation-resilience page tests (slice tester), grown from the conversation-loop fakes. Built
// from the contract, not the code. conversation.js is loaded as the page loads it (vm context = the window), so
// attach(document, window) runs. Added for S2b: oscillators and gains with recorded AudioParams (a tone is told
// apart by the first frequency of its oscillator), ctx `statechange` and a resume() that can fail, microphone
// tracks that can end, navigator.wakeLock with sentinels, document visibility, timeouts of 1 s and longer held
// for the test, /retry, /speak and decodeAudioData failing per call, and a reply stream the test feeds by hand.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const SRC_PATH = path.resolve(here, "../../../src/thinkhow/web/static/conversation.js");
const SRC = fs.readFileSync(SRC_PATH, "utf8");
const realSetTimeout = globalThis.setTimeout;
const realClearTimeout = globalThis.clearTimeout;

export const WEBM = "audio/webm;codecs=opus";
export const NO_WORDS = "Не почули слів — спробуйте ще раз.";
export const NO_MIC = "Немає доступу до мікрофона.";

// tone bands (Q1): ±8 % around the frequencies the contract names
export const BAND = { listening: [810, 950], tick: [607, 713], errorHigh: [405, 475], errorLow: [304, 356] };

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
      if (k.startsWith("data-")) el.dataset[k.slice(5)] = String(v);
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

export function emit(obj, type, ev = {}) {
  const e = { type, target: obj, currentTarget: obj, preventDefault() {}, ...ev };
  for (const fn of [...((obj.listeners && obj.listeners[type]) || [])]) fn(e);
  if (typeof obj["on" + type] === "function") obj["on" + type](e);
}

export function fire(el, type) {
  emit(el, type);
}

// an AudioParam: every value set (directly or by automation) is recorded in order
export function audioParam(initial) {
  const param = {
    events: [],
    _value: initial,
    get value() {
      return this._value;
    },
    set value(v) {
      this._value = v;
      this.events.push({ v, t: null, kind: "value" });
    },
    setValueAtTime(v, t) {
      this.events.push({ v, t, kind: "set" });
      return this;
    },
    linearRampToValueAtTime(v, t) {
      this.events.push({ v, t, kind: "linear" });
      return this;
    },
    exponentialRampToValueAtTime(v, t) {
      this.events.push({ v, t, kind: "exp" });
      return this;
    },
    setTargetAtTime(v, t) {
      this.events.push({ v, t, kind: "target" });
      return this;
    },
    setValueCurveAtTime(values, t) {
      for (const v of values) this.events.push({ v, t, kind: "curve" });
      return this;
    },
    cancelScheduledValues() {
      return this;
    },
    cancelAndHoldAtTime() {
      return this;
    },
  };
  return param;
}

const firstValue = (param, fallback) => (param.events.length ? param.events[0].v : fallback);
export const peak = (param) => (param.events.length ? Math.max(...param.events.map((e) => e.v)) : param.value);

function node(ctx, kind, extra = {}) {
  const n = {
    kind,
    ctx,
    connected: [],
    connect(x) {
      this.connected.push(x);
      return x;
    },
    disconnect() {},
    ...extra,
  };
  return n;
}

// a fake AudioContext usable alone (createEarcons) or by the page
export function makeAudioContext(p = {}) {
  return class FakeAudioContext {
    constructor() {
      if (p.ctxs) p.ctxs.push(this);
      this.state = "suspended";
      this.resumed = 0;
      this.closed = false;
      this.destination = { kind: "destination", connected: [] };
      this.currentTime = 5;
      this.sources = [];
      this.analysers = [];
      this.streamSources = [];
      this.oscillators = [];
      this.gains = [];
      this.listeners = {};
      this.onstatechange = null;
    }
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    }
    removeEventListener(type, fn) {
      this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
    }
    resume() {
      this.resumed++;
      if (p.resumeWorks !== false && this.state !== "closed") {
        const changed = this.state !== "running";
        this.state = "running";
        if (changed) queueMicrotask(() => emit(this, "statechange"));
      }
      return Promise.resolve();
    }
    close() {
      this.closed = true;
      this.state = "closed";
      return Promise.resolve();
    }
    createMediaStreamSource(stream) {
      const n = node(this, "stream-source", { stream });
      this.streamSources.push(n);
      return n;
    }
    createAnalyser() {
      const a = {
        kind: "analyser",
        fftSize: 2048,
        connected: [],
        get frequencyBinCount() {
          return this.fftSize / 2;
        },
        connect(x) {
          this.connected.push(x);
          return x;
        },
        disconnect() {},
        getFloatTimeDomainData(arr) {
          for (let i = 0; i < arr.length; i++) arr[i] = (i % 2 ? -1 : 1) * (p.level || 0);
        },
        getByteTimeDomainData(arr) {
          for (let i = 0; i < arr.length; i++) {
            arr[i] = Math.max(0, Math.min(255, Math.round(128 + (i % 2 ? -1 : 1) * (p.level || 0) * 128)));
          }
        },
      };
      this.analysers.push(a);
      return a;
    }
    createGain() {
      const g = node(this, "gain", { gain: audioParam(1) });
      this.gains.push(g);
      return g;
    }
    createOscillator() {
      const ctx = this;
      const o = node(this, "oscillator", {
        type: "sine",
        frequency: audioParam(440),
        detune: audioParam(0),
        listeners: {},
        onended: null,
        startCalls: [],
        stopCalls: [],
        addEventListener(type, fn) {
          (this.listeners[type] ||= []).push(fn);
        },
        removeEventListener() {},
        start(when) {
          this.startCalls.push(when === undefined ? ctx.currentTime : when);
        },
        stop(when) {
          this.stopCalls.push(when === undefined ? ctx.currentTime : when);
        },
      });
      this.oscillators.push(o);
      return o;
    }
    decodeAudioData(buf, ok, err) {
      const index = p.decodes === undefined ? 0 : p.decodes++;
      const fails = p.decodeFailAt && p.decodeFailAt.has(index);
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
      const src = {
        buffer: null,
        connected: [],
        listeners: {},
        onended: null,
        started: false,
        stopped: false,
        ended: false,
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
        },
        stop() {
          this.stopped = true;
        },
      };
      this.sources.push(src);
      return src;
    }
  };
}

// the first frequency of an oscillator tells its tone apart
export const freq0 = (o) => firstValue(o.frequency, 440);
const inBand = (f, [lo, hi]) => f >= lo && f <= hi;
export const oscillators = (p) => p.ctxs.flatMap((c) => c.oscillators).filter((o) => o.startCalls.length > 0);
export const tones = (p, band) => oscillators(p).filter((o) => inBand(freq0(o), band)).length;
export const listeningTones = (p) => tones(p, BAND.listening);
export const tickTones = (p) => tones(p, BAND.tick);
export const errorTones = (p) => tones(p, BAND.errorHigh);

export const json = (obj, status = 200) => () =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
export const fragment = (text, status) => () =>
  new Response(`<p class="error">${text}</p>`, { status, headers: { "content-type": "text/html; charset=utf-8" } });
export const offline = () => () => Promise.reject(new TypeError("Failed to fetch"));
const frame = (e, d) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`;
export const sse = (events) => () =>
  new Response(events.map(([e, d]) => frame(e, d)).join(""), {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
export const reply = (...deltas) =>
  sse([["saved", {}], ...deltas.map((t) => ["delta", { text: t }]), ["answered", {}]]);
export const failedReply = (...deltas) =>
  sse([["saved", {}], ...deltas.map((t) => ["delta", { text: t }]), ["failed", {}]]);
export const audioOk = () => () =>
  new Response(new Uint8Array([0xff, 0xf3, 1, 2, 3]), { status: 200, headers: { "content-type": "audio/mpeg" } });

// a reply stream the test feeds: s.respond is the planned answer; s.delta(t), s.answered(), s.failed()
export function liveReply() {
  let ctl;
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(c) {
      ctl = c;
    },
  });
  const s = {
    respond: () => {
      ctl.enqueue(enc.encode(frame("saved", {})));
      return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
    },
    delta(t) {
      ctl.enqueue(enc.encode(frame("delta", { text: t })));
    },
    answered() {
      ctl.enqueue(enc.encode(frame("answered", {})));
      ctl.close();
    },
    failed() {
      ctl.enqueue(enc.encode(frame("failed", {})));
      ctl.close();
    },
  };
  return s;
}

export function loadPage({ wake = true, refuseWake = false, supported = [WEBM, "audio/mp4"] } = {}) {
  const p = {
    level: 0,
    clock: { t: 1000 },
    ctxs: [],
    recorders: [],
    gum: [],
    streams: [],
    intervals: [],
    timeouts: [],
    marks: [],
    reloads: 0,
    calls: [],
    voice: [],
    reply: [],
    retry: [],
    speak: [],
    denyMic: false,
    resumeWorks: true,
    decodes: 0,
    decodeFailAt: new Set(),
    wakeRequests: [],
    sentinels: [],
    refuseWake,
  };
  const byId = {};
  for (const id of ["reply-form", "send", "retry", "live", "error", "mic", "recognize", "mic-state", "talk", "talk-resume"]) {
    byId[id] = element(id, id === "reply-form" ? "form" : id === "live" ? "div" : "button");
  }
  const field = element("", "textarea");
  const form = byId["reply-form"];
  form.dataset.key = "draft:alice-1/t-0123456789ab";
  form.dataset.voice = "yes";
  form.querySelector = (sel) => (sel === "textarea" || sel === "[name=text]" || sel === 'textarea[name="text"]' ? field : null);
  byId.retry.hidden = true;
  byId.recognize.hidden = true;
  byId.talk.hidden = true;
  byId["talk-resume"].hidden = true;
  byId.talk.ariaPressed = "false";
  byId.talk.stateLog.length = 0;
  p.byId = byId;
  p.field = field;
  p.talk = byId.talk;
  p.resumeButton = byId["talk-resume"];

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
    }
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    }
    removeEventListener() {}
    start() {
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

  const navigator = {
    mediaDevices: {
      getUserMedia: async (constraints) => {
        p.gum.push(constraints);
        if (p.denyMic) throw new DOMException("Permission denied", "NotAllowedError");
        const track = {
          kind: "audio",
          readyState: "live",
          stopped: false,
          listeners: {},
          onended: null,
          addEventListener(type, fn) {
            (this.listeners[type] ||= []).push(fn);
          },
          removeEventListener(type, fn) {
            this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
          },
          stop() {
            this.stopped = true;
            this.readyState = "ended";
          },
        };
        const stream = { tracks: [track], getTracks: () => [track], getAudioTracks: () => [track], active: true };
        p.streams.push(stream);
        return stream;
      },
    },
  };
  if (wake) {
    navigator.wakeLock = {
      request(type) {
        p.wakeRequests.push(type);
        if (p.refuseWake) return Promise.reject(new DOMException("Not allowed", "NotAllowedError"));
        const sentinel = {
          type,
          released: false,
          releaseCalls: 0,
          listeners: {},
          onrelease: null,
          addEventListener(t, fn) {
            (this.listeners[t] ||= []).push(fn);
          },
          removeEventListener(t, fn) {
            this.listeners[t] = (this.listeners[t] || []).filter((f) => f !== fn);
          },
          release() {
            this.releaseCalls++;
            if (!this.released) {
              this.released = true;
              emit(this, "release");
            }
            return Promise.resolve();
          },
        };
        p.sentinels.push(sentinel);
        return Promise.resolve(sentinel);
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
      if (u.endsWith("/speak") && p.speak.length === 0) return Promise.resolve().then(audioOk());
      const a = queue && queue.shift();
      if (!a) return Promise.reject(new Error("fetch not planned by the test: " + u));
      return Promise.resolve().then(a);
    },
    // timeouts under 1 s run for real; 1 s and longer wait for runTimeouts(p)
    setTimeout: (fn, ms = 0, ...args) => {
      if (ms < 1000) return realSetTimeout(fn, ms, ...args);
      const id = nextId++;
      p.timeouts.push({ id, fn: () => fn(...args), ms, cleared: false, done: false });
      return id;
    },
    clearTimeout: (id) => {
      const held = p.timeouts.find((t) => t.id === id);
      if (held) held.cleared = true;
      else if (id !== undefined && id !== null && typeof id !== "number") realClearTimeout(id);
    },
    setInterval: (fn, ms) => {
      const id = 100000 + nextId++;
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
  win.AudioContext = makeAudioContext(p);
  win.window = win;
  const docListeners = {};
  const doc = {
    visibilityState: "visible",
    hidden: false,
    listeners: docListeners,
    onvisibilitychange: null,
    addEventListener(type, fn) {
      (docListeners[type] ||= []).push(fn);
    },
    removeEventListener(type, fn) {
      docListeners[type] = (docListeners[type] || []).filter((f) => f !== fn);
    },
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
  win.document = doc;
  p.doc = doc;
  vm.runInContext(SRC, vm.createContext(win));
  return p;
}

// the frame interval of the page (under 1 s), driven by the test: each tick moves the clock by 50 ms
export function tick(p, level, n = 1) {
  for (let i = 0; i < n; i++) {
    p.clock.t += 50;
    p.level = level;
    for (const iv of p.intervals) if (!iv.cleared && iv.ms < 1000) iv.fn();
  }
  return p.clock.t;
}

// the intervals of 1 s and longer (the tick of thinking) fire once each
export const slowIntervals = (p) => p.intervals.filter((i) => !i.cleared && i.ms >= 1000);
export function fireSlow(p) {
  p.clock.t += 10000;
  for (const iv of slowIntervals(p)) iv.fn();
}

// every held timeout (1 s and longer) that is due runs once
export async function runTimeouts(p) {
  for (const t of p.timeouts) {
    if (!t.cleared && !t.done) {
      t.done = true;
      t.fn();
    }
  }
  await flush();
}

export const calibrate = (p) => tick(p, 0.01, 8);
export const loud = (p) => tick(p, 0.3, 8);
export const silence = (p) => tick(p, 0.01, 36);

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
export const retryCalls = (p) => p.calls.filter((c) => c.url.endsWith("/retry"));
export const speakCalls = (p) => p.calls.filter((c) => c.url.endsWith("/speak"));

export function formText(init, name = "text") {
  const b = init.body;
  if (b === undefined || b === null) return null;
  if (typeof b === "string") return new URLSearchParams(b).get(name);
  return b.get(name);
}

export const spokenTexts = (p) => speakCalls(p).map((c) => formText(c.init));
export const sources = (p) => p.ctxs.flatMap((c) => c.sources);
export const playing = (p) => sources(p).filter((s) => s.started && !s.ended && !s.stopped);

export async function endAudio(p) {
  const s = playing(p)[0];
  if (!s) throw new Error("no sound is playing");
  s.ended = true;
  emit(s, "ended");
  await flush();
}

export async function playAll(p, max = 200) {
  for (let i = 0; i < max && playing(p).length > 0; i++) await endAudio(p);
}

export const live = (p) => p.byId.live.children.map((c) => ({ cls: c.className, text: c.textContent }));
export const recording = (p) => p.recorders.filter((r) => r.state === "recording");

export async function tapTalk(p) {
  fire(p.talk, "click");
  await flush();
}

// the microphone track of stream i ends (the system took the microphone)
export async function endTrack(p, i) {
  for (const t of p.streams[i].getTracks()) {
    t.readyState = "ended";
    emit(t, "ended");
  }
  await flush();
}

export async function ctxState(p, value) {
  const ctx = p.ctxs[0];
  ctx.state = value;
  emit(ctx, "statechange");
  await flush();
}

export async function visibility(p, value) {
  p.doc.visibilityState = value;
  p.doc.hidden = value !== "visible";
  emit(p.doc, "visibilitychange");
  await flush();
}

export const collapse = (s) => s.replace(/\s+/g, " ").trim();
export const noSpace = (s) => s.replace(/\s+/g, "");
