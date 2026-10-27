// Contract tests of conversation-resilience on the page: createTalk through attach(document, window), as the
// page runs it (slice tester). Written from the contract, not the code; fakes in cr_page_fakes.mjs. A tone is
// told apart by the first frequency of its oscillator on the mode's AudioContext (Q1, Q5).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import {
  SRC_PATH,
  NO_WORDS,
  NO_MIC,
  flush,
  loadPage,
  calibrate,
  loud,
  silence,
  utter,
  state,
  voiceCalls,
  replyCalls,
  retryCalls,
  speakCalls,
  spokenTexts,
  formText,
  playing,
  endAudio,
  playAll,
  live,
  recording,
  tapTalk,
  fire,
  emit,
  json,
  fragment,
  offline,
  reply,
  failedReply,
  liveReply,
  listeningTones,
  tickTones,
  errorTones,
  slowIntervals,
  fireSlow,
  runTimeouts,
  endTrack,
  ctxState,
  visibility,
  collapse,
  noSpace,
  sources,
} from "./cr_page_fakes.mjs";

const require = createRequire(import.meta.url);
const { createController } = require(SRC_PATH);

const URL_LIKE = /https?:|:\/\/|htt|adac\.de|\]\(/;

// ---- Seam 1: the voice without «Джерела:», even when the literal comes in pieces ----

test("a sources literal that comes in pieces is never spoken: only the text before it goes to /speak", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply("Ось текст.", "\n", "\nДже", "рела: [a](https://a)"));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.deepEqual(spokenTexts(p), ["Ось текст."]);
  assert.equal(state(p), "listening");
});

test("a link in the middle of the text sounds by its name", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply("Див. [ADAC](https://adac.de) далі. ", "Кінець."));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  // joined: S2a's splitSentences may cut after «Див.» (Q8)
  assert.equal(collapse(spokenTexts(p).join(" ")), "Див. ADAC далі. Кінець.");
});

test("a link split between deltas sounds by its name only", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply("Див. [ADAC](htt", "ps://adac.de) далі. "));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(collapse(spokenTexts(p).join(" ")), "Див. ADAC далі.", JSON.stringify(spokenTexts(p)));
});

test("a sources line in the middle is dropped and the deep part after it is spoken", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(
    reply(
      "Відповідь.",
      "\n\nДжерела: [a](https://a)",
      "\n\nШукаю: ціни\n- питання",
      "\n\nЗвіт.",
      "\n\nДжерела: [b](https://b)",
    ),
  );
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  const said = spokenTexts(p);
  assert.equal(noSpace(said.join(" ")), "Відповідь.Шукаю:ціни-питанняЗвіт.", JSON.stringify(said));
  for (const s of said) assert.ok(!URL_LIKE.test(s), `an address in /speak: ${JSON.stringify(s)}`);
});

test("a bare address split in the middle of its scheme leaves no pieces in /speak", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply("див. htt", "ps://adac.de далі. "));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(collapse(spokenTexts(p).join(" ")), "див. далі.", JSON.stringify(spokenTexts(p)));
});

test("[1] without a link sounds before the answer ends, and the link split after it sounds by its name", async () => {
  const p = loadPage();
  const r = liveReply();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(r.respond);
  await tapTalk(p);
  await utter(p);
  r.delta("[1] Перше. [ADAC](htt");
  await flush();
  assert.deepEqual(spokenTexts(p), ["[1] Перше."], "[1] Перше. did not sound before the end of the answer");
  r.delta("ps://adac.de) далі.");
  r.answered();
  await flush();
  await playAll(p);
  assert.deepEqual(spokenTexts(p), ["[1] Перше.", "ADAC далі."]);
});

// ---- the listening tone ----

test("the listening tone plays each time the mode enters listening, the first time right after the tap", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }), json({ text: "Ще" }));
  p.reply.push(reply("Перша відповідь."), reply("Друга відповідь."));
  await tapTalk(p);
  assert.equal(state(p), "listening");
  assert.equal(listeningTones(p), 1, "no listening tone after the tap");
  await utter(p);
  assert.equal(listeningTones(p), 1, "a listening tone while not listening");
  await playAll(p);
  assert.equal(state(p), "listening");
  assert.equal(listeningTones(p), 2);
  await utter(p);
  await playAll(p);
  assert.equal(listeningTones(p), 3);
});

