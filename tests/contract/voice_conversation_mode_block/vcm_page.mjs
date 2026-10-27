// Driver of the voice-conversation-mode block tests (slice tester, mode `block`). Written from the feature
// artifact (.engine/architecture/feature/voice-conversation-mode.md, «Inter-slice contracts») and the public
// surface, not the bodies.
//
// The REAL conversation.js runs in the page fakes of the conversation-loop tests (cl_page_fakes.mjs: a vm
// context as the window, a fake microphone, AudioContext and MediaRecorder). Every request the page makes to
// /voice, /reply and /speak is sent, unchanged (method, headers, body), to a REAL running server; the
// server's answer (status, Content-Type, bytes) is handed back to the page. The only rewrite: the fake page's
// topic prefix is replaced by the real topic's prefix (taken from the real page's data-key).
//
// argv[2] is a JSON config: {base, prefix, voice, dictate, sendAgain, normal, tap, turn, turns, secondTap}. Prints one JSON
// line. `dictate`: tap #mic (ordinary dictation), speak, press «Надіслати» (submit) while it records; then wait.
import {
  loadPage,
  tapTalk,
  calibrate,
  loud,
  silence,
  flush,
  fire,
  playing,
  endAudio,
  live,
} from "../conversation_loop/cl_page_fakes.mjs";

const cfg = JSON.parse(process.argv[2]);
const FAKE_PREFIX = "/topics/alice-1/t-0123456789ab";
const realFetch = globalThis.fetch;
const realSetTimeout = globalThis.setTimeout;
const sleep = (ms) => new Promise((r) => realSetTimeout(r, ms));

const p = loadPage({ voice: cfg.voice });
const out = { forwarded: [], decoded: [], problems: [] };

const kindOf = (u) => (u.endsWith("/voice") ? "voice" : u.endsWith("/reply") ? "reply" : u.endsWith("/speak") ? "speak" : null);

function fieldsOf(body) {
  if (body instanceof URLSearchParams || body instanceof FormData) {
    return { text: body.get("text"), spoken: body.get("spoken"), encoding: body.constructor.name };
  }
  if (typeof body === "string") {
    const q = new URLSearchParams(body);
    return { text: q.get("text"), spoken: q.get("spoken"), encoding: "string" };
  }
  if (body instanceof Blob) return { blob: body.size, type: body.type, encoding: "Blob" };
  return { encoding: body === undefined ? "none" : typeof body };
}

for (const kind of ["voice", "reply", "speak"]) {
  let k = 0;
  for (let i = 0; i < 300; i++) {
    p[kind].push(async () => {
      const call = p.calls.filter((c) => kindOf(c.url) === kind)[k++];
      let url = call.url;
      if (url.startsWith(FAKE_PREFIX)) url = cfg.prefix + url.slice(FAKE_PREFIX.length);
      else if (url.startsWith("/topics/")) out.problems.push("unexpected topic url " + url);
      const init = call.init || {};
      const res = await realFetch(cfg.base + url, { method: init.method || "GET", headers: init.headers, body: init.body });
      const buf = new Uint8Array(await res.arrayBuffer());
      const type = res.headers.get("content-type") || "";
      out.forwarded.push({
        kind,
        page_url: call.url,
        url,
        method: init.method || "GET",
        sent: fieldsOf(init.body),
        status: res.status,
        type,
        bytes: buf.length,
        body: type.startsWith("audio/") ? null : new TextDecoder().decode(buf),
      });
      return new Response(buf, { status: res.status, headers: { "content-type": type } });
    });
  }
}

const state = () => p.talk.dataset.state ?? "";

async function until(cond, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (cond()) return true;
    await sleep(10);
    await flush(5);
  }
  return false;
}

async function oneTurn() {
  const before = out.forwarded.filter((f) => f.kind === "reply").length;
  calibrate(p);
  loud(p);
  silence(p);
  await flush();
  const end = Date.now() + 30000;
  while (Date.now() < end) {
    if (playing(p).length > 0) {
      await endAudio(p);
      continue;
    }
    const replied = out.forwarded.filter((f) => f.kind === "reply").length > before;
    if (replied && (state() === "listening" || state() === "")) {
      await sleep(50);
      await flush();
      if (playing(p).length === 0 && (state() === "listening" || state() === "")) break;
      continue;
    }
    await sleep(10);
    await flush(5);
  }
}

try {
  if (cfg.dictate) {
    fire(p.byId.mic, "click");
    await flush();
    out.recording_after_mic = p.recorders.filter((r) => r.state === "recording").length;
    fire(p.byId["reply-form"], "submit");
    await until(() => out.forwarded.some((f) => f.kind === "voice") && p.field.value !== "", 15000);
    await sleep(100);
    await flush();
    out.field_after_dictation = p.field.value;
    out.recording_after_send = p.recorders.filter((r) => r.state === "recording").length;
    out.replies_after_dictation = out.forwarded.filter((f) => f.kind === "reply").length;
    if (cfg.sendAgain) {
      fire(p.byId["reply-form"], "submit");
      await until(() => out.forwarded.some((f) => f.kind === "reply") && p.reloads > 0, 15000);
    }
  }
  if (cfg.normal) {
    p.field.value = cfg.normal;
    fire(p.byId["reply-form"], "submit");
    await until(() => out.forwarded.some((f) => f.kind === "reply") && p.reloads > 0, 15000);
  }
  if (cfg.tap) {
    await tapTalk(p);
    for (const ctx of p.ctxs) {
      const orig = ctx.decodeAudioData.bind(ctx);
      ctx.decodeAudioData = (buf, ok, err) => {
        out.decoded.push(buf && (buf.byteLength ?? buf.length));
        return orig(buf, ok, err);
      };
    }
  }
  const turns = cfg.turns ?? (cfg.turn ? 1 : 0);
  out.states_after_each_turn = [];
  for (let i = 0; i < turns; i++) {
    await oneTurn();
    out.states_after_each_turn.push(state());
  }
  out.state_after_turn = state();
  if (cfg.secondTap) {
    await tapTalk(p);
    await flush();
  }
} catch (e) {
  out.problems.push(String(e && e.stack ? e.stack : e));
}

out.hidden = p.talk.hidden;
out.state = state();
out.stateLog = p.talk.stateLog;
out.error = p.byId.error.textContent;
out.live = live(p);
out.started = p.ctxs.flatMap((c) => c.sources).filter((s) => s.started).length;
out.reloads = p.reloads;
out.marks = p.marks.map((m) => m.name);
out.other_calls = p.calls.filter((c) => !kindOf(c.url)).map((c) => c.url);
console.log("VCM_RESULT " + JSON.stringify(out));
process.exit(0);
