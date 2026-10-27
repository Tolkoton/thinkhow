// The conversation page: SSE over fetch POST, the draft kept until the server saved the turn (skel-web).
// Text reaches the page through textContent only.
"use strict";

// Bytes in → complete events out; an event ends with an empty line; data is one JSON line.
function createSseParser() {
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let event = null;
  let data = null;

  function field(line, name) {
    if (!line.startsWith(name + ":")) return null;
    const value = line.slice(name.length + 1);
    return value.startsWith(" ") ? value.slice(1) : value;
  }

  function takeLine(line, out) {
    if (line === "") {
      if (event !== null && data !== null) out.push({ event, data: JSON.parse(data) });
      event = null;
      data = null;
      return;
    }
    const name = field(line, "event");
    if (name !== null) event = name;
    const value = field(line, "data");
    if (value !== null) data = value;
  }

  return {
    push(bytes) {
      buffer += decoder.decode(bytes, { stream: true });
      const out = [];
      let at = buffer.indexOf("\n");
      while (at >= 0) {
        takeLine(buffer.slice(0, at).replace(/\r$/, ""), out);
        buffer = buffer.slice(at + 1);
        at = buffer.indexOf("\n");
      }
      return out;
    },
  };
}

// The draft and the buttons: send(text) for «Надіслати», retry() for «Спробуйте ще раз».
function createController({ fetch, storage, ui, key }) {
  const name = key.startsWith("draft:") ? key : "draft:" + key;
  const base = "/topics/" + name.slice("draft:".length);
  const draft = storage.getItem(name);
  if (draft !== null) ui.setDraft(draft);

  function errorText(body) {
    return body.replace(/<[^>]*>/g, "").trim();
  }

  async function run(url, body) {
    ui.disable();
    let response;
    try {
      response = await fetch(url, { method: "POST", body });
    } catch (e) {
      ui.enable();
      ui.showRetry();
      return;
    }
    const type = response.headers.get("content-type") || "";
    if (!response.ok || !type.startsWith("text/event-stream")) {
      ui.showError(errorText(await response.text()));
      ui.enable();
      return;
    }
    const parser = createSseParser();
    const reader = response.body.getReader();
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const { event, data } of parser.push(value)) {
          if (event === "saved") storage.removeItem(name);
          else if (event === "delta") ui.appendDelta(data.text);
          else if (event === "answered") return ui.reload();
          else if (event === "failed") {
            ui.enable();
            return ui.showRetry();
          }
        }
      }
    } catch (e) {
      // a broken stream ends like a stream without its last event
    }
    ui.enable();
    ui.showRetry();
  }

  return {
    send(text, fields = {}) {
      storage.setItem(name, text);
      return run(base + "/reply", new URLSearchParams({ text, ...fields }));
    },
    retry() {
      return run(base + "/retry", new URLSearchParams());
    },
  };
}