// ---- Seam 2: recognition fails — a tone and on; three in a row — stop ----

test("a failed recognition (empty text, 502, network) plays the error tone and listens again without stopping", async () => {
  for (const [kind, answer] of [
    ["empty", json({ text: "" })],
    ["502", fragment("Не вдалося розпізнати.", 502)],
    ["network", offline()],
  ]) {
    const p = loadPage();
    p.voice.push(answer);
    await tapTalk(p);
    await utter(p);
    assert.equal(errorTones(p), 1, `${kind}: error tones`);
    assert.equal(state(p), "listening", `${kind}: state`);
    assert.ok(!p.talk.stateLog.slice(1).includes(""), `${kind}: the mode went off: ${p.talk.stateLog}`);
    assert.equal(recording(p).length, 1, `${kind}: no recorder records`);
    assert.equal(p.recorders.at(-1).state, "recording");
    assert.equal(replyCalls(p).length, 0);
    assert.equal(p.reloads, 0);
  }
});

test("a failed recognition shows the fragment text; an empty text shows «Не почули слів — спробуйте ще раз.»", async () => {
  const a = loadPage();
  a.voice.push(fragment("Не вдалося розпізнати — спробуйте ще раз.", 502));
  await tapTalk(a);
  await utter(a);
  assert.equal(a.byId.error.textContent, "Не вдалося розпізнати — спробуйте ще раз.");
  assert.equal(state(a), "listening");
  const b = loadPage();
  b.voice.push(json({ text: "" }));
  await tapTalk(b);
  await utter(b);
  assert.equal(b.byId.error.textContent, NO_WORDS);
  assert.equal(state(b), "listening");
});

test("three failed recognitions in a row: the mode goes off with the last text and the error tone", async () => {
  const p = loadPage();
  p.voice.push(fragment("Сервер недоступний.", 502), offline(), json({ text: "" }));
  await tapTalk(p);
  await utter(p);
  await utter(p);
  assert.equal(state(p), "listening", "off after two failures");
  const before = errorTones(p);
  assert.equal(before, 2);
  await utter(p);
  assert.equal(voiceCalls(p).length, 3);
  assert.equal(state(p), "");
  assert.equal(p.byId.error.textContent, NO_WORDS);
  assert.ok(errorTones(p) > before, "no error tone when the mode went off");
  assert.equal(recording(p).length, 0);
  assert.equal(p.reloads, 0);
});

test("a successful recognition between failures resets the count", async () => {
  const p = loadPage();
  p.voice.push(
    fragment("Збій.", 502),
    json({ text: "" }),
    json({ text: "Привіт" }),
    offline(),
    fragment("Збій.", 502),
    json({ text: "Знову" }),
  );
  p.reply.push(reply("Відповідь."), reply("Ще відповідь."));
  await tapTalk(p);
  await utter(p);
  await utter(p);
  await utter(p);
  await playAll(p);
  assert.equal(state(p), "listening");
  await utter(p);
  await utter(p);
  assert.equal(state(p), "listening", "off after two failures following a success");
  await utter(p);
  await playAll(p);
  assert.equal(voiceCalls(p).length, 6);
  assert.deepEqual(replyCalls(p).map((c) => formText(c.init)), ["Привіт", "Знову"]);
  assert.equal(state(p), "listening");
});

// ---- Seam 3: one retry of the answer ----

test("a failed answer: one automatic /retry with spoken=1, a new model paragraph, no glued pieces in /speak", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(failedReply("Привіт, ти зна"));
  p.retry.push(reply("Привіт, ти знаєш."));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(retryCalls(p).length, 1);
  assert.equal(retryCalls(p)[0].init.method, "POST");
  assert.equal(formText(retryCalls(p)[0].init, "spoken"), "1");
  assert.deepEqual(spokenTexts(p), ["Привіт, ти знаєш."]);
  assert.deepEqual(live(p), [
    { cls: "turn user", text: "Привіт" },
    { cls: "turn model", text: "Привіт, ти зна" },
    { cls: "turn model", text: "Привіт, ти знаєш." },
  ]);
  assert.equal(state(p), "listening");
});

