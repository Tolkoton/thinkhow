// Contract tests of conversation-loop, the invariants I1–I3 (slice tester). Written from the contract, not the
// code. The project has no property-based library: the inputs are chosen by hand from each «Domain».
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  flush,
  loadPage,
  tick,
  utter,
  state,
  voiceCalls,
  speakCalls,
  formText,
  endAudio,
  playAll,
  recording,
  tapTalk,
  json,
  reply,
} from "./cl_page_fakes.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { splitSentences } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const bytes = (s) => new TextEncoder().encode(s).length;
const noSpace = (s) => s.replace(/\s+/g, "");

// loud speech, then quiet, then loud again: whatever the page hears now must not become a turn
function shout(p) {
  tick(p, 0.5, 40);
  tick(p, 0.01, 40);
  tick(p, 0.6, 10);
  tick(p, 0.01, 40);
}

test("I1: while thinking or speaking no level from the microphone starts a recording or sends /voice", async () => {
  const p = loadPage();
  let release;
  p.voice.push(() => new Promise((r) => (release = r)), json({ text: "Друга" }));
  p.reply.push(reply("Перше речення. ", "Друге речення."), reply("Відповідь."));
  await tapTalk(p);
  await utter(p);
  // thinking: /voice is on its way
  assert.equal(state(p), "thinking");
  p.talk.stateLog.length = 0;
  shout(p);
  await flush();
  assert.ok(!p.talk.stateLog.includes("hearing"), `hearing while thinking: ${p.talk.stateLog}`);
  assert.equal(p.recorders.length, 1, "a recorder was made while thinking");
  assert.equal(recording(p).length, 0, "a recorder records while thinking");
  assert.equal(voiceCalls(p).length, 1);
  // speaking: the first sentence plays
  release(json({ text: "Перша" })());
  await flush();
  assert.equal(state(p), "speaking");
  p.talk.stateLog.length = 0;
  shout(p);
  await flush();
  assert.ok(!p.talk.stateLog.includes("hearing"), `hearing while speaking: ${p.talk.stateLog}`);
  assert.equal(p.recorders.length, 1, "a recorder was made while speaking");
  assert.equal(recording(p).length, 0, "a recorder records while speaking");
  assert.equal(voiceCalls(p).length, 1);
  // between two sentences of one answer, still speaking
  await endAudio(p);
  shout(p);
  await flush();
  assert.equal(recording(p).length, 0, "a recorder records between two sentences");
  assert.equal(voiceCalls(p).length, 1);
  // after the voice fell silent the page listens again, and speech is a turn again
  await playAll(p);
  assert.equal(state(p), "listening");
  await utter(p);
  assert.equal(voiceCalls(p).length, 2);
});

test("I2: no /speak request carries text over 1000 bytes of UTF-8", async () => {
  const p = loadPage();
  // one answer without a single mark: 150 Cyrillic words, then 300 four-byte characters with no space, then a word;
  // a short sentence of its own after it
  const text =
    Array(150).fill("ж".repeat(10)).join(" ") + " " + "😀".repeat(300) + " кінець і ще речення! Коротке.";
  const chars = Array.from(text);
  const deltas = [];
  for (let i = 0; i < chars.length; i += 7) deltas.push(chars.slice(i, i + 7).join(""));
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply(...deltas));
  await tapTalk(p);
  await utter(p);
  await playAll(p, 100);
  assert.equal(state(p), "listening", "the answer did not play to its end");
  const sent = speakCalls(p).map((c) => formText(c.init));
  assert.ok(sent.length >= 6, `${sent.length} /speak requests`);
  for (const s of sent) assert.ok(bytes(s) <= 1000, `a /speak of ${bytes(s)} bytes`);
});

// the protocol of the page: splitSentences(tail + delta, false) for each delta, then splitSentences(tail, true)
function spoken(deltas) {
  const out = [];
  let tail = "";
  for (const d of deltas) {
    const r = splitSentences(tail + d, false);
    out.push(...r.sentences);
    tail = r.rest;
  }
  const r = splitSentences(tail, true);
  out.push(...r.sentences);
  assert.equal(r.rest, "");
  return out;
}

function splits(text) {
  const chars = Array.from(text);
  const by = (n) => {
    const out = [];
    for (let i = 0; i < chars.length; i += n) out.push(chars.slice(i, i + n).join(""));
    return out;
  };
  // right after every mark and right after every space: the cut falls between a mark and its space
  const atMarks = text.split(/(?<=[.!?…\n ])/);
  return [[text], by(1), by(7), by(13), atMarks, ["", ...by(5).flatMap((d) => [d, ""])]];
}

test("I3: the pieces joined by a space give the input text, up to spaces, for any split into deltas", () => {
  const clause = "ж".repeat(48) + ",";
  const texts = [
    "Перше речення. Друге речення! Третє? Ну… і хвіст без крапки",
    "Так. Так. Так.",
    "Рядок один\n\nРядок два.\nТри",
    "Так.  Ні.   ",
    Array(25).fill(clause).join(" ").slice(0, -1) + ". Кінець",
    Array(150).fill("слово").join(" ") + ". Останнє",
    "Одне",
    "",
  ];
  for (const text of texts) {
    for (const deltas of splits(text)) {
      const got = spoken(deltas);
      assert.equal(noSpace(got.join(" ")), noSpace(text), `text ${JSON.stringify(text.slice(0, 40))}, deltas ${deltas.length}`);
    }
  }
});