// The microphone: record → send the recording → the text into the field; the recording stays until text came (F13).
// The recorder's last chunk and its `stop` event come after recorder.stop() returns, so the Blob is built there.
function createRecorder({ media, Recorder, fetch, ui, url, limitMs, setTimeout, clearTimeout }) {
  const TYPES = ["audio/webm;codecs=opus", "audio/mp4"];
  const NOT_SENT = "Не вдалося надіслати запис — спробуйте ще раз; якщо не вийде, увійдіть знову в новій вкладці.";
  let recorder = null;
  let timer = null;
  let held = null;
  let busy = false; // from start until the text came or recognition failed: «Надіслати» must wait

  function options() {
    const mimeType = TYPES.find((t) => Recorder.isTypeSupported(t));
    return mimeType ? { mimeType, audioBitsPerSecond: 64000 } : { audioBitsPerSecond: 64000 };
  }

  function listen(rec, stream) {
    const chunks = [];
    rec.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size !== 0) chunks.push(e.data);
    });
    rec.addEventListener("stop", () => {
      for (const track of stream.getTracks()) track.stop();
      held = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      recognize();
    });
  }

  async function start() {
    let stream;
    try {
      stream = await media.getUserMedia({ audio: true });
    } catch (e) {
      ui.showError("Немає доступу до мікрофона.");
      return;
    }
    recorder = new Recorder(stream, options());
    listen(recorder, stream);
    recorder.start();
    busy = true;
    ui.recording();
    timer = setTimeout(stop, limitMs);
  }

  function stop() {
    if (!recorder || recorder.state !== "recording") return;
    clearTimeout(timer);
    recorder.stop();
  }

  function fragmentText(body) {
    const m = /^\s*<p class="error">([\s\S]*)<\/p>\s*$/.exec(body);
    return m ? m[1].replace(/<[^>]*>/g, "").trim() : null;
  }

  async function answer(response) {
    const type = response.headers.get("content-type") || "";
    if (response.ok && type.startsWith("application/json")) {
      const { text } = await response.json();
      if (text) {
        held = null;
        ui.insertText(text);
        return ui.idle();
      }
      return ui.showError("Не почули слів — спробуйте ще раз.");
    }
    return ui.showError(fragmentText(await response.text()) || NOT_SENT);
  }

  async function recognize() {
    if (!held) return;
    busy = true;
    ui.recognizing();
    try {
      const response = await fetch(url, { method: "POST", body: held, headers: { "Content-Type": held.type } });
      await answer(response);
    } catch (e) {
      ui.showError(NOT_SENT);
    }
    busy = false;
    if (held) ui.offerRecognize();
  }

  return { start, stop, recognize, recording: () => !!recorder && recorder.state === "recording", busy: () => busy };
}

// The page: wire the form and the buttons to the controller.
function attach(doc, win) {
  const form = doc.getElementById("reply-form");
  if (!form) return;
  const field = form.querySelector("textarea");
  const send = doc.getElementById("send");
  const retry = doc.getElementById("retry");
  const live = doc.getElementById("live");
  const error = doc.getElementById("error");
  let answer = null;
  const ui = {
    disable() {
      for (const b of [send, retry]) if (b) b.disabled = true;
    },
    enable() {
      for (const b of [send, retry]) if (b) b.disabled = false;
    },
    appendDelta(text) {
      if (!answer) {
        answer = doc.createElement("p");
        answer.className = "turn model";
        live.appendChild(answer);
      }
      answer.textContent += text;
    },
    showRetry() {
      if (retry) retry.hidden = false;
    },
    showError(text) {
      error.textContent = text;
    },
    reload() {
      win.location.reload();
    },
    setDraft(text) {
      field.value = text;
    },
  };
  let talk = null; // while the conversation mode is on, the controller's answer goes to it, not to the page
  const modeUi = {
    disable() {},
    enable() {},
    appendDelta: (text) => talk.delta(text),
    reload: () => talk.finished(),
    showRetry: () => talk.failed(),
    showError: (text) => talk.failed(text),
    setDraft() {},
  };
  const routed = {};
  for (const k of Object.keys(ui)) routed[k] = (...a) => (talk && talk.state() !== "off" ? modeUi : ui)[k](...a);
  const controller = createController({
    fetch: win.fetch.bind(win),
    storage: win.localStorage,
    ui: routed,
    key: form.dataset.key,
  });
  if (retry) retry.addEventListener("click", () => controller.retry());
  const recorder = attachMic(doc, win, form, field, error);
  // While the microphone is busy «Надіслати» only stops the recording; the next press sends the text (task 206).
  talk = attachTalk(doc, win, form, field, controller, live, error);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (recorder && recorder.busy()) return recorder.stop();
    error.textContent = "";
    controller.send(field.value);
  });
}

