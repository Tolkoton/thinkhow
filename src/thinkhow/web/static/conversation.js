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
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    error.textContent = "";
    controller.send(field.value);
  });
  if (retry) retry.addEventListener("click", () => controller.retry());
}

const ThinkHow = { createSseParser, createController };
if (typeof module !== "undefined") {
  module.exports = ThinkHow;
} else {
  window.ThinkHow = ThinkHow;
  attach(document, window);
}
