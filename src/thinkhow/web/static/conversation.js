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
    send(text) {
      storage.setItem(name, text);
      return run(base + "/reply", new URLSearchParams({ text }));
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
  const controller = createController({ fetch: win.fetch.bind(win), storage: win.localStorage, ui, key: form.dataset.key });
  if (retry) retry.addEventListener("click", () => controller.retry());
  const recorder = attachMic(doc, win, form, field, error);
  // While the microphone is busy «Надіслати» only stops the recording; the next press sends the text (task 206).
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (recorder && recorder.busy()) return recorder.stop();
    error.textContent = "";
    controller.send(field.value);
  });
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

const ThinkHow = { createSseParser, createController, createRecorder };
if (typeof module !== "undefined") {
  module.exports = ThinkHow;
} else {
  window.ThinkHow = ThinkHow;
  attach(document, window);
}