// The conversation mode's button, shown only where Google has a voice for the person and the browser can do it.
function attachTalk(doc, win, form, field, controller, live, error) {
  const button = doc.getElementById("talk");
  const Context = win.AudioContext || win.webkitAudioContext;
  if (!button || form.dataset.voice !== "yes" || !Context || !win.navigator || !win.navigator.mediaDevices) return null;
  const controls = [doc.getElementById("mic"), doc.getElementById("send"), field].filter(Boolean);
  let answer = null;
  const ui = {
    state(name) {
      button.dataset.state = name;
      button.ariaPressed = name ? "true" : "false";
      for (const c of controls) c.disabled = !!name;
    },
    error(text) {
      error.textContent = text;
    },
    userTurn(text) {
      const p = doc.createElement("p");
      p.className = "turn user";
      p.textContent = text;
      live.appendChild(p);
      answer = null;
    },
    modelDelta(text) {
      if (!answer) {
        answer = doc.createElement("p");
        answer.className = "turn model";
        live.appendChild(answer);
      }
      answer.textContent += text;
    },
    reload() {
      win.location.reload();
    },
  };
  const key = form.dataset.key.slice("draft:".length);
  const talk = createTalk({
    media: win.navigator.mediaDevices,
    AudioContext: Context,
    Recorder: win.MediaRecorder,
    fetch: win.fetch.bind(win),
    controller,
    ui,
    voiceUrl: "/topics/" + key + "/voice",
    speakUrl: "/speak",
    setInterval: win.setInterval.bind(win),
    clearInterval: win.clearInterval.bind(win),
    now: () => win.performance.now(),
    mark: (name, t) => win.performance.mark(name, { startTime: t }),
  });
  button.hidden = false;
  button.addEventListener("click", () => {
    error.textContent = "";
    return talk.state() === "off" ? talk.start() : talk.stop();
  });
  return talk;
}

// The page's microphone: the buttons, the words of the state, and the field the text is appended to (I5).
// The words are for screen readers only; the eye sees the state on #mic itself: data-state (task 207).
function attachMic(doc, win, form, field, error) {
  const mic = doc.getElementById("mic");
  const again = doc.getElementById("recognize");
  const state = doc.getElementById("mic-state");
  if (!mic || !win.navigator || !win.navigator.mediaDevices) return null;
  const key = form.dataset.key;
  function show(name) {
    mic.dataset.state = name;
    mic.ariaPressed = name === "recording" ? "true" : "false";
  }
  const ui = {
    recording() {
      error.textContent = "";
      again.hidden = true;
      show("recording");
      state.textContent = "Запис… натисніть ще раз, щоб зупинити";
    },
    recognizing() {
      mic.disabled = again.disabled = true;
      show("recognizing");
      state.textContent = "Розпізнаю…";
    },
    insertText(text) {
      const before = field.value;
      field.value = before === "" || /[ \n]$/.test(before) ? before + text : before + " " + text;
    },
    idle() {
      mic.disabled = again.disabled = false;
      again.hidden = true;
      show("");
      state.textContent = "";
    },
    showError(text) {
      mic.disabled = again.disabled = false;
      show("");
      state.textContent = "";
      error.textContent = text;
    },
    offerRecognize() {
      again.hidden = false;
    },
  };
  const recorder = createRecorder({
    media: win.navigator.mediaDevices,
    Recorder: win.MediaRecorder,
    fetch: win.fetch.bind(win),
    ui,
    url: "/topics/" + key.slice("draft:".length) + "/voice",
    limitMs: 14.5 * 60 * 1000,
    setTimeout: win.setTimeout.bind(win),
    clearTimeout: win.clearTimeout.bind(win),
  });
  mic.addEventListener("click", () => (recorder.recording() ? recorder.stop() : recorder.start()));
  again.addEventListener("click", () => recorder.recognize());
  return recorder;
}

// The conversation mode (task 308): one tap, then listen → hear the end → send → speak → listen again.
// The end of a turn: the level (RMS) of 50 ms frames against a threshold over the calibrated noise of the room.
function createSilenceDetector({
  startLevel = 0.02,
  startMs = 150,
  silenceMs = 1600,
  calibrateMs = 300,
  maxMs = 870000,
} = {}) {
  let first, calibration, noise, speaking, aboveSince, lastVoiced;

  function reset() {
    first = null;
    calibration = [];
    noise = null;
    speaking = false;
    aboveSince = null;
    lastVoiced = null;
  }

  function calibrated(level, t) {
    if (first === null) first = t;
    if (noise !== null) return true;
    if (t - first < calibrateMs) {
      calibration.push(level);
      return false;
    }
    noise = Math.min(...calibration); // the minimum: a person who answers at once does not raise the threshold
    return true;
  }

  function quiet(level, threshold, t) {
    if (level >= threshold) {
      if (aboveSince === null) aboveSince = t;
      if (t - aboveSince < startMs) return null;
      speaking = true;
      lastVoiced = t;
      return { type: "speech-start" };
    }
    aboveSince = null;
    noise = 0.95 * noise + 0.05 * level; // the noise follows quiet frames only
    return null;
  }

  function voiced(level, threshold, t) {
    if (level >= threshold) lastVoiced = t;
    if (t - first >= maxMs) return end(t);
    return t - lastVoiced >= silenceMs ? end(lastVoiced) : null;
  }

  function end(at) {
    speaking = false;
    aboveSince = null;
    return { type: "speech-end", at };
  }

  reset();
  return {
    push(level, t) {
      if (!calibrated(level, t)) return null;
      const threshold = Math.max(startLevel, 3 * noise);
      return speaking ? voiced(level, threshold, t) : quiet(level, threshold, t);
    },
    reset,
  };
}