test("the retry fails too: an error on the screen, the error tone, the mode goes off", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(failedReply("Поч"));
  p.retry.push(failedReply());
  await tapTalk(p);
  await utter(p);
  assert.equal(retryCalls(p).length, 1);
  assert.equal(state(p), "");
  assert.notEqual(p.byId.error.textContent, "", "no error on the screen");
  assert.ok(errorTones(p) >= 1, "no error tone");
  assert.equal(recording(p).length, 0);
  assert.equal(p.reloads, 0);
});

test("409 from /reply is not retried: an error, the error tone and the stop", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(fragment("Спершу дочекайтеся відповіді.", 409));
  await tapTalk(p);
  await utter(p);
  assert.equal(retryCalls(p).length, 0);
  assert.equal(state(p), "");
  assert.equal(p.byId.error.textContent, "Спершу дочекайтеся відповіді.");
  assert.ok(errorTones(p) >= 1, "no error tone");
});

test("createController.retry(fields) posts the fields; retry() posts no spoken field", async () => {
  const calls = [];
  const ui = {};
  for (const m of ["disable", "enable", "appendDelta", "showRetry", "showError", "reload", "setDraft"]) ui[m] = () => {};
  const fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response("event: saved\ndata: {}\n\nevent: answered\ndata: {}\n\n", {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  };
  const storage = { getItem: () => null, setItem() {}, removeItem() {} };
  const c = createController({ fetch, storage, ui, key: "draft:alice-1/t-0123456789ab" });
  await c.retry({ spoken: "1" });
  await c.retry();
  await flush();
  assert.equal(calls.length, 2);
  assert.ok(calls.every((x) => x.url.endsWith("/retry")), calls.map((x) => x.url).join(", "));
  assert.equal(formText(calls[0].init, "spoken"), "1");
  assert.equal(formText(calls[1].init, "spoken"), null);
});

// ---- Seam 4: a sentence that does not sound is skipped ----

test("a sentence whose /speak fails or does not decode is skipped silently; the rest sounds, then listening", async () => {
  for (const kind of ["502", "network", "decode"]) {
    const p = loadPage();
    p.voice.push(json({ text: "Привіт" }));
    p.reply.push(reply("Перше речення. Друге речення. Третє речення."));
    if (kind === "502") p.speak.push(() => new Response(new Uint8Array([1]), { status: 200, headers: { "content-type": "audio/mpeg" } }), fragment("Озвучення недоступне.", 502));
    if (kind === "network") p.speak.push(() => new Response(new Uint8Array([1]), { status: 200, headers: { "content-type": "audio/mpeg" } }), offline());
    if (kind === "decode") p.decodeFailAt.add(1);
    await tapTalk(p);
    await utter(p);
    await playAll(p);
    assert.deepEqual(spokenTexts(p), ["Перше речення.", "Друге речення.", "Третє речення."], kind);
    assert.equal(sources(p).filter((s) => s.started).length, 2, `${kind}: sounds started`);
    assert.equal(state(p), "listening", kind);
    assert.ok(!p.talk.stateLog.slice(1).includes(""), `${kind}: the mode went off`);
    assert.equal(errorTones(p), 0, `${kind}: a tone for a skipped sentence`);
  }
});

// ---- Seam 5: the tick, Wake Lock, the microphone, the sound ----

test("while thinking a tick tone every 10 s on an interval of its own, cleared when thinking ends", async () => {
  const p = loadPage();
  let release;
  const r = liveReply();
  p.voice.push(() => new Promise((ok) => (release = ok)));
  p.reply.push(r.respond);
  await tapTalk(p);
  assert.equal(slowIntervals(p).length, 0, "a tick interval while listening");
  await utter(p);
  assert.equal(state(p), "thinking");
  const ticks = slowIntervals(p);
  assert.equal(ticks.length, 1, "no interval of its own for the tick");
  assert.equal(ticks[0].ms, 10000);
  fireSlow(p);
  fireSlow(p);
  assert.equal(tickTones(p), 2);
  release(json({ text: "Привіт" })());
  await flush();
  assert.equal(state(p), "thinking");
  fireSlow(p);
  assert.equal(tickTones(p), 3);
  r.delta("Ось відповідь. ");
  await flush();
  assert.equal(state(p), "speaking");
  assert.equal(slowIntervals(p).length, 0, "the tick interval is not cleared after thinking");
  fireSlow(p);
  assert.equal(tickTones(p), 3);
});

test("stop while thinking clears both the tick interval and the frame interval", async () => {
  const p = loadPage();
  p.voice.push(() => new Promise(() => {}));
  await tapTalk(p);
  await utter(p);
  assert.equal(state(p), "thinking");
  assert.equal(slowIntervals(p).length, 1, "no tick interval while thinking");
  await tapTalk(p);
  assert.equal(state(p), "");
  assert.ok(p.intervals.every((i) => i.cleared), `intervals left: ${p.intervals.filter((i) => !i.cleared).map((i) => i.ms)}`);
});

test("start() asks navigator.wakeLock for the screen before its first await, still inside the tap", async () => {
  const p = loadPage();
  fire(p.talk, "click");
  const inTheTap = [...p.wakeRequests];
  await flush();
  assert.deepEqual(inTheTap, ["screen"], "no wake lock asked for synchronously inside the tap");
});

test("without the Wake Lock API, or when it refuses, the mode works silently", async () => {
  const a = loadPage({ wake: false });
  a.voice.push(json({ text: "Привіт" }));
  a.reply.push(reply("Відповідь."));
  await tapTalk(a);
  assert.equal(state(a), "listening");
  assert.equal(listeningTones(a), 1, "the mode did not start fully without the API");
  await utter(a);
  await playAll(a);
  assert.equal(state(a), "listening");
  assert.equal(a.byId.error.textContent, "");
  const b = loadPage({ refuseWake: true });
  await tapTalk(b);
  assert.deepEqual(b.wakeRequests, ["screen"]);
  assert.equal(state(b), "listening");
  assert.equal(b.byId.error.textContent, "");
});

test("stop() releases the wake lock", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(p.sentinels.length, 1);
  assert.equal(p.sentinels[0].released, false);
  await tapTalk(p);
  assert.equal(state(p), "");
  assert.equal(p.sentinels[0].releaseCalls, 1);
});

