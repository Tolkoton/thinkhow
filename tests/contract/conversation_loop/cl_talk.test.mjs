// Contract tests of conversation-loop, Seam 3 and the page: createTalk through attach(document, window), as the
// page runs it (slice tester). Written from the contract, not the code; fakes in cl_page_fakes.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  WEBM,
  STOPPED,
  flush,
  loadPage,
  tick,
  calibrate,
  loud,
  silence,
  utter,
  state,
  voiceCalls,
  replyCalls,
  speakCalls,
  formText,
  contentType,
  playing,
  endAudio,
  playAll,
  live,
  recording,
  tapTalk,
  json,
  fragment,
  sse,
  reply,
  fire,
} from "./cl_page_fakes.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createController } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

test("attach shows #talk only with data-voice=yes, AudioContext and mediaDevices", () => {
  assert.equal(loadPage().talk.hidden, false, "#talk stayed hidden on a voice page");
  assert.equal(loadPage({ voice: "no" }).talk.hidden, true, "#talk shown without data-voice=yes");
  assert.equal(loadPage({ audio: false }).talk.hidden, true, "#talk shown without AudioContext");
  assert.equal(loadPage({ media: false }).talk.hidden, true, "#talk shown without mediaDevices");
});

test("start: AudioContext resumed, one stream, analyser 1024, a frame every 50 ms, listening, a recorder", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(p.ctxs.length, 1);
  assert.ok(p.ctxs[0].resumed >= 1, "resume() not called");
  assert.equal(p.gum.length, 1);
  assert.equal(p.gum[0].audio.echoCancellation, true);
  assert.equal(p.gum[0].audio.noiseSuppression, true);
  const ctx = p.ctxs[0];
  assert.equal(ctx.analysers.length, 1);
  assert.equal(ctx.analysers[0].fftSize, 1024);
  assert.equal(ctx.streamSources.length, 1);
  assert.equal(ctx.streamSources[0].stream, p.streams[0]);
  assert.ok(ctx.streamSources[0].connected.includes(ctx.analysers[0]), "the stream source is not connected to the analyser");
  assert.equal(p.intervals.filter((i) => !i.cleared).length, 1);
  assert.equal(p.intervals[0].ms, 50);
  assert.equal(state(p), "listening");
  assert.equal(p.talk.ariaPressed, "true");
  assert.equal(p.recorders.length, 1);
  assert.equal(p.recorders[0].stream, p.streams[0]);
  assert.equal(p.recorders[0].options.mimeType, WEBM);
  assert.equal(p.recorders[0].options.audioBitsPerSecond, 64000);
  assert.equal(p.recorders[0].state, "recording");
});

test("the recorder type is the first supported of audio/webm;codecs=opus, audio/mp4", async () => {
  const p = loadPage({ supported: ["audio/mp4"] });
  await tapTalk(p);
  assert.equal(p.recorders.length, 1);
  assert.equal(p.recorders[0].options.mimeType, "audio/mp4");
});

test("a refused microphone: the error «Немає доступу до мікрофона.» and the state off", async () => {
  const p = loadPage();
  p.denyMic = true;
  await tapTalk(p);
  assert.equal(p.byId.error.textContent, "Немає доступу до мікрофона.");
  assert.equal(state(p), "");
  assert.equal(recording(p).length, 0);
  assert.equal(p.reloads, 0);
});

test("one cycle: speech, /voice, /reply spoken=1, /speak one sentence at a time, listening", async () => {
  const p = loadPage();
  let release;
  p.voice.push(() => new Promise((r) => (release = r)));
  p.reply.push(reply("Перше речення. Дру", "ге речення! Тре", "тє"));
  await tapTalk(p);
  calibrate(p);
  loud(p);
  await flush();
  assert.equal(state(p), "hearing");
  silence(p);
  await flush();
  assert.equal(state(p), "thinking");
  release(json({ text: "Привіт" })());
  await flush();
  // the recording went to /voice: a Blob with its own type as Content-Type
  assert.equal(voiceCalls(p).length, 1);
  const v = voiceCalls(p)[0].init;
  assert.equal(v.method, "POST");
  assert.ok(v.body instanceof Blob, "the body of /voice is not a Blob");
  assert.equal(contentType(v), v.body.type);
  assert.equal(p.recorders[0].state, "inactive");
  // the text went as a reply with spoken=1
  assert.equal(replyCalls(p).length, 1);
  const r = replyCalls(p)[0].init;
  assert.equal(formText(r), "Привіт");
  assert.equal(formText(r, "spoken"), "1");
  // the first sentence is playing; the next /speak waits for its end
  assert.equal(state(p), "speaking");
  assert.equal(speakCalls(p).length, 1);
  assert.equal(formText(speakCalls(p)[0].init), "Перше речення.");
  assert.equal(playing(p).length, 1);
  await endAudio(p);
  assert.equal(speakCalls(p).length, 2);
  assert.equal(formText(speakCalls(p)[1].init), "Друге речення!");
  await endAudio(p);
  assert.equal(speakCalls(p).length, 3);
  assert.equal(formText(speakCalls(p)[2].init), "Третє");
  assert.equal(p.recorders.length, 1, "a recorder was made before the voice fell silent");
  await endAudio(p);
  assert.equal(speakCalls(p).length, 3);
  assert.ok(speakCalls(p).every((c) => c.init.method === "POST"));
  // listening again, with a new recorder; the page was not reloaded
  assert.equal(state(p), "listening");
  assert.equal(p.recorders.length, 2);
  assert.equal(p.recorders[1].state, "recording");
  assert.equal(p.reloads, 0);
  assert.equal(p.byId.error.textContent, "");
});