const MAX_SPOKEN_BYTES = 1000; // Gemini-TTS fails near its 4000-byte limit; short pieces also start sooner
const ENDS = ".!?…\n";
function byteLength(text) {
  let bytes = 0;
  for (const ch of text) {
    const code = ch.codePointAt(0);
    bytes += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
  }
  return bytes;
}

// Text → the sentences ready to be spoken, and the unfinished rest (kept until more text or the end comes).
function splitSentences(text, final) {
  const sentences = [];
  let from = 0;
  for (let i = 0; i < text.length; i++) {
    const next = text[i + 1];
    const ends = ENDS.includes(text[i]) && (next === " " || next === "\n" || (final && next === undefined));
    if (!ends) continue;
    sentences.push(...pieces(text.slice(from, i + 1)));
    from = i + 1;
  }
  if (!final) return { sentences, rest: text.slice(from) };
  sentences.push(...pieces(text.slice(from)));
  return { sentences, rest: "" };
}

// One sentence → pieces of at most MAX_SPOKEN_BYTES: at the last comma, else the last space, else a character.
function pieces(sentence) {
  const out = [];
  let left = sentence.trim();
  while (byteLength(left) > MAX_SPOKEN_BYTES) {
    const head = longestHead(left);
    const comma = head.lastIndexOf(",");
    const space = head.lastIndexOf(" ");
    const cut = comma > 0 ? comma + 1 : space > 0 ? space : head.length;
    out.push(left.slice(0, cut).trim());
    left = left.slice(cut).trim();
  }
  if (left) out.push(left);
  return out.filter((piece) => piece !== "");
}

function longestHead(text) {
  let bytes = 0;
  let end = 0;
  for (const ch of text) {
    bytes += byteLength(ch);
    if (bytes > MAX_SPOKEN_BYTES) break;
    end += ch.length;
  }
  return text.slice(0, end);
}

function fragmentOf(body) {
  const m = /^\s*<p class="error">([\s\S]*)<\/p>\s*$/.exec(body);
  return m ? m[1].replace(/<[^>]*>/g, "").trim() : null;
}

