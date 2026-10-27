// Driver of the voice block tests with S2b in place (slice tester, mode `block`). Written from the feature
// artifact (.engine/architecture/feature/voice-conversation-mode.md, «Inter-slice contracts», «Policies»,
// «Acceptance criteria») and the public surface, not the bodies.
//
// The REAL conversation.js runs in the page fakes of the conversation-resilience tests (cr_page_fakes.mjs: earcons
// as oscillators, wakeLock, document visibility). Every request the page makes to /voice, /reply, /retry and
// /speak goes unchanged (method, headers, body) to a REAL running server; the server's answer (status,
// Content-Type, bytes) is handed back to the page. The only rewrite: the fake topic prefix → the real one.
//
// argv[2] is JSON: {base, prefix, turns}. Each turn: the person says something (loud, then silence), every sound
// the page starts plays to its end, and the turn is over when no request is in flight, nothing plays and the
// mode is listening or off. Prints one JSON line.
import {
  loadPage,
  tapTalk,
  utter,
  flush,
  playing,
  endAudio,
  live,
  state,
  listeningTones,
  errorTones,
} from "../conversation_resilience/cr_page_fakes.mjs";

const cfg = JSON.parse(process.argv[2]);
const FAKE_PREFIX = "/topics/alice-1/t-0123456789ab";
const realFetch = globalThis.fetch;
const realSetTimeout = globalThis.setTimeout;
const sleep = (ms) => new Promise((r) => realSetTimeout(r, ms));

const p = loadPage();
const out = { forwarded: [], problems: [], turns: [] };
let inflight = 0;

const kindOf = (u) =>
  u.endsWith("/voice") ? "voice" : u.endsWith("/reply") ? "reply" : u.endsWith("/retry") ? "retry" : u.endsWith("/speak") ? "speak" : null;

function fieldsOf(body) {
  if (body instanceof URLSearchParams || body instanceof FormData) {
    return { text: body.get("text"), spoken: body.get("spoken") };
  }
  if (typeof body === "string") {
    const q = new URLSearchParams(body);
    return { text: q.get("text"), spoken: q.get("spoken") };
  }
  if (body instanceof Blob) return { blob: body.size };
  return {};
}

for (const kind of ["voice", "reply", "retry", "speak"]) {
  let k = 0;
  for (let i = 0; i < 300; i++) {
    p[kind].push(async () => {
      const call = p.calls.filter((c) => kindOf(c.url) === kind)[k++];
      let url = call.url;
      if (url.startsWith(FAKE_PREFIX)) url = cfg.prefix + url.slice(FAKE_PREFIX.length);
      else if (url.startsWith("/topics/")) out.problems.push("unexpected topic url " + url);
      const init = call.init || {};
      inflight++;
      try {
        const res = await realFetch(cfg.base + url, { method: init.method || "GET", headers: init.headers, body: init.body });
        const buf = new Uint8Array(await res.arrayBuffer());
        const type = res.headers.get("content-type") || "";
        out.forwarded.push({
          kind,
          url,
          sent: fieldsOf(init.body),
          status: res.status,
          type,
          body: type.startsWith("audio/") ? null : new TextDecoder().decode(buf),
        });
        return new Response(buf, { status: res.status, headers: { "content-type": type } });
      } finally {
        inflight--;
      }
    });
  }
}

const settled = () => inflight === 0 && playing(p).length === 0 && ["listening", "", "off"].includes(state(p));

async function oneTurn() {
  const voicesBefore = out.forwarded.filter((f) => f.kind === "voice").length;
  await utter(p);
  const end = Date.now() + 30000;
  while (Date.now() < end) {
    if (playing(p).length > 0) {
      await endAudio(p);
      continue;
    }
    const heard = out.forwarded.filter((f) => f.kind === "voice").length > voicesBefore;
    if (heard && settled()) {
      await sleep(80);
      await flush();
      if (settled()) return;
      continue;
    }
    await sleep(10);
    await flush(5);
  }
  out.problems.push("a turn did not settle in 30 s; state " + state(p));
}

try {
  await tapTalk(p);
  await sleep(50);
  await flush();
  out.state_after_tap = state(p);
  for (let i = 0; i < (cfg.turns ?? 1); i++) {
    await oneTurn();
    out.turns.push({ state: state(p), error: p.byId.error.textContent, forwarded: out.forwarded.length });
  }
} catch (e) {
  out.problems.push(String(e && e.stack ? e.stack : e));
}

out.state = state(p);
out.stateLog = p.talk.stateLog;
out.error = p.byId.error.textContent;
out.live = live(p);
out.started = p.ctxs.flatMap((c) => c.sources).filter((s) => s.started).length;
out.listening_tones = listeningTones(p);
out.error_tones = errorTones(p);
out.wake_requests = p.wakeRequests;
out.other_calls = p.calls.filter((c) => !kindOf(c.url)).map((c) => c.url);
console.log("VCM_RESULT " + JSON.stringify(out));
process.exit(0);