test("visibilitychange to visible while on, with the lock released or missing, asks for it again", async () => {
  // released by the system while the page was hidden
  const a = loadPage();
  await tapTalk(a);
  assert.equal(a.sentinels.length, 1, "no wake lock at start");
  await visibility(a, "hidden");
  a.sentinels[0].released = true;
  emit(a.sentinels[0], "release");
  await visibility(a, "visible");
  assert.deepEqual(a.wakeRequests, ["screen", "screen"]);
  assert.equal(state(a), "listening");
  // missing: the first request was refused
  const b = loadPage({ refuseWake: true });
  await tapTalk(b);
  b.refuseWake = false;
  await visibility(b, "hidden");
  await visibility(b, "visible");
  assert.deepEqual(b.wakeRequests, ["screen", "screen"]);
});

test("the visibilitychange listener is removed at stop", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(p.wakeRequests.length, 1);
  await tapTalk(p);
  assert.equal(state(p), "");
  await visibility(p, "hidden");
  await visibility(p, "visible");
  assert.equal(p.wakeRequests.length, 1, "a wake lock asked for after the stop");
  assert.equal((p.doc.listeners.visibilitychange || []).length, 0, "a visibilitychange listener is left");
});

test("the microphone track ends while listening: one new getUserMedia, a new analyser source, a new recorder", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(state(p), "listening");
  await endTrack(p, 0);
  assert.equal(p.gum.length, 2, "no new getUserMedia");
  assert.deepEqual(p.gum[1], p.gum[0], "other constraints for the new stream");
  const ctx = p.ctxs[0];
  const src = ctx.streamSources.find((s) => s.stream === p.streams[1]);
  assert.ok(src, "no MediaStreamSource on the new stream");
  assert.ok(src.connected.some((x) => ctx.analysers.includes(x)), "the new source is not connected to an analyser");
  assert.equal(state(p), "listening");
  assert.equal(p.recorders.at(-1).stream, p.streams[1]);
  assert.equal(p.recorders.at(-1).state, "recording");
});