// The mode's loop. States: off → listening → hearing → thinking → speaking → listening; half duplex.
function createTalk({ media, AudioContext, Recorder, fetch, controller, ui, voiceUrl, speakUrl, setInterval,
  clearInterval, now, mark }) {
  const TYPES = ["audio/webm;codecs=opus", "audio/mp4"];
  const STOPPED = "Режим розмови зупинено — спробуйте ще раз.";
  let state = "off";
  let run = 0; // every stop starts a new run: answers of an older run are dropped
  let ctx, stream, analyser, frame, timer, detector, recorder, source;
  let queue = [];
  let tail = "";
  let answered = false;
  let playing = false;
  let first = true;

  function setState(name) {
    state = name;
    ui.state(name === "off" ? "" : name);
  }

  async function start() {
    if (state !== "off") return;
    const mine = ++run;
    ctx = new AudioContext();
    ctx.resume();
    try {
      stream = await media.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      ctx.close();
      ctx = null;
      return ui.error("Немає доступу до мікрофона.");
    }
    if (mine !== run) return;
    analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    frame = new Float32Array(analyser.fftSize);
    detector = createSilenceDetector();
    timer = setInterval(onFrame, 50);
    listen();
  }

  function level() {
    analyser.getFloatTimeDomainData(frame);
    let sum = 0;
    for (const x of frame) sum += x * x;
    return Math.sqrt(sum / frame.length);
  }

  function onFrame() {
    const event = detector.push(level(), now());
    if (!event) return;
    if (state === "listening" && event.type === "speech-start") return setState("hearing");
    if (state === "hearing" && event.type === "speech-end") {
      mark("talk:speech-end", event.at);
      endTurn();
    }
  }

  function listen() {
    detector.reset();
    recorder = record();
    setState("listening");
  }

  function record() {
    const mimeType = TYPES.find((t) => Recorder.isTypeSupported(t));
    const options = mimeType ? { mimeType, audioBitsPerSecond: 64000 } : { audioBitsPerSecond: 64000 };
    const rec = new Recorder(stream, options);
    const chunks = [];
    const mine = run;
    rec.wanted = false;
    rec.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size !== 0) chunks.push(e.data);
    });
    rec.addEventListener("stop", () => {
      if (rec.wanted && mine === run) recognize(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
    });
    rec.start();
    return rec;
  }

  function endTurn() {
    setState("thinking");
    const rec = recorder;
    recorder = null;
    rec.wanted = true;
    rec.stop();
  }

  async function recognize(blob) {
    const mine = run;
    let text;
    try {
      const response = await fetch(voiceUrl, { method: "POST", body: blob, headers: { "Content-Type": blob.type } });
      if (!response.ok) return fail(fragmentOf(await response.text()), mine);
      text = ((await response.json()).text || "").trim();
    } catch (e) {
      return fail(null, mine);
    }
    if (mine !== run) return;
    if (!text) return listen();
    ui.userTurn(text);
    queue = [];
    tail = "";
    answered = false;
    first = true;
    controller.send(text, { spoken: "1" });
  }

  function delta(text) {
    if (state === "off") return;
    ui.modelDelta(text);
    const { sentences, rest } = splitSentences(tail + text, false);
    tail = rest;
    queue.push(...sentences);
    pump();
  }

  function finished() {
    if (state === "off") return;
    queue.push(...splitSentences(tail, true).sentences);
    tail = "";
    answered = true;
    pump();
  }

  function pump() {
    if (playing || state === "off") return;
    if (queue.length === 0) {
      if (answered) {
        answered = false;
        listen();
      }
      return;
    }
    playing = true;
    speak(queue.shift());
  }

  async function speak(text) {
    const mine = run;
    let buffer;
    try {
      const response = await fetch(speakUrl, { method: "POST", body: new URLSearchParams({ text }) });
      if (!response.ok) return fail(fragmentOf(await response.text()), mine);
      buffer = await ctx.decodeAudioData(await response.arrayBuffer());
    } catch (e) {
      return fail(null, mine);
    }
    if (mine !== run) return;
    play(buffer);
  }

  function play(buffer) {
    source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.addEventListener("ended", () => {
      source = null;
      playing = false;
      pump();
    });
    if (first) {
      first = false;
      setState("speaking");
      mark("talk:voice-start", now());
    }
    source.start();
  }

  function fail(text, mine = run) {
    if (mine !== run || state === "off") return;
    ui.error(text || STOPPED);
    halt();
  }

  function halt() {
    run++;
    clearInterval(timer);
    if (recorder && recorder.state === "recording") recorder.stop();
    recorder = null;
    if (stream) for (const track of stream.getTracks()) track.stop();
    if (source) source.stop();
    if (ctx) ctx.close();
    ctx = stream = source = null;
    queue = [];
    tail = "";
    playing = answered = false;
    setState("off");
  }

  return {
    start,
    stop() {
      halt();
      ui.reload();
    },
    state: () => state,
    delta,
    finished,
    failed: (text) => fail(text),
  };
}

const ThinkHow = { createSseParser, createController, createRecorder, createSilenceDetector, splitSentences, createTalk };
if (typeof module !== "undefined") {
  module.exports = ThinkHow;
} else {
  window.ThinkHow = ThinkHow;
  attach(document, window);
}