test("marks: talk:speech-end at the last speech frame, talk:voice-start at start() of the first sentence", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(reply("Перше речення. ", "Друге речення."));
  await tapTalk(p);
  calibrate(p);
  const lastSpeech = loud(p);
  silence(p);
  p.clock.t = 77777;
  await flush();
  await playAll(p);
  const ends = p.marks.filter((m) => m.name === "talk:speech-end");
  const starts = p.marks.filter((m) => m.name === "talk:voice-start");
  assert.equal(ends.length, 1);
  assert.equal(ends[0].startTime, lastSpeech);
  assert.equal(starts.length, 1, "one talk:voice-start per answer");
  const first = p.ctxs[0].sources.find((s) => s.started);
  assert.equal(starts[0].startTime, first.startedAt);
  assert.equal(starts[0].startTime, 77777);
});

test("the second turn goes the same way without another start()", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }), json({ text: "Ще раз" }));
  p.reply.push(reply("Перша відповідь."), reply("Друга відповідь."));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(state(p), "listening");
  await utter(p);
  assert.equal(voiceCalls(p).length, 2);
  assert.equal(replyCalls(p).length, 2);
  assert.equal(formText(replyCalls(p)[1].init), "Ще раз");
  assert.equal(formText(replyCalls(p)[1].init, "spoken"), "1");
  await playAll(p);
  assert.deepEqual(speakCalls(p).map((c) => formText(c.init)), ["Перша відповідь.", "Друга відповідь."]);
  assert.equal(state(p), "listening");
  assert.equal(p.ctxs.length, 1, "a second AudioContext");
  assert.equal(p.gum.length, 1, "a second getUserMedia");
  assert.equal(p.recorders.length, 3);
  assert.equal(p.reloads, 0);
});

test("each answer goes into a new turn model paragraph after the turn user paragraph of its turn in #live", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }), json({ text: "Ще раз" }));
  p.reply.push(reply("Перша ", "відповідь."), reply("Друга ", "відповідь."));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  await utter(p);
  await playAll(p);
  assert.deepEqual(live(p), [
    { cls: "turn user", text: "Привіт" },
    { cls: "turn model", text: "Перша відповідь." },
    { cls: "turn user", text: "Ще раз" },
    { cls: "turn model", text: "Друга відповідь." },
  ]);
});

test("empty text from /voice: listening again with a new recorder, no reply sent", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "" }), json({ text: "Тепер чути" }));
  p.reply.push(reply("Добре."));
  await tapTalk(p);
  await utter(p);
  assert.equal(voiceCalls(p).length, 1);
  assert.equal(replyCalls(p).length, 0, "an empty reply was sent");
  assert.equal(state(p), "listening");
  assert.equal(p.recorders.length, 2);
  assert.equal(p.recorders[1].state, "recording");
  assert.deepEqual(live(p), []);
  await utter(p);
  assert.equal(voiceCalls(p).length, 2);
  assert.equal(formText(replyCalls(p)[0].init), "Тепер чути");
});

test("an error with a fragment (/voice or /speak not 200): its text in #error, the mode stops, no reload", async () => {
  // /voice 502
  const a = loadPage();
  a.voice.push(fragment("Не вдалося розпізнати — спробуйте ще раз.", 502));
  await tapTalk(a);
  await utter(a);
  assert.equal(a.byId.error.textContent, "Не вдалося розпізнати — спробуйте ще раз.");
  assert.equal(state(a), "");
  assert.ok(a.streams[0].tracks[0].stopped, "the microphone track was not stopped");
  assert.ok(a.ctxs[0].closed, "the AudioContext was not closed");
  assert.ok(a.intervals.every((i) => i.cleared), "the interval was not cleared");
  assert.equal(a.reloads, 0);
  // /speak 409
  const b = loadPage();
  b.voice.push(json({ text: "Привіт" }));
  b.reply.push(reply("Речення. "));
  b.speak.push(fragment("Озвучення недоступне.", 409));
  await tapTalk(b);
  await utter(b);
  assert.equal(b.byId.error.textContent, "Озвучення недоступне.");
  assert.equal(state(b), "");
  assert.ok(b.ctxs[0].closed);
  assert.equal(b.reloads, 0);
});

