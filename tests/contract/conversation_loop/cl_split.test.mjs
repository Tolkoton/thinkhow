// Contract tests of conversation-loop, Seam 2: splitSentences of conversation.js (slice tester).
// Written from the contract, not the code. Expected values are written by hand. Where the contract leaves the
// side of the cut comma open (Q1) or whether `rest` keeps its spaces, the check holds under both readings.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { splitSentences } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const bytes = (s) => new TextEncoder().encode(s).length;
const noSpace = (s) => s.replace(/\s+/g, "");

test("a sentence ends on . ! ? … followed by a space; the unfinished tail goes to rest", () => {
  const r = splitSentences("Так. Ні! Чому? Ну… А далі", false);
  assert.deepEqual(r.sentences, ["Так.", "Ні!", "Чому?", "Ну…"]);
  assert.equal(r.rest.trim(), "А далі");
});

test("a newline followed by a newline ends a sentence; so does a mark followed by a newline", () => {
  const r = splitSentences("Перше\n\nДруге.\nТретє.", true);
  assert.deepEqual(r.sentences, ["Перше", "Друге.", "Третє."]);
  assert.equal(r.rest, "");
});

test("a mark not followed by a space or newline does not end a sentence", () => {
  const r = splitSentences("Число 3.14 і т.д. кінець.", true);
  assert.deepEqual(r.sentences, ["Число 3.14 і т.д.", "кінець."]);
});

test("without final a mark at the very end of the text does not end the sentence; with final it does", () => {
  const open = splitSentences("Привіт.", false);
  assert.deepEqual(open.sentences, []);
  assert.equal(open.rest.trim(), "Привіт.");
  const closed = splitSentences("Привіт.", true);
  assert.deepEqual(closed.sentences, ["Привіт."]);
  assert.equal(closed.rest, "");
});

test("with final the tail without a mark goes too and rest is empty", () => {
  const r = splitSentences("Так. Ну і все", true);
  assert.deepEqual(r.sentences, ["Так.", "Ну і все"]);
  assert.equal(r.rest, "");
});

test("sentences of spaces only are dropped and the edges are trimmed", () => {
  const r = splitSentences("  Так.   \n\n  Ні.  ", true);
  assert.deepEqual(r.sentences, ["Так.", "Ні."]);
  assert.equal(r.rest, "");
  const empty = splitSentences("", true);
  assert.deepEqual(empty.sentences, []);
  assert.equal(empty.rest, "");
});

test("a sentence of 2500 bytes of Cyrillic is cut into pieces of at most 1000 bytes at the last comma", () => {
  // clause: 48 Cyrillic letters (96 bytes) and a comma = 97 bytes; clauses joined by a space
  const clause = "ж".repeat(48) + ",";
  const long = Array(25).fill(clause).join(" ");
  const text = long.slice(0, -1) + ". Далі";
  assert.ok(bytes(text) > 2400);
  const r = splitSentences(text, false);
  for (const s of r.sentences) assert.ok(bytes(s) <= 1000, `a piece of ${bytes(s)} bytes`);
  assert.ok(r.sentences.length >= 3, `${r.sentences.length} pieces`);
  // the last comma before 1000 bytes is the 10th (it ends at byte 979): the first piece holds 10 clauses
  assert.equal(r.sentences[0].replace(/[,\s]/g, ""), "ж".repeat(480));
  // every piece ends where a clause ended: whole runs of 48 letters only
  for (const s of r.sentences) {
    for (const run of s.replace(/[.,]/g, " ").split(/\s+/).filter(Boolean)) assert.equal(run.length, 48, s);
  }
  assert.equal(noSpace(r.sentences.join(" ")), noSpace(long.slice(0, -1) + "."));
  assert.equal(r.rest.trim(), "Далі");
});

test("no comma: cut at the last space before the limit; the final tail is cut too", () => {
  const word = "ж".repeat(10); // 20 bytes
  const text = Array(150).fill(word).join(" "); // 3149 bytes, no mark at all
  const r = splitSentences(text, true);
  assert.equal(r.rest, "");
  assert.ok(r.sentences.length >= 4, `${r.sentences.length} pieces`);
  for (const s of r.sentences) {
    assert.ok(bytes(s) <= 1000, `a piece of ${bytes(s)} bytes`);
    for (const w of s.split(/\s+/).filter(Boolean)) assert.equal(w, word, "a word was cut");
    // cut at the LAST space: one more word would not fit
    if (s !== r.sentences.at(-1)) assert.ok(bytes(s) + 21 > 1000, `piece of ${bytes(s)} bytes cut too early`);
  }
  assert.equal(r.sentences.join(" ").split(/\s+/).length, 150);
});

test("a long run without a space is cut at a character boundary", () => {
  const text = "a" + "😀".repeat(400); // 1601 bytes, 4-byte characters
  const r = splitSentences(text, true);
  assert.equal(r.rest, "");
  assert.equal(r.sentences.join(""), text);
  for (const s of r.sentences) {
    assert.ok(bytes(s) <= 1000, `a piece of ${bytes(s)} bytes`);
    assert.equal(new TextDecoder().decode(new TextEncoder().encode(s)), s, "a character was cut in two");
  }
  assert.equal(bytes(r.sentences[0]), 997, "the cut is at the last character boundary before 1000 bytes");
});