test("the microphone track ends while hearing: the utterance is dropped, listening again on the new stream", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(reply("Відповідь."));
  await tapTalk(p);
  calibrate(p);
  loud(p);
  await flush();
  assert.equal(state(p), "hearing");
  await endTrack(p, 0);
  assert.equal(p.gum.length, 2);
  assert.equal(state(p), "listening");
  silence(p);
  await flush();
  assert.equal(voiceCalls(p).length, 0, "the utterance from the dead stream went to /voice");
  assert.equal(p.recorders.at(-1).stream, p.streams[1]);
  await utter(p);
  assert.equal(voiceCalls(p).length, 1);
  assert.equal(formText(replyCalls(p)[0].init), "Привіт");
});

test("the microphone track ends while thinking or speaking: the stream is replaced and the cycle goes on", async () => {
  // thinking
  const a = loadPage();
  let release;
  a.voice.push(() => new Promise((ok) => (release = ok)));
  a.reply.push(reply("Перше речення. Друге речення."));
  await tapTalk(a);
  await utter(a);
  assert.equal(state(a), "thinking");
  await endTrack(a, 0);
  assert.equal(a.gum.length, 2);
  release(json({ text: "Привіт" })());
  await flush();
  await playAll(a);
  assert.equal(spokenTexts(a).length, 2);
  assert.equal(state(a), "listening");
  assert.equal(a.recorders.at(-1).stream, a.streams[1]);
  // speaking
  const b = loadPage();
  b.voice.push(json({ text: "Привіт" }));
  b.reply.push(reply("Перше речення. Друге речення."));
  await tapTalk(b);
  await utter(b);
  assert.equal(state(b), "speaking");
  await endTrack(b, 0);
  assert.equal(b.gum.length, 2);
  await playAll(b);
  assert.equal(spokenTexts(b).length, 2);
  assert.equal(state(b), "listening");
  assert.equal(b.recorders.at(-1).stream, b.streams[1]);
});

test("the microphone cannot be opened again: «Немає доступу до мікрофона.» and the mode goes off", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(state(p), "listening");
  p.denyMic = true;
  await endTrack(p, 0);
  assert.equal(p.gum.length, 2, "no new getUserMedia");
  assert.equal(p.byId.error.textContent, NO_MIC);
  assert.equal(state(p), "");
});

test("statechange to suspended or interrupted: resume(); not running after 1 s shows #talk-resume; a tap hides it", async () => {
  const p = loadPage();
  await tapTalk(p);
  const ctx = p.ctxs[0];
  assert.equal(ctx.state, "running");
  // resume helps: the button stays hidden
  let n = ctx.resumed;
  await ctxState(p, "interrupted");
  assert.ok(ctx.resumed > n, "no resume() on interrupted");
  await runTimeouts(p);
  assert.equal(p.resumeButton.hidden, true, "#talk-resume shown though the sound runs");
  // resume does not help
  p.resumeWorks = false;
  n = ctx.resumed;
  await ctxState(p, "suspended");
  assert.ok(ctx.resumed > n, "no resume() on suspended");
  assert.equal(p.resumeButton.hidden, true, "#talk-resume shown before 1 s");
  await runTimeouts(p);
  assert.equal(p.resumeButton.hidden, false, "#talk-resume stays hidden after 1 s without running");
  assert.equal(state(p), "listening", "the mode went off");
  // the tap
  p.resumeWorks = true;
  n = ctx.resumed;
  fire(p.resumeButton, "click");
  await flush();
  assert.ok(ctx.resumed > n, "no resume() on the tap");
  assert.equal(p.resumeButton.hidden, true);
});

test("one check at the end of start(): a context still suspended is resumed, and after 1 s #talk-resume shows", async () => {
  const p = loadPage();
  p.resumeWorks = false;
  await tapTalk(p);
  const ctx = p.ctxs[0];
  assert.equal(ctx.state, "suspended");
  assert.ok(ctx.resumed >= 2, `resume() called ${ctx.resumed} time(s)`);
  await runTimeouts(p);
  assert.equal(p.resumeButton.hidden, false);
});