test("an error without a fragment (failed, decodeAudioData, network): the stop text, the mode stops", async () => {
  // failed in the reply stream
  const a = loadPage();
  a.voice.push(json({ text: "Привіт" }));
  a.reply.push(sse([["saved", {}], ["failed", {}]]));
  await tapTalk(a);
  await utter(a);
  assert.equal(a.byId.error.textContent, STOPPED);
  assert.equal(state(a), "");
  assert.ok(a.ctxs[0].closed);
  assert.equal(a.reloads, 0);
  // decodeAudioData fails
  const b = loadPage();
  b.voice.push(json({ text: "Привіт" }));
  b.reply.push(reply("Речення. "));
  b.decodeFails = true;
  await tapTalk(b);
  await utter(b);
  assert.equal(b.byId.error.textContent, STOPPED);
  assert.equal(state(b), "");
  assert.ok(b.ctxs[0].closed);
  assert.equal(b.reloads, 0);
  // the network fails on /speak
  const c = loadPage();
  c.voice.push(json({ text: "Привіт" }));
  c.reply.push(reply("Речення. "));
  c.speak.push(() => Promise.reject(new TypeError("Failed to fetch")));
  await tapTalk(c);
  await utter(c);
  assert.equal(c.byId.error.textContent, STOPPED);
  assert.equal(state(c), "");
  assert.ok(c.ctxs[0].closed);
  assert.equal(c.reloads, 0);
});

test("the second tap stops everything and reloads the page", async () => {
  // while listening
  const a = loadPage();
  await tapTalk(a);
  assert.equal(state(a), "listening");
  assert.equal(a.streams.length, 1);
  calibrate(a);
  await tapTalk(a);
  assert.ok(a.intervals.every((i) => i.cleared), "the interval was not cleared");
  assert.equal(recording(a).length, 0, "the recorder still records");
  assert.ok(a.streams[0].tracks[0].stopped, "the microphone track was not stopped");
  assert.ok(a.ctxs[0].closed, "the AudioContext was not closed");
  assert.equal(state(a), "");
  assert.equal(a.talk.ariaPressed, "false");
  assert.equal(a.reloads, 1);
  // while speaking
  const b = loadPage();
  b.voice.push(json({ text: "Привіт" }));
  b.reply.push(reply("Перше речення. Друге речення."));
  await tapTalk(b);
  await utter(b);
  assert.equal(state(b), "speaking");
  const src = playing(b)[0];
  await tapTalk(b);
  assert.ok(src.stopped, "the playing sound was not stopped");
  assert.ok(b.ctxs[0].closed);
  assert.equal(state(b), "");
  assert.equal(b.reloads, 1);
});

test("#mic, #send and the field are disabled while the mode is on", async () => {
  const p = loadPage();
  await tapTalk(p);
  assert.equal(state(p), "listening");
  assert.equal(p.byId.mic.disabled, true, "#mic");
  assert.equal(p.byId.send.disabled, true, "#send");
  assert.equal(p.field.disabled, true, "the field");
});

test("createController: send(text, fields) posts text and the fields; send(text) posts text only", async () => {
  const bodies = [];
  const ui = {};
  for (const m of ["disable", "enable", "appendDelta", "showRetry", "showError", "reload", "setDraft"]) ui[m] = () => {};
  const fetch = async (url, init) => {
    bodies.push(init.body);
    return new Response("event: saved\ndata: {}\n\nevent: answered\ndata: {}\n\n", {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  };
  const storage = { getItem: () => null, setItem() {}, removeItem() {} };
  const c = createController({ fetch, storage, ui, key: "draft:alice-1/t-0123456789ab" });
  await c.send("Так", { spoken: "1" });
  await c.send("Ні");
  await flush();
  assert.equal(bodies.length, 2);
  assert.equal(bodies[0].get("text"), "Так");
  assert.equal(bodies[0].get("spoken"), "1");
  assert.deepEqual([...bodies[1].keys()], ["text"]);
  assert.equal(bodies[1].get("text"), "Ні");
});

// keeps: the ordinary mode before and after the slice
test("without a tap on #talk «Надіслати» sends a body with text only and answered reloads the page", async () => {
  const p = loadPage();
  p.reply.push(sse([["saved", {}], ["delta", { text: "Відповідь." }], ["answered", {}]]));
  p.field.value = "Звичайна репліка";
  fire(p.byId["reply-form"], "submit");
  await flush();
  assert.equal(replyCalls(p).length, 1);
  const body = replyCalls(p)[0].init.body;
  assert.deepEqual([...body.keys()], ["text"]);
  assert.equal(body.get("text"), "Звичайна репліка");
  assert.equal(p.reloads, 1);
  assert.equal(speakCalls(p).length, 0);
});
